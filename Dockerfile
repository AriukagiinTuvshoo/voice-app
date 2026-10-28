FROM node:20-bookworm-slim

# Install Python 3, ffmpeg, and audio libraries for VoiceStudio DSP + Trilingual STT/TTS
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    ffmpeg \
    libsndfile1 \
    flac \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies directly
RUN pip3 install --no-cache-dir --break-system-packages \
    fastapi uvicorn edge-tts numpy scipy soundfile SpeechRecognition pydantic python-multipart miniaudio

# Install Node.js dependencies
COPY package*.json ./
RUN npm install

# Copy application code
COPY . .

# Build Next.js application
RUN npm run build
RUN chmod +x start-cloud.sh

EXPOSE 3000 10000
ENV NODE_ENV=production
ENV HOSTNAME=0.0.0.0
ENV LOCAL_PY_URL=http://127.0.0.1:8000
ENV LOCAL_TTS_URL=http://127.0.0.1:8000/tts
ENV LOCAL_TTS_HEALTH=http://127.0.0.1:8000/health
ENV LOCAL_STT_URL=http://127.0.0.1:8000/transcribe

CMD ["./start-cloud.sh"]
