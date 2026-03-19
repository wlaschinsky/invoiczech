import os

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session

from .config import get_settings

settings = get_settings()

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    from .models import contact, invoice, expense, invoice_template, profile  # noqa — import side effects
    Base.metadata.create_all(bind=engine)
    _migrate_expense_attachments()
    _migrate_profile_from_env()


def _migrate_expense_attachments():
    """Migrate legacy attachment_path on expenses to expense_attachments table."""
    inspector = inspect(engine)
    if "expense_attachments" not in inspector.get_table_names():
        return
    db = SessionLocal()
    try:
        rows = db.execute(
            text("SELECT id, attachment_path FROM expenses WHERE attachment_path IS NOT NULL AND attachment_path != ''")
        ).fetchall()
        if not rows:
            return
        # Check if already migrated
        existing = db.execute(text("SELECT COUNT(*) FROM expense_attachments")).scalar()
        if existing:
            return
        for row in rows:
            expense_id, path = row
            filename = os.path.basename(path)
            db.execute(
                text("INSERT INTO expense_attachments (expense_id, filename, filepath, position) VALUES (:eid, :fn, :fp, 0)"),
                {"eid": expense_id, "fn": filename, "fp": path},
            )
        db.commit()
    finally:
        db.close()


def _migrate_profile_from_env():
    """One-time migration: seed profile from .env variables if profile is empty."""
    from .models.profile import Profile
    db = SessionLocal()
    try:
        profile = db.query(Profile).first()
        if profile and profile.ico:
            return  # Already has data
        if not profile:
            profile = Profile(id=1)
            db.add(profile)

        # Read .env file directly
        env_vals = {}
        env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
        if os.path.isfile(env_path):
            for line in open(env_path):
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                env_vals[key.strip()] = val.strip()

        if not env_vals:
            db.commit()
            return

        name = env_vals.get("OWNER_NAME", "") or env_vals.get("SUPPLIER_NAME", "")
        if name and " " in name:
            parts = name.split(" ", 1)
            profile.first_name = profile.first_name or parts[0]
            profile.last_name = profile.last_name or parts[1]
        elif name:
            profile.last_name = profile.last_name or name

        profile.company_name = profile.company_name or env_vals.get("SUPPLIER_NAME", "")
        profile.email = profile.email or env_vals.get("SUPPLIER_EMAIL", "") or env_vals.get("OWNER_EMAIL", "")
        profile.phone = profile.phone or env_vals.get("SUPPLIER_PHONE", "")
        profile.street = profile.street or env_vals.get("SUPPLIER_STREET", "")
        profile.city = profile.city or env_vals.get("SUPPLIER_CITY", "")
        profile.zip_code = profile.zip_code or env_vals.get("SUPPLIER_ZIP", "")
        profile.ico = profile.ico or env_vals.get("SUPPLIER_ICO", "")
        profile.dic = profile.dic or env_vals.get("SUPPLIER_DIC", "")
        profile.bank_account = profile.bank_account or env_vals.get("SUPPLIER_ACCOUNT", "")
        profile.iban = profile.iban or env_vals.get("SUPPLIER_IBAN", "")
        profile.fu_ufo = profile.fu_ufo or env_vals.get("SUPPLIER_FU_UFO", "")
        profile.fu_pracufo = profile.fu_pracufo or env_vals.get("SUPPLIER_FU_PRACUFO", "")
        profile.okec = profile.okec or env_vals.get("SUPPLIER_OKEC", "")
        profile.default_invoice_text = profile.default_invoice_text or env_vals.get("DEFAULT_INVOICE_TEXT", "")

        db.commit()
    finally:
        db.close()
