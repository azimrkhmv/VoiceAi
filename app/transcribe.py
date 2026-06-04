import os
import base64
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

PROMPT = (
    "Ushbu audio yoki video xabarni o'zbek tilida aniq va to'liq transkripsiya qiling. "
    "Faqat gapni yozing, hech qanday izoh, sarlavha yoki qo'shimcha matn qo'shmang."
)


async def transcribe(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()
    mime = MIME_TYPES.get(ext, "application/octet-stream")

    with open(file_path, "rb") as f:
        file_b64 = base64.b64encode(f.read()).decode("utf-8")

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
                            "url": f"data:{mime};base64,{file_b64}"
                        },
                    },
                ],
            }
        ],
    }

    async with httpx.AsyncClient(timeout=55) as client:
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
