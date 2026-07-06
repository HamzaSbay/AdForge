import os
import json
import shutil
from pathlib import Path
from pipeline.analyzer import ClipAnalyzer
from pipeline.selector import TimelineSelector
from pipeline.scriptwriter import ScriptWriter
from pipeline.narrator import AdNarrator
from pipeline.music import AdMusicManager
from pipeline.colorgrader import ClipColorGrader
from pipeline.editor import AdEditor
from pipeline.mixer import AudioMixer
from pipeline.renderer import AdRenderer
from pipeline.llm import LLMManager
from pipeline.stockvideo import AdStockVideoManager

class AdForgeOrchestrator:
    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self.workspace_dir = self.base_dir / "workspace"
        self.output_dir = self.base_dir / "output"
        
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.analyzer = ClipAnalyzer(str(self.workspace_dir / "thumbs"))
        self.selector = TimelineSelector()
        self.scriptwriter = ScriptWriter()
        self.narrator = AdNarrator(str(self.workspace_dir / "audio"))
        self.music = AdMusicManager(str(self.workspace_dir / "audio"))
        self.grader = ClipColorGrader(str(self.workspace_dir / "graded"))
        self.editor = AdEditor(str(self.workspace_dir / "editor"))
        self.mixer = AudioMixer(str(self.workspace_dir / "mixer"))
        self.renderer = AdRenderer(str(self.workspace_dir / "remotion"))

    def run(self, clips_dir: str, brief: str, duration: float = 60.0, lut_name: str = "cinematic", project_name: str = "adforge_ad", draft_script: dict = None, draft_timeline: list = None, theme: str = "bold", transition: str = "none", llm_provider: str = None, llm_model: str = None, music_volume: float = None, narration_volume: float = None, fade_duration: float = None, tts_provider: str = None, tts_voice: str = None, aspect_ratio: str = "9:16", primary_color: str = None, accent_color: str = None, font_family: str = None) -> str:
        """Run the full video generation pipeline."""
        print(f"=== Starting AdForge Video Production: {project_name} ===")
        
        # Dynamically inject selected LLM parameters if provided
        llm = LLMManager(provider=llm_provider, model=llm_model)
        self.selector.llm = llm
        self.scriptwriter.llm = llm
        
        if draft_script and draft_timeline:
            print("Pre-approved draft script and timeline cuts found. Bypassing AI generator steps.")
            timeline = draft_timeline
            script = draft_script
        else:
            # Step 1: Scan for video clips
            allowed_exts = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
            clips_paths = [
                str(p) for p in Path(clips_dir).iterdir()
                if p.suffix.lower() in allowed_exts and p.is_file()
            ]
            
            if not clips_paths:
                print("No video clips found in uploads. Sourcing stock B-roll clips...")
                stock_manager = AdStockVideoManager(str(self.workspace_dir), llm_manager=llm)
                queries = stock_manager.generate_queries(brief)
                print(f"Generated search queries for stock video: {queries}")
                clips_paths = stock_manager.search_and_download_broll(queries, clips_dir)
                if not clips_paths:
                    raise ValueError(f"No valid video clips found in {clips_dir} and automated B-roll sourcing failed.")
                
            print(f"Found {len(clips_paths)} video clips to analyze.")
            
            # Step 2: Multi-modal clip analysis
            analyzed_clips = []
            for path in clips_paths:
                res = self.analyzer.analyze_clip(path)
                if "error" not in res:
                    analyzed_clips.append(res)
                    
            if not analyzed_clips:
                raise RuntimeError("None of the clips could be successfully analyzed.")
                
            # Save analysis data for debugging
            with open(self.workspace_dir / "analyzed_clips.json", "w") as f:
                json.dump(analyzed_clips, f, indent=2)
                
            # Step 3: AI Timeline cuts planning
            timeline = self.selector.create_timeline(analyzed_clips, brief, target_duration=duration)
            with open(self.workspace_dir / "timeline.json", "w") as f:
                json.dump(timeline, f, indent=2)
                
            # Step 4: AI Script & copy writing
            script = self.scriptwriter.write_script(timeline, brief, target_duration=duration)
            with open(self.workspace_dir / "script.json", "w") as f:
                json.dump(script, f, indent=2)
            
        # Step 5: Narration Voice synthesis
        final_narr_audio = self.narrator.generate_aligned_voiceover(
            paragraphs=script["voiceover_paragraphs"],
            timeline=timeline,
            provider=tts_provider,
            voice=tts_voice
        )
        
        # Step 6: Background music search & download
        music_path = self.workspace_dir / "audio" / "background_music.mp3"
        custom_music_path = self.workspace_dir / "audio" / "custom_music.mp3"
        
        if custom_music_path.exists():
            print("Using custom uploaded background music track.")
            shutil.copy(str(custom_music_path), str(music_path))
            final_music_audio = str(music_path)
        else:
            music_query = script.get("music_mood", "upbeat dynamic corporate")
            final_music_audio = self.music.search_and_download(music_query, str(music_path))
        
        # Step 7 & 8: Grade, crop, trim clip segments
        processed_segments = []
        for i, scene in enumerate(timeline):
            raw_clip = scene["path"]
            graded_path = self.workspace_dir / "graded" / f"scene_{i}_graded.mp4"
            trimmed_path = self.workspace_dir / "editor" / f"scene_{i}_trimmed.mp4"
            
            # Crop + Color grade
            self.grader.grade_and_crop(raw_clip, str(graded_path), lut_name=lut_name, aspect_ratio=aspect_ratio)
            
            # Trim to exact timeframe
            self.editor.trim_clip(str(graded_path), scene["start"], scene["end"], str(trimmed_path))
            processed_segments.append(str(trimmed_path))
            
        # Step 9: Concatenate scenes
        raw_video = self.workspace_dir / "assembled_raw.mp4"
        self.editor.stitch_clips(processed_segments, str(raw_video))
        
        # Step 10: Compile React overlay cards
        scene_titles = [t.get("caption_text", "") for t in timeline]
        if not any(scene_titles):
            scene_titles = script.get("overlay_titles", [])
        scene_durations = [t["end"] - t["start"] for t in timeline]
        overlay_video = self.renderer.render_remotion_overlays(
            video_path=str(raw_video),
            title=script.get("title", "AdForge Ad"),
            scene_titles=scene_titles,
            scene_durations=scene_durations,
            cta_text=script.get("cta_text", "Learn More"),
            duration_sec=duration,
            theme=theme,
            transition=transition,
            aspect_ratio=aspect_ratio,
            primary_color=primary_color,
            accent_color=accent_color,
            font_family=font_family
        )
        
        # Step 11: Overlay Remotion graphics onto video
        video_with_overlays = self.workspace_dir / "video_with_overlays.mp4"
        self.renderer.merge_overlays(str(raw_video), overlay_video, str(video_with_overlays))
        
        # Step 12: Combine and duck voiceover + music
        final_output = self.output_dir / f"{project_name}.mp4"
        self.mixer.mix_audio(
            video_path=str(video_with_overlays),
            narration_path=final_narr_audio,
            music_path=final_music_audio,
            output_path=str(final_output),
            video_duration=duration,
            music_volume=music_volume,
            narration_volume=narration_volume,
            fade_duration=fade_duration,
            timeline=timeline
        )
        
        print(f"=== Video ad created successfully: {final_output} ===")
        
        # Cleanup workspace temp files
        self.cleanup_temp_files()
        
        return str(final_output)

    def cleanup_temp_files(self):
        """Cleanup transient temporary directories to save disk space."""
        print("Cleaning up workspace...")
        # Keep analyzed_clips.json and final output, clear temporary visual stages
        for sub in ["thumbs", "graded", "editor", "remotion"]:
            p = self.workspace_dir / sub
            if p.exists():
                shutil.rmtree(p)
