import cv2
import numpy as np
import os
import requests
import json
import re
from PIL import Image

try:
    import opencc
    _opencc_converter = opencc.OpenCC('s2twp')  # Simplified → Traditional (Taiwan)
except ImportError:
    _opencc_converter = None
    print("WARNING: opencc not installed. Run: pip install opencc-python-reimplemented")

# Abandon simple-lama-inpainting due to TorchScript CUDA incompatibility on this system.
# We use OpenCV NS algorithm with aggressive mask dilation instead.
# INPAINT_NS is better than TELEA for speech bubbles (preserves curvature).

MASK_DILATE_PX = 14  # pixels to expand each bbox mask -> covers text + anti-aliasing halo


class TranslatorAndInpainter:
    def __init__(self):
        self.ollama_url = "http://localhost:11434/api/chat"
        self.model_name = "hf.co/SakuraLLM/Sakura-14B-Qwen2.5-v1.0-GGUF"
        print(f"LLM Translator ready → {self.model_name}")
        print("Inpainting: OpenCV NS mode.")
        # OpenCC converter for Simplified → Traditional Chinese post-processing
        self._opencc = _opencc_converter
        if self._opencc:
            print("OpenCC s2twp loaded: will convert Simplified → Traditional.")
        else:
            print("WARNING: OpenCC not available, output may contain Simplified characters.")

    # ── Translation ────────────────────────────────────────────────────────
    def translate_texts(self, texts: list[str]) -> list[str]:
        """
        Translate Japanese manga dialogue to Traditional Chinese via Sakura LLM.
        Uses line-tagged format [0]...[N] because Sakura reliably outputs that
        rather than JSON.
        """
        if not texts:
            return []

        print(f"  Translating {len(texts)} segments...")
        numbered = "\n".join(f"[{i}] {t}" for i, t in enumerate(texts))

        # Sakura-specific prompt: the model respects this format well
        system_msg = (
            "你是一名專業的日文漫畫本地化翻譯員，目標語言是繁體中文（台灣用語）。"
            "請將以下日文對話翻譯成自然流暢的繁體中文，保留說話語氣與情感。"
            "翻譯規則："
            "1. 嚴格使用繁體中文字（如：說、學、歡迎、聲音等），不得使用簡體字。"
            "2. 以 [序號] 翻譯文字 的格式逐行輸出，不要有多餘說明。"
            "3. 只有對話和心聲才翻譯；若原文是擬聲詞（如ガチ、シュコ、ふ），請原樣保留。"
        )
        user_msg = (
            f"請翻譯以下漫畫對話（範例：[0] 翻譯結果）：\n\n{numbered}"
        )

        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user",   "content": user_msg},
            ],
            "stream": False,
            "options": {"temperature": 0.05, "num_predict": 2048},
        }

        try:
            resp = requests.post(self.ollama_url, json=payload, timeout=180)
            resp.raise_for_status()
            content = resp.json()["message"]["content"].strip()
            print(f"  LLM raw output:\n{content}\n")

            result = self._parse_response(content, texts)
            return result

        except Exception as e:
            print(f"  Translation error: {e}")
            return texts  # return originals on failure

    def _to_traditional(self, text: str) -> str:
        """Convert Simplified Chinese to Traditional (Taiwan) if OpenCC is available."""
        if self._opencc and text:
            try:
                return self._opencc.convert(text)
            except Exception:
                pass
        return text

    @staticmethod
    def _is_sfx(text: str) -> bool:
        """
        Heuristic: decide if a detected text is a sound effect (SFX) / onomatopoeia.
        Returns True if it should NOT be translated.
        """
        text = text.strip()
        if not text or len(text) == 0:
            return True

        # Rule 1: contains only kana, common punctuation, symbols?
        # Expanded range to catch almost all phonetic Japanese
        clean = re.sub(r'[\u3040-\u30FF\u3002\u3001\uff01\uff1f\u2026\u30fb\u301c\u30fc\uff0e\.\!\?\~\u3063\uff0e\+\-\*\s\(\)\[\]\<\>\d\w\-]+', '', text)
        if len(clean) == 0:
            return True

        # Rule 2: High kana ratio + short length (OCR noise often mixes a bit of junk)
        kana_chars = sum(1 for c in text if '\u3040' <= c <= '\u30FF')
        if len(text) <= 5 and (kana_chars / len(text)) > 0.5:
            return True
            
        # Rule 3: Single Kanji that look like SFX or are common misreads
        if len(text) <= 2 and all(c in "二冫シツ八之三口一乙" for c in text):
            return True

        return False

    def _parse_response(self, content: str, texts: list[str]) -> list[str]:
        """
        Parse tagged line-format [N] text output from Sakura.
        Falls back to JSON array parse if the model complied with JSON.
        """
        result_map: dict[int, str] = {}

        # ── Try JSON array first ──────────────────────────────────
        if "[{" in content or '{"id"' in content:
            try:
                start = content.find("[")
                end   = content.rfind("]") + 1
                if start != -1 and end > 0:
                    parsed = json.loads(content[start:end])
                    for item in parsed:
                        idx = item.get("id")
                        tr  = str(item.get("translation", "")).strip()
                        if isinstance(idx, int) and 0 <= idx < len(texts) and tr:
                            result_map[idx] = self._to_traditional(tr)
            except Exception:
                pass

        # ── Try [N] tagged lines if JSON failed or partial ─────────
        if not result_map:
            pattern = re.compile(r'\[(\d+)\]\s*(.+?)(?=\[\d+\]|$)', re.DOTALL)
            for m in pattern.finditer(content):
                idx = int(m.group(1))
                tr  = m.group(2).strip().replace("\n", " ")
                if 0 <= idx < len(texts) and tr:
                    result_map[idx] = self._to_traditional(tr)

            if not result_map:
                lines = [l.strip() for l in content.splitlines() if l.strip()]
                for i, line in enumerate(lines):
                    if i < len(texts):
                        clean = re.sub(r'^\[\d+\]\s*', '', line).strip()
                        if clean:
                            result_map[i] = self._to_traditional(clean)

        # ── Final aggregation & Post-process hallucination check ──
        # Expanded blacklist for common LLM hallucinations from SFX/phonetic noise
        hallucination_blacklist = {
            "肚子", "心臟", "大腦", "胃", "肝臟", "肺", "腸",  # Organs
            "打雷", "雷聲", "突然", "跌倒", "閃亮", "發光", "咚", "哐", # Actions/Noises
            "是的", "對", "哼", "啊", "嘿", "呼"             # Generic fillers
        }
        final_results = []
        for i in range(len(texts)):
            tr = result_map.get(i, texts[i])
            # If the original text was mostly kana/SFX-like and result is a short blacklisted word, use original
            # Also if result is just repeating phonetic Japanese (Sakura sometimes does this), leave it.
            if tr in hallucination_blacklist and self._is_sfx(texts[i]):
                final_results.append(texts[i])
            elif len(tr) <= 3 and self._is_sfx(texts[i]) and tr != texts[i]:
                # If short translation for something that looks like SFX, be suspicious
                final_results.append(texts[i])
            else:
                final_results.append(tr)

        return final_results

    # ── Inpainting ─────────────────────────────────────────────────────────
    def inpaint_image(
        self,
        image: np.ndarray,
        bboxes: list[tuple[int, int, int, int]],
    ) -> np.ndarray:
        """
        Clean text regions by filling only the interior of the speech bubble contour.
        This preserves the original bubble shapes and borders while clearing text.
        """
        if not bboxes:
            return image

        img_cleaned = image.copy()
        
        for (x, y, w, h) in bboxes:
            # 1. Take a slightly expanded crop to catch bubble edges
            pad = 5
            x1 = max(0, x - pad)
            y1 = max(0, y - pad)
            x2 = min(image.shape[1], x + w + pad)
            y2 = min(image.shape[0], y + h + pad)
            
            crop = image[y1:y2, x1:x2]
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            
            # 2. Threshold to find white areas (speech bubble)
            _, thresh = cv2.threshold(gray, 210, 255, cv2.THRESH_BINARY)
            
            # 3. Find contours
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if contours:
                # Find the largest contour by area
                c = max(contours, key=cv2.contourArea)
                
                # Create a mask for this specific contour
                mask = np.zeros(crop.shape[:2], dtype=np.uint8)
                cv2.drawContours(mask, [c], -1, 255, -1)
                
                # Erode mask slightly to avoid over-filling borders? 
                # Actually, drawContours with -1 is fill.
                
                # Fill the white region in the cleaned image
                # We only fill pixels that were in the mask
                roi = img_cleaned[y1:y2, x1:x2]
                roi[mask == 255] = [255, 255, 255]

        print(f"  Cleaned {len(bboxes)} bubbles using contour-based preservation.")
        return img_cleaned


# ── smoke test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    ti = TranslatorAndInpainter()
    tests = ["中野くん", "すごいですね！", "ちょっと待って…"]
    result = ti.translate_texts(tests)
    for jp, zh in zip(tests, result):
        print(f"  {jp} → {zh}")
