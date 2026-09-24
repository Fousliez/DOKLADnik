# DOKLADník – funkční požadavky

## 1. Smysl programu

DOKLADník je osobní desktopová evidence zakázek, klientů, peněz a jednoduchých faktur pro dvě činnosti:

- **DDD**
- **Dočista**

Program **není plné účetnictví**. V první linii neřeší DPH, podvojné účetnictví, sklad ani účetní předkontace.

## 2. Základní principy

1. Všechna data jsou v jedné databázi napříč roky.
2. DDD a Dočista lze zobrazit zvlášť i dohromady.
3. Každá entita má stabilní interní ID. Jméno, číslo faktury ani jiný uživatelský údaj není interní identifikátor.
4. Mazání běžných dat je měkké (koš), ne okamžité fyzické odstranění.
5. Změny se zapisují jen tehdy, když se hodnota skutečně změnila.
6. Uživatelská data jsou oddělená od programových souborů.
7. Databáze musí jít bezpečně zálohovat a přenést.
8. Výkon se při problému měří; nepředělává se naslepo.

## 3. Hlavní části programu

- **Přehled**
- **Zakázky**
- **Klienti**
- **Faktury**
- **Statistiky**
- **Nastavení**

Ve všech relevantních částech je přepínač **Vše / DDD / Dočista**.

## 4. Zakázka

### Společná pole

- interní ID
- datum
- činnost: DDD / Dočista
- vazba na klienta (volitelná)
- jméno zákazníka / kontaktní osoba
- adresa zakázky
- telefon
- e-mail
- co se dělalo / popis služby
- cena práce
- dýško
- cestovné v Kč
- počet km
- způsob platby: hotovost / převod / karta
- stav platby: nezaplaceno / částečně / zaplaceno
- datum zaplacení
- doklad: bez dokladu / účtenka / faktura
- vazba na fakturu a její číslo
- zdroj zákazníka
- poznámka
- datum vytvoření a poslední změny

### DDD navíc

- typ zásahu
- škůdce
- protokol ano/ne
- číslo protokolu
- fáze zásahu (např. první / opakovaný)
- datum dalšího zásahu
- detail zásahu

### Dočista navíc

- typ čištění
- počet kusů
- plocha v m²
- detail práce

## 5. Klienti

Klient má:

- interní ID
- jméno / název firmy
- kontaktní osobu
- telefon
- e-mail
- adresu
- fakturační adresu
- IČO
- DIČ
- zaměření DDD / Dočista / oboje
- oblíbený
- stálý klient
- zdroj zákazníka
- poznámku

U klienta se zobrazí odvozené informace:

- počet zakázek
- celková utracená částka
- poslední zakázka
- historie zakázek

Při výběru klienta v nové zakázce se jeho údaje nabídnou k předvyplnění. Zakázka si ale uchovává vlastní údaje, aby pozdější změna klienta nezměnila historický záznam.

## 6. Faktury

Jednoduchá fakturace:

- automatické číslo faktury, výchozí tvar `2026-001`
- datum vystavení
- datum splatnosti
- klient / odběratel
- fakturační údaje
- položky
- částka
- způsob úhrady
- stav platby
- datum zaplacení
- poznámka
- vazba na zakázku
- export do PDF

Číslování je samostatná uživatelská hodnota, nikoli interní ID.

Výchozí faktura vytvořená ze zakázky zahrnuje cenu práce a cestovné. Dýško se do faktury automaticky nezahrnuje.

## 7. Přehledy a období

Filtr období:

- všechny roky
- konkrétní rok
- konkrétní měsíc
- vlastní období od–do

Souhrny:

- tržby za práci
- dýška
- cestovné
- celkem
- počet zakázek
- průměrná hodnota zakázky
- nezaplacené částky
- počet faktur

Rozdělení:

- DDD / Dočista
- hotovost / převod / karta
- zdroj zákazníka
- typ služby / zásahu
- rok a měsíc

## 8. Zdroj zákazníka

Výchozí číselník:

- Google vyhledávání
- Google reklama
- Seznam
- Facebook
- doporučení
- stálý zákazník
- web
- jiné

Číselník musí být rozšiřitelný bez zásahu do kódu.

## 9. UX a funkce převzaté jako princip z Latflixu

Nejde o kopii Latflixu. Převzaté jsou pouze obecné požadavky na spolehlivý desktopový program:

- rychlé tabulky i pro tisíce záznamů
- okamžité hledání a filtrování
- aktivní filtry musí být jasně vidět
- výběr řádku se má při rozumném překreslení zachovat
- dvojklik otevře detail/editaci
- hromadné akce mají být oddělené od běžné editace
- klávesové zkratky pro časté operace
- stavový řádek s počtem záznamů a stavem databáze
- měkké mazání + koš + možnost obnovy
- historie změn
- skutečné undo/redo pro podporované změny
- automatické ukládání nastavení
- automatické a ruční zálohy
- kontrola databáze při spuštění
- verzované databázové migrace
- import/export a přenositelnost dat
- ochrana proti duplicitnímu renderování a event stormům
- GUI nesmí zapisovat do databáze při pouhém načtení/refreshi
- diagnostické měření pomalých operací
- zapisovat pouze skutečně změněné hodnoty
- nebezpečné akce potvrdit nebo umožnit snadno vrátit

## 10. Klávesové zkratky – cílový návrh

- `Ctrl+N` nová zakázka v záložce Zakázky
- `Ctrl+F` hledání v aktivní tabulce
- `Ctrl+S` uložit otevřený dialog
- `Ctrl+Z` undo
- `Ctrl+Shift+Z` redo
- `Delete` přesun vybraného záznamu do koše
- `F5` obnovení aktuálního pohledu
- `Ctrl+B` ruční záloha

## 11. Bezpečnost dat

- SQLite foreign keys zapnuté
- WAL režim
- transakce pro více souvisejících změn
- automatický audit změn
- denní automatická záloha
- ruční ZIP záloha
- obnova ze zálohy musí před přepsáním vytvořit bezpečnostní kopii
- test obnovy musí být součástí vývoje

## 12. Rozsah první programové verze

První funkční verze má obsahovat:

- vytvoření databáze a migrací
- Přehled se základními souhrny
- seznam zakázek
- přidání/editaci/smazání zakázky
- seznam klientů
- přidání/editaci/smazání klienta
- oblíbené a stálé klienty
- faktury navázané na zakázku
- automatické číslování faktur
- PDF faktury
- základní statistiky
- nastavení údajů dodavatele
- audit změn
- automatickou a ruční zálohu

Koš s plným UI, undo/redo, hromadný import a pokročilé grafy mohou následovat po ověření základního workflow.
