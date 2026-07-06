import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from pipeline.orchestrator import AdForgeOrchestrator

def test_orchestrator_pipeline_flow(mock_clips_data, tmp_path):
    # Instantiate orchestrator using tmp_path
    base_dir = str(tmp_path)
    orchestrator = AdForgeOrchestrator(base_dir)
    
    # Mock internal sub-components
    orchestrator.analyzer.analyze_clip = MagicMock(side_effect=lambda p: {
        "path": p,
        "filename": Path(p).name,
        "metadata": {"duration": 10.0, "width": 1920, "height": 1080},
        "analysis": {"best_segment": {"start": 2.0, "end": 6.5}, "description": "Offline scene"}
    })
    
    orchestrator.selector.create_timeline = MagicMock(return_value=[
        {"path": "clip1.mp4", "filename": "clip1.mp4", "start": 2.0, "end": 6.5, "caption_text": "Scene 1"}
    ])
    
    orchestrator.scriptwriter.write_script = MagicMock(return_value={
        "title": "Mock Ad",
        "voiceover_paragraphs": ["This is scene one."],
        "overlay_titles": ["Scene 1"],
        "cta_text": "Buy Now",
        "music_mood": "upbeat corporate"
    })
    
    orchestrator.narrator.generate_speech = MagicMock(return_value=f"{base_dir}/workspace/audio/scene_0.mp3")
    orchestrator.narrator.generate_aligned_voiceover = MagicMock(return_value=f"{base_dir}/workspace/audio/final_narration.mp3")
    orchestrator.narrator.get_audio_duration = MagicMock(return_value=4.5)
    
    orchestrator.music.search_and_download = MagicMock(return_value=f"{base_dir}/workspace/audio/music.mp3")
    
    orchestrator.grader.grade_and_crop = MagicMock(return_value=f"{base_dir}/workspace/graded/scene_0_graded.mp4")
    orchestrator.editor.trim_clip = MagicMock(return_value=f"{base_dir}/workspace/editor/scene_0_trimmed.mp4")
    orchestrator.editor.stitch_clips = MagicMock(return_value=f"{base_dir}/workspace/assembled_raw.mp4")
    
    orchestrator.renderer.render_remotion_overlays = MagicMock(return_value=f"{base_dir}/workspace/overlays_raw.mp4")
    orchestrator.renderer.merge_overlays = MagicMock(return_value=f"{base_dir}/workspace/video_with_overlays.mp4")
    
    orchestrator.mixer.mix_audio = MagicMock(return_value=f"{base_dir}/output/test_project.mp4")
    
    # Execute the mock pipeline
    with patch("pathlib.Path.iterdir") as mock_iterdir:
        mock_file = MagicMock()
        mock_file.is_file.return_value = True
        mock_file.suffix = ".mp4"
        mock_file.__str__.return_value = f"{base_dir}/clip1.mp4"
        mock_iterdir.return_value = [mock_file]
        
        output_path = orchestrator.run(
            clips_dir=base_dir,
            brief="Test brief",
            duration=15.0,
            lut_name="cinematic",
            project_name="test_project"
        )
    
    # Assertions to ensure every stage of the pipeline was triggered
    import os
    assert os.path.normpath(output_path) == os.path.normpath(f"{base_dir}/output/test_project.mp4")
    orchestrator.analyzer.analyze_clip.assert_called_once()
    orchestrator.selector.create_timeline.assert_called_once()
    orchestrator.scriptwriter.write_script.assert_called_once()
    orchestrator.narrator.generate_aligned_voiceover.assert_called_once()
    orchestrator.music.search_and_download.assert_called_once()
    orchestrator.grader.grade_and_crop.assert_called_once()
    orchestrator.editor.trim_clip.assert_called_once()
    orchestrator.editor.stitch_clips.assert_called_once()
    orchestrator.renderer.render_remotion_overlays.assert_called_once()
    orchestrator.renderer.merge_overlays.assert_called_once()
    orchestrator.mixer.mix_audio.assert_called_once()


def test_orchestrator_pipeline_bypass_flow(tmp_path):
    base_dir = str(tmp_path)
    orchestrator = AdForgeOrchestrator(base_dir)

    # Set up mocks for steps starting at Step 5
    orchestrator.analyzer.analyze_clip = MagicMock()
    orchestrator.selector.create_timeline = MagicMock()
    orchestrator.scriptwriter.write_script = MagicMock()

    orchestrator.narrator.generate_aligned_voiceover = MagicMock(return_value=f"{base_dir}/workspace/audio/final_narration.mp3")
    orchestrator.music.search_and_download = MagicMock(return_value=f"{base_dir}/workspace/audio/music.mp3")
    orchestrator.grader.grade_and_crop = MagicMock(return_value=f"{base_dir}/workspace/graded/scene_0_graded.mp4")
    orchestrator.editor.trim_clip = MagicMock(return_value=f"{base_dir}/workspace/editor/scene_0_trimmed.mp4")
    orchestrator.editor.stitch_clips = MagicMock(return_value=f"{base_dir}/workspace/assembled_raw.mp4")
    orchestrator.renderer.render_remotion_overlays = MagicMock(return_value=f"{base_dir}/workspace/overlays_raw.mp4")
    orchestrator.renderer.merge_overlays = MagicMock(return_value=f"{base_dir}/workspace/video_with_overlays.mp4")
    orchestrator.mixer.mix_audio = MagicMock(return_value=f"{base_dir}/output/test_project_bypass.mp4")

    draft_script = {
        "title": "Bypass Ad",
        "voiceover_paragraphs": ["Edited speech paragraph."],
        "overlay_titles": ["Edited Subtitle"],
        "cta_text": "Join Now",
        "music_mood": "cyberpunk synth"
    }

    draft_timeline = [
        {"path": "clip1.mp4", "filename": "clip1.mp4", "start": 1.0, "end": 4.0, "caption_text": "Edited Subtitle"}
    ]

    output_path = orchestrator.run(
        clips_dir=base_dir,
        brief="Test brief",
        duration=10.0,
        lut_name="cool_tech",
        project_name="test_project_bypass",
        draft_script=draft_script,
        draft_timeline=draft_timeline,
        theme="cyberpunk"
    )

    import os
    assert os.path.normpath(output_path) == os.path.normpath(f"{base_dir}/output/test_project_bypass.mp4")
    
    # Analyzer/Selector/Scriptwriter should NEVER have been called!
    orchestrator.analyzer.analyze_clip.assert_not_called()
    orchestrator.selector.create_timeline.assert_not_called()
    orchestrator.scriptwriter.write_script.assert_not_called()

    # Audio synthesis and overlays rendering SHOULD have been called with parameters!
    orchestrator.narrator.generate_aligned_voiceover.assert_called_once()
    
    orchestrator.renderer.render_remotion_overlays.assert_called_once()
    args, kwargs = orchestrator.renderer.render_remotion_overlays.call_args
    assert os.path.normpath(kwargs["video_path"]) == os.path.normpath(f"{base_dir}/workspace/assembled_raw.mp4")
    assert kwargs["title"] == "Bypass Ad"
    assert kwargs["scene_titles"] == ["Edited Subtitle"]
    assert kwargs["scene_durations"] == [3.0]
    assert kwargs["cta_text"] == "Join Now"
    assert kwargs["duration_sec"] == 10.0
    assert kwargs["theme"] == "cyberpunk"


