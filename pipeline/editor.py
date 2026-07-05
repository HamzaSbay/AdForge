import subprocess
from pathlib import Path

class AdEditor:
    def __init__(self, workspace_dir: str):
        self.workspace_dir = Path(workspace_dir)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

    def trim_clip(self, graded_clip_path: str, start: float, end: float, output_path: str) -> str:
        """Trim a clip using FFmpeg."""
        duration = end - start
        print(f"Trimming {graded_clip_path} from {start}s to {end}s (dur: {duration:.2f}s)...")
        
        # Use seek before input for speed, but do it accurately
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start),
            "-t", str(duration),
            "-i", graded_clip_path,
            "-c:v", "libx264",
            "-c:a", "aac",
            output_path
        ]
        
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            return output_path
        except Exception as e:
            print(f"Failed to trim {graded_clip_path}: {e}")
            raise e

    def stitch_clips(self, clip_paths: list[str], output_path: str, use_transitions: bool = True) -> str:
        """Stitch multiple trimmed clips together using FFmpeg concat filter."""
        print(f"Stitching {len(clip_paths)} clips together...")
        
        if not clip_paths:
            raise ValueError("No clips to stitch.")
        if len(clip_paths) == 1:
            # Just copy the single clip
            cmd = ["ffmpeg", "-y", "-i", clip_paths[0], "-c", "copy", output_path]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            return output_path

        # Option A: Simple sequential concat (Instant cuts - very reliable and standard for vertical ads)
        # We write a text file of clips and use concat demuxer
        concat_txt = self.workspace_dir / "concat_list.txt"
        with open(concat_txt, "w") as f:
            for p in clip_paths:
                # Escape path for FFmpeg concat format
                escaped_path = p.replace("\\", "/")
                f.write(f"file '{escaped_path}'\n")

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_txt),
            "-c", "copy",
            output_path
        ]
        
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            return output_path
        except Exception as e:
            print(f"Demuxer stitch failed: {e}. Trying filter concat...")
            
            # Option B: Filter concat as fallback
            inputs = []
            filter_str = ""
            for i, p in enumerate(clip_paths):
                inputs.extend(["-i", p])
                filter_str += f"[{i}:v][{i}:a]"
            filter_str += f"concat=n={len(clip_paths)}:v=1:a=1[v][a]"
            
            cmd_filter = [
                "ffmpeg", "-y"
            ] + inputs + [
                "-filter_complex", filter_str,
                "-map", "[v]",
                "-map", "[a]",
                "-c:v", "libx264",
                "-c:a", "aac",
                output_path
            ]
            subprocess.run(cmd_filter, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            return output_path
        finally:
            if concat_txt.exists():
                concat_txt.unlink()
