import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from pipeline.stockvideo import AdStockVideoManager

def test_generate_queries_offline_heuristic():
    manager = AdStockVideoManager(workspace_dir="dummy")
    
    with patch.dict("os.environ", {}, clear=True):
        queries = manager.generate_queries("Tech widget app builder.")
        assert len(queries) == 3
        assert any(x in queries for x in ["tech", "widget", "app", "cinematic"])

def test_download_broll_fallback(tmp_path):
    workspace = str(tmp_path)
    manager = AdStockVideoManager(workspace_dir=workspace)

    def mock_download(url, target_path):
        Path(target_path).write_text("mock video")
        return True

    manager._download_file = MagicMock(side_effect=mock_download)
    manager._search_pexels = MagicMock(return_value=None)
    manager._search_pixabay = MagicMock(return_value=None)
    manager._scrape_pixabay = MagicMock(return_value=None)

    with patch.dict("os.environ", {}, clear=True):
        files = manager.search_and_download_broll(["laptop", "coding"], workspace)
        
        assert len(files) == 2
        manager._download_file.assert_any_call(manager.FALLBACK_VIDEOS[0], files[0])
        manager._download_file.assert_any_call(manager.FALLBACK_VIDEOS[1], files[1])
        assert Path(files[0]).exists()
