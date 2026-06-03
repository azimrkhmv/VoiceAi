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
    with av.open(input_path) as in_container:
        in_audio = next((s for s in in_container.streams if s.type == "audio"), None)
        if in_audio is None:
            raise Exception("Videoda audio yo'q.")

        with av.open(output_path, "w", format="mp3") as out_container:
            out_stream = out_container.add_stream("libmp3lame", rate=44100)
            resampler = av.AudioResampler(format="s16p", layout="stereo", rate=44100)

            for frame in in_container.decode(in_audio):
                for resampled in resampler.resample(frame):
                    resampled.pts = None
                    for packet in out_stream.encode(resampled):
                        out_container.mux(packet)

            for resampled in resampler.resample(None):
                resampled.pts = None
                for packet in out_stream.encode(resampled):
                    out_container.mux(packet)

            for packet in out_stream.encode(None):
                out_container.mux(packet)


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

    temp_audio = None
    if ext in VIDEO_EXTENSIONS:
        temp_audio = await _extract_audio(file_path)
        send_path = temp_audio
    else:
        send_path = file_path

    try:
        mime = MIME_TYPES.get(os.path.splitext(send_path)[1].lower(), "application/octet-stream")

        with open(send_path, "rb") as f:
            audio_b64 = base64.b64encode(f.read()).decode("utf-8")

        payload = {
            "model": MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime};base64,{audio_b64}"
                            },
                        },
                    ],
                }
            ],
        }

        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )

        if response.status_code != 200:
            raise Exception(f"OpenRouter error {response.status_code}: {response.text}")

        return response.json()["choices"][0]["message"]["content"].strip()
    finally:
        if temp_audio and os.path.exists(temp_audio):
            os.remove(temp_audio)
