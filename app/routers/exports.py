from datetime import date

from ..tmpl import templates
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.xml_generator import generate_kh1, generate_dp3
from .utils import flash

router = APIRouter(prefix="/exporty")


@router.get("", response_class=HTMLResponse)
async def exports_page(request: Request, db: Session = Depends(get_db)):
    from ..models.invoice import Invoice
    from ..models.expense import Expense
    today = date.today()
    inv_years = {r.year for r in db.query(Invoice.issue_date).all() if r.issue_date}
    exp_years = {r.year for r in db.query(Expense.issue_date).all() if r.issue_date}
    years = sorted(inv_years | exp_years, reverse=True)
    return templates.TemplateResponse(
        "exports/index.html",
        {"request": request, "today": today, "years": years},
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
