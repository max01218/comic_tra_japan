"""
診斷腳本：分析 YOLO 偵測品質與排版問題。
執行: python diagnose.py <image_path>
"""
import sys
import cv2
import numpy as np
from PIL import Image, ImageDraw
from ultralytics import YOLO

IMG_PATH = sys.argv[1] if len(sys.argv) > 1 else None

if not IMG_PATH:
    print("Usage: python diagnose.py <path_to_manga_image>")
    sys.exit(1)

model = YOLO("yolov8s-manga-text.pt")
img = cv2.imread(IMG_PATH)
im_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
pil_img = Image.fromarray(im_rgb)

results = model(img, verbose=False, conf=0.1)  # low conf to see everything

draw = ImageDraw.Draw(pil_img)

print(f"Model classes: {model.names}")
print(f"Image size: {img.shape}")

boxes = results[0].boxes
print(f"Found {len(boxes)} boxes at conf>=0.10")

for box in boxes:
    x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].cpu().numpy()]
    conf = float(box.conf[0])
    cls = int(box.cls[0])
    name = model.names[cls]
    print(f"  [{name}] conf={conf:.2f} box=({x1},{y1},{x2},{y2}) size={x2-x1}x{y2-y1}")
    color = (255, 0, 0) if name != 'text_bubble' else (0, 200, 0)
    draw.rectangle([x1, y1, x2, y2], outline=color, width=3)
    draw.text((x1, y1-15), f"{name} {conf:.2f}", fill=color)

out_path = "diagnose_output.jpg"
pil_img.save(out_path)
print(f"\nSaved annotated image to: {out_path}")
