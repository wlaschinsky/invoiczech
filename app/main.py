import os
from datetime import datetime
from pathlib import Path

import markdown as md

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from .config import get_settings
from .database import create_tables
from .tmpl import templates  # noqa — importem se zaregistrují filtry a flash injection
from .routers import auth, dashboard, invoices, expenses, contacts, exports, invoice_templates, search, overview, profile

settings = get_settings()

app = FastAPI(title="Fakturace", docs_url=None, redoc_url=None)

# Statické soubory
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Upload adresář
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)


# --- Auth middleware ---
# DŮLEŽITÉ: @app.middleware musí být definován PŘED add_middleware(SessionMiddleware),
# aby SessionMiddleware byl zpracován jako první (vnější vrstva).
EXEMPT_PATHS = {"/prihlaseni", "/odhlaseni"}
EXEMPT_PREFIXES = ("/static/",)


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path

    if path in EXEMPT_PATHS or any(path.startswith(p) for p in EXEMPT_PREFIXES):
        return await call_next(request)

    authenticated = request.session.get("authenticated")
    expires_at_str = request.session.get("expires_at")

    if authenticated and expires_at_str:
        try:
            expires_at = datetime.fromisoformat(expires_at_str)
            if datetime.now() > expires_at:
                request.session.clear()
                return RedirectResponse(url="/prihlaseni", status_code=302)
        except ValueError:
            request.session.clear()
            return RedirectResponse(url="/prihlaseni", status_code=302)
        return await call_next(request)

    return RedirectResponse(url="/prihlaseni", status_code=302)


# Session middleware přidán PO auth_middleware dekorátoru, aby byl zpracován jako PRVNÍ
# (starlette přidává middleware na index 0 = "nejblíže" žádosti, ale build_middleware_stack
# iteruje v obraceném pořadí = poslední add_middleware je nejzevnější).
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    max_age=28800,
    session_cookie="fakturace_session",
    https_only=False,
)


# --- Routery ---
app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(invoices.router)
app.include_router(expenses.router)
app.include_router(contacts.router)
app.include_router(exports.router)
app.include_router(invoice_templates.router)
app.include_router(search.router)
app.include_router(overview.router)
app.include_router(profile.router)


# --- Changelog API ---
_CHANGELOG_PATH = Path(__file__).parent.parent / "CHANGELOG.md"


@app.get("/api/changelog", response_class=HTMLResponse)
async def api_changelog(request: Request):
    if not request.session.get("authenticated"):
        return HTMLResponse("<p>Neautorizováno.</p>", status_code=401)
    try:
        raw = _CHANGELOG_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return HTMLResponse("<p>Soubor CHANGELOG.md nenalezen.</p>")
    html = md.markdown(raw, extensions=["nl2br"])
    return HTMLResponse(html)


# --- Startup ---
@app.on_event("startup")
async def startup():
    create_tables()
    if not settings.PASSWORD_HASH:
        import sys
        print(
            "\nVAROVANI: PASSWORD_HASH neni nastaven v .env souboru.\n"
            "   Spustte: python setup.py\n",
            file=sys.stderr,
        )
