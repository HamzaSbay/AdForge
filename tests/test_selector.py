import pytest
from unittest.mock import patch
from pipeline.selector import TimelineSelector

def test_selector_fallback_timeline_duration(mock_clips_data):
    selector = TimelineSelector()
    
    with patch.dict("os.environ", {}, clear=True):
        timeline = selector.create_timeline(mock_clips_data, "Make a baking ad", target_duration=15.0)
        
        # Verify it loops and cuts clips correctly to reach target_duration
        assert len(timeline) > 0
        total_duration = sum(t["end"] - t["start"] for t in timeline)
        assert abs(total_duration - 15.0) < 0.5
        
        # Verify segment cuts are offset differently on loops (cycle 0, cycle 1)
        # First cut of clip1 should use start offset ~15%
        assert timeline[0]["start"] == 1.5  # 10.0s * 0.15 = 1.5s
        
        # Second cut of clip1 (index 2) should use start offset ~50%
        if len(timeline) >= 3:
            assert timeline[2]["start"] == 5.0  # 10.0s * 0.50 = 5.0s
