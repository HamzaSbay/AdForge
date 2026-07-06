import subprocess
from pathlib import Path
from pipeline.config import settings

class ClipColorGrader:
    def __init__(self, workspace_dir: str):
        self.workspace_dir = Path(workspace_dir)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

    def get_video_dimensions(self, clip_path: str) -> tuple[int, int]:
        import json
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "json", clip_path
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            info = json.loads(result.stdout)
            stream = info.get("streams", [{}])[0]
            return int(stream.get("width", 0)), int(stream.get("height", 0))
        except Exception:
            return 0, 0

    def grade_and_crop(self, clip_path: str, output_path: str, lut_name: str = "cinematic", aspect_ratio: str = "9:16") -> str:
        """
        Crop, scale to target aspect ratio, and apply color grading.
        Uses FFmpeg filters.
        """
        print(f"Color grading and cropping {clip_path} to {aspect_ratio}...")
        
        target_w = settings.get("video", "target_width", 1080)
        target_h = settings.get("video", "target_height", 1920)
        fps = settings.get("video", "fps", 30)
        v_codec = settings.get("video", "codec", "libx264")
        pix_fmt = settings.get("video", "pix_fmt", "yuv420p")
        a_codec = settings.get("video", "audio_codec", "aac")
        ar = settings.get("video", "audio_sample_rate", 44100)
        ac = settings.get("video", "audio_channels", 2)
        sharpen = settings.get("video", "sharpen_filter", "unsharp=3:3:0.5:3:3:0.5")

        w, h = self.get_video_dimensions(clip_path)
        if w > 0 and h > 0:
            aspect = w / h
            if aspect_ratio == "9:16":
                # Target is vertical 9:16
                if aspect > (9.0 / 16.0):
                    crop_filter = "crop=ih*9/16:ih"
                else:
                    crop_filter = "crop=iw:iw*16/9"
                video_filter = f"{crop_filter},scale={target_w}:{target_h}"
            elif aspect_ratio == "1:1":
                # Target is square 1:1
                if aspect > 1.0:
                    crop_filter = "crop=ih:ih"
                else:
                    crop_filter = "crop=iw:iw"
                video_filter = f"{crop_filter},scale=1080:1080"
            else:
                # Target is horizontal 16:9
                if aspect > (16.0 / 9.0):
                    crop_filter = "crop=ih*16/9:ih"
                else:
                    crop_filter = "crop=iw:iw*9/16"
                video_filter = f"{crop_filter},scale={target_h}:{target_w}"
        else:
            # Fallback if dimensions could not be read
            if aspect_ratio == "9:16":
                video_filter = f"crop=ih*9/16:ih,scale={target_w}:{target_h}"
            elif aspect_ratio == "1:1":
                video_filter = "crop=ih:ih,scale=1080:1080"
            else:
                video_filter = f"scale={target_h}:{target_w}"
        
        # 2. Add color grading options
        lut_file = Path(__file__).parent.parent / "luts" / f"{lut_name}.cube"
        
        if lut_file.exists():
            print(f"Applying 3D LUT: {lut_file.name}")
            lut_path_escaped = str(lut_file).replace("\\", "/").replace(":", "\\:")
            video_filter += f",lut3d='{lut_path_escaped}'"
        else:
            print("LUT file not found. Applying default cinematic EQ filter.")
            video_filter += ",eq=contrast=1.1:brightness=0.03:saturation=1.25"
            
        # Add slight sharpening
        if sharpen:
            video_filter += f",{sharpen}"

        # Final command: Scale, crop, grade, re-encode audio, fps
        cmd = [
            "ffmpeg", "-y",
            "-i", clip_path,
            "-vf", video_filter,
            "-r", str(fps),
            "-c:v", v_codec,
            "-pix_fmt", pix_fmt,
            "-c:a", a_codec,
            "-ar", str(ar),
            "-ac", str(ac),
            output_path
        ]
        
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            return output_path
        except Exception as e:
            print(f"Failed to grade/crop {clip_path}: {e}")
            raise e
