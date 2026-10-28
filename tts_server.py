import io
import os
import re
import asyncio
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, JSONResponse
from pydantic import BaseModel

app = FastAPI(title="Mongolian AI Voice Server (Edge Neural & MMS)", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Available voices
VOICES = [
    {
        "id": "mn-MN-YesuiNeural",
        "name": "Есүй",
        "gender": "female",
        "engine": "edge-neural",
        "description": "Эелдэг, уян зөөлөн, байгалийн өнгө аяс",
        "tag": "Үндсэн • Эмэгтэй",
    },
    {
        "id": "mn-MN-BataaNeural",
        "name": "Батаа",
        "gender": "male",
        "engine": "edge-neural",
        "description": "Цэвэр тод, өөртөө итгэлтэй, баргил",
        "tag": "Эрэгтэй",
    },
    {
        "id": "facebook/mms-tts-khk",
        "name": "MMS Халх",
        "gender": "neutral",
        "engine": "mms-vits",
        "description": "Meta офлайн VITS модел",
        "tag": "Офлайн VITS",
    },
]

# Check if edge-tts is available
try:
    import edge_tts
    HAS_EDGE_TTS = True
    print("[+] Edge-TTS engine is ready (YesuiNeural & BataaNeural)")
except ImportError:
    HAS_EDGE_TTS = False
    print("[-] edge-tts not installed")

# Check if torch and transformers are available for optional MMS-TTS
mms_tokenizer = None
mms_model = None
try:
    import torch
    from scipy.io import wavfile
    from transformers import AutoTokenizer, VitsModel
    import numpy as np

    mms_model_id = "facebook/mms-tts-khk"
    print(f"[*] Attempting to load MMS model ({mms_model_id})...")
    mms_tokenizer = AutoTokenizer.from_pretrained(mms_model_id)
    mms_model = VitsModel.from_pretrained(mms_model_id)
    mms_model.eval()
    print("[+] MMS-TTS model loaded successfully!")
except Exception as e:
    print(f"[*] MMS-TTS torch engine skipped (using high-speed Edge Neural): {e}")


class TTSRequest(BaseModel):
    text: str
    voice: Optional[str] = "mn-MN-YesuiNeural"
    speed: Optional[float] = 1.0
    pitch: Optional[float] = 1.0


@app.get("/")
def index():
    return {
        "service": "Mongolian AI Voice Engine",
        "engines": {
            "edge_neural": HAS_EDGE_TTS,
            "mms_vits": mms_model is not None,
        },
        "voices": VOICES,
        "status": "ready",
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "has_edge": HAS_EDGE_TTS,
        "has_mms": mms_model is not None,
    }


@app.get("/voices")
def get_voices():
    return VOICES


@app.post("/tts")
async def tts(req: TTSRequest):
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text is empty")

    voice_id = req.voice or "mn-MN-YesuiNeural"

    # 1. MMS-TTS offline fallback if requested specifically
    if voice_id == "facebook/mms-tts-khk" and mms_model is not None and mms_tokenizer is not None:
        try:
            clean_text = text.lower()
            inputs = mms_tokenizer(clean_text, return_tensors="pt")
            with torch.no_grad():
                waveform = mms_model(**inputs).waveform[0].cpu().numpy()

            pcm = (np.clip(waveform, -1.0, 1.0) * 32767).astype(np.int16)
            buf = io.BytesIO()
            wavfile.write(buf, mms_model.config.sampling_rate, pcm)
            return Response(
                content=buf.getvalue(),
                media_type="audio/wav",
                headers={"Content-Disposition": 'inline; filename="mms-speech.wav"'},
            )
        except Exception as e:
            print("MMS error, falling back to Edge:", e)

    # 2. Edge-TTS (Default: YesuiNeural or BataaNeural)
    if HAS_EDGE_TTS:
        selected_voice = "mn-MN-YesuiNeural"
        if "bataa" in voice_id.lower() or "male" in voice_id.lower():
            selected_voice = "mn-MN-BataaNeural"

        # Format rate and pitch for edge-tts (e.g. +10%, -5%)
        rate_percent = int((req.speed - 1.0) * 100) if req.speed else 0
        rate_str = f"{rate_percent:+d}%"

        pitch_percent = int((req.pitch - 1.0) * 50) if req.pitch else 0
        pitch_str = f"{pitch_percent:+d}Hz"

        try:
            communicate = edge_tts.Communicate(
                text=text,
                voice=selected_voice,
                rate=rate_str,
                pitch=pitch_str,
            )
            audio_data = bytearray()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data.extend(chunk["data"])

            if not audio_data:
                raise HTTPException(status_code=500, detail="Empty audio generated")

            return Response(
                content=bytes(audio_data),
                media_type="audio/mpeg",
                headers={
                    "Content-Disposition": f'inline; filename="{selected_voice}.mp3"',
                    "X-TTS-Voice": selected_voice,
                },
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Edge-TTS synthesis error: {str(e)}")

    raise HTTPException(status_code=503, detail="No TTS engine available")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("tts_server:app", host="0.0.0.0", port=8000, reload=True)
