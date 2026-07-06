import subprocess
from pathlib import Path
from pipeline.config import settings

class AudioMixer:
    def __init__(self, workspace_dir: str):
        self.workspace_dir = Path(workspace_dir)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

    def mix_audio(self, video_path: str, narration_path: str, music_path: str, output_path: str, video_duration: float, music_volume: float = None, narration_volume: float = None, fade_duration: float = None, timeline: list = None) -> str:
        """Mix video audio, narration, and background music with sidechain ducking and synchronized SFX."""
        print("Mixing voiceover, music, and synchronized SFX tracks...")
        
        # Load settings or overrides
        v_vol = settings.get("audio", "video_volume", 0.08)
        n_vol = narration_volume if narration_volume is not None else settings.get("audio", "narration_volume", 1.15)
        m_vol = music_volume if music_volume is not None else settings.get("audio", "music_volume", 0.08)
        fade_dur = fade_duration if fade_duration is not None else settings.get("audio", "music_fade_out_duration", 2.0)

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

        # SFX files path
        whoosh_sfx = Path(__file__).parent.parent / "static" / "sfx" / "whoosh.mp3"
        pop_sfx = Path(__file__).parent.parent / "static" / "sfx" / "pop.mp3"
        has_sfx = whoosh_sfx.exists() and pop_sfx.exists() and timeline is not None

        # Build FFmpeg command inputs
        inputs = [
            "-i", video_path,
            "-i", narration_path,
            "-i", str(trimmed_music)
        ]

        filters = [
            f"[0:a]volume={v_vol}[a_vid]",
            f"[1:a]volume={n_vol}[a_nar]",
            f"[2:a]volume={m_vol}[a_mus]"
        ]
        mix_inputs = ["[a_vid]", "[a_nar]", "[a_mus]"]

        if has_sfx:
            print("Adding synchronized transition WHOOSH and overlay POP sound effects...")
            # Compute transition whoosh times (at the end of each scene except the last)
            scene_ends = []
            current_t = 0.0
            for scene in timeline[:-1]:
                current_t += (scene["end"] - scene["start"])
                scene_ends.append(current_t)

            # Compute overlay pop times (at intro hook, scene title displays, and end card reveal)
            pop_times = [0.0]
            end_card_start = max(0.0, video_duration - 4.5)
            pop_times.append(end_card_start)

            current_t = 0.0
            for scene in timeline:
                scene_dur = scene["end"] - scene["start"]
                if current_t >= 3.5 and current_t < end_card_start - 1.0:
                    pop_times.append(current_t)
                current_t += scene_dur

            # Append whoosh inputs
            whoosh_start_idx = len(inputs) // 2
            for _ in scene_ends:
                inputs.extend(["-i", str(whoosh_sfx)])
            
            # Append pop inputs
            pop_start_idx = len(inputs) // 2
            for _ in pop_times:
                inputs.extend(["-i", str(pop_sfx)])

            # Build delay filters
            for idx, t in enumerate(scene_ends):
                delay_ms = int(t * 1000)
                input_idx = whoosh_start_idx + idx
                filters.append(f"[{input_idx}:a]adelay={delay_ms}|{delay_ms}[whoosh_{idx}]")
                mix_inputs.append(f"[whoosh_{idx}]")

            for idx, t in enumerate(pop_times):
                delay_ms = int(t * 1000)
                input_idx = pop_start_idx + idx
                filters.append(f"[{input_idx}:a]adelay={delay_ms}|{delay_ms}[pop_{idx}]")
                mix_inputs.append(f"[pop_{idx}]")

        # Combine all audio streams
        mix_inputs_str = "".join(mix_inputs)
        filters.append(f"{mix_inputs_str}amix=inputs={len(mix_inputs)}:duration=first:dropout_transition=2[out]")
        
        filter_str = "; ".join(filters)

        cmd = [
            "ffmpeg", "-y"
        ] + inputs + [
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
            print(f"Audio mixing with SFX failed: {e}. Trying simple merge without SFX.")
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
            if trimmed_music.exists() and trimmed_music != Path(music_path):
                trimmed_music.unlink()
