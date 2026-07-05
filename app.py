import os
import sys
import queue
import threading
import io
import time
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pipeline.orchestrator import AdForgeOrchestrator

app = FastAPI(title="AdForge Studio")

# Base directory
BASE_DIR = Path(__file__).parent.resolve()
UPLOAD_DIR = BASE_DIR / "workspace" / "uploads"
OUTPUT_DIR = BASE_DIR / "output"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Mount static folder
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Custom stdout redirector to capture print logs
class QueueWriter(io.StringIO):
    def __init__(self, log_queue: queue.Queue):
        super().__init__()
        self.log_queue = log_queue

    def write(self, s):
        clean = s.strip()
        if clean:
            self.log_queue.put(clean)
        # Still write to actual console
        sys.__stdout__.write(s)

@app.get("/", response_class=HTMLResponse)
def get_home():
    html_file = BASE_DIR / "static" / "index.html"
    if html_file.exists():
        return html_file.read_text(encoding="utf-8")
    return "<h3>AdForge UI not found. Run setup first.</h3>"

@app.post("/upload")
async def upload_files(files: list[UploadFile] = File(...)):
    """Upload raw video clips to the workspace directory."""
    uploaded_files = []
    
    # Clean previous uploads to keep workspace fresh
    if UPLOAD_DIR.exists():
        for item in UPLOAD_DIR.iterdir():
            if item.is_file():
                item.unlink()
                
    for file in files:
        target_path = UPLOAD_DIR / file.filename
        try:
            with target_path.open("wb") as buffer:
                buffer.write(await file.read())
            uploaded_files.append(file.filename)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to save {file.filename}: {e}")
            
    return {"message": "Files uploaded successfully", "files": uploaded_files}

@app.get("/generate")
def generate_ad(brief: str, duration: float = 60.0, lut: str = "cinematic", name: str = "adforge_ad"):
    """
    Run the production pipeline and stream logs to the client using SSE.
    """
    log_queue = queue.Queue()
    
    def run_pipeline():
        # Redirect stdout to capture all prints
        old_stdout = sys.stdout
        sys.stdout = QueueWriter(log_queue)
        
        try:
            orchestrator = AdForgeOrchestrator(str(BASE_DIR))
            output_file = orchestrator.run(
                clips_dir=str(UPLOAD_DIR),
                brief=brief,
                duration=duration,
                lut_name=lut,
                project_name=name
            )
            # Signal success and return filename
            filename = Path(output_file).name
            log_queue.put(f"SUCCESS:{filename}")
        except Exception as e:
            log_queue.put(f"ERROR:{str(e)}")
        finally:
            sys.stdout = old_stdout
            # Put Sentinel value to terminate queue reader
            log_queue.put(None)

    # Start orchestrator in background thread
    thread = threading.Thread(target=run_pipeline)
    thread.start()

    # Generator for Server-Sent Events (SSE)
    def sse_event_generator():
        while True:
            try:
                log_line = log_queue.get(timeout=120)  # wait up to 2 min
                if log_line is None:
                    break
                if log_line.startswith("SUCCESS:"):
                    filename = log_line.split(":", 1)[1]
                    yield f"event: done\ndata: {filename}\n\n"
                elif log_line.startswith("ERROR:"):
                    err = log_line.split(":", 1)[1]
                    yield f"event: error\ndata: {err}\n\n"
                else:
                    yield f"data: {log_line}\n\n"
            except queue.Empty:
                yield "data: Pipeline is processing...\n\n"

    return StreamingResponse(sse_event_generator(), media_type="text/event-stream")

@app.get("/output/{filename}")
def get_output_video(filename: str):
    """Serve the final rendered video file."""
    video_path = OUTPUT_DIR / filename
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found.")
    return FileResponse(str(video_path), media_type="video/mp4")
