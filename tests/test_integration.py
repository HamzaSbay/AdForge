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
