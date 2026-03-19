import os
import subprocess

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    SECRET_KEY: str = "zmenit-na-nahodny-retezec-v-produkci"
    PASSWORD_HASH: str = ""
    DATABASE_URL: str = "sqlite:///./faktury.db"
    UPLOAD_DIR: str = "uploads"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


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
