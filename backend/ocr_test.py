import os
from PIL import Image
from manga_ocr import MangaOcr

# Initialize MangaOcr (This will download the model on the first run)
mocr = MangaOcr()

def test_ocr(image_path: str):
    if not os.path.exists(image_path):
        print(f"File not found: {image_path}")
        return
        
    print(f"Testing OCR on {image_path}...")
    try:
        # manga-ocr expects a PIL Image or file path
        # In a real scenario, we would pass cropped bounding boxes of text regions
        # For now, let's just pass the whole image to see if it detects anything
        # (Note: MangaOcr is optimized for cropped text lines, passing a full page might not yield good results directly, 
        # but it's a simple first test to ensure the model loads)
        text = mocr(image_path)
        print("Detected text:")
        print(text)
    except Exception as e:
        print(f"OCR Error: {e}")

if __name__ == "__main__":
    # Test with one of the downloaded images
    test_dir = "downloads"
    if os.path.exists(test_dir):
        files = os.listdir(test_dir)
        if files:
            # Pick the first image
            img_path = os.path.join(test_dir, files[0])
            test_ocr(img_path)
        else:
            print("No images found in downloads directory.")
    else:
        print("Downloads directory not found.")
