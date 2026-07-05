import os
import re
import json
import urllib.parse
import urllib.request
import http.cookiejar
from pathlib import Path

class AdMusicManager:
    _USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )

    _BROWSER_HEADERS = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Upgrade-Insecure-Requests": "1",
    }

    def __init__(self, workspace_dir: str):
        self.workspace_dir = Path(workspace_dir)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

    def _build_opener(self) -> urllib.request.OpenerDirector:
        cj = http.cookiejar.CookieJar()
        return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

    def search_and_download(self, query: str, output_path: str) -> str:
        """Search Pixabay Music for the query and download the first matching track."""
        print(f"Searching Pixabay Music for: '{query}'...")
        slug = re.sub(r"\s+", "-", query.strip().lower())
        slug = urllib.parse.quote(slug, safe="-")
        search_url = f"https://pixabay.com/music/search/{slug}/"

        opener = self._build_opener()

        try:
            # Step 1: Fetch search page HTML
            request = urllib.request.Request(search_url)
            request.add_header("User-Agent", self._USER_AGENT)
            for key, val in self._BROWSER_HEADERS.items():
                request.add_header(key, val)

            with opener.open(request, timeout=30) as response:
                html = response.read().decode("utf-8", errors="replace")

            # Step 2: Try to parse bootstrap tracks
            tracks = []
            bootstrap_match = re.search(r'window\.__BOOTSTRAP_URL__\s*=\s*["\']([^"\']+)["\']', html)
            if bootstrap_match:
                bootstrap_path = bootstrap_match.group(1)
                if bootstrap_path:
                    bootstrap_url = f"https://pixabay.com{bootstrap_path}"
                    req = urllib.request.Request(bootstrap_url)
                    req.add_header("User-Agent", self._USER_AGENT)
                    req.add_header("Accept", "application/json, text/plain, */*")
                    req.add_header("Referer", search_url)
                    
                    try:
                        with opener.open(req, timeout=15) as res:
                            data = json.loads(res.read().decode("utf-8"))
                            results = data.get("page", {}).get("results", [])
                            for item in results:
                                src = item.get("sources", {}).get("src")
                                if src:
                                    tracks.append({
                                        "title": item.get("name") or "Pixabay Track",
                                        "audio_url": src
                                    })
                    except Exception as e:
                        print(f"Error parsing bootstrap JSON: {e}")

            # Step 3: Fallback - regex search MP3 URLs in HTML
            if not tracks:
                mp3_urls = re.findall(r'(https?://cdn\.pixabay\.com/audio/[^\s"\'<>]+\.mp3[^\s"\'<>]*)', html)
                for url in mp3_urls:
                    tracks.append({
                        "title": "Pixabay Track",
                        "audio_url": url
                    })

            if not tracks:
                raise RuntimeError("No tracks found on Pixabay.")

            selected_track = tracks[0]
            audio_url = selected_track["audio_url"]
            if audio_url.startswith("//"):
                audio_url = "https:" + audio_url
            elif audio_url.startswith("/"):
                audio_url = "https://pixabay.com" + audio_url

            # Download
            print(f"Downloading track from {audio_url}...")
            dl_req = urllib.request.Request(
                audio_url,
                headers={
                    "User-Agent": self._USER_AGENT,
                    "Referer": "https://pixabay.com/music/",
                }
            )
            with urllib.request.urlopen(dl_req, timeout=60) as dl_res:
                Path(output_path).write_bytes(dl_res.read())

            print(f"Downloaded music to {output_path}")
            return output_path

        except Exception as e:
            print(f"Pixabay download failed: {e}. Downloading a fallback music track...")
            # Fallback to a stable, free music asset
            fallback_url = "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"
            try:
                urllib.request.urlretrieve(fallback_url, output_path)
                return output_path
            except Exception as fe:
                print(f"Absolute fallback failed: {fe}")
                raise e
