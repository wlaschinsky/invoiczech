import bcrypt as _bcrypt

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from ..tmpl import templates
from ..config import get_settings

router = APIRouter()
settings = get_settings()


@router.get("/prihlaseni", response_class=HTMLResponse)
async def login_page(request: Request):
    if request.session.get("authenticated"):
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/prihlaseni")
async def login_submit(
    request: Request,
    password: str = Form(...),
):
    if not settings.PASSWORD_HASH:
        # První spuštění bez hesla — nastavení hesla
        _flash(request, "Heslo není nastaveno. Spusťte setup.py a nastavte PASSWORD_HASH v .env.", "error")
        return templates.TemplateResponse("login.html", {"request": request})

    if _bcrypt.checkpw(password.encode(), settings.PASSWORD_HASH.encode()):
        from datetime import datetime
        request.session["authenticated"] = True
        request.session["login_time"] = datetime.now().isoformat()
        return RedirectResponse(url="/", status_code=302)

    _flash(request, "Nesprávné heslo.", "error")
    return templates.TemplateResponse("login.html", {"request": request}, status_code=401)


@router.get("/odhlaseni")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/prihlaseni", status_code=302)


def _flash(request: Request, message: str, category: str = "info") -> None:
    if "_flashes" not in request.session:
        request.session["_flashes"] = []
    msgs = list(request.session["_flashes"])
    msgs.append({"message": message, "category": category})
    request.session["_flashes"] = msgs
