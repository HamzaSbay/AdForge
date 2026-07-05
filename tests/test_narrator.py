import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from pipeline.narrator import AdNarrator

def test_narrator_offline_fallback():
    narrator = AdNarrator("workspace/remotion")
    
    # We patch pythoncom, pyttsx3, and subprocess to simulate offline run without side effects
    with patch("pipeline.narrator.api_key", None), \
         patch("pythoncom.CoInitialize", return_value=None), \
         patch("pyttsx3.init") as mock_pyttsx3_init, \
         patch("subprocess.run") as mock_sub_run:
         
        # Set up pyttsx3 engine mocks
        mock_engine = MagicMock()
        mock_pyttsx3_init.return_value = mock_engine
        
        # Mock file write for the WAV conversion
        def mock_wav_write(*args, **kwargs):
            # Create a mock temporary file
            Path("workspace/remotion/test_speech.wav").touch()
            
        mock_engine.runAndWait.side_effect = mock_wav_write
        
        # Synthesize speech
        out_path = "workspace/remotion/test_speech.mp3"
        narrator.generate_speech("Hello offline world", out_path)
        
        # Verify SAPI5/pyttsx3 is initialized and run
        mock_pyttsx3_init.assert_called_once()
        mock_engine.setProperty.assert_called_with('rate', 185)
        mock_engine.save_to_file.assert_called_once()
        mock_engine.runAndWait.assert_called_once()
        
        # Verify FFmpeg conversion command ran
        assert mock_sub_run.call_count >= 1
        cmd = mock_sub_run.call_args[0][0]
        assert "ffmpeg" in cmd
        assert "libmp3lame" in cmd
        
        # Cleanup
        wav_path = Path("workspace/remotion/test_speech.wav")
        if wav_path.exists():
            wav_path.unlink()
