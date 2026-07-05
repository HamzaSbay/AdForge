# Contributing to AdForge

Thank you for your interest in contributing to **AdForge**! We want to build a highly customizable, open-source video ad production pipeline, and we welcome contributions of all shapes and sizes.

---

## 🛠️ Development Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/AdForge.git
   cd AdForge
   ```

2. **Initialize Environment**:
   We recommend using a Python virtual environment. You can use the included `Makefile` to quickly set up your workspace:
   ```bash
   make install
   ```
   *For Windows PowerShell users:*
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\pip install -r requirements.txt
   .\.venv\Scripts\pip install pytest black flake8
   ```

3. **External Dependencies**:
   Ensure you have the following installed on your system PATH:
   - **FFmpeg & FFprobe**: Required for video trimming, cropping, color grading, and audio mixing.
   - **Node.js & npm**: Required to run Remotion components and compile React templates.

---

## 🧪 Testing Guidelines

Before submitting any code changes, please make sure the test suite passes successfully. We use `pytest` for all unit and integration testing.

Run tests:
```bash
make test
```
*For Windows PowerShell users:*
```powershell
.\.venv\Scripts\python.exe -m pytest tests/
```

- **Write Mocked Tests**: If you are adding integrations with external APIs (like new AI models or TTS services), mock the actual requests using `unittest.mock` to ensure tests run fast and hermetically without active keys.

---

## 🎨 Code Style

We enforce standard formatting using `black` and style checks using `flake8`.

Format code:
```bash
make lint
```
*For Windows PowerShell users:*
```powershell
.\.venv\Scripts\black pipeline/ app.py main.py
.\.venv\Scripts\flake8 pipeline/ app.py main.py --max-line-length=120 --ignore=E203,W503
```

---

## 🚀 Pull Request Checklist

1. Create a descriptive feature branch (e.g., `feature/custom-lut-support`).
2. Add comprehensive unit tests covering the new functionality.
3. Verify that all linting and test suites pass locally.
4. Document any new config parameters in `config.yaml` and `.env.example`.
5. Open a Pull Request outlining your changes, rationale, and target milestones.
