import os
import re
import json
import base64
import asyncio
import requests
import subprocess
from pathlib import Path
from pipeline.config import settings

class BaseTTS:
    def generate_speech(self, text: str, output_path: str, voice_name: str = None) -> str:
        """Synthesize text to audio output file. Return output path."""
        raise NotImplementedError

class GoogleTTS(BaseTTS):
    def generate_speech(self, text: str, output_path: str, voice_name: str = None) -> str:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY is not configured.")
        
        if not voice_name:
            voice_name = settings.get("tts", "default_voice", "en-US-Journey-D")
            
        print(f"Google Cloud TTS narrating using voice {voice_name}...")
        
        speaking_rate = settings.get("tts", "speaking_rate", 1.0)
        pitch = settings.get("tts", "pitch", 0.0)

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
        params = {"key": api_key}
        
        response = requests.post(url, headers=headers, params=params, json=payload, timeout=60)
        response.raise_for_status()
        audio_data = base64.b64decode(response.json()["audioContent"])
        Path(output_path).write_bytes(audio_data)
        return output_path

class EdgeTTSBackend(BaseTTS):
    def generate_speech(self, text: str, output_path: str, voice_name: str = None) -> str:
        import edge_tts
        
        # Default edge-tts voice if none provided
        if not voice_name:
            voice_name = "en-US-GuyNeural"  # Guy (male), Aria (female)
            
        print(f"EdgeTTS (free cloud) narrating using voice {voice_name}...")
        
        async def _run():
            communicate = edge_tts.Communicate(text, voice_name)
            await communicate.save(output_path)
            
        # Run edge_tts asynchronously
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_run())
        finally:
            loop.close()
            
        return output_path

class LocalTTS(BaseTTS):
    def __init__(self, rate: int = None):
        self.rate = rate or settings.get("tts", "local_fallback_rate", 185)

    def generate_speech(self, text: str, output_path: str, voice_name: str = None) -> str:
        print("Local pyttsx3 offline narrating...")
        try:
            try:
                import pythoncom
                pythoncom.CoInitialize()
            except Exception:
                pass
            import pyttsx3
            temp_wav = Path(output_path).with_suffix(".wav")
            engine = pyttsx3.init()
            engine.setProperty('rate', self.rate)
            engine.save_to_file(text, str(temp_wav))
            engine.runAndWait()
            
            # Convert WAV to MP3 using FFmpeg
            cmd = [
                "ffmpeg", "-y",
                "-i", str(temp_wav),
                "-c:a", "libmp3lame",
                output_path
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            if temp_wav.exists():
                temp_wav.unlink()
            return output_path
        except Exception as e:
            print(f"Local pyttsx3 TTS failed: {e}")
            raise e

class OpenAITTS(BaseTTS):
    def generate_speech(self, text: str, output_path: str, voice_name: str = None) -> str:
        from openai import OpenAI
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is not configured.")
        
        if not voice_name:
            voice_name = "alloy"  # alloy, echo, fable, onyx, nova, shimmer
            
        print(f"OpenAI TTS narrating using voice {voice_name}...")
        
        client = OpenAI(api_key=api_key)
        response = client.audio.speech.create(
            model="tts-1",
            voice=voice_name,
            input=text
        )
        response.stream_to_file(output_path)
        return output_path

def get_tts_provider(provider_name: str) -> BaseTTS:
    """Return the requested TTS backend instance."""
    p = provider_name.strip().lower() if provider_name else "google"
    if p == "edge" or p == "edge-tts":
        return EdgeTTSBackend()
    elif p == "local" or p == "pyttsx3":
        return LocalTTS()
    elif p == "openai":
        return OpenAITTS()
    else:
        return GoogleTTS()
