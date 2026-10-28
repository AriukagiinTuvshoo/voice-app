import io
import re
import numpy as np
import torch
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, JSONResponse
from pydantic import BaseModel
from scipy.io import wavfile
from transformers import AutoTokenizer, VitsModel

MODEL_ID = "facebook/mms-tts-khk"  # Khalkha Mongolian MMS VITS model

print(f"[*] Loading MMS-TTS model ({MODEL_ID})...")
try:
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    model = VitsModel.from_pretrained(MODEL_ID)
    model.eval()
    print("[+] Model loaded successfully!")
except Exception as e:
    print(f"[-] Error loading model: {e}")
    tokenizer = None
    model = None

app = FastAPI(title="Mongolian MMS-TTS Server", version="1.0.0")

# Enable CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TTSRequest(BaseModel):
    text: str


# Basic number to Mongolian words converter to help MMS model pronounce numbers properly
NUMBERS_MN = {
    "0": "тэг",
    "1": "нэг",
    "2": "хоёр",
    "3": "гурав",
    "4": "дөрөв",
    "5": "тав",
    "6": "зургаа",
    "7": "долоо",
    "8": "найм",
    "9": "ес",
    "10": "арав",
    "20": "хорь",
    "30": "гуч",
    "40": "дөч",
    "50": "тавь",
    "60": "жар",
    "70": "дал",
    "80": "ная",
    "90": "ер",
    "100": "зуу",
    "1000": "мянга",
}


def normalize_mongolian_text(text: str) -> str:
    """Preprocess text for MMS-TTS: lowercase, convert digits to words, clean whitespace."""
    t = text.strip().lower()

    # Simple digit replacement for 0-9
    for digit, word in NUMBERS_MN.items():
        if len(digit) == 1:
            t = re.sub(rf"\b{digit}\b", f" {word} ", t)

    # Clean redundant punctuation and whitespace
    t = re.sub(r"\s+", " ", t).strip()
    return t


@app.get("/")
def index():
    return {
        "service": "Mongolian MMS-TTS Local Engine",
        "model": MODEL_ID,
        "status": "ready" if model is not None else "model_not_loaded",
    }


@app.get("/health")
def health():
    if model is None or tokenizer is None:
        return JSONResponse(
            status_code=503,
            content={"status": "loading_or_failed", "model": MODEL_ID},
        )
    return {"status": "ok", "model": MODEL_ID}


@app.post("/tts")
def tts(req: TTSRequest):
    if model is None or tokenizer is None:
        raise HTTPException(
            status_code=503,
            detail="Model is not loaded. Please verify internet connection on first run or check disk space.",
        )

    text = normalize_mongolian_text(req.text)
    if not text:
        raise HTTPException(status_code=400, detail="Text is empty")

    try:
        inputs = tokenizer(text, return_tensors="pt")
        with torch.no_grad():
            waveform = model(**inputs).waveform[0].cpu().numpy()

        pcm = (np.clip(waveform, -1.0, 1.0) * 32767).astype(np.int16)
        buf = io.BytesIO()
        wavfile.write(buf, model.config.sampling_rate, pcm)

        return Response(
            content=buf.getvalue(),
            media_type="audio/wav",
            headers={
                "Content-Disposition": 'inline; filename="speech.wav"',
                "X-TTS-Model": MODEL_ID,
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS synthesis error: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("tts_server:app", host="0.0.0.0", port=8000, reload=True)
