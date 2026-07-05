import base64
import os
import requests
import subprocess
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

from pipeline.config import settings

class AdNarrator:
    def __init__(self, workspace_dir: str):
        self.workspace_dir = Path(workspace_dir)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

    def generate_speech(self, text: str, output_path: str, voice_name: str = None) -> str:
        """Call Google Cloud TTS to synthesize text to an MP3 file."""
        if not voice_name:
            voice_name = settings.get("tts", "default_voice", "en-US-Journey-D")
            
        print(f"Narrating text: '{text[:40]}...' using voice {voice_name}")
        
        speaking_rate = settings.get("tts", "speaking_rate", 1.0)
        pitch = settings.get("tts", "pitch", 0.0)
        fallback_rate = settings.get("tts", "local_fallback_rate", 185)

        # Journey/Chirp voices require v1beta1, others use v1
        api_version = "v1beta1" if ("Journey" in voice_name or "Chirp" in voice_name) else "v1"
        url = f"https://texttospeech.googleapis.com/{api_version}/text:synthesize"
        
        payload = {
            "input": {"text": text},
            "voice": {
                "languageCode": "en-US",
                "name": voice_name,
            },
            "audioConfig": {
                "audioEncoding": "MP3",
                "speakingRate": speaking_rate,
                "pitch": pitch,
            },
        }
        
        headers = {"Content-Type": "application/json"}
        params = {"key": api_key or ""}
        
        try:
            if not api_key:
                raise ValueError("GOOGLE_API_KEY is empty")
            response = requests.post(url, headers=headers, params=params, json=payload, timeout=60)
            response.raise_for_status()
            audio_data = base64.b64decode(response.json()["audioContent"])
            Path(output_path).write_bytes(audio_data)
            return output_path
        except Exception as e:
            print(f"Google Cloud TTS failed/unauthorized ({e}). Falling back to local offline TTS engine...")
            try:
                try:
                    import pythoncom
                    pythoncom.CoInitialize()
                except Exception:
                    pass
                import pyttsx3
                temp_wav = Path(output_path).with_suffix(".wav")
                engine = pyttsx3.init()
                engine.setProperty('rate', fallback_rate)
                engine.save_to_file(text, str(temp_wav))
                engine.runAndWait()
                
                # Convert the generated WAV to MP3 or output format
                cmd = [
                    "ffmpeg", "-y",
                    "-i", str(temp_wav),
                    "-c:a", "libmp3lame",
                    output_path
                ]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                
                # Cleanup temp wav
                if temp_wav.exists():
                    temp_wav.unlink()
                return output_path
            except Exception as fe:
                print(f"Offline TTS fallback failed: {fe}. Creating a silent placeholder audio.")
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

    def generate_aligned_voiceover(self, paragraphs: list[str], timeline: list[dict]) -> str:
        """
        Generate narration audio for each scene, pad/space them out to match
        the starting times of each scene in the timeline, and mix them together.
        """
        scene_audios = []
        
        # Voice names: en-US-Journey-D (male), en-US-Journey-F (female)
        voice = "en-US-Journey-D"
        
        # Step 1: Synthesize each paragraph
        for i, (para, t) in enumerate(zip(paragraphs, timeline)):
            if not para.strip():
                continue
            para_path = self.workspace_dir / f"scene_{i}_narr.mp3"
            self.generate_speech(para, str(para_path), voice_name=voice)
            
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
        # e.g. -filter_complex "[0]adelay=3000|3000[a0]; [1]adelay=8000|8000[a1]; [a0][a1]amix=inputs=2"
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
