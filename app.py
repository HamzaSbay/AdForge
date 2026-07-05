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
from pydantic import BaseModel
from typing import List, Dict, Any
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

@app.post("/api/analyze")
def analyze_uploaded_clips():
    """Scan and analyze all uploaded clips, returning metadata and descriptions."""
    allowed_exts = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
    clips_paths = [
        str(p) for p in UPLOAD_DIR.iterdir()
        if p.suffix.lower() in allowed_exts and p.is_file()
    ]
    if not clips_paths:
        raise HTTPException(status_code=400, detail="No video files uploaded yet.")
    
    orchestrator = AdForgeOrchestrator(str(BASE_DIR))
    analyzed_clips = []
    for path in clips_paths:
        try:
            res = orchestrator.analyzer.analyze_clip(path)
            if "error" not in res:
                analyzed_clips.append(res)
        except Exception as e:
            print(f"Analysis failed for {path}: {e}")
            
    if not analyzed_clips:
        raise HTTPException(status_code=500, detail="Failed to analyze any of the uploaded files.")
        
    return {"clips": analyzed_clips}

class PlanRequest(BaseModel):
    brief: str
    duration: float = 60.0
    clips: List[Dict[str, Any]]

@app.post("/api/plan")
def plan_campaign_timeline(req: PlanRequest):
    """Generate script and timeline cuts based on analyzed clips and brief."""
    orchestrator = AdForgeOrchestrator(str(BASE_DIR))
    try:
        timeline = orchestrator.selector.create_timeline(req.clips, req.brief, target_duration=req.duration)
        script = orchestrator.scriptwriter.write_script(timeline, req.brief, target_duration=req.duration)
        return {"timeline": timeline, "script": script}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate campaign plan: {e}")

class DraftRequest(BaseModel):
    timeline: List[Dict[str, Any]]
    script: Dict[str, Any]
    theme: str = "bold"

@app.post("/api/save_draft")
def save_campaign_draft(req: DraftRequest):
    """Temporarily save pre-approved timeline, script, and theme to workspace drafts."""
    import json
    draft_script_path = BASE_DIR / "workspace" / "draft_script.json"
    draft_timeline_path = BASE_DIR / "workspace" / "draft_timeline.json"
    draft_theme_path = BASE_DIR / "workspace" / "draft_theme.txt"
    
    try:
        with open(draft_script_path, "w", encoding="utf-8") as f:
            json.dump(req.script, f, indent=2)
        with open(draft_timeline_path, "w", encoding="utf-8") as f:
            json.dump(req.timeline, f, indent=2)
        draft_theme_path.write_text(req.theme.strip(), encoding="utf-8")
        return {"status": "ok", "message": "Draft saved successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save draft files: {e}")

@app.get("/generate")
def generate_ad(brief: str, duration: float = 60.0, lut: str = "cinematic", name: str = "adforge_ad"):
    """
    Run the production pipeline and stream logs to the client using SSE.
    If draft files exist, it reads and injects them to bypass AI generation.
    """
    import json
    log_queue = queue.Queue()
    
    # Check for pre-existing drafts
    draft_script_path = BASE_DIR / "workspace" / "draft_script.json"
    draft_timeline_path = BASE_DIR / "workspace" / "draft_timeline.json"
    draft_theme_path = BASE_DIR / "workspace" / "draft_theme.txt"
    
    draft_script = None
    draft_timeline = None
    theme = "bold"
    
    if draft_script_path.exists() and draft_timeline_path.exists():
        try:
            with open(draft_script_path, "r", encoding="utf-8") as f:
                draft_script = json.load(f)
            with open(draft_timeline_path, "r", encoding="utf-8") as f:
                draft_timeline = json.load(f)
            if draft_theme_path.exists():
                theme = draft_theme_path.read_text(encoding="utf-8").strip()
        except Exception as e:
            print(f"Warning: Failed to load draft files ({e}). Falling back to standard generation.")
            
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
                project_name=name,
                draft_script=draft_script,
                draft_timeline=draft_timeline,
                theme=theme
            )
            
            # Clean up drafts after successful production
            for p in [draft_script_path, draft_timeline_path, draft_theme_path]:
                if p.exists():
                    p.unlink()
                    
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
