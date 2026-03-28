# Plánované funkce

## Paginace seznamů

### Rozsah
- Faktury, náklady, kontakty — všechny 3 najednou
- 30 záznamů na stránku

### Čeho se to dotkne

**Backend**
- Endpointy pro výpis záznamů — přidat `?strana` a `?limit` parametry
- Odpověď musí vracet `total` (celkový počet) vedle dat
- Nový endpoint `GET /*/ids?filtr=...` pro bulk selection přes všechny stránky

**Frontend**
- Stav filtrů přesunout z JS do URL query params
- Přidat pagination komponent (sdílený pro všechny 3 seznamy)
- Bulk selection logika — rozlišit "stránka" vs "vše dle filtru"
- Count po označení — zobrazit kolik celkem označeno

### Pořadí implementace
1. Filtry do URL query params — základ bez kterého nic nefunguje
2. Backend paginace
3. Sdílený pagination komponent
4. Bulk selection přes stránky + nový endpoint na IDs
5. Count update

### Co se musí otestovat
- Správný počet záznamů na stránce (včetně poslední neúplné)
- Navigace mezi stránkami
- Filtr resetuje na stránku 1, ale drží při přechodu stránek
- URL params se správně updatují a přežijí refresh
- Bulk: označení jen na stránce vs. vše dle filtru
- Count odpovídá skutečnosti přes stránky
- Akce (smazat, export) operují na správném setu
- Prázdný výsledek filtru
- Mobilní zobrazení pagination controls
