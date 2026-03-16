from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    SECRET_KEY: str = "zmenit-na-nahodny-retezec-v-produkci"
    PASSWORD_HASH: str = ""
    DATABASE_URL: str = "sqlite:///./faktury.db"
    UPLOAD_DIR: str = "uploads"

    # Vlastník aplikace (login stránka, sidebar)
    OWNER_NAME: str = "Samuel Wlaschinský"
    OWNER_EMAIL: str = "samuel@invoiczech.cz"

    # Údaje dodavatele
    SUPPLIER_NAME: str = "Samuel Wlaschinský"
    SUPPLIER_STREET: str = "Kovanecká 2284/21"
    SUPPLIER_CITY: str = "Praha 9"
    SUPPLIER_ZIP: str = "190 00"
    SUPPLIER_ICO: str = "04980026"
    SUPPLIER_DIC: str = "CZ9007242926"
    SUPPLIER_ACCOUNT: str = "29489130140/3030"
    SUPPLIER_IBAN: str = ""
    SUPPLIER_EMAIL: str = "wlaschinsky.samuel@gmail.com"
    SUPPLIER_PHONE: str = "605412302"
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
