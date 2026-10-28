#!/usr/bin/env bash
set -e

# 1. Start VoiceStudio + Trilingual STT/TTS FastAPI Backend on 127.0.0.1:8000
python3 -m uvicorn tts_server:app --host 127.0.0.1 --port 8000 &

# 2. Start Next.js Production Web Server on $PORT (default 3000)
export PORT="${PORT:-3000}"
npm run start -- -p "$PORT"
