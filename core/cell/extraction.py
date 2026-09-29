"""Prenos podataka domena iz deljene CORE baze u bazu ćelije.

Šema ćelije se ne kopira — nju grade migracije domena. Ovde se prenose samo
redovi, plus zapisi o već primenjenim migracijama, da ćelija ne bi pokušala da
ih ponovi.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from core.cell.database import initialize_cell_database
from core.cell.manifest import CellManifest


def domain_table_names(
    connection: sqlite3.Connection,
    domain_id: str,
    schema: str = "main",
) -> tuple[str, ...]:
    """
    Vraća imena tabela koje pripadaju domenu, po prefiksu imena.

    Args:
        connection: Otvorena konekcija ka bazi (izvornoj ili ciljnoj).
        domain_id: Identifikator domena, npr. `filmium`.
        schema: Naziv šeme nad kojom se pretražuje `sqlite_master` — `main`
            za samu konekciju, ili naziv koji je dat pri `ATTACH DATABASE`
            (npr. `source`) da bi se videla priključena baza.

    Returns:
        Sortirana imena tabela.
    """
    rows = connection.execute(
        f"SELECT name FROM {schema}.sqlite_master WHERE type = 'table' "
        "AND name LIKE ? ORDER BY name",
        (f"{domain_id}_%",),
    ).fetchall()

    return tuple(row[0] for row in rows)


def _row_count(connection: sqlite3.Connection, table: str) -> int:
    return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def _read_only_uri(path: Path) -> str:
    """
    URI oblik `path`-a za `ATTACH DATABASE ... AS source`, sa `mode=ro`.

    SQLite URI filename-ovi se UVEK prepoznaju kao argument `ATTACH DATABASE`
    komande, bez obzira na to da li je konekcija koja izvršava ATTACH sama
    otvorena sa `uri=True` (vidi https://www.sqlite.org/uri.html, tačka 4).
    Obično `ATTACH DATABASE <putanja>` je otvoren za čitanje-i-pisanje čak i
    kad se izvorna baza samo čita — `mode=ro` u URI-ju to menja na nivou
    same SQLite konekcije, ne samo na nivou fajl-sistema, pa i pokušaj pisanja
    unutar iste transakcije puca umesto da tiho prođe.

    `Path.as_uri()` zahteva apsolutnu putanju (otud `resolve()`) i ispravno
    URI-enkodira specijalne znakove (razmake i sl.) — bitno na ovoj mašini,
    gde CORE baza živi pod putanjom sa razmakom.
    """
    return f"{path.resolve().as_uri()}?mode=ro"


def extract_domain_data(source_db: Path, manifest: CellManifest) -> dict[str, int]:
    """
    Prenosi redove domena iz CORE baze u bazu ćelije.

    Ponovljeno pokretanje daje isti rezultat: ciljne tabele se prvo prazne.
    Izvorna baza se otvara samo za čitanje i ostaje netaknuta.

    Šema ćelije (izgrađena migracijama domena) je merodavna za to koje tabele
    ćelija sme da drži. Ako CORE baza ima zastarelu `filmium_` tabelu koju
    ćelija više ne poznaje, ta tabela se preskače. Ako, obrnuto, CORE baza
    više nema tabelu koju ćelija poznaje (npr. obrisana u međuvremenu), ta
    tabela se takođe preskače — ne prenosi se i ne izaziva grešku;
    `verify_extraction` će takvo odstupanje prijaviti kao neslaganje.

    Args:
        source_db: Putanja CORE baze.
        manifest: Manifest ćelije.

    Returns:
        Broj prenetih redova po tabeli (samo za tabele koje postoje i u
        izvoru i u ćeliji).
    """
    initialize_cell_database(manifest)

    target = sqlite3.connect(manifest.database_path, uri=True)
    counts: dict[str, int] = {}

    try:
        target.execute("PRAGMA foreign_keys = OFF")
        target.execute(
            "ATTACH DATABASE ? AS source", (_read_only_uri(source_db),)
        )

        target_tables = domain_table_names(target, manifest.domain_id)
        source_tables = set(
            domain_table_names(target, manifest.domain_id, schema="source")
        )

        for table in target_tables:
            if table not in source_tables:
                continue

            target.execute(f"DELETE FROM {table}")
            target.execute(f"INSERT INTO {table} SELECT * FROM source.{table}")
            counts[table] = _row_count(target, table)

        target.execute(
            "DELETE FROM core_schema_migrations WHERE scope = ?",
            (manifest.domain_id,),
        )
        target.execute(
            "INSERT INTO core_schema_migrations "
            "SELECT * FROM source.core_schema_migrations WHERE scope = ?",
            (manifest.domain_id,),
        )

        target.commit()
    finally:
        try:
            target.execute("DETACH DATABASE source")
        except sqlite3.Error:
            pass
        target.close()

    return counts


def verify_extraction(source_db: Path, manifest: CellManifest) -> tuple[str, ...]:
    """
    Poredi broj redova po tabeli u izvoru i u ćeliji.

    Tabele se upoređuju po uniji imena iz obe baze — izvor i ćelija mogu se
    razlikovati u šemi (zastarela tabela u CORE bazi koju ćelija više ne
    poznaje, ili obrnuto). Tabela koja postoji samo u jednoj od dve baze
    smatra se neslaganjem, bez pokušaja da se broje redovi tabele koja ne
    postoji.

    Args:
        source_db: Putanja CORE baze.
        manifest: Manifest ćelije.

    Returns:
        Sortirana imena tabela kod kojih se brojevi razlikuju ili tabela
        postoji samo u jednoj bazi. Prazna torka znači da je prenos ispravan.
    """
    source = sqlite3.connect(source_db)
    target = sqlite3.connect(manifest.database_path)

    mismatched: list[str] = []

    try:
        source_tables = set(domain_table_names(source, manifest.domain_id))
        target_tables = set(domain_table_names(target, manifest.domain_id))

        for table in sorted(source_tables | target_tables):
            if table not in source_tables or table not in target_tables or _row_count(source, table) != _row_count(target, table):
                mismatched.append(table)
    finally:
        source.close()
        target.close()

    return tuple(mismatched)
