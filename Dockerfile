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

# Install Python dependencies
COPY requirements*.txt ./
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

# Install Node.js dependencies and build Next.js app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build
RUN chmod +x start-cloud.sh

EXPOSE 3000
ENV NODE_ENV=production
ENV LOCAL_PY_URL=http://127.0.0.1:8000
ENV LOCAL_TTS_URL=http://127.0.0.1:8000/tts
ENV LOCAL_TTS_HEALTH=http://127.0.0.1:8000/health
ENV LOCAL_STT_URL=http://127.0.0.1:8000/transcribe

CMD ["./start-cloud.sh"]