def test_orchestrator_pipeline_advanced_parameters(tmp_path):
    base_dir = str(tmp_path)
    orchestrator = AdForgeOrchestrator(base_dir)

    # Set up mocks for steps
    orchestrator.analyzer.analyze_clip = MagicMock()
    orchestrator.selector.create_timeline = MagicMock()
    orchestrator.scriptwriter.write_script = MagicMock()

    orchestrator.narrator.generate_aligned_voiceover = MagicMock(return_value=f"{base_dir}/workspace/audio/final_narration.mp3")
    orchestrator.music.search_and_download = MagicMock(return_value=f"{base_dir}/workspace/audio/music.mp3")
    orchestrator.grader.grade_and_crop = MagicMock(return_value=f"{base_dir}/workspace/graded/scene_0_graded.mp4")
    orchestrator.editor.trim_clip = MagicMock(return_value=f"{base_dir}/workspace/editor/scene_0_trimmed.mp4")
    orchestrator.editor.stitch_clips = MagicMock(return_value=f"{base_dir}/workspace/assembled_raw.mp4")
    orchestrator.renderer.render_remotion_overlays = MagicMock(return_value=f"{base_dir}/workspace/overlays_raw.mp4")
    orchestrator.renderer.merge_overlays = MagicMock(return_value=f"{base_dir}/workspace/video_with_overlays.mp4")
    orchestrator.mixer.mix_audio = MagicMock(return_value=f"{base_dir}/output/test_advanced.mp4")

    # Create dummy custom music file
    audio_dir = Path(base_dir) / "workspace" / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    custom_music = audio_dir / "custom_music.mp3"
    custom_music.write_text("dummy mp3 content")

    draft_script = {
        "title": "Advanced Ad",
        "voiceover_paragraphs": ["Advanced speech."],
        "overlay_titles": ["Advanced Subtitle"],
        "cta_text": "Buy",
        "music_mood": "chill lofi"
    }

    draft_timeline = [
        {"path": "clip1.mp4", "filename": "clip1.mp4", "start": 0.0, "end": 5.0, "caption_text": "Advanced Subtitle"}
    ]

    output_path = orchestrator.run(
        clips_dir=base_dir,
        brief="Test brief",
        duration=5.0,
        lut_name="cinematic",
        project_name="test_advanced",
        draft_script=draft_script,
        draft_timeline=draft_timeline,
        theme="bold",
        transition="glitch",
        music_volume=0.12,
        narration_volume=1.5,
        fade_duration=3.0,
        aspect_ratio="1:1",
        primary_color="#FFA500",
        accent_color="#FF00FF",
        font_family="Georgia"
    )

    import os
    assert os.path.normpath(output_path) == os.path.normpath(f"{base_dir}/output/test_advanced.mp4")

    # Verify transition and styling parameters were passed to Remotion renderer
    orchestrator.renderer.render_remotion_overlays.assert_called_once()
    _, r_kwargs = orchestrator.renderer.render_remotion_overlays.call_args
    assert r_kwargs["transition"] == "glitch"
    assert r_kwargs["theme"] == "bold"
    assert r_kwargs["aspect_ratio"] == "1:1"
    assert r_kwargs["primary_color"] == "#FFA500"
    assert r_kwargs["accent_color"] == "#FF00FF"
    assert r_kwargs["font_family"] == "Georgia"

    # Verify aspect_ratio was passed to colorgrader
    orchestrator.grader.grade_and_crop.assert_called_once()
    _, c_kwargs = orchestrator.grader.grade_and_crop.call_args
    assert c_kwargs["aspect_ratio"] == "1:1"

    # Verify custom music is detected and copied, and search/download is NOT called
    orchestrator.music.search_and_download.assert_not_called()
    assert (audio_dir / "background_music.mp3").exists()

    # Verify custom volume/fade parameters are passed to mixer
    orchestrator.mixer.mix_audio.assert_called_once()
    _, m_kwargs = orchestrator.mixer.mix_audio.call_args
    assert m_kwargs["music_volume"] == 0.12
    assert m_kwargs["narration_volume"] == 1.5
    assert m_kwargs["fade_duration"] == 3.0

