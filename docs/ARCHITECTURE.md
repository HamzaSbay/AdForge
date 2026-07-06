# AdForge — System Architecture Guide

This document explains the technical architecture, pipeline data flow, and the bridge between the Python backend and the React Remotion compiler.

---

## 🗺️ High-Level System Architecture

AdForge is a decoupled campaign editor. The backend is built using **FastAPI** (Python), while the visual graphics layer is powered by **Remotion** (React/TypeScript). 

```
┌────────────────────────────────────────────────────────┐
│                     FastAPI Web UI                     │
└───────────────────────────┬────────────────────────────┘
                            │ (JSON / SSE Event Stream)
                            ▼
┌────────────────────────────────────────────────────────┐
│                   AdForge Orchestrator                 │
└─────┬──────────────┬──────────────┬──────────────┬─────┘
      │              │              │              │
      ▼              ▼              ▼              ▼
┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐
│ Analyzer  │  │ Selector  │  │Scriptwritr│  │ Narrator  │
└───────────┘  └───────────┘  └───────────┘  └───────────┘
      │              │              │              │
      ▼              ▼              ▼              ▼
┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐
│   Music   │  │ColorGrader│  │  Editor   │  │ Renderer  │
└───────────┘  └───────────┘  └───────────┘  └───────────┘
                                                   │ (remotion_props.json)
                                                   ▼
                                             ┌───────────┐
                                             │ Remotion  │
                                             │ Composer  │
                                             └─────┬─────┘
                                                   │ (overlays_raw.mp4)
                                                   ▼
                                             ┌───────────┐
                                             │Audio Mixer│
                                             └─────┬─────┘
                                                   │
                                                   ▼
                                             [  Final MP4  ]
```

---

## 🔄 Core Pipeline Execution Flow

The `AdForgeOrchestrator` runs an 11-step pipeline inside its `run()` loop:

### 1. Sourcing / Video Scanner
- Checks if the input uploads directory contains video files.
- **Automated B-Roll mode**: If empty, invokes the `AdStockVideoManager` to query portrait stock video clips from **Pexels/Pixabay APIs** or scraper/public URLs and downloads them into the workspace.

### 2. Clip Analysis (`analyzer.py`)
- Extracts metadata (duration, width, height, FPS) using `ffprobe`.
- Grabs 3 evenly-spaced thumbnail frames per clip using FFmpeg.
- Sends frames to **Gemini 1.5 Flash Vision** (or fallback text analyzer) to rate visual scores, motion energy, and generate scene descriptions.

### 3. Timeline Planning (`selector.py`)
- Invokes the active LLM (Gemini, Claude, GPT, or Ollama) to read clip descriptions and select the best 2-6s segments to compile a cohesive ad sequence matching the campaign duration.

### 4. Copywriting (`scriptwriter.py`)
- Generates a timed voiceover script split into scene-specific paragraphs, screen titles (overlay texts), CTA text, and music mood suggestions.

### 5. Narration Synthesis (`narrator.py` & `tts.py`)
- Forwards paragraph text to the pluggable TTS system:
  - **Google Cloud TTS** (REST API)
  - **EdgeTTS** (Free cloud scraper, used if Google key is missing)
  - **pyttsx3** (Local SAPI5 offline engine)
  - **OpenAI TTS** (model `tts-1`)
- Spaces out speech WAV blocks to match timeline scene start times, and mixes them using the FFmpeg `adelay` and `amix` filter complex.

### 6. Music Sourcing (`music.py`)
- Searches Pixabay Music for background music matching the suggested mood, downloading it and applying a fade-out curve. Uses uploaded custom MP3 tracks if provided.

### 7. Crop & Color Grade (`colorgrader.py`)
- Center-crops clips to standard vertical mobile format (`1080x1920` for 9:16 ads).
- Applies a chosen 3D LUT (cinematic, warm product, cool tech) using FFmpeg's `lut3d` filter.

### 8. Trim & Concat (`editor.py`)
- Trims clips to exact second segments and stitches them into `assembled_raw.mp4`.

### 9. Remotion Overlays Compiler (`renderer.py`)
- Passes titles, durations, cta, and custom theme/transition options to Remotion.
- Renders the overlay layers to `overlays_raw.mp4`.

### 10. Audio Mixing & Sidechain Ducking (`mixer.py`)
- Combines conformed video audio, narration, and background tracks.
- Ducks background music under active narration sections.

---

## 🌉 The Python-Remotion Bridge

Python communicates with React Remotion using transient **JSON properties**.

### 1. Properties Generation (`renderer.py`)
`AdRenderer` writes a temporary JSON configuration file `remotion_props.json` containing:
```json
{
  "videoSrc": "assembled_raw.mp4",
  "title": "Unmatched Headset",
  "sceneTitles": ["Wireless Comfort", "Active Noise Canceling", "Shop Now"],
  "sceneDurations": [4.5, 5.0, 4.5],
  "ctaText": "Shop Now",
  "theme": "cyberpunk",
  "transition": "glitch"
}
```

### 2. Compilation Invocation
`renderer.py` runs a sub-process executing `npx remotion render` targeting `src/index.tsx` in `OpenMontage/remotion-composer`:
```bash
npx remotion render src/index.tsx AdForgeOverlay output_file.mp4 --props=remotion_props.json --frames=0-N --public-dir=video_directory
```
- `--props` loads the JSON file and binds it to the component's React props.
- `--public-dir` maps the directory hosting `assembled_raw.mp4` so Remotion's browser engine can reference it securely without CORS blocks.
