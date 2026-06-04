import os
import tempfile
import aiofiles
from fastapi import APIRouter, Request, UploadFile, File
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from app.auth import check_login
from app.transcribe import transcribe, ALLOWED_EXTENSIONS

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

router = APIRouter()
templates = Jinja2Templates(directory=os.path.join(_ROOT, "templates"))

MAX_UPLOAD_BYTES = 4 * 1024 * 1024  # 4 MB — keeps payload under Vercel's 4.5 MB request limit


def allowed_file(filename: str) -> bool:
    ext = os.path.splitext(filename)[1].lower()
    return ext in ALLOWED_EXTENSIONS


@router.get("/")
async def index(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse(
        "upload.html", {"request": request},
        headers={"Cache-Control": "no-store"},
    )


@router.post("/upload")
async def upload_file(request: Request, file: UploadFile = File(...)):
    if not check_login(request):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    if not allowed_file(file.filename):
        return JSONResponse(
            {"error": "Fayl formati qo'llab-quvvatlanmaydi. OGG, MP3, WAV, M4A, FLAC, MP4, MOV, AVI, WEBM yuklang."},
            status_code=400,
        )

    ext = os.path.splitext(file.filename)[1].lower()
    tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
    tmp.close()
    file_path = tmp.name

    size = 0
    too_large = False
    async with aiofiles.open(file_path, "wb") as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                too_large = True
                break
            await out.write(chunk)

    if too_large:
        if os.path.exists(file_path):
            os.remove(file_path)
        return JSONResponse(
            {"error": "Fayl hajmi 100 MB dan oshmasligi kerak."},
            status_code=400,
        )

    try:
        transcript = await transcribe(file_path)
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        return JSONResponse({"error": f"Transkripsiya xatosi: {str(e)}"}, status_code=500)
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

    return JSONResponse({"transcript": transcript})
