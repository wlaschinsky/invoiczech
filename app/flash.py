"""Flash message helpers (bez závislosti na routerech)."""
from fastapi import Request


def flash(request: Request, message: str, category: str = "info") -> None:
    if "_flashes" not in request.session:
        request.session["_flashes"] = []
    msgs = list(request.session["_flashes"])
    msgs.append({"message": message, "category": category})
    request.session["_flashes"] = msgs


def get_flashes(request: Request) -> list:
    msgs = list(request.session.get("_flashes", []))
    request.session["_flashes"] = []
    return msgs
