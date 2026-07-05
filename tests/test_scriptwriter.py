import pytest
from unittest.mock import patch
from pipeline.scriptwriter import ScriptWriter

def test_scriptwriter_offline_brand_and_theme():
    writer = ScriptWriter()
    
    dummy_timeline = [
        {"filename": "scene1.mp4", "start": 1.0, "end": 5.0},
        {"filename": "scene2.mp4", "start": 0.0, "end": 4.5},
        {"filename": "scene3.mp4", "start": 2.0, "end": 6.0}
    ]
    
    with patch("pipeline.scriptwriter.api_key", None):
        # Test baking theme detection and brand name capitalization extraction
        script = writer.write_script(
            timeline=dummy_timeline,
            brief="Make a sweet video for HappyKids brand cookies.",
            target_duration=12.5
        )
        
        # Verify brand name detected was "HappyKids"
        assert "HappyKids" in script["title"]
        assert any("HappyKids" in para for para in script["voiceover_paragraphs"])
        
        # Verify correct number of voiceover paragraphs and overlay titles match the timeline length (3)
        assert len(script["voiceover_paragraphs"]) == 3
        assert len(script["overlay_titles"]) == 3
        assert script["music_mood"] == "upbeat acoustic"
        
        # Test technology theme
        script_tech = writer.write_script(
            timeline=dummy_timeline,
            brief="A video showing off our new fast tech SaaS App builder.",
            target_duration=12.5
        )
        assert "SaaS" in script_tech["title"] or "App" in script_tech["title"] or "AdForge" in script_tech["title"]
        assert script_tech["music_mood"] == "upbeat corporate"
