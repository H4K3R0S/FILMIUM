"""Torrent greške korisničkog zahteva — izdvojeno radi veličine fajla."""


class TorrentServiceError(ValueError):
    """Neispravan zahtev korisnika (prazan izbor, nepoznat torrent, i slično)."""
