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
    OWNER_NAME: str = ""
    OWNER_EMAIL: str = ""

    # Údaje dodavatele (nastavit v .env)
    SUPPLIER_NAME: str = ""
    SUPPLIER_STREET: str = ""
    SUPPLIER_CITY: str = ""
    SUPPLIER_ZIP: str = ""
    SUPPLIER_ICO: str = ""
    SUPPLIER_DIC: str = ""
    SUPPLIER_ACCOUNT: str = ""
    SUPPLIER_IBAN: str = ""
    SUPPLIER_EMAIL: str = ""
    SUPPLIER_PHONE: str = ""
    SUPPLIER_FU_UFO: str = ""
    SUPPLIER_FU_PRACUFO: str = ""
    SUPPLIER_OKEC: str = ""
    DEFAULT_INVOICE_TEXT: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_version() -> str:
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # 1) Soubor VERSION (zapisuje deploy pipeline)
    version_file = os.path.join(project_root, "VERSION")
    if os.path.isfile(version_file):
        v = open(version_file).read().strip()
        if v:
            return v
    # 2) Fallback na git (lokální vývoj)
    try:
        return subprocess.check_output(
            ["git", "describe", "--tags", "--abbrev=0"],
            cwd=project_root,
            stderr=subprocess.PIPE,
        ).decode().strip()
    except Exception:
        return "dev"


APP_VERSION = get_version()
