import os
import subprocess
import json
from pathlib import Path
from PIL import Image
import google.generativeai as genai

# Setup Gemini API key
from dotenv import load_dotenv
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

class ClipAnalyzer:
    def __init__(self, workspace_dir: str):
        self.workspace_dir = Path(workspace_dir)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.model = genai.GenerativeModel("gemini-2.5-flash")

    def get_video_metadata(self, clip_path: str) -> dict:
        """Extract metadata using ffprobe."""
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate,duration",
            "-of", "json", clip_path
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            info = json.loads(result.stdout)
            stream = info.get("streams", [{}])[0]
            
            # Parse duration
            duration = float(stream.get("duration", 0))
            if duration == 0:
                # Fallback check if duration isn't in streams
                cmd_format = [
                    "ffprobe", "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "json", clip_path
                ]
                res_format = subprocess.run(cmd_format, capture_output=True, text=True, check=True)
                info_format = json.loads(res_format.stdout)
                duration = float(info_format.get("format", {}).get("duration", 0))

            # Parse framerate
            r_frame_rate = stream.get("r_frame_rate", "30/1")
            if "/" in r_frame_rate:
                num, den = map(int, r_frame_rate.split("/"))
                fps = num / den if den != 0 else 30.0
            else:
                fps = float(r_frame_rate)

            return {
                "width": int(stream.get("width", 0)),
                "height": int(stream.get("height", 0)),
                "duration": duration,
                "fps": fps
            }
        except Exception as e:
            print(f"Error reading metadata for {clip_path}: {e}")
            return {"width": 0, "height": 0, "duration": 0.0, "fps": 30.0}

    def extract_thumbnails(self, clip_path: str, duration: float) -> list[str]:
        """Extract 3 thumbnail images from the video."""
        thumbnails = []
        clip_name = Path(clip_path).stem
        
        # Extract at 25%, 50%, and 75% of duration
        timestamps = [duration * 0.25, duration * 0.50, duration * 0.75]
        
        for i, ts in enumerate(timestamps):
            out_path = self.workspace_dir / f"{clip_name}_thumb_{i}.jpg"
            cmd = [
                "ffmpeg", "-y",
                "-ss", str(ts),
                "-i", clip_path,
                "-vframes", "1",
                "-q:v", "2",
                str(out_path)
            ]
            try:
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                if out_path.exists():
                    thumbnails.append(str(out_path))
            except Exception as e:
                print(f"Failed to extract thumbnail at {ts}s for {clip_path}: {e}")
        
        return thumbnails

    def analyze_clip(self, clip_path: str) -> dict:
        """Perform metadata and AI content analysis on a clip."""
        print(f"Analyzing {clip_path}...")
        meta = self.get_video_metadata(clip_path)
        duration = meta["duration"]
        
        if duration <= 0:
            return {
                "path": clip_path,
                "error": "Invalid video duration",
                "metadata": meta
            }
            
        thumbs = self.extract_thumbnails(clip_path, duration)
        
        # Load images for Gemini
        images = []
        for t in thumbs:
            try:
                images.append(Image.open(t))
            except Exception as e:
                print(f"Error opening image {t}: {e}")

        # Determine dynamic segment (e.g. from 20% of video to capture active action)
        start_seg = max(0.0, duration * 0.20)
        end_seg = min(duration, start_seg + 4.5)
        if end_seg - start_seg < 2.0:
            start_seg = 0.0
            end_seg = duration

        analysis = {
            "description": f"Local offline analysis for {Path(clip_path).name}.",
            "visual_score": 8,
            "energy_score": 7,
            "suitability_score": 8,
            "best_segment": {"start": round(start_seg, 2), "end": round(end_seg, 2)},
            "labels": ["Footage", "Scene"]
        }

        if images and api_key:
            prompt = """
            Analyze these 3 sequential frames from a video clip.
            Provide your analysis in EXACT JSON format with these keys:
            - "description": A concise summary of what is happening in the clip, visual style, subjects, lighting.
            - "visual_score": Score from 0 to 10 of visual appeal/lighting/composition.
            - "energy_score": Score from 0 to 10 of action/motion/camera movement.
            - "suitability_score": Score from 0 to 10 of how good this clip would be in a professional commercial/ad.
            - "best_segment": An object with "start" and "end" (floats) suggesting the most visually engaging 3-second continuous segment within this clip (which is {duration} seconds long).
            - "labels": List of 3-5 tags describing the objects or theme.
            
            Do NOT include markdown wrapping like ```json or any other text. Only return raw JSON.
            """.format(duration=duration)
            
            try:
                response = self.model.generate_content([prompt] + images)
                text = response.text.strip()
                # Clean up any potential markdown formatting in case the model ignored instructions
                if text.startswith("```"):
                    text = text.replace("```json", "").replace("```", "").strip()
                analysis = json.loads(text)
            except Exception as e:
                print(f"Gemini analysis failed for {clip_path}: {e}")

        # Add metadata & path information
        return {
            "path": os.path.abspath(clip_path),
            "filename": Path(clip_path).name,
            "metadata": meta,
            "analysis": analysis
        }
