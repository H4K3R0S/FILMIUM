# ==========          AUTO UPDATE — PIPELINE JEDNOG NASLOVA          ==========
"""TMDB dopuna + srpska latinica (transliteracija/prevod) + ključne reči,
pa snimanje u bazu.

Deljeno jezgro: koristi ga i editor dugme „Updatuj" (preko API-ja) i budući
bulk cron. Bez UI-ja. Postojeća neprazna polja se ne gaze (fill-empty), osim
što se ćirilični opis uvek prevodi u latinicu.
"""

import re
from dataclasses import dataclass

from core.domains.filmium import tmdb_client
from core.domains.filmium.models import MediaItemCreate
from core.domains.filmium.transliteration import cyrillic_to_latin, is_cyrillic


@dataclass(frozen=True)
class AutoUpdateResult:
    matched: bool
    changed_fields: tuple[str, ...]
    message: str


def _to_latin(text: str | None) -> str | None:
    """Ćirilicu u latinicu; ostalo netaknuto."""

    if not text:
        return text
    return cyrillic_to_latin(text) if is_cyrillic(text) else text


def _trailing_number(text: str | None) -> int | None:
    """Redni broj na kraju naziva (npr. „Toy Story 4" → 4), inače None."""

    match = re.search(r"\s(\d{1,3})$", (text or "").strip())
    return int(match.group(1)) if match else None
# ==========          FAZE PIPELINE-A (izdvojene radi jasnoće)          ==========

def _fill(current, value, name, *, renamed, changed):
    """Fill-empty: popuni samo ako je trenutno prazno (ili prepiši pri
    preimenovanju u drugi nastavak). Beleži naziv polja u `changed`."""

    has_value = value and str(value).strip() != ""
    is_empty = not current or str(current).strip() == ""
    if has_value and (is_empty or renamed) and value != current:
        changed.append(name)
        return value
    return current


def _resolve_titles(item, enrichment, translator, *, renamed, changed):
    """Originalni + engleski naslov (fill-empty). Ako EN fali svuda, prevedi
    originalni na engleski (best-effort)."""

    original_title = _fill(item.original_title, enrichment.original_title,
                           "original_title", renamed=renamed, changed=changed)
    english_title = _fill(item.english_title, enrichment.english_title,
                          "english_title", renamed=renamed, changed=changed)
    if not (english_title and str(english_title).strip()):
        source_title = original_title or enrichment.original_title
        if source_title:
            try:
                translated = translator.translate(
                    source_title, source="auto", target="en"
                )
            except Exception:  # noqa: BLE001 — prevod je best-effort
                translated = None
            if translated and translated.strip():
                english_title = translated.strip()
                changed.append("english_title")
    return original_title, english_title


def _resolve_notes_local(item, enrichment, translator, *, renamed, changed):
    """Domaći naslov (latinica) + domaći opis: transliteracija postojećeg,
    inače TMDB lokalni opis, inače prevod EN opisa (srpska latinica)."""

    local_title = _to_latin(enrichment.local_title) if enrichment.local_title \
        else None
    # Pri preimenovanju stari opis pripada pogrešnom delu — osveži ga.
    notes = None if renamed else item.notes
    if notes:
        # Postoji domaći opis: samo ćirilicu prebaci u latinicu, ostalo ostaje.
        latin_notes = _to_latin(notes)
        if latin_notes != notes:
            changed.append("notes")
        notes = latin_notes
    elif enrichment.local_overview:
        notes = _to_latin(enrichment.local_overview)
        changed.append("notes")
    elif enrichment.english_overview or enrichment.english_title:
        translated_title, translated_overview = translator.translate_pair(
            enrichment.english_title or enrichment.original_title or "",
            enrichment.english_overview or "",
        )
        notes = _to_latin(translated_overview) or None
        if notes:
            changed.append("notes")
        if not local_title:
            local_title = _to_latin(translated_title) or None
    return notes, local_title


def _apply_local_title(settings, local_title, *, renamed, changed):
    """Domaći naslov u editor_settings.basic.local_title_sr (fill-empty; pri
    preimenovanju prepiši jer stari pripada pogrešnom nastavku). Menja `settings`."""

    basic = dict(settings.get("basic") or {})
    if local_title and (renamed or not basic.get("local_title_sr")) \
            and basic.get("local_title_sr") != local_title:
        basic["local_title_sr"] = local_title
        settings["basic"] = basic
        changed.append("local_title_sr")


def _translate_keywords(settings, keywords, translator, *, changed):
    """Prevedi nove TMDB ključne reči (EN→SR, srpska latinica) i DODAJ ih na
    postojeće (bez duplikata). Mapa {en: sr} u settings sprečava dupli prevod.
    Best-effort — greška prevodioca ne obara update. Menja `settings`, vraća
    ažurirane ključne reči."""

    translations = dict(settings.get("keyword_translations") or {})
    # „already" = reči koje su već engleski izvor ili već dodat srpski prevod.
    already = {word.lower() for word in translations}
    already |= {word.lower() for word in translations.values()}
    missing = [
        word for word in keywords if word and word.lower() not in already
    ]
    if missing:
        try:
            rendered = translator.translate_batch(missing, source="en", target="sr")
        except Exception:  # noqa: BLE001 — prevod je best-effort
            rendered = []
        additions: list[str] = []
        for source_word, translated in zip(missing, rendered):
            latin = _to_latin(translated)
            if latin and latin.strip() and latin.strip().lower() != source_word.lower():
                translations[source_word] = latin.strip()
                additions.append(latin.strip())
        if additions:
            settings["keyword_translations"] = translations
            keywords = tuple(dict.fromkeys((*keywords, *additions)))
    return keywords


