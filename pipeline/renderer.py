import json
import subprocess
import os
from pathlib import Path

class AdRenderer:
    def __init__(self, workspace_dir: str):
        self.workspace_dir = Path(workspace_dir)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

    def render_remotion_overlays(self, video_path: str, title: str, scene_titles: list[str], scene_durations: list[float], cta_text: str, duration_sec: float, theme: str = "bold") -> str:
        """Render React overlays combined with the background video using Remotion."""
        print(f"Rendering Remotion animated overlays (theme: {theme}) on top of background video...")
        
        props_path = self.workspace_dir / "remotion_props.json"
        overlay_mp4 = self.workspace_dir / "overlays_raw.mp4"
        
        # Use directory of the video as the public folder to bypass browser file:// security
        abs_public_dir = os.path.dirname(os.path.abspath(video_path))
        video_filename = os.path.basename(video_path)
        
        # Format the props
        props_data = {
            "videoSrc": video_filename,
            "title": title,
            "sceneTitles": scene_titles,
            "sceneDurations": scene_durations,
            "ctaText": cta_text,
            "theme": theme
        }
        
        with open(props_path, "w") as f:
            json.dump(props_data, f)
            
        # We invoke Remotion from OpenMontage's remotion-composer folder
        composer_dir = Path(__file__).parent.parent.parent / "OpenMontage" / "remotion-composer"
        
        # Calculate duration in frames (30fps)
        duration_frames = int(duration_sec * 30)

        # Build absolute path to props and output
        abs_props_path = props_path.resolve()
        abs_overlay_mp4 = overlay_mp4.resolve()

        # Run npx remotion render
        cmd = [
            "npx", "remotion", "render",
            "src/index.tsx", "AdForgeOverlay",
            str(abs_overlay_mp4),
            f"--props={abs_props_path}",
            f"--frames=0-{duration_frames - 1}",
            f"--public-dir={abs_public_dir}"
        ]
        
        # Include Node in Path
        env = os.environ.copy()
        env["PATH"] = "C:\\Program Files\\nodejs;" + env.get("PATH", "")
        
        try:
            print("Running Remotion compiler (this may take a few seconds)...")
            # Executing in remotion-composer directory
            subprocess.run(
                cmd,
                cwd=str(composer_dir),
                env=env,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=True
            )
            return str(overlay_mp4)
        except subprocess.CalledProcessError as e:
            print(f"Remotion render failed: {e.stderr}")
            raise RuntimeError(f"Remotion compile error: {e.stderr}")
        finally:
            if props_path.exists():
                props_path.unlink()

    def merge_overlays(self, video_path: str, overlay_path: str, output_path: str) -> str:
        """Overlay merge is bypassed because Remotion rendered the background video directly."""
        import shutil
        print("Bypassing FFmpeg blend layer (Remotion pre-composited)...")
        shutil.copy(overlay_path, output_path)
        return output_path
