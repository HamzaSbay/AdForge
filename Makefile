# Makefile for AdForge

.PHONY: install run test lint clean help

help:
	@echo "AdForge Development Commands:"
	@echo "  make install  - Set up virtual environment and install packages"
	@echo "  make run      - Run the FastAPI local server"
	@echo "  make test     - Run automated tests using pytest"
	@echo "  make lint     - Format Python files with black and check style"
	@echo "  make clean    - Clean workspace cache and intermediate renders"

install:
	python -m venv .venv
	.venv/Scripts/pip install -r requirements.txt
	.venv/Scripts/pip install pytest black flake8

run:
	.venv/Scripts/python -m uvicorn app:app --reload --host 127.0.0.1 --port 8000

test:
	.venv/Scripts/pytest tests/ -v

lint:
	.venv/Scripts/black pipeline/ app.py main.py
	.venv/Scripts/flake8 pipeline/ app.py main.py --max-line-length=120 --ignore=E203,W503

clean:
	rm -rf workspace/thumbs/ workspace/graded/ workspace/editor/ workspace/remotion/ workspace/audio/
	rm -rf __pycache__ pipeline/__pycache__
	find . -type d -name "__pycache__" -exec rm -r {} + 2>/dev/null || true
