from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from crawler import ComicCrawler
from processor import ComicProcessor
import os
import uuid
import threading

app = FastAPI(title="Comic Translation API", version="0.1.0")

# CORS MUST be added before any mounts.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount output directory for static file serving
os.makedirs("processed_output", exist_ok=True)
app.mount("/output", StaticFiles(directory="processed_output"), name="output")

# Global processor instance
try:
    processor = ComicProcessor()
except Exception as e:
    print(f"Failed to initialize processor: {e}")
    processor = None

class TranslateRequest(BaseModel):
    url: str

# In-memory status store
translation_jobs = {}
# GPU concurrency lock to prevent OOM
gpu_lock = threading.Lock()

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Comic Translation API is running"}

def process_translation_job(job_id: str, url: str):
    print(f"[{job_id}] Queued translation process for {url}")
    try:
        # Step 1: Download images (Can be done concurrently)
        translation_jobs[job_id]["status"] = "downloading"
        downloaded_files, comic_title = ComicCrawler.get_images_from_url(url)
        print(f"[{job_id}] Downloaded {len(downloaded_files)} images for {comic_title}.")
        
        if not downloaded_files:
            translation_jobs[job_id] = {"status": "failed", "error": "No images found or failed to download."}
            return
            
        processed_urls = []
        target_output_dir = os.path.join("processed_output", comic_title)
        os.makedirs(target_output_dir, exist_ok=True)
        
        # Step 2-5: GPU bound operations (Must be sequential)
        for img_path in downloaded_files:
            translation_jobs[job_id]["status"] = f"waiting in GPU queue ({os.path.basename(img_path)})"
            
            with gpu_lock:
                translation_jobs[job_id]["status"] = f"processing {os.path.basename(img_path)}"
                if processor:
                    out_path = processor.process_image(img_path, output_dir=target_output_dir)
                    if out_path:
                        filename = os.path.basename(out_path)
                        processed_urls.append(f"/output/{comic_title}/{filename}")
                else:
                     translation_jobs[job_id]["status"] = "failed: processor not initialized"
                     return
                 
        translation_jobs[job_id] = {
            "status": "completed",
            "result_images": processed_urls
        }
        print(f"[{job_id}] Translation job completed successfully.")
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[{job_id}] Job failed: {e}")
        translation_jobs[job_id] = {"status": "failed", "error": str(e)}

@app.post("/translate")
def translate_comic(request: TranslateRequest, background_tasks: BackgroundTasks):
    if len(translation_jobs) >= 100:
        to_delete = [k for k, v in translation_jobs.items() if v["status"] in ["completed", "failed"]]
        for k in to_delete:
            if len(translation_jobs) <= 80: break
            del translation_jobs[k]

    job_id = str(uuid.uuid4())
    translation_jobs[job_id] = {"status": "pending", "url": request.url}
    
    background_tasks.add_task(process_translation_job, job_id, request.url)
    
    return {
        "status": "accepted",
        "job_id": job_id,
        "message": "Translation started in background. Polling the status endpoint to get results."
    }

@app.get("/status/{job_id}")
def get_status(job_id: str):
    if job_id not in translation_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return translation_jobs[job_id]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
