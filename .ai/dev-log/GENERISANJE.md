---
id: filmium-devlog-generisanje
type: reference
domain: filmium
title: Dev-log — pokazivač na kanonski proces (jedan za sve)
summary: Dev-log se pravi alatom ai_workplace/scripts/devlog.py; kanonsko uputstvo živi u ai_workplace (ne dupliraj ovde).
status: stable
keywords: [dev-log, generisanje, pokazivac, devlog.py, kanonski]
tags: [dev-log, uputstvo, pokazivac]
source_path: .ai/dev-log/GENERISANJE.md
---

# 📌 Dev-log — pokazivač

Kanonski proces (isti za ai_workplace + sve domene + aplikacije):
- Uputstvo: `~/ai/ai_workplace/.ai/dev-log/GENERISANJE.md`
- Alat: `~/ai/ai_workplace/scripts/devlog.py` (frontmatter + `edges` + INDEX idu sami)

Pravi/apenduj unos za OVAJ domen:
```bash
python3 ~/ai/ai_workplace/scripts/devlog.py new --root ~/ai/domains/filmium \
  --title "Naslov" --summary "Suština" --body -
```
