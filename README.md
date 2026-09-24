# DOKLADník

Jednoduchá desktopová evidence zakázek, klientů, tržeb a faktur pro **DDD** a **Dočista**.

## Cíl

DOKLADník není plné účetnictví. Neřeší podvojné účetnictví ani DPH. Má rychle a spolehlivě evidovat:

- zakázky a tržby,
- DDD a Dočista odděleně i dohromady,
- klienty a stálé/oblíbené klienty,
- hotovost / převod / kartu,
- stav zaplacení,
- doklady a faktury,
- DDD protokoly,
- cestovné, kilometry a dýška,
- zdroj zákazníka,
- přehledy za měsíc, rok, vlastní období a všechny roky.

## Technologie

- Python 3.12+
- PySide6
- SQLite
- lokální data bez serveru

## Spuštění

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

## Zásady projektu

- stabilní interní ID; vazby nikdy nestojí na jménu,
- GUI, databáze a aplikační logika jsou oddělené,
- data se ukládají pouze při skutečné změně,
- nebezpečné akce musí být vratné nebo potvrzené,
- databáze je přenositelná a zálohovatelná,
- výkon se měří, neodhaduje,
- filtry nesmí ničit výběr a stav uživatele.

Podrobný rozsah první verze je v `docs/REQUIREMENTS.md`.
