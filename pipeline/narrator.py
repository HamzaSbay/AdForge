import os
import subprocess
from pathlib import Path
from dotenv import load_dotenv
from pipeline.config import settings
from pipeline.tts import get_tts_provider

load_dotenv()

class AdNarrator:
    def __init__(self, workspace_dir: str, provider: str = None):
        self.workspace_dir = Path(workspace_dir)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.provider = provider or settings.get("tts", "provider", "google")

    def generate_speech(self, text: str, output_path: str, voice_name: str = None, provider_name: str = None) -> str:
        """Generate speech using selected or configured TTS provider with fallback support."""
        provider = provider_name or self.provider
        
        # Journey/Chirp voices only exist on google
        resolved_voice = voice_name
        if resolved_voice:
            if "Journey" in resolved_voice or "Chirp" in resolved_voice:
                if provider != "google":
                    resolved_voice = None # Let backend choose default
                    
        # If Google API key is missing and provider is google, default to edge-tts
        if provider == "google" and not os.getenv("GOOGLE_API_KEY"):
            print("GOOGLE_API_KEY is missing. Redirecting Google Cloud TTS to EdgeTTS...")
            provider = "edge"
            resolved_voice = None

        # Try primary provider
        try:
            tts_engine = get_tts_provider(provider)
            return tts_engine.generate_speech(text, output_path, voice_name=resolved_voice)
        except Exception as e:
            print(f"Primary TTS provider '{provider}' failed ({e}). Attempting free EdgeTTS fallback...")
            if provider != "edge":
                try:
                    from pipeline.tts import EdgeTTSBackend
                    return EdgeTTSBackend().generate_speech(text, output_path)
                except Exception as ex:
                    print(f"EdgeTTS fallback failed: {ex}. Falling back to pyttsx3 offline engine...")
            
            # Absolute fallback to pyttsx3
            try:
                from pipeline.tts import LocalTTS
                return LocalTTS().generate_speech(text, output_path)
            except Exception as fe:
                print(f"Offline pyttsx3 fallback failed: {fe}. Creating a silent placeholder audio.")
                cmd = [
                    "ffmpeg", "-y",
                    "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                    "-t", "5",
                    output_path
                ]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                return output_path

    def get_audio_duration(self, audio_path: str) -> float:
        """Get the duration of an audio file using ffprobe."""
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            audio_path
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return float(res.stdout.strip())
        except Exception as e:
            print(f"Error checking duration of {audio_path}: {e}")
            return 0.0

    def generate_aligned_voiceover(self, paragraphs: list[str], timeline: list[dict], provider: str = None, voice: str = None) -> str:
        """
        Generate narration audio for each scene, pad/space them out to match
        the starting times of each scene in the timeline, and mix them together.
        """
        scene_audios = []
        
        # Step 1: Synthesize each paragraph
        for i, (para, t) in enumerate(zip(paragraphs, timeline)):
            if not para.strip():
                continue
            para_path = self.workspace_dir / f"scene_{i}_narr.mp3"
            self.generate_speech(para, str(para_path), voice_name=voice, provider_name=provider)
            
            # Duration of this narration segment
            narr_dur = self.get_audio_duration(str(para_path))
            scene_dur = t["end"] - t["start"]
            
            print(f"Scene {i} narration duration: {narr_dur:.2f}s (scene duration: {scene_dur:.2f}s)")
            
            # Store path, narration duration, and the target timeline start time
            scene_audios.append({
                "path": str(para_path),
                "start_time": sum((timeline[j]["end"] - timeline[j]["start"]) for j in range(i)),
                "duration": narr_dur
            })

        # Step 2: Mix narration audios with silence delay using FFmpeg complex filter
        if not scene_audios:
            # Create a silent audio track as fallback
            silent_path = self.workspace_dir / "silent_narration.mp3"
            cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", "60", str(silent_path)]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            return str(silent_path)
            
        inputs = []
        delay_filters = []
        for i, sa in enumerate(scene_audios):
            inputs.extend(["-i", sa["path"]])
            delay_ms = int(sa["start_time"] * 1000)
            # adelay format: adelay=delay_left|delay_right
            delay_filters.append(f"[{i}:a]adelay={delay_ms}|{delay_ms}[a{i}]")
            
        mix_inputs = "".join(f"[a{i}]" for i in range(len(scene_audios)))
        filter_str = ";".join(delay_filters) + f";{mix_inputs}amix=inputs={len(scene_audios)}:normalize=0[out]"
        
        final_narr_path = self.workspace_dir / "final_narration.mp3"
        cmd = ["ffmpeg", "-y"] + inputs + [
            "-filter_complex", filter_str,
            "-map", "[out]",
            str(final_narr_path)
        ]
        
        print("Mixing and aligning narration clips...")
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return str(final_narr_path)
