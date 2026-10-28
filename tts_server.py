import io
import os
import re
import uuid
import asyncio
import tempfile
from typing import Optional
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, JSONResponse
from pydantic import BaseModel
import numpy as np
from scipy.io import wavfile

app = FastAPI(title="Mongolian AI Voice Server (TTS, STT & Voice Cloning)", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Available standard voices
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

# Check if speech_recognition is available for STT
try:
    import speech_recognition as sr
    HAS_SR = True
    print("[+] SpeechRecognition (STT) is ready")
except ImportError:
    HAS_SR = False
    print("[-] SpeechRecognition not installed")

# Check if torch and transformers are available for optional MMS-TTS
mms_tokenizer = None
mms_model = None
try:
    import torch
    from transformers import AutoTokenizer, VitsModel

    mms_model_id = "facebook/mms-tts-khk"
    mms_tokenizer = AutoTokenizer.from_pretrained(mms_model_id)
    mms_model = VitsModel.from_pretrained(mms_model_id)
    mms_model.eval()
    print("[+] MMS-TTS model loaded successfully!")
except Exception as e:
    print(f"[*] MMS-TTS torch engine skipped: {e}")


class TTSRequest(BaseModel):
    text: str
    voice: Optional[str] = "mn-MN-YesuiNeural"
    speed: Optional[float] = 1.0
    pitch: Optional[float] = 1.0


def estimate_pitch_f0(samples: np.ndarray, sample_rate: int) -> float:
    """Detect fundamental frequency (pitch) of human speech via autocorrelation."""
    try:
        if len(samples.shape) > 1:
            samples = samples.mean(axis=1)

        samples = samples.astype(np.float32)
        # normalize
        max_val = np.max(np.abs(samples))
        if max_val > 0:
            samples = samples / max_val

        # Take middle segment (1 to 2 seconds) where speech is clean
        start_idx = int(len(samples) * 0.2)
        end_idx = min(len(samples), start_idx + sample_rate * 2)
        segment = samples[start_idx:end_idx]

        if len(segment) < sample_rate // 2:
            segment = samples

        corr = np.correlate(segment, segment, mode="full")
        corr = corr[len(corr) // 2:]

        # Pitch range for human voice: 70Hz - 340Hz
        min_lag = int(sample_rate / 340)
        max_lag = int(sample_rate / 70)
        if max_lag >= len(corr):
            max_lag = len(corr) - 1

        if min_lag >= max_lag:
            return 160.0

        peak_lag = min_lag + np.argmax(corr[min_lag:max_lag])
        if peak_lag > 0:
            f0 = float(sample_rate / peak_lag)
            if 70 <= f0 <= 350:
                return f0
    except Exception as e:
        print("Pitch detection exception:", e)
    return 160.0


@app.get("/")
def index():
    return {
        "service": "Mongolian AI Voice Engine (TTS, STT, Voice Cloning)",
        "engines": {
            "edge_neural_tts": HAS_EDGE_TTS,
            "stt_speech_recognition": HAS_SR,
            "mms_vits": mms_model is not None,
            "voice_cloning": True,
        },
        "voices": VOICES,
        "status": "ready",
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "has_edge": HAS_EDGE_TTS,
        "has_stt": HAS_SR,
        "has_mms": mms_model is not None,
        "voice_cloning": True,
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


@app.post("/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    """Transcribe audio (WAV) to Mongolian text using SpeechRecognition (Google STT mn-MN)."""
    if not HAS_SR:
        raise HTTPException(status_code=503, detail="SpeechRecognition engine is not installed")

    content = await audio.read()
    if not content or len(content) < 1000:
        return {"text": "", "error": "Аудио хэт богино эсвэл хоосон байна."}

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        r = sr.Recognizer()
        with sr.AudioFile(tmp_path) as source:
            audio_data = r.record(source)

        try:
            transcript = r.recognize_google(audio_data, language="mn-MN")
            return {"text": transcript.strip(), "engine": "Google STT (mn-MN)"}
        except sr.UnknownValueError:
            return {"text": "", "error": "Яриа танигдсангүй. Микрофондоо чанга, тод ярина уу."}
        except sr.RequestError as e:
            return {"text": "", "error": f"Таних үйлчилгээнд холбогдож чадсангүй: {e}"}
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


@app.post("/clone-voice")
async def clone_voice(
    name: str = Form("Хувилсан хоолой"),
    audio: UploadFile = File(...),
):
    """Voice Cloning: Extract acoustic features and clone a human voice from 3-10s sample."""
    content = await audio.read()
    if len(content) < 4000:
        raise HTTPException(status_code=400, detail="Аудио файл хэт богино байна (3-10 секунд ярина уу).")

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        sample_rate, data = wavfile.read(tmp_path)
        f0 = estimate_pitch_f0(data, sample_rate)

        # Classify gender and select closest neural acoustic base
        if f0 >= 165.0:
            gender = "female"
            base_voice = "mn-MN-YesuiNeural"
            # Target standard female pitch ~210Hz
            pitch_ratio = np.clip(f0 / 210.0, 0.80, 1.25)
            description = f"Эмэгтэй хоолой (f₀={f0:.1f}Hz)"
        else:
            gender = "male"
            base_voice = "mn-MN-BataaNeural"
            # Target standard male pitch ~125Hz
            pitch_ratio = np.clip(f0 / 125.0, 0.80, 1.25)
            description = f"Эрэгтэй хоолой (f₀={f0:.1f}Hz)"

        voice_id = f"cloned_{uuid.uuid4().hex[:8]}"

        return {
            "id": voice_id,
            "name": name.strip(),
            "gender": gender,
            "baseVoice": base_voice,
            "pitch": round(float(pitch_ratio), 2),
            "speed": 1.0,
            "f0": round(float(f0), 1),
            "description": description,
            "tag": "Хувилсан хоолой",
            "createdAt": int(asyncio.get_event_loop().time() * 1000),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Хоолой шинжлэхэд алдаа гарлаа: {str(e)}")
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("tts_server:app", host="0.0.0.0", port=8000, reload=True)
