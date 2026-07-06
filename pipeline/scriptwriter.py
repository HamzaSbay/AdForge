import json
import os
from dotenv import load_dotenv
from pipeline.llm import LLMManager

load_dotenv()

class ScriptWriter:
    def __init__(self, llm_manager: LLMManager = None):
        self.llm = llm_manager or LLMManager()

    def write_script(self, timeline: list[dict], brief: str, target_duration: float = 60.0) -> dict:
        """Generate a script for voiceover matched with timeline segments."""
        print("Writing voiceover script...")
        
        # Format timeline for the prompt
        timeline_desc = []
        for i, t in enumerate(timeline):
            dur = t["end"] - t["start"]
            timeline_desc.append({
                "scene_index": i,
                "duration": dur,
                "scene_action": t.get("caption_text", "")
            })

        # Smart offline template scriptwriter
        # Try to extract topic/brand name from brief
        words = brief.split()
        brand_name = "AdForge"
        # Find capitalized words (excluding first word of brief) as brand candidates
        for w in words[1:]:
            clean = "".join(c for c in w if c.isalnum())
            if clean and clean[0].isupper() and clean.lower() not in {"the", "and", "for", "with", "this", "your"}:
                brand_name = clean
                break
        
        # Topic detection
        topic = "quality"
        brief_lower = brief.lower()
        if "cookie" in brief_lower or "food" in brief_lower or "bake" in brief_lower:
            topic = "baking"
        elif "kid" in brief_lower or "child" in brief_lower or "toy" in brief_lower:
            topic = "family"
        elif "tech" in brief_lower or "app" in brief_lower or "software" in brief_lower:
            topic = "technology"
        elif "fitness" in brief_lower or "gym" in brief_lower or "sport" in brief_lower:
            topic = "wellness"

        # Templates per topic
        templates = {
            "baking": {
                "hooks": [f"Welcome to the pure joy of {brand_name}.", f"Taste the love in every single bite of {brand_name}."],
                "mid": [
                    "Crafted with fresh ingredients and secret recipes.",
                    "Carefully mixed, formed, and baked to absolute perfection.",
                    "Warm, sweet, and completely irresistible.",
                    "Bringing happy moments to your kitchen table.",
                    "Made with high quality standards you can taste.",
                    "Delightful flavors designed for children and families alike."
                ],
                "cta": [f"Order your fresh batch of {brand_name} today!", f"Taste the magic of {brand_name} now."]
            },
            "family": {
                "hooks": [f"Discover a world of laughter and play with {brand_name}.", f"Where pure happiness and development meet — {brand_name}."],
                "mid": [
                    "Designed with safety, care, and quality in mind.",
                    "Sparking creativity and smiles every single day.",
                    "Loved by kids, trusted by smart parents everywhere.",
                    "Building beautiful childhood memories that last.",
                    "Made to inspire curiosity and active play.",
                    "Because your child deserves the absolute best."
                ],
                "cta": [f"Bring home the joy of {brand_name} today!", f"Start your child's journey with {brand_name}."]
            },
            "technology": {
                "hooks": [f"Step into the future of productivity with {brand_name}.", f"Meet the tool built to optimize your workflow: {brand_name}."],
                "mid": [
                    "Engineered for speed, efficiency, and robust performance.",
                    "Simplifying complex processes in one click.",
                    "Designed for builders, creators, and innovators.",
                    "Stay ahead of the curve with smart integrations.",
                    "Unlocking raw capabilities you didn't know you had.",
                    "Power and elegance combined in a single suite."
                ],
                "cta": [f"Get started with {brand_name} for free today!", f"Elevate your stack with {brand_name} now."]
            },
            "wellness": {
                "hooks": [f"Reclaim your energy and health with {brand_name}.", f"Your partner in daily wellness and nutrition: {brand_name}."],
                "mid": [
                    "Formulated with natural, organic ingredients.",
                    "Fueling active lifestyles and healthy minds.",
                    "Pure, simple, and honest clean choices.",
                    "Designed to support your body's natural strength.",
                    "Feel better, live better, and thrive daily.",
                    "Because health is the ultimate investment."
                ],
                "cta": [f"Start your wellness habit with {brand_name} today!", f"Try {brand_name} and feel the difference."]
            },
            "quality": {
                "hooks": [f"Introducing the unmatched standard of {brand_name}.", f"Discover the difference premium craftsmanship makes with {brand_name}."],
                "mid": [
                    "Designed with precision and tested to the extreme.",
                    "Crafted using only the finest premium components.",
                    "Engineered to help you build, grow, and succeed.",
                    "Simple, intuitive, and extremely powerful.",
                    "Trusted by thousands of professionals globally.",
                    "Every detail has been optimized for quality."
                ],
                "cta": [f"Experience the power of {brand_name} today!", f"Upgrade your life with {brand_name} now."]
            }
        }

        # Select template deck
        deck = templates.get(topic, templates["quality"])
        
        # Build timeline-matched scripts
        voiceover_paragraphs = []
        overlay_titles = []
        
        # Scene 0 is always Hook
        voiceover_paragraphs.append(deck["hooks"][0])
        overlay_titles.append(f"Meet {brand_name}")
        
        # Middle Scenes
        mid_index = 0
        for i in range(1, len(timeline) - 1):
            para = deck["mid"][mid_index % len(deck["mid"])]
            voiceover_paragraphs.append(para)
            
            # Simple 2-3 word overlay text matching paragraph theme
            words_in_para = para.replace(",", "").replace(".", "").split()
            overlay = " ".join(words_in_para[0:3])
            overlay_titles.append(overlay)
            
            mid_index += 1
            
        # Final Scene is CTA
        voiceover_paragraphs.append(deck["cta"][0])
        overlay_titles.append(deck["cta"][0].split("!")[0].split("now")[0].strip())
        
        # Create default script object
        default_script = {
            "title": f"Ad for {brand_name}",
            "voiceover_paragraphs": voiceover_paragraphs,
            "full_script_text": " ".join(voiceover_paragraphs),
            "overlay_titles": overlay_titles,
            "cta_text": "Learn More",
            "music_mood": "upbeat " + ("acoustic" if topic in {"baking", "family"} else "corporate")
        }

        has_api_keys = bool(os.getenv("GOOGLE_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY") or self.llm.provider == "ollama")
        
        if has_api_keys:
            prompt = f"""
            You are a professional advertising scriptwriter.
            Write a highly engaging voiceover script for a {target_duration}-second commercial ad.
            
            Brief / Concept: "{brief}"
            
            Here is the timeline of the video scenes (total {target_duration}s):
            {json.dumps(timeline_desc, indent=2)}
            
            Tasks:
            1. Write a voiceover script containing narration text split into sections that align with the scenes.
            2. The spoken text must fit nicely within the timeline duration. A good rule of thumb is 2.5 to 3 words per second.
            3. Make it sound professional, punchy, persuasive, and fit for the tone of the brief.
            4. Include a strong opening hook and a clear Call To Action (CTA) at the end.
            5. Output in EXACT JSON format with these keys:
               - "title": A catchy title for the ad.
               - "voiceover_paragraphs": A list of strings, where each string corresponds to the voiceover lines for each scene in the timeline (should have {len(timeline)} elements).
               - "full_script_text": The complete unified text of the voiceover.
               - "music_mood": A 2-3 word description of the music style suited for this ad (e.g. "upbeat electronic corporate", "warm cinematic piano", "lofi chill hiphop").
               - "overlay_titles": A list of short texts (maximum 4 words) to display as big text overlays on screen for each scene (should have {len(timeline)} elements).
               - "cta_text": Call to action text for the end card (e.g. "Visit our website", "Sign up now").
               
            Do NOT include markdown wrapping like ```json. Only return the raw JSON.
            """
            
            try:
                text = self.llm.generate_text(prompt, json_mode=True)
                if text.startswith("```"):
                    text = text.replace("```json", "").replace("```", "").strip()
                
                script_data = json.loads(text)
                # Ensure sizes match timeline to avoid index out of bound errors
                if len(script_data.get("voiceover_paragraphs", [])) == len(timeline):
                    return script_data
            except Exception as e:
                print(f"AI scriptwriting failed: {e}. Using fallback.")
                
        return default_script
