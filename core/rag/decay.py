from __future__ import annotations

from datetime import datetime, timezone

import psycopg


def run_decay(connection: psycopg.Connection, *, half_life_days: int,
              dormant_threshold: float, now: datetime | None = None) -> dict[str, int]:
    """Opada tezinu nekoriscenih NE-exempt veza; ispod praga -> dormant.

    Exempt veze (contradicts/depends_on/resolves/derived_from/owned_by) se NE
    diraju — CISA blokade ne smeju tiho da se ugase.
    """
    trenutak = now or datetime.now(timezone.utc)
    redovi = connection.execute(
        "SELECT src, dst, edge_type, weight, "
        "COALESCE(last_used_at, created_at) AS koriscena "
        "FROM edges WHERE state = 'active' AND decay_exempt = false"
    ).fetchall()

    decayed = 0
    dormant = 0
    for r in redovi:
        dani = (trenutak - r["koriscena"]).days
        if dani <= half_life_days:
            continue
        faktor = 0.5 ** (dani / half_life_days)
        novi = r["weight"] * faktor
        stanje = "dormant" if novi < dormant_threshold else "active"
        connection.execute(
            "UPDATE edges SET weight = %s, state = %s "
            "WHERE src = %s AND dst = %s AND edge_type = %s",
            (novi, stanje, r["src"], r["dst"], r["edge_type"]),
        )
        decayed += 1
        if stanje == "dormant":
            dormant += 1
    connection.commit()
    return {"decayed": decayed, "dormant": dormant}
