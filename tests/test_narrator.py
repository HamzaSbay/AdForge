import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from pipeline.narrator import AdNarrator
from pipeline.tts import get_tts_provider, EdgeTTSBackend, LocalTTS, GoogleTTS

def test_narrator_google_redirects_to_edge_when_no_key():
    narrator = AdNarrator("workspace/remotion")
    
    with patch.dict("os.environ", {}, clear=True), \
         patch("pipeline.tts.EdgeTTSBackend.generate_speech", return_value="dummy_path") as mock_edge_gen:
         
        out_path = "workspace/remotion/test_speech.mp3"
        narrator.generate_speech("Hello Google redirect", out_path, provider_name="google")
        
        # Verify it redirected and called EdgeTTSBackend since GOOGLE_API_KEY is empty
        mock_edge_gen.assert_called_once_with("Hello Google redirect", out_path, voice_name=None)

def test_narrator_edge_tts():
    backend = EdgeTTSBackend()
    
    with patch("edge_tts.Communicate") as mock_comm_cls:
        mock_comm = MagicMock()
        mock_comm_cls.return_value = mock_comm
        
        async def mock_save(path):
            pass
        mock_comm.save.side_effect = mock_save
        
        out_path = "workspace/remotion/test_edge.mp3"
        backend.generate_speech("Hello Edge", out_path)
        
        mock_comm_cls.assert_called_once_with("Hello Edge", "en-US-GuyNeural")
        mock_comm.save.assert_called_once_with(out_path)

def test_narrator_offline_fallback():
    narrator = AdNarrator("workspace/remotion")
    
    # We patch pythoncom, pyttsx3, and subprocess to simulate offline run without side effects
    with patch.dict("os.environ", {}, clear=True), \
         patch("pythoncom.CoInitialize", return_value=None), \
         patch("pyttsx3.init") as mock_pyttsx3_init, \
         patch("subprocess.run") as mock_sub_run:
         
        # Set up pyttsx3 engine mocks
        mock_engine = MagicMock()
        mock_pyttsx3_init.return_value = mock_engine
        
        def mock_wav_write(*args, **kwargs):
            Path("workspace/remotion/test_speech.wav").touch()
            
        mock_engine.runAndWait.side_effect = mock_wav_write
        
        # Synthesize speech using local provider directly
        out_path = "workspace/remotion/test_speech.mp3"
        narrator.generate_speech("Hello offline world", out_path, provider_name="local")
        
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
