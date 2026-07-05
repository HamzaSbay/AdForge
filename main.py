import argparse
import sys
import os
from pipeline.orchestrator import AdForgeOrchestrator

def main():
    parser = argparse.ArgumentParser(description="AdForge: Custom Local Ad Video Generator")
    parser.add_argument("--clips", required=True, help="Directory containing raw video clips")
    parser.add_argument("--brief", required=True, help="Ad Brief or description of the ad concept")
    parser.add_argument("--duration", type=float, default=60.0, help="Target duration in seconds (default 60s)")
    parser.add_argument("--lut", default="cinematic", help="Lut name for color grading (default 'cinematic')")
    parser.add_argument("--name", default="adforge_ad", help="Project name (output filename)")
    
    args = parser.parse_args()
    
    # Verify clips directory
    if not os.path.isdir(args.clips):
        print(f"Error: {args.clips} is not a valid directory.")
        sys.exit(1)
        
    # Check Google API key
    if not os.environ.get("GOOGLE_API_KEY") and not os.environ.get("GEMINI_API_KEY"):
        print("Warning: GOOGLE_API_KEY or GEMINI_API_KEY not found in env.")
        print("AdForge will run in fallback offline mode (no AI, template scripts).")
        
    try:
        orchestrator = AdForgeOrchestrator(os.path.dirname(os.path.abspath(__file__)))
        output_file = orchestrator.run(
            clips_dir=args.clips,
            brief=args.brief,
            duration=args.duration,
            lut_name=args.lut,
            project_name=args.name
        )
        print(f"\nSuccess! Your ad video is ready at: {output_file}")
    except Exception as e:
        print(f"\nError running pipeline: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
