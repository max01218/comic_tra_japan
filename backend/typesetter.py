"""
改良版排版引擎：
1. 自動偵測直書/橫書（基於框的長寬比）
2. 智慧字型大小縮放，確保文字不溢出
3. 直書：從右往左排列，支援全形標點正確旋轉
4. 白色描邊保證在各種背景上的可讀性
5. 水平置中 + 垂直置中
"""
from PIL import Image, ImageDraw, ImageFont
import textwrap
import math

# 日文全形標點 → 直書時旋轉位置補正
ROTATE_PUNCT = set("。、！？…・")
# 這些字元在直書時向右移（放在欄位右側）
SIDE_PUNCT = set("ーｰ〜")

class Typesetter:
    def __init__(self, font_path: str = None):
        self.font_path = font_path

    # -----------------------------------------------------------------------
    def draw_text_in_box(
        self,
        image_pil: Image.Image,
        text: str,
        bbox: tuple,
        text_color: tuple = (0, 0, 0),
        is_vertical: bool = None,
    ) -> Image.Image:
        """
        Put *text* inside a bounding box on *image_pil*.
        The box is (x, y, w, h) in pixels.
        """
        x, y, w, h = bbox
        if w <= 0 or h <= 0 or not text:
            return image_pil

        # ── padding for elliptical bubbles ──────────────────────────────────
        # Use a tighter padding for smaller boxes to avoid squeezing text
        padding_ratio = 0.08 if w < 100 or h < 100 else 0.12
        px = max(4, int(w * padding_ratio))
        py = max(4, int(h * padding_ratio))
        ix = x + px           # inner box x
        iy = y + py           # inner box y
        iw = max(2, w - px * 2)
        ih = max(2, h - py * 2)

        # ── decide orientation ───────────────────────────────────────────────
        if is_vertical is None:
            # Vertical when box is significantly taller than wide
            is_vertical = (h > w * 1.3) and (h > 60)

        # ── render ──────────────────────────────────────────────────────────
        draw = ImageDraw.Draw(image_pil)
        if is_vertical:
            self._draw_vertical(draw, text, ix, iy, iw, ih, text_color)
        else:
            self._draw_horizontal(draw, text, ix, iy, iw, ih, text_color)

        return image_pil

    # -----------------------------------------------------------------------
    # HORIZONTAL rendering
    # -----------------------------------------------------------------------
    def _draw_horizontal(self, draw, text, ix, iy, iw, ih, text_color):
        sw = 2  # stroke width
        sc = (255, 255, 255)

        # Binary search for max font size that fits
        lo, hi = 8, min(iw, ih, 72)
        best_size, best_lines = lo, [text]

        while lo <= hi:
            mid = (lo + hi) // 2
            font = self._font(mid)
            lines = self._wrap_h(text, font, draw, iw)
            th = len(lines) * (mid + 2)
            if th <= ih:
                best_size, best_lines = mid, lines
                lo = mid + 1
            else:
                hi = mid - 1

        font = self._font(best_size)
        line_h = best_size + 2
        total_h = len(best_lines) * line_h
        cur_y = iy + max(0, (ih - total_h) // 2)

        for line in best_lines:
            bb = draw.textbbox((0, 0), line, font=font)
            lw = bb[2] - bb[0]
            cur_x = ix + max(0, (iw - lw) // 2)
            draw.text((cur_x, cur_y), line, font=font,
                      fill=text_color, stroke_width=sw, stroke_fill=sc)
            cur_y += line_h

    def _wrap_h(self, text, font, draw, max_w) -> list:
        """Greedy CJK-aware word wrap."""
        lines, cur = [], ""
        for ch in text:
            test = cur + ch
            bb = draw.textbbox((0, 0), test, font=font)
            if bb[2] - bb[0] > max_w and cur:
                lines.append(cur)
                cur = ch
            else:
                cur = test
        if cur:
            lines.append(cur)
        return lines or [text]

    # -----------------------------------------------------------------------
    # VERTICAL rendering (right-to-left columns)
    # -----------------------------------------------------------------------
    def _draw_vertical(self, draw, text, ix, iy, iw, ih, text_color):
        sw = 2
        sc = (255, 255, 255)
        text = text.replace(" ", "").replace("\n", "")

        # Binary search for font size
        lo, hi = 8, min(iw, ih, 72)
        best_size = lo
        # We define a spacing factor for columns and vertical separation
        line_spacing = 6
        col_spacing = 14

        while lo <= hi:
            mid = (lo + hi) // 2
            cols = self._split_cols(text, mid, ih)
            # Increase estimated width to include more space between columns
            total_w = len(cols) * mid + (len(cols) - 1) * col_spacing
            if total_w <= iw:
                best_size, best_cols = mid, cols
                lo = mid + 1
            else:
                hi = mid - 1

        fs = best_size
        font = self._font(fs)
        col_step = fs + col_spacing
        total_col_w = len(best_cols) * fs + (len(best_cols) - 1) * col_spacing

        # Start from the RIGHT side of the inner box (traditional tategumi)
        # Offset start_x so the rightmost char fits in the box
        start_x = ix + iw - fs
        # If columns don't fill width, centre them
        if total_col_w < iw:
            start_x = ix + iw - fs - (iw - total_col_w) // 2

        for ci, col_chars in enumerate(best_cols):
            cx = start_x - ci * col_step

            # Update col_h calculation with larger line spacing
            col_h = len(col_chars) * fs + (len(col_chars) - 1) * line_spacing
            cy = iy + max(0, (ih - col_h) // 2)

            for ch in col_chars:
                # Punctuation: shift right & down a bit
                draw_x = cx
                draw_y = cy
                if ch in ROTATE_PUNCT:
                    draw_x += int(fs * 0.3)
                    draw_y += int(fs * 0.1)
                
                draw.text((draw_x, draw_y), ch, font=font,
                          fill=text_color, stroke_width=sw, stroke_fill=sc)
                cy += fs + line_spacing

    def _split_cols(self, text, fs, ih) -> list[list[str]]:
        """Split characters into vertical columns, distributing them somewhat evenly."""
        # Use a slightly more conservative height limit
        line_spacing = 4
        chars_per_col_limit = max(1, ih // (fs + line_spacing))
        num_cols = math.ceil(len(text) / chars_per_col_limit)
        if num_cols <= 1:
            return [list(text)]
        
        # Try to balance characters across columns
        avg = len(text) / num_cols
        cols = []
        start = 0
        for i in range(num_cols):
            end = start + math.ceil(avg) if i < (len(text) % num_cols) else start + math.floor(avg)
            chunk = list(text[start:end])
            if chunk:
                cols.append(chunk)
            start = end
        return cols or [[]]

    # -----------------------------------------------------------------------
    def _font(self, size: int):
        if self.font_path:
            try:
                return ImageFont.truetype(self.font_path, size)
            except IOError:
                pass
        try:
            return ImageFont.load_default(size)
        except TypeError:
            return ImageFont.load_default()


# ── quick smoke test ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    import numpy as np
    ts = Typesetter(font_path="C:/Windows/Fonts/msjh.ttc")

    # 1. Horizontal wide bubble
    img = Image.fromarray(np.full((300, 500, 3), 240, dtype=np.uint8))
    ts.draw_text_in_box(img, "老師，妳確定現在接受補課的是我嗎……", (20, 20, 460, 80))

    # 2. Vertical tall bubble
    ts.draw_text_in_box(img, "在補課的時間裡，請全力以赴", (20, 120, 60, 160))

    # 3. Mixed large box
    ts.draw_text_in_box(img, "好想摸摸看……", (100, 120, 200, 100))

    img.save("test_typesetter.png")
    print("Saved test_typesetter.png")
