import subprocess
from pathlib import Path
from pipeline.config import settings

class AudioMixer:
    def __init__(self, workspace_dir: str):
        self.workspace_dir = Path(workspace_dir)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

    def mix_audio(self, video_path: str, narration_path: str, music_path: str, output_path: str, video_duration: float) -> str:
        """Mix video audio, narration, and background music with ducking."""
        print("Mixing voiceover and music tracks...")
        
        # Load settings
        v_vol = settings.get("audio", "video_volume", 0.08)
        n_vol = settings.get("audio", "narration_volume", 1.15)
        m_vol = settings.get("audio", "music_volume", 0.08)
        fade_dur = settings.get("audio", "music_fade_out_duration", 2.0)

        # 1. Trim background music to match video duration with a fade-out
        trimmed_music = self.workspace_dir / "trimmed_music.mp3"
        music_filter = f"afade=t=out:st={video_duration - fade_dur}:d={fade_dur}"
        
        cmd_trim_music = [
            "ffmpeg", "-y",
            "-i", music_path,
            "-filter_complex", music_filter,
            "-t", str(video_duration),
            str(trimmed_music)
        ]
        try:
            subprocess.run(cmd_trim_music, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        except Exception as e:
            print(f"Failed to trim background music: {e}. Using untrimmed.")
            trimmed_music = Path(music_path)

        # 2. Mix:
        # [0:a] = video audio
        # [1:a] = narration
        # [2:a] = music
        filter_str = (
            f"[0:a]volume={v_vol}[a_vid]; "
            f"[1:a]volume={n_vol}[a_nar]; "
            f"[2:a]volume={m_vol}[a_mus]; "
            "[a_vid][a_nar][a_mus]amix=inputs=3:duration=first:dropout_transition=2[out]"
        )

        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", narration_path,
            "-i", str(trimmed_music),
            "-filter_complex", filter_str,
            "-map", "0:v",
            "-map", "[out]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-shortest",
            output_path
        ]
        
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            return output_path
        except Exception as e:
            print(f"Audio mixing failed: {e}. Trying simple merge without original video audio.")
            fallback_filter = f"[0:a]volume={n_vol}[a_nar]; [1:a]volume={m_vol}[a_mus]; [a_nar][a_mus]amix=inputs=2:duration=first[out]"
            cmd_fb = [
                "ffmpeg", "-y",
                "-i", video_path,
                "-i", narration_path,
                "-i", str(trimmed_music),
                "-filter_complex", fallback_filter,
                "-map", "0:v",
                "-map", "[out]",
                "-c:v", "copy",
                "-c:a", "aac",
                "-shortest",
                output_path
            ]
            subprocess.run(cmd_fb, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            return output_path
        finally:
            # Cleanup temp trimmed music if it was created
            if trimmed_music.exists() and trimmed_music != Path(music_path):
                trimmed_music.unlink()
