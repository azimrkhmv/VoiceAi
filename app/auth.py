from fastapi import Request
from fastapi.responses import RedirectResponse
import os


def check_login(request: Request) -> bool:
    return request.session.get("authenticated") is True


def require_login(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=302)
    return None


def verify_credentials(username: str, password: str) -> bool:
    return (
        username == os.getenv("APP_USERNAME")
        and password == os.getenv("APP_PASSWORD")
    )
