"""Načítání dat firem z ARES API (MFČR)."""
from typing import Optional

import httpx

ARES_URL = "https://ares.gov.cz/ekonomicke-subjekty-v-be/rest/ekonomicke-subjekty/{ico}"


async def lookup_ico(ico: str) -> Optional[dict]:
    """Vrátí slovník s daty firmy nebo None při chybě."""
    ico = ico.strip().zfill(8)
    url = ARES_URL.format(ico=ico)
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(url, headers={"Accept": "application/json"})
            if resp.status_code == 200:
                return _parse(resp.json())
            if resp.status_code == 404:
                return {"error": "IČO nenalezeno v ARES"}
        except httpx.TimeoutException:
            return {"error": "Časový limit dotazu na ARES vypršel"}
        except Exception as exc:
            return {"error": f"Chyba při komunikaci s ARES: {exc}"}
    return None


def _parse(data: dict) -> dict:
    """Parsuje odpověď ARES API na slovník polí kontaktu."""
    sidlo = data.get("sidlo") or {}

    ulice = sidlo.get("nazevUlice") or ""
    c_pop = str(sidlo.get("cisloDomovni") or "")
    c_ori = str(sidlo.get("cisloOrientacni") or "")
    if c_pop and c_ori:
        street = f"{ulice} {c_pop}/{c_ori}".strip()
    elif c_pop:
        street = f"{ulice} {c_pop}".strip()
    else:
        street = ulice.strip()

    raw_psc = str(sidlo.get("psc") or "")
    if len(raw_psc) == 5:
        zip_code = raw_psc[:3] + " " + raw_psc[3:]
    else:
        zip_code = raw_psc

    city = sidlo.get("nazevObce") or ""
    city_part = sidlo.get("nazevCastiObce") or ""
    if city_part and city_part != city:
        city = f"{city} - {city_part}"

    ico_out = str(data.get("ico") or "").lstrip("0") or str(data.get("ico") or "")
    dic = data.get("dic") or ""
    name = data.get("obchodniJmeno") or ""

    return {
        "name": name,
        "ico": str(data.get("ico") or ""),
        "dic": dic,
        "street": street,
        "city": city,
        "zip_code": zip_code,
        "country": "Česká republika",
    }
