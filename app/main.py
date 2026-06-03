import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from app.routes import auth, upload

app = FastAPI()

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SECRET_KEY", "fallback-secret"),
    max_age=86400,
)

app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

app.include_router(auth.router)
app.include_router(upload.router)
