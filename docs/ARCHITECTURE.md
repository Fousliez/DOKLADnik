# Architektura DOKLADníku

## Vrstvy

```
GUI (PySide6)
    ↓
aplikační služby / repository
    ↓
SQLite
```

GUI nesmí skládat SQL dotazy a databázová vrstva nesmí obsahovat widgety.

## Data

Výchozí datový adresář v Linuxu:

```
~/.local/share/DOKLADnik/
```

Lze přesměrovat proměnnou prostředí:

```bash
DOKLADNIK_DATA_DIR=/cesta/k/datum python main.py
```

To umožňuje i přenositelnou instalaci bez změny kódu.

## Databáze

- SQLite
- foreign keys
- WAL
- `schema_version`
- měkké mazání přes `deleted_at`
- `audit_log` pro historii změn

Peníze se ukládají jako celé haléře (`INTEGER`), nikoli `REAL`.

Datum se ukládá jako ISO `YYYY-MM-DD`.

## Identita

Každá tabulka používá interní celočíselné ID. Zobrazované hodnoty (jméno, číslo faktury, telefon) se nikdy nepoužívají jako vztahový klíč.

## Výkon

Tabulky v GUI mají používat model/view, ne tisíce samostatně řízených widgetů. Refresh pouze načte data; nesmí vytvářet databázové zápisy.

Při regresi výkonu se nejprve měří konkrétní operace a počet databázových/GUI událostí.
