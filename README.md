# InvoiCzech

Fakturační aplikace pro české OSVČ. Správa faktur, nákladů, kontaktů, generování PDF a daňových XML exportů (KH1, DP3).

## Požadavky

- Python 3.11+
- Systémové závislosti pro [WeasyPrint](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#installation) (generování PDF)

Na macOS:

```bash
brew install pango
```

## Instalace

```bash
# Klonování repozitáře
git clone <repo-url> && cd account_app

# Virtuální prostředí
python -m venv venv
source venv/bin/activate

# Závislosti
pip install -r requirements.txt
```

## Konfigurace

Zkopíruj `.env.example` do `.env` a vyplň hodnoty:

```bash
cp .env.example .env
```

### Povinné proměnné

| Proměnná | Popis |
|---|---|
| `SECRET_KEY` | Náhodný řetězec pro šifrování sessions |
| `PASSWORD_HASH` | Bcrypt hash hesla (viz níže) |

### Vlastník aplikace

Jméno a email vlastníka se zobrazují na login stránce a v sidebaru. Nastavují se v `.env`:

```
OWNER_NAME=Jan Novák
OWNER_EMAIL=jan@example.cz
```

### Údaje dodavatele

Výchozí hodnoty dodavatele (pro PDF faktury, exporty) lze přepsat v `.env`:

```
SUPPLIER_NAME=Jan Novák
SUPPLIER_ICO=12345678
SUPPLIER_DIC=CZ1234567890
SUPPLIER_STREET=Ulice 123
SUPPLIER_CITY=Praha
SUPPLIER_ZIP=110 00
SUPPLIER_ACCOUNT=1234567890/0100
SUPPLIER_IBAN=CZ1234567890123456789012
SUPPLIER_EMAIL=jan@example.cz
SUPPLIER_PHONE=123456789
```

### Nastavení hesla

Heslo se neukládá v plaintextu — v `.env` je pouze bcrypt hash. Vygeneruj ho pomocí:

```bash
python setup.py
```

Skript se zeptá na heslo (min. 8 znaků), vygeneruje hash a vypíše ho. Hash vlož do `.env`:

```
PASSWORD_HASH=$2b$12$...
```

## Spuštění

```bash
source venv/bin/activate
uvicorn app.main:app --reload
```

Aplikace běží na `http://localhost:8000`.

## Struktura projektu

```
app/
├── main.py              # FastAPI app, middleware, startup
├── config.py            # Pydantic Settings (.env)
├── database.py          # SQLAlchemy engine + session
├── tmpl.py              # Jinja2 šablony, filtry, flash injection
├── flash.py             # Flash messages
├── models/
│   ├── contact.py       # Kontakty
│   ├── invoice.py       # Faktury + položky
│   └── expense.py       # Náklady + položky
├── routers/
│   ├── auth.py          # Přihlášení / odhlášení
│   ├── dashboard.py     # Dashboard se statistikami
│   ├── invoices.py      # CRUD faktury
│   ├── expenses.py      # CRUD náklady
│   ├── contacts.py      # CRUD kontakty + ARES
│   └── exports.py       # DPH exporty (KH1, DP3)
├── services/
│   ├── pdf_generator.py # PDF faktur (WeasyPrint)
│   ├── qr_code.py       # QR platba (SPD formát)
│   ├── xml_generator.py # XML exporty pro FÚ
│   └── ares.py          # Napojení na ARES API
├── templates/           # Jinja2 šablony
└── static/              # CSS, favicon, PWA assets
```

## Databáze

SQLite (`faktury.db`). Tabulky se vytvoří automaticky při prvním spuštění — žádné migrace nejsou potřeba.

## Funkce

- Správa faktur (vystavení, úprava, storno, úhrada, PDF export)
- Správa nákladů s přílohami
- Adresář kontaktů s napojením na ARES (automatické doplnění dle IČO)
- QR kód pro platbu na PDF faktuře (český SPD formát)
- XML exporty pro kontrolní hlášení (KH1) a daňové přiznání (DP3)
- PWA podpora (offline-ready)
- Session autentizace s 8h timeoutem
