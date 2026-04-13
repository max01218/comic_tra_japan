"""
端對端 pipeline 測試腳本。
用法:
    python test_pipeline.py <image_path>

它會把翻譯後的圖片輸出到 test_output/ 並印出每個步驟的中間結果。
"""
import sys, os
# Fix Windows console encoding
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

os.makedirs("test_output", exist_ok=True)

img_path = sys.argv[1] if len(sys.argv) > 1 else None
if not img_path:
    print("Usage: python test_pipeline.py <path-to-manga-image.jpg>")
    sys.exit(1)

print("=" * 60)
print(f"Testing full pipeline on: {img_path}")
print("=" * 60)

# ── Step 1: YOLO detection ────────────────────────────────────────────────
print("\n[1] YOLO Detection")
import cv2, numpy as np
from ultralytics import YOLO
from PIL import Image, ImageDraw, ImageFont

img_arr = np.fromfile(img_path, dtype=np.uint8)
img = cv2.imdecode(img_arr, cv2.IMREAD_COLOR)
print(f"    Image size: {img.shape[1]}x{img.shape[0]}")

model = YOLO("yolov8s-manga-text.pt")
results = model(img, verbose=False, conf=0.20, iou=0.45)
boxes_raw = []
for box in results[0].boxes:
    x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].cpu().numpy()]
    w, h = x2 - x1, y2 - y1
    conf = float(box.conf[0])
    cls  = model.names[int(box.cls[0])]
    if w > 10 and h > 10:
        boxes_raw.append((x1, y1, w, h))

# --- Deduplication (NMS) ---
boxes_raw.sort(key=lambda b: b[2] * b[3], reverse=True)
boxes = []
for box in boxes_raw:
    is_redundant = False
    for fbox in boxes:
        # Calculate IOU
        ix1, iy1 = max(box[0], fbox[0]), max(box[1], fbox[1])
        ix2, iy2 = min(box[0] + box[2], fbox[0] + fbox[2]), min(box[1] + box[3], fbox[1] + fbox[3])
        iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
        inter = iw * ih
        area1, area2 = box[2] * box[3], fbox[2] * fbox[3]
        iou = inter / float(area1 + area2 - inter) if (area1 + area2 - inter) > 0 else 0
        overlap_ratio = inter / float(area1) if area1 > 0 else 0
        if iou > 0.3 or overlap_ratio > 0.6:
            is_redundant = True
            break
    if not is_redundant:
        boxes.append(box)

for b in boxes:
    print(f"    [text] ({b[0]},{b[1]}) {b[2]}x{b[3]}")

print(f"    Total boxes: {len(boxes)}")

# Save annotated detection image
annot = img.copy()
for (x, y, w, h) in boxes:
    cv2.rectangle(annot, (x, y), (x+w, y+h), (0, 255, 0), 2)
cv2.imwrite("test_output/1_detections.jpg", annot)
print("    Saved: test_output/1_detections.jpg")

# ── Step 2: OCR ───────────────────────────────────────────────────────────
print("\n[2] MangaOCR")
from manga_ocr import MangaOcr
mocr = MangaOcr()
valid_boxes, texts = [], []
for (x, y, w, h) in boxes:
    crop = img[max(0,y-2):y+h+2, max(0,x-2):x+w+2]
    pil_crop = Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
    text = mocr(pil_crop)
    cjk_n = sum(1 for c in text if '\u3040'<=c<='\u30FF' or '\u4E00'<=c<='\u9FFF')
    if cjk_n >= 2 or len(text.strip()) >= 3:
        valid_boxes.append((x, y, w, h))
        texts.append(text)
        print(f"    '{text}'")
    else:
        print(f"    SKIP noise: '{text}'")
print(f"    Valid segments: {len(texts)}")

# ── Step 3: Translation ───────────────────────────────────────────────────
print("\n[3] Translation")
from translator import TranslatorAndInpainter
ti = TranslatorAndInpainter()
translated = ti.translate_texts(texts)
for src, dst in zip(texts, translated):
    print(f"    JP: {src}")
    print(f"    ZH: {dst}")
    print()

# ── Step 4: Inpainting ────────────────────────────────────────────────────
print("\n[4] Inpainting")
inpainted = ti.inpaint_image(img, valid_boxes)
cv2.imwrite("test_output/2_inpainted.jpg", inpainted)
print("    Saved: test_output/2_inpainted.jpg")

# ── Step 5: Typesetting ───────────────────────────────────────────────────
print("\n[5] Typesetting")
from typesetter import Typesetter
ts = Typesetter(font_path="C:/Windows/Fonts/msjh.ttc")
final = Image.fromarray(cv2.cvtColor(inpainted, cv2.COLOR_BGR2RGB))
for bbox, tr_text in zip(valid_boxes, translated):
    if tr_text.strip():
        final = ts.draw_text_in_box(final, tr_text, bbox)
final.save("test_output/3_final.jpg", quality=95)
print("    Saved: test_output/3_final.jpg")
print("\nDone! Check test_output/ folder.")
