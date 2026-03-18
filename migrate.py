#!/usr/bin/env python3
"""
Migrace DB — přidá chybějící sloupce do SQLite databáze
na základě aktuálních SQLAlchemy modelů.

Idempotentní: lze spustit opakovaně, nikdy nesmaže data.
"""

import sqlite3
from sqlalchemy import Integer, String, Numeric, Date, DateTime, Text, Boolean, inspect

# Import modelů (side-effect: registrace do Base.metadata)
from app.database import Base, engine
from app.models import contact, invoice, expense, invoice_template  # noqa


# Mapování SQLAlchemy typů na SQLite typy
def sa_type_to_sqlite(col):
    t = type(col.type)
    if t in (Integer,):
        return "INTEGER"
    if t in (String, Text):
        return "TEXT"
    if t in (Numeric,):
        return "NUMERIC"
    if t in (Date, DateTime):
        return "TEXT"
    if t in (Boolean,):
        return "INTEGER"
    return "TEXT"


def get_default_clause(col):
    """Vrátí DEFAULT klauzuli pro ALTER TABLE ADD COLUMN."""
    if col.server_default is not None:
        return f" DEFAULT {col.server_default.arg.text}"
    if col.default is not None:
        val = col.default.arg
        if callable(val):
            return ""
        if isinstance(val, bool):
            return f" DEFAULT {1 if val else 0}"
        if isinstance(val, (int, float)):
            return f" DEFAULT {val}"
        return f" DEFAULT '{val}'"
    return ""


def migrate():
    db_url = str(engine.url)
    # Extrahuje cestu k souboru ze sqlite URL
    if db_url.startswith("sqlite:///"):
        db_path = db_url.replace("sqlite:///", "")
    else:
        print(f"Nepodporovaný DB backend: {db_url}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    added = []
    existing = []

    for table_name, table in Base.metadata.tables.items():
        # Zkontroluj, jestli tabulka existuje
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        )
        if not cursor.fetchone():
            print(f"  Tabulka '{table_name}' neexistuje — bude vytvořena při startu aplikace.")
            continue

        # Zjisti existující sloupce
        cursor.execute(f"PRAGMA table_info('{table_name}')")
        existing_cols = {row[1] for row in cursor.fetchall()}

        # Porovnej s modelem
        for col in table.columns:
            if col.name in existing_cols:
                existing.append(f"{table_name}.{col.name}")
            else:
                sqlite_type = sa_type_to_sqlite(col)
                default = get_default_clause(col)
                sql = f"ALTER TABLE {table_name} ADD COLUMN {col.name} {sqlite_type}{default}"
                try:
                    cursor.execute(sql)
                    added.append(f"{table_name}.{col.name}")
                    print(f"  + {table_name}.{col.name} ({sqlite_type}{default})")
                except sqlite3.OperationalError as e:
                    print(f"  ! {table_name}.{col.name}: {e}")

    conn.commit()
    conn.close()

    print()
    print(f"Hotovo: {len(added)} sloupců přidáno, {len(existing)} již existovalo.")
    if added:
        print(f"  Přidáno: {', '.join(added)}")


if __name__ == "__main__":
    print("Migrace databáze...\n")
    migrate()
