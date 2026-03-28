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
git clone https://github.com/wlaschinsky/invoiczech.git && cd invoiczech

python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Konfigurace

```bash
cp .env.example .env
```

### Proměnné prostředí

| Proměnná | Povinná | Popis |
|---|---|---|
| `SECRET_KEY` | Ano | Náhodný řetězec pro šifrování sessions |
| `PASSWORD_HASH` | Ano | Bcrypt hash hesla (viz níže) |
| `DATABASE_URL` | Ne | SQLite cesta (default `sqlite:///./faktury.db`) |
| `UPLOAD_DIR` | Ne | Adresář pro přílohy (default `uploads`) |

### Nastavení hesla

```bash
python setup.py
```

Skript vygeneruje bcrypt hash, který vložíš do `.env`:

```
PASSWORD_HASH=$2b$12$...
```

### Profil podnikatele

Všechny údaje (jméno, adresa, IČO, DIČ, banka, finanční úřad, výchozí nastavení faktur) se nastavují v aplikaci na stránce **Profil** (`/profil`). Žádné osobní údaje se neukládají do konfiguračních souborů.

## Spuštění

```bash
source venv/bin/activate
uvicorn app.main:app --reload
```

Aplikace běží na `http://localhost:8000`.

## Migrace databáze

Při přidání nových sloupců do modelů spusť migraci:

```bash
python migrate.py
```

Skript je idempotentní — přidá chybějící sloupce, existující data neovlivní.

## Struktura projektu

```
app/
├── main.py                # FastAPI app, middleware, startup
├── config.py              # Pydantic Settings (.env)
├── database.py            # SQLAlchemy engine + session
├── tmpl.py                # Jinja2 šablony, filtry, flash injection
├── models/
│   ├── contact.py         # Kontakty
│   ├── invoice.py         # Faktury + položky
│   ├── invoice_template.py # Šablony faktur
│   ├── expense.py         # Náklady + položky
│   └── profile.py         # Profil podnikatele (singleton)
├── routers/
│   ├── auth.py            # Přihlášení / odhlášení
│   ├── dashboard.py       # Dashboard se statistikami
│   ├── invoices.py        # CRUD faktury
│   ├── invoice_templates.py # Šablony faktur
│   ├── expenses.py        # CRUD náklady
│   ├── contacts.py        # CRUD kontakty + ARES
│   ├── exports.py         # XML exporty (KH1, DP3)
│   ├── overview.py        # Roční přehled
│   ├── profile.py         # Profil podnikatele
│   └── search.py          # Globální vyhledávání
├── services/
│   ├── pdf_generator.py   # PDF faktur (WeasyPrint)
│   ├── qr_code.py         # QR platba (SPD formát)
│   ├── xml_generator.py   # XML exporty pro FÚ
│   └── ares.py            # Napojení na ARES API
├── templates/             # Jinja2 šablony
└── static/                # CSS, favicon, PWA assets
```

## Funkce

- **Faktury** — vystavení, úprava, storno, úhrada, PDF export s QR kódem
- **Náklady** — evidence s přílohami, daňová uznatelnost
- **Kontakty** — adresář s napojením na ARES (automatické doplnění dle IČO)
- **Šablony faktur** — opakované fakturace
- **Dashboard** — měsíční statistiky příjmů, nákladů, DPH a neuhrazených faktur
- **Roční přehled** — měsíční breakdown s PDF/CSV exportem
- **XML exporty** — kontrolní hlášení (KH1) a přiznání k DPH (DP3) pro portál Moje Daně
- **Profil** — veškeré údaje podnikatele na jednom místě (osobní, banka, FÚ, výchozí nastavení)
- **PWA** — instalovatelná jako aplikace, offline-ready
- **Autentizace** — session s 8h timeoutem

## Claude Code Skills

Projekt obsahuje vlastní skills pro [Claude Code](https://claude.ai/code) v `.claude/skills/`:

```bash
claude /deploy      # nasadí aktuální větev na produkci
claude /seed-demo   # re-seeduje demo instanci
claude /db          # inspekce a dotazy na lokální SQLite
```

Skills čtou konfiguraci z `.env` — viz `.env.example`.

## Changelog

Changelog je dostupný přímo v aplikaci — tlačítko s hodinami v levém panelu.

### Workflow při vydání verze

```bash
# 1. Vyvíjíš a committuješ normálně (feat:, fix:, style: ...)

# 2. Až je verze hotová — vytvoř tag
git tag v0.9.0

# 3. Vygeneruj sekci changelogu ze všech commitů od posledního tagu
python scripts/make_changelog.py v0.9.0
# → ukáže preview, potvrdíš y/N → zapíše do CHANGELOG.md

# 4. Commitni CHANGELOG.md
git add CHANGELOG.md && git commit -m "docs: changelog v0.9.0"
git push && git push --tags
```

Skript automaticky rozřadí commity do kategorií (feat→Přidáno, fix→Opraveno, style→Styl…).

## Deploy

Automatický deploy přes GitHub Actions při push do `main` nebo vytvoření tagu `v*`. Viz `.github/workflows/deploy.yml`.

## Licence

MIT
