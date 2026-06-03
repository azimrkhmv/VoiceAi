import os
from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from app.auth import verify_credentials

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

router = APIRouter()
templates = Jinja2Templates(directory=os.path.join(_ROOT, "templates"))


@router.get("/login")
async def login_page(request: Request):
    if request.session.get("authenticated"):
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@router.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    if verify_credentials(username, password):
        request.session["authenticated"] = True
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse(
        "login.html", {"request": request, "error": "Invalid username or password"}
    )


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)
