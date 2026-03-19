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
    from .models import contact, invoice, expense, invoice_template  # noqa — import side effects
    Base.metadata.create_all(bind=engine)
    _migrate_expense_attachments()


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