def _run_external_enrichment(item_id):
    """POSLE TMDB upisa: best-effort dopuna iz spoljnih izvora (IMDb / Rotten
    Tomatoes / TVmaze / Jikan) — da „Updatuj" dugme istrajno snimi i spoljne
    podatke. Greška NIKAD ne obara auto-update; zasebna konekcija sa
    busy_timeout (živa ćelija, NTFS), commit u malom batch-u."""

    try:
        from core.domains.filmium.media_external import (
            apply_external_enrichment,
            open_connection,
        )

        con = open_connection()
        try:
            apply_external_enrichment(con, item_id)
            con.commit()
        finally:
            con.close()
    except Exception:  # noqa: BLE001, S110
        pass


def auto_update_item(
    item_id,
    service,
    translator,
    *,
    tmdb_id=None,
    override_title=None,
):
    """Kompletno dopuni jedan naslov iz TMDB-a i snimi. Vraća AutoUpdateResult."""

    item = service.get_media_item(item_id)
    media_type = item.media_type.value
    query = (item.original_title or item.title or "").strip()

    enrichment = tmdb_client.enrich_best(
        query,
        item.release_year,
        media_type,
        tmdb_id=tmdb_id,
        override_title=override_title,
        collection_hint=item.collection,
        # Vidljivi Naslov vodi tačan nastavak (npr. korisnik ispravio 3 → 4).
        title_hint=item.title,
    )
    if enrichment is None:
        return AutoUpdateResult(False, (), "TMDB nije pronašao ovaj naslov.")

    changed: list[str] = []

    # Preimenovanje u drugi nastavak: vidljivi Naslov nosi drugi redni broj od
    # (starog) originalnog naslova. Tada stara identifikaciona polja (originalni/
    # engleski naslov, godina, opisi) pripadaju pogrešnom delu — pa se PREPIŠU
    # tačnim TMDB podacima umesto fill-empty logike.
    renamed = (
        _trailing_number(item.title) is not None
        and _trailing_number(item.title) != _trailing_number(item.original_title)
    )

    original_title, english_title = _resolve_titles(
        item, enrichment, translator, renamed=renamed, changed=changed
    )
    english_description = _fill(item.english_description,
                               enrichment.english_overview,
                               "english_description", renamed=renamed,
                               changed=changed)
    studio = _fill(item.studio, enrichment.studio, "studio",
                   renamed=renamed, changed=changed)
    director = _fill(item.director, enrichment.director, "director",
                     renamed=renamed, changed=changed)

    # Pri preimenovanju godina starog dela je pogrešna — uzmi TMDB godinu.
    release_year = (
        enrichment.year
        if renamed and enrichment.year
        else (item.release_year or enrichment.year)
    )
    if release_year != item.release_year:
        changed.append("release_year")

    genres = tuple(dict.fromkeys((*item.genres, *enrichment.genres)))
    cast = tuple(dict.fromkeys((*(item.cast_names or ()), *enrichment.cast_names)))
    keywords = tuple(dict.fromkeys((*(item.keywords or ()), *enrichment.keywords)))

    notes, local_title = _resolve_notes_local(
        item, enrichment, translator, renamed=renamed, changed=changed
    )

    settings = dict(item.editor_settings or {})
    _apply_local_title(settings, local_title, renamed=renamed, changed=changed)
    keywords = _translate_keywords(settings, keywords, translator, changed=changed)

    if set(keywords) != set(item.keywords or ()):
        changed.append("keywords")

    # TMDB ID: popuni ako ga stavka još nema (fill-empty). Omogućava listi
    # „za preuzeti" pouzdano poklapanje kad naslov uđe u biblioteku.
    tmdb_identifier = item.tmdb_id or enrichment.tmdb_id
    if tmdb_identifier != item.tmdb_id:
        changed.append("tmdb_id")

    payload = MediaItemCreate(
        title=item.title,
        media_type=item.media_type,
        original_title=original_title,
        english_title=english_title,
        release_year=release_year,
        runtime_minutes=item.runtime_minutes,
        watch_status=item.watch_status,
        rating=item.rating,
        notes=notes,
        english_description=english_description,
        content_category=item.content_category,
        cast_names=cast,
        studio=studio,
        director=director,
        keywords=keywords,
        collection=item.collection or enrichment.collection,
        is_synchronized=item.is_synchronized,
        editor_settings=settings,
        genres=genres,
        is_favorite=item.is_favorite,
        tmdb_id=tmdb_identifier,
        related_tmdb=enrichment.recommendations,
    )
    service.update_media_item(item_id, payload)

    # Spoljna dopuna posle TMDB upisa (best-effort; nikad ne obara update).
    _run_external_enrichment(item_id)

    return AutoUpdateResult(True, tuple(changed), "Ažurirano i snimljeno.")
