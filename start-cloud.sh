#!/usr/bin/env bash
set -e

# 1. Start VoiceStudio + Trilingual STT/TTS FastAPI Backend on 127.0.0.1:8000
python3 -m uvicorn tts_server:app --host 127.0.0.1 --port 8000 &

# 2. Wait 2 seconds for Python backend to initialize
sleep 2

# 3. Start Next.js Production Web Server on $PORT (Render sets PORT=10000 by default, binds to 0.0.0.0)
export PORT="${PORT:-3000}"
export HOSTNAME="0.0.0.0"
exec npm run start -- -p "$PORT" -H 0.0.0.0

