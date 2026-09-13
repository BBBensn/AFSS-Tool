---
date_created: 2026-09-14 01:25:00
type: changelog
tags:
  - project
  - changelog
date_modified: 2026-09-14 01:25:00
---

# v1.28.0 — WSGI-Einstiegspunkt für Server-Deploy (2026-09-14)

- Neu `afss/wsgi.py`: dünner Gunicorn-Einstiegspunkt für den Deploy auf `afss.bensn.me` (siehe
  `docs/AFSS-Tool.md`/Session-Notiz für den vollen Deploy-Ablauf). Liest `AFSS_CONFIG_DIR`/
  `AFSS_DB_PATH` aus der Umgebung (mit lokalen Fallbacks: `config/` bzw. das lokale `afss.db`),
  ruft ansonsten unverändert die bestehende `afss.dashboard.app.create_app()` auf - keine neue
  Logik, nur Verdrahtung, damit dieselbe App auch über Gunicorn statt `flask run` erreichbar ist.
- `afss/dashboard/app.py`: `app.secret_key` liest jetzt `AFSS_SECRET_KEY` aus der Umgebung (Fallback
  weiterhin der bisherige feste String für lokale Nutzung). Der bisherige hart codierte Wert war
  laut eigenem Kommentar bewusst "nur für 127.0.0.1 unkritisch" gedacht - das stimmt nicht mehr,
  sobald die App über eine echte Domain erreichbar ist (Sessions, u.a. das "Auswahl wiederholen"-
  Feature im Artist-Editor, werden damit signiert).
- Grund: Sortier-Studio/Artist-Editor/Tag-Editor brauchen für ihre Kernfunktion keinen Zugriff auf
  die eigentlichen Mediendateien - nur auf `afss.db` und die drei `config/*.json`-Dateien. Damit
  lässt sich eine Kopie von DB+Config auf einen Server legen und von unterwegs taggen, ohne dass der
  Server Zugriff aufs NAS/die externen Platten braucht. `scan`/`resolve`/`plan`/`apply`/`transcode`
  bleiben weiterhin zwingend lokal (brauchen die echten Laufwerke).

**Hinweis:** Dies ist nur der Code-seitige Teil. Server-Setup (Systemd-Service, Nginx-Vhost hinter
`bensn-auth`, SSL, Erstbefüllung mit den echten Daten) folgt als separater, nicht-versionierter
Infrastruktur-Schritt außerhalb dieses Repos.
