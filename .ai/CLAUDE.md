# FILMIUM — uputstva za AI

Ovo je odcepljena ćelija domena filmium. Radi samostalno, bez CORE-a.

Aplikacija se otvara preko `FILMIUM.exe` (prozor koji sam pokreće API iz
`.venv`). `.venv` pravi `build_cell.py` (nije u repou); `.venv` je korisnički
prostor ćelije — `--update` ga nikad ne dira.

## Struktura

- `core/foundation`, `core/database`, `core/cell`, `core/system`, `core/rag`,
  `core/ai` — kernel. Ne menja se ovde; menja se nadogradnjom kernela.
- `core/domains/filmium` — kod domena. Ovde ide najveći deo rada.
- `apps/api/` — routeri i sheme.
- `gui/` — korisnički deo.
- `.ai/atomi/` — atomske beleške, jedna činjenica po fajlu.
- `.ai/nadogradnje/` — beleške primljene iz CORE-a; ništa se ne primenjuje samo od sebe.

## Ažuriranje iz CORE-a

`build_cell.py --update` zamenjuje SAMO generisane putanje: `core/`, `apps/`,
`FILMIUM.exe` (prozor ćelije), `cell_app.py`, `start.bat`,
`requirements.txt`, `cell.json` (spojen sa postojećim portom i AI
podešavanjima), `.ai/CLAUDE.md` i u `gui/`: `src/`,
`dist/`, `public/`, `cell.html`, `vite.cell.config.ts`,
`cell-substitutions.json`, `package.json` i tsconfig fajlove.

Sve ostalo ostaje netaknuto: `data/`, `config/`, `.ai/atomi/`,
`.ai/nadogradnje/`, `.ai/dev-log/`, `.git`, `gui/node_modules` i tvoji fajlovi.

PAŽNJA: `gui/src` je generisan — izmene u njemu se pri ažuriranju NAMERNO
zamenjuju. Trajna izmena GUI-ja ide u CORE repo. Ažuriranje se odbija dok
ćelija radi.

## Pravila

- Testovi se pokreću iz korena ćelije.
- Kod domena ne sme da uvozi nijedan drugi domen.
- Pre izmene pročitaj `.ai/PROJECT.yaml` i poslednje unose u `.ai/dev-log/entries/`.
