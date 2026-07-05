import json
import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

class TimelineSelector:
    def __init__(self):
        self.model = genai.GenerativeModel("gemini-2.5-flash")

    def create_timeline(self, clips_data: list[dict], brief: str, target_duration: float = 60.0) -> list[dict]:
        """Use Gemini to select the best cuts and form a timeline sequence."""
        print("Selecting best cuts and planning timeline...")
        
        # Prepare clips overview for Gemini
        clips_summary = []
        for i, c in enumerate(clips_data):
            clips_summary.append({
                "index": i,
                "filename": c["filename"],
                "path": c["path"],
                "duration": c["metadata"]["duration"],
                "description": c["analysis"].get("description", ""),
                "visual_score": c["analysis"].get("visual_score", 5),
                "energy_score": c["analysis"].get("energy_score", 5),
                "suitability_score": c["analysis"].get("suitability_score", 5),
                "recommended_segment": c["analysis"].get("best_segment", {})
            })

        default_timeline = []
        # Fallback timeline: dynamically cut and loop clips to fill target_duration
        current_time = 0.0
        cycle = 0
        
        # Keep cycling clips to fill the target duration
        while current_time < target_duration and len(clips_summary) > 0:
            for c in clips_summary:
                if current_time >= target_duration:
                    break
                
                orig_dur = c["duration"]
                # Determine scene segment duration (3.5 to 5.0 seconds for good pacing)
                scene_dur = min(4.5, orig_dur)
                if scene_dur < 1.5:
                    continue
                
                # Pick different segments depending on the cycle
                if cycle == 0:
                    start_sec = max(0.0, orig_dur * 0.15)
                elif cycle == 1:
                    start_sec = max(0.0, orig_dur * 0.50)
                else:
                    start_sec = max(0.0, orig_dur * 0.30)
                    
                end_sec = min(orig_dur, start_sec + scene_dur)
                actual_dur = end_sec - start_sec
                if current_time + actual_dur > target_duration:
                    actual_dur = target_duration - current_time
                    end_sec = start_sec + actual_dur
                    
                if actual_dur < 0.5:
                    continue
                    
                default_timeline.append({
                    "path": c["path"],
                    "filename": c["filename"],
                    "start": round(start_sec, 2),
                    "end": round(end_sec, 2),
                    "caption_text": f"Scene {len(default_timeline) + 1}"
                })
                current_time += actual_dur
            
            cycle += 1
            if cycle > 5: # safety break
                break

        if api_key:
            prompt = f"""
            You are a professional video editor creating a commercial ad.
            
            Target Ad Duration: {target_duration} seconds.
            Target Aspect Ratio: 9:16 (vertical mobile video).
            Ad Brief / Concept: "{brief}"
            
            Available video clips:
            {json.dumps(clips_summary, indent=2)}
            
            Tasks:
            1. Select and order clips from the list to construct a cohesive {target_duration}-second video timeline.
            2. Avoid using the exact same segment twice. You can trim clips to fit.
            3. Each scene segment should typically be between 2 to 6 seconds long to maintain dynamic pacing.
            4. Make sure the total duration of the selected segments sums up exactly or very close to {target_duration} seconds (e.g. 58-62 seconds).
            5. For each segment in the timeline, output a JSON object with:
               - "path": The exact absolute path of the clip.
               - "start": The start timestamp in seconds (must be within the clip's duration).
               - "end": The end timestamp in seconds.
               - "caption_text": A short text label/description of what is happening or what text overlay should highlight in this scene.
               
            Return the output in EXACT JSON format as a list of these segment objects.
            Do NOT include markdown wrapping like ```json. Only return the raw JSON array.
            """
            
            try:
                response = self.model.generate_content(prompt)
                text = response.text.strip()
                if text.startswith("```"):
                    text = text.replace("```json", "").replace("```", "").strip()
                
                timeline = json.loads(text)
                if isinstance(timeline, list) and len(timeline) > 0:
                    return timeline
            except Exception as e:
                print(f"Gemini timeline selection failed: {e}. Using fallback.")
                
        return default_timeline
