import pytest
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

@pytest.fixture
def mock_clips_data():
    return [
        {
            "filename": "clip1.mp4",
            "path": "workspace/uploads/clip1.mp4",
            "metadata": {"duration": 10.0, "width": 1920, "height": 1080},
            "analysis": {
                "description": "A sunny scene.",
                "visual_score": 8,
                "energy_score": 7,
                "suitability_score": 8,
                "best_segment": {"start": 2.0, "end": 6.5},
                "labels": ["sunny", "outdoor"]
            }
        },
        {
            "filename": "clip2.mp4",
            "path": "workspace/uploads/clip2.mp4",
            "metadata": {"duration": 8.0, "width": 1080, "height": 1920},
            "analysis": {
                "description": "A vertical portrait scene.",
                "visual_score": 7,
                "energy_score": 5,
                "suitability_score": 7,
                "best_segment": {"start": 1.0, "end": 5.0},
                "labels": ["portrait", "close-up"]
            }
        }
    ]
