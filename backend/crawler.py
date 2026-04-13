import requests
from bs4 import BeautifulSoup
import os
import uuid
import re
from urllib.parse import urljoin

DOWNLOAD_DIR = "downloads"

# Ensure download directory exists
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

class ComicCrawler:
    @staticmethod
    def get_images_from_url(url: str) -> tuple[list[str], str]:
        """
        Fetches a URL and attempts to extract comic images from the page.
        Returns a tuple of (downloaded_paths, comic_title).
        """
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Extract title and sanitize for folding naming
            title = soup.title.string.strip() if soup.title else "Unknown_Comic"
            safe_title = re.sub(r'[\\/\:\*\?\"\<\>\|]', '_', title)[:50]
            
            target_dir = os.path.join(DOWNLOAD_DIR, safe_title)
            os.makedirs(target_dir, exist_ok=True)
            
            # Special case for wnacg.com
            if "wnacg.com/photos-index-aid-" in url:
                return ComicCrawler._crawl_wnacg_gallery(url, headers, target_dir), safe_title
                
            # Basic generic heuristic: find all img tags
            images = soup.find_all("img")
            downloaded_paths = []
            session_id = str(uuid.uuid4())[:8]
            
            for idx, img in enumerate(images):
                img_url = img.get("src") or img.get("data-src")
                if not img_url:
                    continue
                    
                # Fix relative URLs
                if img_url.startswith("//"):
                    img_url = "https:" + img_url
                elif img_url.startswith("/"):
                    img_url = urljoin(url, img_url)
                
                # Filter out small UI icons typically < 100px or ending in SVG
                if img_url.lower().endswith(".svg"):
                    continue
                
                download_path = ComicCrawler._download_image(img_url, headers, session_id, idx, target_dir)
                if download_path:
                    downloaded_paths.append(download_path)
                    
            return downloaded_paths, safe_title
            
        except Exception as e:
            print(f"Error crawling {url}: {e}")
            return [], "Error"
            
    @staticmethod
    def _download_image(img_url: str, headers: dict, session_id: str, idx: int, target_dir: str = DOWNLOAD_DIR) -> str | None:
        try:
            img_response = requests.get(img_url, headers=headers, stream=True, timeout=10)
            if img_response.status_code == 200:
                content_type = img_response.headers.get('content-type', '')
                if 'image' not in content_type:
                    return None
                    
                # Use a simple naming scheme
                ext = img_url.split(".")[-1].split("?")[0]
                if len(ext) > 4 or not ext.isalnum():
                    ext = "jpg" # default fallback
                    
                file_path = os.path.join(target_dir, f"{session_id}_page_{idx:03d}.{ext}")
                
                with open(file_path, "wb") as f:
                    for chunk in img_response.iter_content(1024):
                        f.write(chunk)
                        
                return file_path
        except Exception as e:
            print(f"Failed to download image {img_url}: {e}")
        return None

    @staticmethod
    def _crawl_wnacg_gallery(gallery_url: str, headers: dict, target_dir: str) -> list[str]:
        print(f"Detected wnacg.com gallery: {gallery_url}")
        try:
            response = requests.get(gallery_url, headers=headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Find all image page links
            view_links = []
            for a in soup.find_all('a', href=True):
                if 'photos-view-id' in a['href']:
                    full_link = urljoin(gallery_url, a['href'])
                    if full_link not in view_links:
                        view_links.append(full_link)
            
            print(f"Found {len(view_links)} image pages.")
            downloaded_paths = []
            session_id = str(uuid.uuid4())[:8]
            
            # Download all image pages
            print(f"Downloading {len(view_links)} images...")
            
            for idx, page_url in enumerate(view_links):
                page_res = requests.get(page_url, headers=headers, timeout=10)
                page_soup = BeautifulSoup(page_res.text, "html.parser")
                
                img_tag = page_soup.find('img', id='picarea')
                if img_tag and img_tag.get('src'):
                    img_url = img_tag['src']
                    if img_url.startswith("//"):
                        img_url = "https:" + img_url
                        
                    print(f"Downloading {img_url}")
                    download_path = ComicCrawler._download_image(img_url, headers, session_id, idx, target_dir)
                    if download_path:
                        downloaded_paths.append(download_path)
            
            return downloaded_paths
        except Exception as e:
            print(f"Error crawling wnacg: {e}")
            return []

if __name__ == "__main__":
    # Test crawler
    test_url = "https://wnacg.com/photos-index-aid-350849.html"
    print(f"Testing crawler with {test_url}...")
    paths, title = ComicCrawler.get_images_from_url(test_url)
    print(f"Downloaded {len(paths)} images to {title}")
