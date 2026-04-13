"""
改良版處理器：
1. 使用雙重偵測策略：YOLO + easyocr 作為備援
2. 加入 mask 膨脹 (dilation) 提升去背乾淨程度
3. 將 YOLO confidence 調低至 0.25 拿到更多框
"""
import cv2
import os
import numpy as np
from PIL import Image
from manga_ocr import MangaOcr
from translator import TranslatorAndInpainter
from typesetter import Typesetter

try:
    from ultralytics import YOLO
except ImportError:
    print("WARNING: ultralytics (YOLO) not installed.")
    YOLO = None

YOLO_CONF = 0.20     # low conf to catch more bubbles
YOLO_IOU  = 0.45     # NMS iou threshold
MIN_BOX_W = 30       # minimum bubble width in pixels
MIN_BOX_H = 30       # minimum bubble height in pixels
MIN_BOX_AREA = 1200  # skip tiny SFX labels (typically <30x30)
MASK_DILATE_PX = 8   # 膨脹像素，確保文字邊緣完整被蓋住

class ComicProcessor:
    def __init__(self):
        print("Initializing MangaOcr...")
        self.mocr = MangaOcr()
        print("MangaOcr initialized successfully.")

        self.translator_inpainter = TranslatorAndInpainter()
        self.typesetter = Typesetter(font_path="C:/Windows/Fonts/msjh.ttc")

        print("Initializing YOLO Comic Text Detector...")
        self.model_path = "yolov8s-manga-text.pt"
        self.yolo_model = None

        if YOLO:
            if not os.path.exists(self.model_path):
                print(f"Downloading YOLO model...")
                import urllib.request
                url = "https://huggingface.co/sandrik1271/manga-translator-yolov8/resolve/main/best.pt"
                try:
                    urllib.request.urlretrieve(url, self.model_path)
                    print("Download complete.")
                except Exception as e:
                    print(f"Failed to download model: {e}")
            if os.path.exists(self.model_path):
                try:
                    self.yolo_model = YOLO(self.model_path)
                    print(f"YOLO initialized. Classes: {self.yolo_model.names}")
                except Exception as e:
                    import traceback; traceback.print_exc()
                    print(f"YOLO initialization failed: {e}")
            else:
                print("YOLO model file not found.")

    def process_image(self, image_path: str, output_dir: str = "processed_output") -> str | None:
        if not os.path.exists(image_path):
            print(f"File not found: {image_path}")
            return None

        os.makedirs(output_dir, exist_ok=True)
        basename = os.path.basename(image_path)

        # Read image (handle unicode paths on Windows)
        img_array = np.fromfile(image_path, dtype=np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        if img is None:
            print(f"[{basename}] Failed to decode image")
            return None

        # === Step 1: Detect text regions ===
        boxes = self._detect_text_regions(img)
        print(f"[{basename}] Detected {len(boxes)} text regions.")

        if not boxes:
            output_path = os.path.join(output_dir, f"translated_{basename}")
            import shutil
            shutil.copy(image_path, output_path)
            print(f"[{basename}] No text found, copying directly to: {output_path}")
            return output_path

        # === Step 2: OCR each region ===
        results = []
        original_texts = []

        for idx, (x, y, w, h) in enumerate(boxes):
            pad = 4
            x1 = max(0, x - pad)
            y1 = max(0, y - pad)
            x2 = min(img.shape[1], x + w + pad)
            y2 = min(img.shape[0], y + h + pad)

            cropped = img[y1:y2, x1:x2]
            cropped_pil = Image.fromarray(cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB))

            try:
                text = self.mocr(cropped_pil)
                if not text or len(text.strip()) < 1:
                    continue

                # Filter 1: skip if less than 2 CJK/kana chars (noise)
                cjk_count = sum(1 for c in text if (
                    '\u3040' <= c <= '\u30FF' or  # hiragana + katakana
                    '\u4E00' <= c <= '\u9FFF' or  # CJK
                    '\uFF00' <= c <= '\uFFEF'      # fullwidth
                ))
                if cjk_count < 2 and len(text.strip()) < 3:
                    print(f"[{basename}] Skip noise [{idx}]: '{text}'")
                    continue

                # Filter 2: skip SFX / onomatopoeia (preserve artistic text)
                if TranslatorAndInpainter._is_sfx(text):
                    print(f"[{basename}] Skip SFX [{idx}]: '{text}'")
                    continue

                results.append({"bbox": (x, y, w, h)})
                original_texts.append(text)
                print(f"[{basename}] OCR [{idx}]: '{text}'")
            except Exception as e:
                print(f"[{basename}] OCR Error on region {idx}: {e}")

        if not results:
            output_path = os.path.join(output_dir, f"translated_{basename}")
            import shutil
            shutil.copy(image_path, output_path)
            print(f"[{basename}] No valid text after OCR, copying directly.")
            return output_path

        # === Step 3: Translate ===
        print(f"[{basename}] Translating {len(original_texts)} text blocks...")
        translated_texts = self.translator_inpainter.translate_texts(original_texts)
        print(f"[{basename}] Translations: {translated_texts}")

        # === Step 4: Inpaint (remove original text) ===
        print(f"[{basename}] Inpainting...")
        inpainted_img_cv = self.translator_inpainter.inpaint_image(
            img,
            [r["bbox"] for r in results]
        )

        # === Step 5: Typeset translated text ===
        print(f"[{basename}] Typesetting...")
        final_pil = Image.fromarray(cv2.cvtColor(inpainted_img_cv, cv2.COLOR_BGR2RGB))

        for idx, r in enumerate(results):
            if idx < len(translated_texts) and translated_texts[idx]:
                final_pil = self.typesetter.draw_text_in_box(
                    final_pil,
                    translated_texts[idx],
                    r["bbox"]
                )

        # === Step 6: Save ===
        output_path = os.path.join(output_dir, f"translated_{basename}")
        final_pil.save(output_path, quality=95)
        print(f"[{basename}] Done: {output_path}")
        return output_path

    def _detect_text_regions(self, img: np.ndarray) -> list[tuple[int, int, int, int]]:
        """Use YOLO to detect text bounding boxes with fallback to contour detection."""
        if self.yolo_model:
            return self._detect_yolo(img)
        else:
            print("WARNING: YOLO not loaded, using contour fallback.")
            return self._detect_contour_fallback(img)

    def _detect_yolo(self, img: np.ndarray) -> list[tuple[int, int, int, int]]:
        results = self.yolo_model(
            img,
            verbose=False,
            conf=YOLO_CONF,
            iou=YOLO_IOU
        )
        boxes_list = []
        if len(results) > 0:
            for box in results[0].boxes:
                x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].cpu().numpy()]
                w = x2 - x1
                h = y2 - y1
                area = w * h

                # 1. Skip tiny boxes
                if w < MIN_BOX_W or h < MIN_BOX_H or area < MIN_BOX_AREA:
                    continue

                # 2. Skip extremely thin/long boxes
                aspect_ratio = w / h if h > 0 else 0
                if aspect_ratio > 4.5 or aspect_ratio < 0.15:
                    continue

                # 3. White ratio check
                crop_gray = cv2.cvtColor(img[y1:y2, x1:x2], cv2.COLOR_BGR2GRAY)
                white_ratio = float(np.sum(crop_gray > 200)) / max(area, 1)
                if white_ratio < 0.20:  
                    continue

                boxes_list.append((x1, y1, w, h))

        # --- Deduplication (NMS) ---
        if not boxes_list:
            return []

        # Sort by area (larger boxes first) to prefer keeping the main bubble over sub-detections
        boxes_list.sort(key=lambda b: b[2] * b[3], reverse=True)
        
        final_boxes = []
        for box in boxes_list:
            is_redundant = False
            for fbox in final_boxes:
                # Calculate Intersection
                ix1 = max(box[0], fbox[0])
                iy1 = max(box[1], fbox[1])
                ix2 = min(box[0] + box[2], fbox[0] + fbox[2])
                iy2 = min(box[1] + box[3], fbox[1] + fbox[3])
                
                iw = max(0, ix2 - ix1)
                ih = max(0, iy2 - iy1)
                inter = iw * ih
                
                area1 = box[2] * box[3]
                area2 = fbox[2] * fbox[3]
                union = float(area1 + area2 - inter)
                iou = inter / union if union > 0 else 0
                
                overlap_ratio = inter / float(area1) if area1 > 0 else 0
                
                if iou > 0.3 or overlap_ratio > 0.6:
                    is_redundant = True
                    break
            if not is_redundant:
                final_boxes.append(box)

        return final_boxes

    def _detect_contour_fallback(self, img: np.ndarray) -> list[tuple[int, int, int, int]]:
        """
        Fallback: find white speech bubbles via thresholding + contour detection.
        Works reasonably well for standard black-and-white manga.
        """
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        # Threshold to find very light (white/near-white) regions
        _, thresh = cv2.threshold(gray, 230, 255, cv2.THRESH_BINARY)
        # Morphological closing to join nearby regions
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
        closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        boxes_list = []
        img_area = img.shape[0] * img.shape[1]
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < 2000 or area > img_area * 0.4:
                continue
            x, y, w, h = cv2.boundingRect(cnt)
            boxes_list.append((x, y, w, h))
        return boxes_list


if __name__ == "__main__":
    import sys
    processor = ComicProcessor()
    img_path = sys.argv[1] if len(sys.argv) > 1 else None
    if img_path:
        out = processor.process_image(img_path, output_dir="test_output")
        print(f"Output: {out}")
    else:
        print("Usage: python processor.py <image_path>")
