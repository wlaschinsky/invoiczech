# Changelog — InvoiCzech

Všechny změny jsou řazeny od nejnovějších. Verze odpovídají logickým milníkům vývoje, nikoliv git tagům.

## [v1.4.0] — 2026-03-28

### Styl
- changelog tlačítko v sidebaru přesunuto pod nápovědu
- blur pozadí při otevření dokumentačního modalu

### Přidáno
- Claude Code skills (deploy, seed-demo, db) + settings.json permissions + .env.example deployment vars
- skript make_changelog.py — generuje sekci v CHANGELOG.md z git commitů od posledního tagu
- changelog v docs modalu — /api/changelog endpoint + nová sekce v nápovědě
- dokumentační popup — tlačítko ? v sidebaru, 11 sekcí nápovědy

### Dokumentace
- workflow pro changelog v README
- CHANGELOG.md — přehled verzí od v0.1.0, doplněny sekce Deploy/Bezpečnost/README do CLAUDE.md

### Refaktoring
- changelog — vlastní popup modal oddělený od nápovědy, tlačítko v sidebaru

### Opraveno
- výběr šablony — odebráním šablony se vyčistí předvyplněná pole
- odstraněn duplicitní block scripts v base.html

---

## [v0.7.0] — Šablony, naseptávač, importy

### Přidáno
- Naseptávač kontaktů ve fakturách, šablonách a nákladech (combobox s live filtrováním)
- Text faktury v šabloně — uložení a přenos při aplikaci šablony
- Náklady — plný formulář dodavatele (IČO, DIČ, adresa)
- Řazení sloupců v seznamech (faktury, náklady, adresář) — jen desktop
- Seed script pro demo data (profil, kontakty, faktury, náklady 2025–2026)
- Volitelné argumenty v import scriptu (`--contacts` / `--invoices` / `--expenses`)
- Auto-fill název nákladu z první položky

### Opraveno
- Vymazání kontaktu resetuje i IČO, DIČ a adresu
- Combobox kontaktů — šipka toggleuje dropdown správně
- Výběr z adresáře v nákladech — chybějící funkce a filtr kontaktů
- Export formulář odesílal špatné období (hidden select stále submitoval)
- Import nákladů — správný výpočet DPH dle sloupce Výpočet DPH
- KH1 VetaB2 pro náklady B2B > 10 000 Kč
- Oprava encoding v VetaP XML exportu (mojibake Latin-1/UTF-8)
- Opravy KH1/DP3 exportů — `c_evid_dd`, desetinná místa, čtvrtletní VetaD

### Styl
- Combobox kontaktů — rotující šipka, tlačítko vymazat, vizuál sjednocen s `.cs-dropdown`

---

## [v0.6.0] — Faktury pro neplátce DPH, QR platby, datové atributy

### Přidáno
- Skrytí DPH polí a exportů pro neplátce DPH (přehled, formuláře, dashboard)
- Auto-výpočet IBAN z čísla účtu a oprava formátu QR platebního kódu
- `data-testid` atributy na všechny šablony (pro E2E testování)

### Opraveno
- Login card layout
- Zpět tlačítko v profilu
- Vygenerovaný QR kód
- Hlavička PDF faktury → „FAKTURA — DAŇOVÝ DOKLAD" pro plátce DPH
- Skrytí sekce ARES při vybraném kontaktu, vyčištění polí při odebrání

---

## [v0.5.0] — Exporty (KH1, DP3), inline přílohy

### Přidáno
- Exporty daňových přiznání — KH1 (XML) a DP3
- Odstraněn export DPFDP7
- Inline preview přílohy s tlačítkem pro stažení na detailu nákladu

### Styl
- Stránka exportů
- Přihlašovací karta

---

## [v0.4.0] — Šablony, adresář, ARES integrace

### Přidáno
- Modul šablony faktur (nová faktura předvyplněná ze šablony)
- Adresář — zobrazení počtů faktur a nákladů místo typu kontaktu
- ARES vyhledávání — sdílená JS logika, auto-skrytí polí
- Přesný přehled faktur/nákladů v detailu kontaktu (query-based počty)
- Podmíněné tlačítko „Přidat nový" a filter bar dle prázdnosti seznamu
- Tlačítko „Vymazat filtr" pouze když je filtr aktivní
- Vlastní confirm dialogy a detekce neuložených změn na formulářích
- Breadcrumbs navigace
- Globální vyhledávání s kategorizovanými výsledky a tlačítkem vymazat

### Opraveno
- Šablony — opravy gridu a formuláře
- DPH v šablonách a fakturách
- ARES vyhledávání a uložení do kontaktů
- Reliable unsaved-changes guard (`beforeunload`)

---

## [v0.3.0] — Responzivní design, custom UI komponenty

### Přidáno
- Hamburger menu a mobilní drawer sidebar
- Responzivní tabulky (scroll wrapper, skrývání sloupců)
- Mobile-friendly formuláře, záhlaví stránek, detailní stránky
- Bulk výběr, akce a date range filtry pro faktury a náklady
- Custom themed datepicker (nahrazuje nativní calendar)
- Custom themed dropdowny (nahrazují nativní `<select>`)
- Interní poznámka na faktuře
- Výchozí datum DUZP
- Footer s git verzí a odkazem na GitHub

### Styl
- Tématické checkboxy, amber bulk bar, tmavý datepicker
- User dropdown s blur backdropem a výrazným tlačítkem odhlásit
- Ikony v sidebaru
- Sjednocení barev dropdownů s paletou tématu

---

## [v0.2.0] — Základní fakturace, kontakty, náklady

### Přidáno
- Vytváření, editace, mazání faktur a nákladů
- Adresář kontaktů
- Generování PDF faktur
- QR kód na faktuře
- Logo na faktuře
- Favicon pro mobil i desktop
- Sbalitelný sidebar
- Přehled ročních statistik
- Vlastní název pole v nákladech

### Opraveno
- Oprava vytváření faktury a kontaktu
- Oprava generování faktury

---

## [v0.1.0] — Počáteční struktura

### Přidáno
- Základní struktura aplikace InvoiCzech (FastAPI + Jinja2 + SQLite)
- Autentizace (přihlášení, session)
- Sidebar s navigací
- Profil uživatele
- Nastavení a migrate.py
