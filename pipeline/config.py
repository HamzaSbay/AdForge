import os
from pathlib import Path
import yaml

DEFAULT_CONFIG = {
    "video": {
        "target_width": 1080,
        "target_height": 1920,
        "fps": 30,
        "codec": "libx264",
        "pix_fmt": "yuv420p",
        "audio_codec": "aac",
        "audio_sample_rate": 44100,
        "audio_channels": 2,
        "sharpen_filter": "unsharp=3:3:0.5:3:3:0.5",
        "default_aspect_ratio": "9:16"
    },
    "audio": {
        "video_volume": 0.08,
        "narration_volume": 1.15,
        "music_volume": 0.08,
        "music_fade_out_duration": 2.0
    },
    "tts": {
        "default_voice": "en-US-Journey-D",
        "speaking_rate": 1.0,
        "pitch": 0.0,
        "local_fallback_rate": 185
    },
    "ui": {
        "host": "127.0.0.1",
        "port": 8000,
        "title": "AdForge Studio"
    }
}

class AdForgeConfig:
    def __init__(self):
        self.config = DEFAULT_CONFIG.copy()
        
        # Load from config.yaml if it exists
        config_path = Path(__file__).parent.parent / "config.yaml"
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    user_config = yaml.safe_load(f)
                    if user_config and isinstance(user_config, dict):
                        # Merge dictionaries carefully
                        for section, keys in user_config.items():
                            if section in self.config and isinstance(keys, dict):
                                self.config[section].update(keys)
            except Exception as e:
                print(f"Warning: Failed to load config.yaml ({e}). Using default settings.")

    def get(self, section: str, key: str, fallback=None):
        return self.config.get(section, {}).get(key, fallback)

# Global configuration instance
settings = AdForgeConfig()
