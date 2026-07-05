import pytest
from unittest.mock import MagicMock, patch
from pipeline.analyzer import ClipAnalyzer

def test_analyzer_fallback_behavior():
    # Instantiate analyzer
    analyzer = ClipAnalyzer("workspace/remotion")
    
    # Mock get_video_metadata and extract_thumbnails
    analyzer.get_video_metadata = MagicMock(return_value={"duration": 10.0, "width": 1920, "height": 1080})
    analyzer.extract_thumbnails = MagicMock(return_value=[])
    
    # Trigger clip analysis with empty API key to force fallback behavior
    with patch("pipeline.analyzer.api_key", None):
        result = analyzer.analyze_clip("dummy_clip.mp4")
        
        assert "analysis" in result
        analysis = result["analysis"]
        assert analysis["visual_score"] == 8
        assert analysis["energy_score"] == 7
        assert analysis["suitability_score"] == 8
        assert analysis["best_segment"]["start"] == 2.0
        assert analysis["best_segment"]["end"] == 6.5
        assert "Local offline analysis" in analysis["description"]
