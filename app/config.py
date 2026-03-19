import os
import subprocess

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    SECRET_KEY: str = "zmenit-na-nahodny-retezec-v-produkci"
    PASSWORD_HASH: str = ""
    DATABASE_URL: str = "sqlite:///./faktury.db"
    UPLOAD_DIR: str = "uploads"

    # Vlastník aplikace (login stránka, sidebar)
    OWNER_NAME: str = "Vlastník Aplikace"
    OWNER_EMAIL: str = "owner@example.com"

    # Údaje dodavatele
    SUPPLIER_NAME: str = "Vlastník Aplikace"
    SUPPLIER_STREET: str = "Ulice XX"
    SUPPLIER_CITY: str = "Město"
    SUPPLIER_ZIP: str = "XXX XX"
    SUPPLIER_ICO: str = "XXXXXXXX"
    SUPPLIER_DIC: str = "CZXXXXXXXXXX"
    SUPPLIER_ACCOUNT: str = "XXXXXXXXXX/XXXX"
    SUPPLIER_IBAN: str = ""
    SUPPLIER_EMAIL: str = "owner@example.com"
    SUPPLIER_PHONE: str = "XXXXXXXXXX"
    SUPPLIER_FU_UFO: str = "451"
    SUPPLIER_FU_PRACUFO: str = "2009"
    SUPPLIER_OKEC: str = "620000"
    DEFAULT_INVOICE_TEXT: str = (
        "Fakturuji Vám za smluvně prací, na základě "
        "dodatku k rámcové smlouvě o dílo ze dne 1.5.2025."
    )

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_version() -> str:
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        return subprocess.check_output(
            ["git", "describe", "--tags", "--abbrev=0"],
            cwd=project_root,
            stderr=subprocess.PIPE,
            env={**os.environ, "HOME": os.path.expanduser("~")},
        ).decode().strip()
    except Exception:
        return "dev"


APP_VERSION = get_version()
