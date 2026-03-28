# InvoiCzech — Pravidla pro vývoj

## Obecná pravidla
- Každá funkce nebo oprava = jeden git commit s popisným názvem (feat:, fix:, style:)
- Neměň vizuální styl ani barvy pokud není explicitně řečeno
- Piš funkční kód, rozhoduj se sám, neptej se zbytečně
- Vždy otestuj že existující funkce fungují po změně

## Responzivita
- Změny pro mobil POUZE v `@media (max-width: 768px)`
- Změny pro desktop POUZE v `@media (min-width: 769px)` nebo v globálních pravidlech
- Nikdy nepřepisuj mobile styly při opravě desktopu a naopak

## Osobní údaje
- Žádné osobní údaje natvrdo v kódu
- Vše se načítá z DB tabulky settings nebo z .env
- .env nikdy do Gitu

## Databáze
- Při každé změně modelů aktualizuj migrate.py
- migrate.py musí být idempotentní

## Commit konvence
- `feat:` nová funkce
- `fix:` oprava bugu
- `style:` vizuální změna
- `refactor:` přepis bez změny funkce
- `docs:` dokumentace

## Lokátory
- Každý nový interaktivní element musí mít `data-testid`
- Formuláře: `data-testid="nazev-form"`
- Inputy: `data-testid="nazev-field"`
- Tlačítka: `data-testid="nazev-btn"`
- Tabulky: `data-testid="nazev-list"`
- Řádky: `data-testid="nazev-row-{id}"`
- Dropdowny: `data-testid="nazev-select"`
- Uložené hodnoty: `data-testid="nazev-value"`
- Každá option: `data-value="{hodnota}"`

Prefixy: `invoice-*` `expense-*` `contact-*` `template-*` `export-*` `profile-*` `login-*` `dashboard-*`

## Deploy stack
- **Uvicorn** — ASGI server, musí poslouchat na `127.0.0.1`, nikdy `0.0.0.0`
- **Nginx** — reverse proxy (80/443 → uvicorn)
- **Certbot** — Let's Encrypt SSL
- **systemd** — správa procesu (autostart, restart při pádu)
- Každá instance = jiný port (8001, 8002, ...)
- Konfigurace v `.env` — nikdy v gitu, `chmod 600 .env`
- Skills `/deploy` a `/seed-demo` čtou `DEPLOY_HOST`, `DEPLOY_PATH` z `.env`

## Bezpečnost
- Uvicorn: `--host 127.0.0.1`, nikdy `--host 0.0.0.0`
- UFW: povolit pouze porty 22, 80, 443
- Appka nesmí běžet jako root — `User=` v systemd service
- Rate limit na `/prihlaseni` přes nginx (`limit_req_zone`)
- FastAPI produkce: `docs_url=None, redoc_url=None`
- Session timeout 8h, HTTPS only

## README pravidla
- README je veřejné — žádné IP adresy, server paths, SSH targety, tokeny
- Deployment konfigurace patří pouze do `.env` (lokálně) nebo `.env.example` (jako placeholder)
