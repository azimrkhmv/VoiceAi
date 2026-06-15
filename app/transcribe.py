import asyncio
import os
import base64
import tempfile
import av
import httpx
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL = "google/gemini-2.5-flash"

MIME_TYPES = {
    ".ogg":  "audio/ogg",
    ".mp3":  "audio/mpeg",
    ".wav":  "audio/wav",
    ".m4a":  "audio/mp4",
    ".flac": "audio/flac",
    ".mp4":  "video/mp4",
    ".mov":  "video/quicktime",
    ".avi":  "video/x-msvideo",
    ".webm": "video/webm",
}

ALLOWED_EXTENSIONS = set(MIME_TYPES.keys())
VIDEO_EXTENSIONS = {ext for ext, mime in MIME_TYPES.items() if mime.startswith("video/")}

PROMPT = (
    "Ushbu audio yoki video xabarni o'zbek tilida aniq va to'liq transkripsiya qiling. "
    "Faqat gapni yozing, hech qanday izoh, sarlavha yoki qo'shimcha matn qo'shmang."
)


def _extract_audio_sync(input_path: str, output_path: str):
    with av.open(input_path) as container:
        audio_stream = next((s for s in container.streams if s.type == "audio"), None)
        if audio_stream is None:
            raise Exception("Videoda audio yo'q.")

        # 16 kHz mono — standard for speech recognition, ~4x smaller than 44 kHz stereo
        with av.open(output_path, "w", format="mp3") as out:
            out_stream = out.add_stream("libmp3lame", rate=16000)
            resampler = av.AudioResampler(format="s16p", layout="mono", rate=16000)

            for frame in container.decode(audio_stream):
                for r in resampler.resample(frame):
                    r.pts = None
                    for pkt in out_stream.encode(r):
                        out.mux(pkt)

            for r in resampler.resample(None):
                r.pts = None
                for pkt in out_stream.encode(r):
                    out.mux(pkt)

            for pkt in out_stream.encode(None):
                out.mux(pkt)


async def _extract_audio(file_path: str) -> str:
    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp.close()
    try:
        await asyncio.to_thread(_extract_audio_sync, file_path, tmp.name)
    except Exception:
        if os.path.exists(tmp.name):
            os.remove(tmp.name)
        raise
    return tmp.name


async def transcribe(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()

    audio_path = None
    if ext in VIDEO_EXTENSIONS:
        audio_path = await _extract_audio(file_path)
        send_path = audio_path
        mime = "audio/mpeg"
    else:
        send_path = file_path
        mime = MIME_TYPES.get(ext, "application/octet-stream")

    try:
        with open(send_path, "rb") as f:
            file_b64 = base64.b64encode(f.read()).decode("utf-8")

        payload = {
            "model": MODEL,
            "temperature": 0,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime};base64,{file_b64}"},
                        },
                    ],
                }
            ],
        }

        async with httpx.AsyncClient(timeout=290) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )

        if response.status_code != 200:
            raise Exception(f"OpenRouter error {response.status_code}: {response.text[:500]}")

        try:
            return response.json()["choices"][0]["message"]["content"].strip()
        except Exception:
            raise Exception(f"OpenRouter javobini o'qib bo'lmadi: {response.text[:200]}")

    finally:
        if audio_path and os.path.exists(audio_path):
            os.remove(audio_path)
