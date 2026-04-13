import cv2
import numpy as np
import os

def detect_text_regions(image_path: str, output_dir: str = "debug_output") -> list[tuple[int, int, int, int]]:
    """
    Use OpenCV to find potential text regions (speech bubbles).
    Returns a list of bounding boxes: (x, y, w, h)
    """
    if not os.path.exists(image_path):
        print(f"File not found: {image_path}")
        return []

    os.makedirs(output_dir, exist_ok=True)
    basename = os.path.basename(image_path)
    
    # Read image
    img = cv2.imread(image_path)
    if img is None:
        return []
        
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Morphological operations to enhance text regions
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    grad = cv2.morphologyEx(gray, cv2.MORPH_GRADIENT, kernel)
    
    # Binarization
    _, thresh = cv2.threshold(grad, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    
    # Connect text components
    kernel_connected = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 1))
    connected = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel_connected)
    
    # Find contours
    contours, hierarchy = cv2.findContours(connected.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    
    boxes = []
    debug_img = img.copy()
    
    for idx, contour in enumerate(contours):
        x, y, w, h = cv2.boundingRect(contour)
        
        # Filter out very small or very large boxes based on heuristics
        if w > 10 and h > 10 and w < img.shape[1] * 0.8 and h < img.shape[0] * 0.8:
            # Aspect ratio check for text lines
            aspect_ratio = float(w) / h
            if 0.1 < aspect_ratio < 10:
                boxes.append((x, y, w, h))
                cv2.rectangle(debug_img, (x, y), (x+w, y+h), (0, 255, 0), 2)
                
    # Save debug image
    cv2.imwrite(os.path.join(output_dir, f"debug_text_boxes_{basename}"), debug_img)
    print(f"Found {len(boxes)} potential text regions.")
    
    return boxes

if __name__ == "__main__":
    test_dir = "downloads"
    if os.path.exists(test_dir):
        files = os.listdir(test_dir)
        if files:
            img_path = os.path.join(test_dir, files[0])
            boxes = detect_text_regions(img_path)
            print("Finished detection.")
    else:
        print("Downloads directory not found.")
