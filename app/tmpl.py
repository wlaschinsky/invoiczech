"""Sdílená instance Jinja2Templates s filtry a automatickým flash injection."""
from decimal import Decimal

from fastapi.templating import Jinja2Templates

from .flash import get_flashes
from .config import get_settings, APP_VERSION

settings = get_settings()

templates = Jinja2Templates(directory="app/templates")


# ---- Filtry ----

def _fmt_czk(value) -> str:
    if value is None:
        return "0,00 Kč"
    d = Decimal(str(value))
    negative = d < 0
    d = abs(d)
    integer_part = int(d)
    decimal_part = int(round((d - integer_part) * 100))
    int_str = f"{integer_part:,}".replace(",", "\u00a0")  # nezlomitelná mezera
    result = f"{int_str},{decimal_part:02d} Kč"
    return ("-" + result) if negative else result


def _fmt_date(value) -> str:
    if value is None:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%d.%m.%Y")
    return str(value)


def _fmt_num(value, decimals: int = 2) -> str:
    if value is None:
        return "0"
    d = Decimal(str(value))
    return f"{d:.{decimals}f}".replace(".", ",")


templates.env.filters["czk"] = _fmt_czk
templates.env.filters["date_cs"] = _fmt_date
templates.env.filters["num"] = _fmt_num

# ---- Global variables ----
templates.env.globals["app_version"] = APP_VERSION


# ---- Flash injection ----

_orig_response = templates.TemplateResponse


def _get_profile():
    """Načte profil z DB (lazy, singleton per request)."""
    from .database import SessionLocal
    from .models.profile import Profile
    db = SessionLocal()
    try:
        profile = db.query(Profile).first()
        if not profile:
            profile = Profile(id=1)
            db.add(profile)
            db.commit()
            db.refresh(profile)
        # Detach from session so it can be used in templates
        db.expunge(profile)
        return profile
    finally:
        db.close()


def _response_with_flash(name, context, *args, **kwargs):
    request = context.get("request")
    if request is not None:
        context.setdefault("flashes", get_flashes(request))
        context.setdefault("settings", settings)
        context.setdefault("profile", _get_profile())
    return _orig_response(name, context, *args, **kwargs)


templates.TemplateResponse = _response_with_flash  # type: ignore
