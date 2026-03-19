from datetime import date

from ..tmpl import templates
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.xml_generator import generate_kh1, generate_dp3, generate_dpfdp7
from .utils import flash

router = APIRouter(prefix="/exporty")


@router.get("", response_class=HTMLResponse)
async def exports_page(request: Request):
    today = date.today()
    return templates.TemplateResponse(
        "exports/index.html",
        {"request": request, "today": today},
    )


@router.post("/kh1")
async def export_kh1(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    year, period, quarter = _parse_period(form)
    sub_date = date.fromisoformat(form.get("submission_date", date.today().isoformat()))

    xml_content = generate_kh1(db, year, period, quarter, sub_date)

    mesic_str = f"Q{period}" if quarter else f"{period:02d}"
    filename = f"KH1_{year}_{mesic_str}.xml"
    return Response(
        content=xml_content.encode("utf-8"),
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/dp3")
async def export_dp3(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    year, period, quarter = _parse_period(form)
    sub_date = date.fromisoformat(form.get("submission_date", date.today().isoformat()))

    xml_content = generate_dp3(db, year, period, quarter, sub_date)

    mesic_str = f"Q{period}" if quarter else f"{period:02d}"
    filename = f"DP3_{year}_{mesic_str}.xml"
    return Response(
        content=xml_content.encode("utf-8"),
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/dpfdp7")
async def export_dpfdp7(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    try:
        year = int(form.get("year", date.today().year - 1))
    except ValueError:
        year = date.today().year - 1

    # Paušál se načítá z profilu
    from ..models.profile import Profile
    profile = db.query(Profile).first()
    pausal = profile.expense_flat_rate if profile and profile.expense_flat_rate else 60

    sleva = 30840 if form.get("sleva_poplatnik") else 0

    try:
        zalohy = int(form.get("zalohy", 0))
    except ValueError:
        zalohy = 0

    sub_date = date.fromisoformat(form.get("submission_date", date.today().isoformat()))

    xml_content = generate_dpfdp7(db, year, pausal, sleva, zalohy, sub_date)

    filename = f"DPFDP7-{year}.xml"
    return Response(
        content=xml_content.encode("utf-8"),
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _parse_period(form) -> tuple[int, int, bool]:
    """Vrátí (year, period, is_quarter)."""
    try:
        year = int(form.get("year", date.today().year))
    except ValueError:
        year = date.today().year

    period_type = form.get("period_type", "month")
    quarter = period_type == "quarter"

    try:
        period = int(form.get("period", 1))
    except ValueError:
        period = 1

    # Validace
    if quarter:
        period = max(1, min(4, period))
    else:
        period = max(1, min(12, period))

    return year, period, quarter
