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
