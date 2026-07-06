import os
import re
import json
import urllib.parse
import urllib.request
import http.cookiejar
from pathlib import Path
from pipeline.llm import LLMManager

class AdStockVideoManager:
    FALLBACK_VIDEOS = [
        "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4",
        "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerEscapes.mp4",
        "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerFun.mp4",
        "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerJoyrides.mp4"
    ]

    def __init__(self, workspace_dir: str, llm_manager: LLMManager = None):
        self.workspace_dir = Path(workspace_dir)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.llm = llm_manager or LLMManager()

    def generate_queries(self, brief: str) -> list[str]:
        """Convert brief into 3 distinct search terms using AI or simple text heuristic."""
        has_api_keys = bool(
            os.getenv("GOOGLE_API_KEY") or 
            os.getenv("OPENAI_API_KEY") or 
            os.getenv("ANTHROPIC_API_KEY") or 
            self.llm.provider == "ollama"
        )

        if has_api_keys:
            prompt = f"""
            You are a professional video editor creating a commercial ad.
            Given this video ad campaign brief: "{brief}"
            Generate a JSON list of exactly 3 short search terms (1-3 words) to search for background stock videos.
            Make them simple, visual, and relevant to the brief.
            Return ONLY a JSON list of strings like ["query1", "query2", "query3"].
            Do NOT include markdown wrapping or code blocks.
            """
            try:
                text = self.llm.generate_text(prompt, json_mode=True)
                if text.startswith("```"):
                    text = text.replace("```json", "").replace("```", "").strip()
                queries = json.loads(text)
                if isinstance(queries, list) and len(queries) > 0:
                    return [q.strip() for q in queries[:3]]
            except Exception as e:
                print(f"AI search queries generation failed: {e}. Using fallback.")

        return self._get_fallback_queries(brief)

    def _get_fallback_queries(self, brief: str) -> list[str]:
        """Offline text fallback to extract keywords."""
        words = [w.strip(".,!?\"'()").lower() for w in brief.split()]
        stop_words = {
            "a", "an", "the", "and", "or", "but", "if", "then", "else", "when", 
            "at", "by", "for", "with", "about", "against", "between", "into", 
            "through", "during", "before", "after", "above", "below", "to", 
            "from", "up", "down", "in", "out", "on", "off", "over", "under", 
            "again", "further", "then", "once", "here", "there", "all", "any", 
            "both", "each", "few", "more", "most", "other", "some", "such", 
            "no", "nor", "not", "only", "own", "same", "so", "than", "too", 
            "very", "can", "will", "just", "should", "now", "campaign", "ad", "video"
        }
        meaningful_words = [w for w in words if w and w not in stop_words and len(w) > 2]
        
        queries = []
        if len(meaningful_words) >= 3:
            queries = [meaningful_words[0], meaningful_words[1], meaningful_words[2]]
        elif len(meaningful_words) > 0:
            queries = [meaningful_words[0]]
            if len(meaningful_words) > 1:
                queries.append(meaningful_words[1])
            queries.append("cinematic")
        else:
            queries = ["cinematic", "lifestyle", "corporate"]
        return queries[:3]

    def search_and_download_broll(self, queries: list[str], output_dir: str) -> list[str]:
        """Download one stock video for each query to output_dir, using Pexels/Pixabay/Scraper/Fallback."""
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        
        downloaded_files = []
        pexels_key = os.getenv("PEXELS_API_KEY")
        pixabay_key = os.getenv("PIXABAY_API_KEY")

        for i, q in enumerate(queries):
            print(f"Sourcing stock video for query: '{q}'...")
            download_url = None
            
            # 1. Pexels API
            if pexels_key:
                print("Trying Pexels API...")
                download_url = self._search_pexels(q, pexels_key)

            # 2. Pixabay API (if Pexels failed/no key)
            if not download_url and pixabay_key:
                print("Trying Pixabay API...")
                download_url = self._search_pixabay(q, pixabay_key)

            # 3. Scrape Pixabay (if APIs failed/no keys)
            if not download_url:
                print("Trying Pixabay Scraping fallback...")
                download_url = self._scrape_pixabay(q)

            # Target path
            filename = f"stock_{i}_{slugify(q)}.mp4"
            target_file = out_path / filename

            # Try downloading if URL found
            success = False
            if download_url:
                print(f"Found stock video URL: {download_url}")
                success = self._download_file(download_url, str(target_file))

            # 4. Final stable URL fallback if all else fails
            if not success:
                fallback_url = self.FALLBACK_VIDEOS[i % len(self.FALLBACK_VIDEOS)]
                print(f"All search paths failed. Using public fallback URL: {fallback_url}")
                success = self._download_file(fallback_url, str(target_file))

            if success:
                downloaded_files.append(str(target_file))

        return downloaded_files

    def _search_pexels(self, query: str, api_key: str) -> str:
        query_esc = urllib.parse.quote(query)
        url = f"https://api.pexels.com/videos/search?query={query_esc}&per_page=3&orientation=portrait"
        req = urllib.request.Request(url)
        req.add_header("Authorization", api_key)
        req.add_header("User-Agent", "AdForge/1.0")
        try:
            with urllib.request.urlopen(req, timeout=15) as res:
                data = json.loads(res.read().decode("utf-8"))
                videos = data.get("videos", [])
                if videos:
                    v = videos[0]
                    v_files = v.get("video_files", [])
                    # Prefer standard mobile portrait resolution
                    for vf in v_files:
                        if vf.get("width") == 1080 and vf.get("height") == 1920:
                            return vf.get("link")
                    if v_files:
                        return v_files[0].get("link")
        except Exception as e:
            print(f"Pexels search failed for '{query}': {e}")
        return None

    def _search_pixabay(self, query: str, api_key: str) -> str:
        query_esc = urllib.parse.quote(query)
        url = f"https://pixabay.com/api/videos/?key={api_key}&q={query_esc}&per_page=3"
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "AdForge/1.0")
        try:
            with urllib.request.urlopen(req, timeout=15) as res:
                data = json.loads(res.read().decode("utf-8"))
                hits = data.get("hits", [])
                if hits:
                    videos = hits[0].get("videos", {})
                    v_info = videos.get("large") or videos.get("medium") or videos.get("small") or videos.get("tiny")
                    if v_info:
                        return v_info.get("url")
        except Exception as e:
            print(f"Pixabay API search failed for '{query}': {e}")
        return None

    def _scrape_pixabay(self, query: str) -> str:
        slug = re.sub(r"\s+", "-", query.strip().lower())
        slug = urllib.parse.quote(slug, safe="-")
        search_url = f"https://pixabay.com/videos/search/{slug}/"
        
        cj = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        
        user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        )
        
        try:
            req = urllib.request.Request(search_url)
            req.add_header("User-Agent", user_agent)
            req.add_header("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")
            
            with opener.open(req, timeout=15) as response:
                html = response.read().decode("utf-8", errors="replace")
                
            mp4_urls = re.findall(r'(https?://cdn\.pixabay\.com/video/[^\s"\'<>]+\.mp4[^\s"\'<>]*)', html)
            if mp4_urls:
                return mp4_urls[0]
                
            preview_urls = re.findall(r'https?://[^\s"\'<>]+_preview\.mp4', html)
            if preview_urls:
                return preview_urls[0]
        except Exception as e:
            print(f"Pixabay scrape failed for '{query}': {e}")
        return None

    def _download_file(self, url: str, target_path: str) -> bool:
        user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        )
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": user_agent}
            )
            with urllib.request.urlopen(req, timeout=40) as res:
                Path(target_path).write_bytes(res.read())
            print(f"Successfully downloaded stock clip to {target_path}")
            return True
        except Exception as e:
            print(f"Failed to download stock clip from {url}: {e}")
            return False

def slugify(s: str) -> str:
    s = re.sub(r"[^\w\s-]", "", s.lower())
    return re.sub(r"[-\s]+", "_", s).strip("_")
