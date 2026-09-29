import codecs
import re
from collections.abc import Iterable
from typing import ClassVar

from core.domains.filmium.subtitle_inspector_models import (
    SubtitleInspectionResult,
    SubtitleIssue,
    SubtitleIssueSeverity,
    SubtitleIssueType,
    SubtitleRepairChange,
    SubtitleRepairPreview,
)

# ==========          GRESKE INSPEKTORA          ==========

class SubtitleInspectionValidationError(ValueError):
    """Oznacava datoteku koju inspektor ne moze bezbedno analizirati."""


# ==========          SUBTITLE INSPECTOR          ==========

class SubtitleInspectorService:
    """Otkriva probleme prevoda bez menjanja originalne datoteke."""

    _MAX_FILE_SIZE = 10 * 1024 * 1024
    _TIMESTAMP_PATTERN = re.compile(
        r"^\s*\d{1,2}:\d{2}:\d{2}[,.]\d{3}\s+-->\s+"
        r"\d{1,2}:\d{2}:\d{2}[,.]\d{3}"
    )
    _SERBIAN_WORDS = frozenset(
        {
            "ako",
            "ali",
            "bih",
            "bila",
            "bili",
            "bio",
            "biće",
            "da",
            "dobro",
            "gde",
            "hoću",
            "i",
            "ima",
            "iz",
            "ja",
            "je",
            "kada",
            "kao",
            "ko",
            "koji",
            "me",
            "mi",
            "moj",
            "na",
            "ne",
            "nije",
            "od",
            "on",
            "ona",
            "ovo",
            "sam",
            "se",
            "si",
            "smo",
            "sta",
            "ste",
            "što",
            "su",
            "sve",
            "ti",
            "to",
            "treba",
            "u",
            "za",
        }
    )
    _MOJIBAKE_REPLACEMENTS: ClassVar = {
        "Ä": "č",
        "Ä‡": "ć",
        "Å¾": "ž",
        "Å¡": "š",
        "Ä‘": "đ",
        "ÄŒ": "Č",
        "Ä†": "Ć",
        "Å½": "Ž",
        "Å\u00a0": "Š",
        "Ä": "Đ",
        "â€“": "–",
        "â€”": "—",
        "â€¦": "…",
        "â€ž": "„",
        "â€œ": "“",
        "â€": "”",
        "â€™": "’",
        "Â\u00a0": " ",
    }
    _SUSPICIOUS_CHARACTERS = frozenset(
        {
            "\ufffd",
            "\x00",
        }
    )
    # cp1252 C1 bajtovi (0x80-0x9F) pogrešno dekodirani kao kontrolni
    # znakovi — npr. „š"/„Š"/„ž"/„Ž" upisani cp1252 vrednostima u
    # iso-8859-2/latin fajlu. Ovi znaci nikada ne postoje u ispravnom
    # tekstu, pa se bezbedno mapiraju na svoje cp1252 značenje.
    _CP1252_C1: ClassVar = {
        chr(_byte): bytes([_byte]).decode("cp1252", errors="ignore")
        for _byte in range(0x80, 0xA0)
        if bytes([_byte]).decode("cp1252", errors="ignore")
    }
    # Potpisi prevodioca / sinhronizacije i URL-ovi — cele cue-ove koji
    # sadrže ovo treba ukloniti iz prevoda.
    _CREDIT_PATTERN = re.compile(
        r"(https?://|www\.|opensubtitles|titlovi\.\w+|\.(com|net|org|rs)\b"
        r"|\bsync\b|synced|sinhronizov|\bpreveo\b|\bprevela\b"
        r"|\bpreveli\b|\bprijevod\b|\bprevod\s*:|\bobrada\s*:"
        r"|\badaptacija\b"
        # YTS/YIFY promo (YTS.MX, YTS.BZ...) i tipični potpisi revizije.
        r"|\byts\b|\byify\b|downloaded\s+from|official\s+yify"
        r"|preuzeto\s+sa|zvani\w*\s+yify|ad-?lib\s+verzija"
        r"|zasnovan\w*\s+na\s+original|revizija\s+zasnovana"
        r"|prutswerk|metalmanij|icie@|beechan"
        # Mejl adresa u potpisu (npr. vajee555@gmail.com).
        r"|[\w.+-]+@[\w.-]+\.[a-z]{2,})",
        re.IGNORECASE,
    )
    # „Typewriter" potpis: fraza se ispisuje slovo-po-slovo kroz niz kratkih
    # uzastopnih cue-ova (npr. „O" → „Ow" → … → „Owned by Vajira Lasantha").
    # Detekcija je jezički nezavisna — oslanja se na STRUKTURU (rast dužine
    # dijaloga od jednog znaka kroz mnogo cue-ova), ne na ključne reči, jer
    # prevod menja same reči u hodu.
    _WATERMARK_MIN_RUN = 6
    _WATERMARK_START_MAX_LEN = 3
    _WATERMARK_DIP_TOLERANCE = 3
    _WATERMARK_MAX_STEP = 10
    _WATERMARK_MIN_FINAL_LEN = 8
    # Zvučne oznake u uglastim zagradama, npr. [Grgljanje], [Zvižduci].
    _BRACKET_CUE_PATTERN = re.compile(r"\[[^\]]*\]")
    _TAG_RE = re.compile(r"<[^>]+>")

    def inspect(
        self,
        content: bytes,
        file_name: str,
    ) -> SubtitleInspectionResult:
        """Dekodira i analizira prevod bez upisa na disk."""

        self._validate_input(content, file_name)

        # Binaran/sumnjiv fajl (nije tekstualni prevod): ne dekoduj i ne nudi
        # „popravku" mojibake — samo prijavi. Moguće preimenovan izvršni /
        # šifrovan / oštećen fajl.
        if self._looks_binary(content):
            return SubtitleInspectionResult(
                file_name=file_name,
                detected_encoding="binarno",
                detected_language_code=None,
                language_confidence=0.0,
                is_probably_serbian=False,
                needs_repair=False,
                issues=(
                    SubtitleIssue(
                        issue_type=(
                            SubtitleIssueType.BINARY_OR_SUSPICIOUS
                        ),
                        severity=SubtitleIssueSeverity.ERROR,
                        message=(
                            "Fajl nije tekstualni prevod — sadržaj je "
                            "binaran (moguće preimenovan izvršni, šifrovan "
                            "ili oštećen fajl). Ne otvarati; preporučuje se "
                            "brisanje."
                        ),
                    ),
                ),
                decoded_text="",
            )

        decoded_text, encoding, decode_issue = self._decode(content)
        issues: list[SubtitleIssue] = []

        if decode_issue is not None:
            issues.append(decode_issue)

        issues.extend(self._find_text_issues(decoded_text))
        issues.extend(self._find_credit_issues(decoded_text))
        issues.extend(self._find_bracket_cue_issues(decoded_text))
        issues.extend(self._find_watermark_sequence_issues(decoded_text))

        if not self._has_valid_srt_structure(decoded_text):
            issues.append(
                SubtitleIssue(
                    issue_type=SubtitleIssueType.INVALID_SRT_STRUCTURE,
                    severity=SubtitleIssueSeverity.WARNING,
                    message=(
                        "Datoteka nema prepoznatljivu SRT vremensku "
                        "strukturu."
                    ),
                )
            )

        language_code, confidence = self._detect_language(decoded_text)
        needs_repair = any(
            issue.issue_type
            in {
                SubtitleIssueType.INVALID_ENCODING,
                SubtitleIssueType.MOJIBAKE,
                SubtitleIssueType.REPLACEMENT_CHARACTER,
                SubtitleIssueType.SUSPICIOUS_CHARACTER,
                SubtitleIssueType.CREDIT_LINE,
                SubtitleIssueType.BRACKET_CUE,
                SubtitleIssueType.PROGRESSIVE_WATERMARK,
            }
            for issue in issues
        )

        return SubtitleInspectionResult(
            file_name=file_name,
            detected_encoding=encoding,
            detected_language_code=language_code,
            language_confidence=confidence,
            is_probably_serbian=(
                language_code in {"sr", "sr-Latn", "sr-Cyrl"}
                and confidence >= 0.45
            ),
            needs_repair=needs_repair,
            issues=tuple(issues),
            decoded_text=decoded_text,
        )

    def create_repair_preview(
        self,
        inspection: SubtitleInspectionResult,
    ) -> SubtitleRepairPreview:
        """Pravi pregled samo pouzdanih zamena mojibake znakova."""

        repaired_lines: list[str] = []
        changes: list[SubtitleRepairChange] = []

        for line_number, line in enumerate(
            inspection.decoded_text.splitlines(keepends=True),
            start=1,
        ):
            repaired = self._repair_known_mojibake(line)
            repaired_lines.append(repaired)

            if repaired != line:
                changes.append(
                    SubtitleRepairChange(
                        line_number=line_number,
                        original_text=line.rstrip("\r\n"),
                        repaired_text=repaired.rstrip("\r\n"),
                    )
                )

        repaired_text = "".join(repaired_lines)
        # Watermark-niz PRVI: dok je završna potpis/mejl linija još prisutna
        # ona razdvaja „typewriter" niz od pravog dijaloga (veliki skok dužine
        # prekida niz). Kada bi credit-strip prvo uklonio tu liniju, prvi red
        # pravog dijaloga bi se spojio na niz i greškom bio uklonjen.
        repaired_text = self._strip_watermark_sequences(repaired_text)
        repaired_text = self._strip_bracket_cues(repaired_text)
        repaired_text = self._strip_credits(repaired_text)

        return SubtitleRepairPreview(
            file_name=inspection.file_name,
            detected_encoding=inspection.detected_encoding,
            detected_language_code=(
                inspection.detected_language_code
            ),
            original_text=inspection.decoded_text,
            repaired_text=repaired_text,
            changes=tuple(changes),
        )

    def _validate_input(
        self,
        content: bytes,
        file_name: str,
    ) -> None:
        if not file_name.strip().lower().endswith(".srt"):
            raise SubtitleInspectionValidationError(
                "Subtitle Inspector trenutno podrzava samo SRT datoteke."
            )

        if not content:
            raise SubtitleInspectionValidationError(
                "Datoteka prevoda je prazna."
            )

        if len(content) > self._MAX_FILE_SIZE:
            raise SubtitleInspectionValidationError(
                "Datoteka prevoda je veca od dozvoljenih 10 MB."
            )

    @staticmethod
    def _looks_binary(content: bytes) -> bool:
        """
        True ako fajl nije tekstualni prevod nego binaran sadržaj.

        Redosled provera (da se ne označi lažno pravi prevod, npr. ćirilica
        u UTF-8/cp1251 koja ima mnogo high bajtova):
          1. BOM (UTF-8/UTF-16) → tekst.
          2. NUL bajt (bez BOM-a) → binarno.
          3. Validan UTF-8 → tekst.
          4. Sadrži SRT strelicu „-->" (uvek ASCII) → tekst.
          5. Inače: > 30% bajtova van štampljivog ASCII-ja → binarno.
        """

        if not content:
            return False

        for bom in (b"\xef\xbb\xbf", b"\xff\xfe", b"\xfe\xff"):
            if content.startswith(bom):
                return False

        sample = content[:8192]
        if b"\x00" in sample:
            return True

        try:
            sample.decode("utf-8")
            return False
        except UnicodeDecodeError:
            pass

        if b"-->" in content[:65536]:
            return False

        text_bytes = set(range(0x20, 0x7F)) | {0x09, 0x0A, 0x0D, 0x0C}
        non_text = sum(1 for byte in sample if byte not in text_bytes)
        return non_text / len(sample) > 0.30

    def _decode(
        self,
        content: bytes,
    ) -> tuple[str, str, SubtitleIssue | None]:
        bom_encodings = (
            (codecs.BOM_UTF8, "utf-8-sig"),
            (codecs.BOM_UTF16_LE, "utf-16"),
            (codecs.BOM_UTF16_BE, "utf-16"),
        )

        for bom, encoding in bom_encodings:
            if content.startswith(bom):
                return content.decode(encoding), encoding, None

        try:
            return content.decode("utf-8"), "utf-8", None
        except UnicodeDecodeError:
            pass

        candidates: list[tuple[int, str, str]] = []

        for encoding in ("cp1250", "iso-8859-2", "cp1252"):
            try:
                text = content.decode(encoding)
            except UnicodeDecodeError:
                continue

            candidates.append(
                (
                    self._decoding_score(text),
                    encoding,
                    text,
                )
            )

        if not candidates:
            text = content.decode("utf-8", errors="replace")
            return (
                text,
                "utf-8-replacement",
                SubtitleIssue(
                    issue_type=SubtitleIssueType.INVALID_ENCODING,
                    severity=SubtitleIssueSeverity.ERROR,
                    message=(
                        "Kodiranje nije moglo pouzdano da bude "
                        "prepoznato."
                    ),
                ),
            )

        _, encoding, text = max(candidates, key=lambda item: item[0])
        return (
            text,
            encoding,
            SubtitleIssue(
                issue_type=SubtitleIssueType.INVALID_ENCODING,
                severity=SubtitleIssueSeverity.INFO,
                message=(
                    f"Datoteka nije UTF-8; prepoznato je {encoding} "
                    "kodiranje."
                ),
            ),
        )

    def _find_text_issues(
        self,
        text: str,
    ) -> Iterable[SubtitleIssue]:
        for line_number, line in enumerate(text.splitlines(), start=1):
            repaired = self._repair_known_mojibake(line)

            if repaired != line:
                yield SubtitleIssue(
                    issue_type=SubtitleIssueType.MOJIBAKE,
                    severity=SubtitleIssueSeverity.WARNING,
                    message="Pronadjeni su pogresno dekodirani znakovi.",
                    line_number=line_number,
                    original_text=line,
                    suggested_text=repaired,
                )

            if "\ufffd" in line:
                yield SubtitleIssue(
                    issue_type=(
                        SubtitleIssueType.REPLACEMENT_CHARACTER
                    ),
                    severity=SubtitleIssueSeverity.ERROR,
                    message=(
                        "Red sadrzi znak zamene; originalni znak nije "
                        "mogao da bude procitan."
                    ),
                    line_number=line_number,
                    original_text=line,
                )

            if any(
                character in line
                for character in self._SUSPICIOUS_CHARACTERS
                if character != "\ufffd"
            ):
                yield SubtitleIssue(
                    issue_type=SubtitleIssueType.SUSPICIOUS_CHARACTER,
                    severity=SubtitleIssueSeverity.WARNING,
                    message="Red sadrzi sumnjiv kontrolni znak.",
                    line_number=line_number,
                    original_text=line,
                )

    @classmethod
    def _find_credit_issues(cls, text: str):
        for line_number, line in enumerate(text.splitlines(), start=1):
            stripped = cls._TAG_RE.sub(" ", line)
            if cls._CREDIT_PATTERN.search(stripped):
                yield SubtitleIssue(
                    issue_type=SubtitleIssueType.CREDIT_LINE,
                    severity=SubtitleIssueSeverity.WARNING,
                    message=(
                        "Red je potpis prevodioca ili URL; bice uklonjen."
                    ),
                    line_number=line_number,
                    original_text=line,
                )

    @classmethod
    def _find_bracket_cue_issues(cls, text: str):
        for line_number, line in enumerate(text.splitlines(), start=1):
            if "-->" in line or line.strip().isdigit():
                continue
            if cls._BRACKET_CUE_PATTERN.search(line):
                yield SubtitleIssue(
                    issue_type=SubtitleIssueType.BRACKET_CUE,
                    severity=SubtitleIssueSeverity.WARNING,
                    message=(
                        "Red sadrzi zvučnu oznaku u uglastim zagradama; "
                        "bice uklonjena."
                    ),
                    line_number=line_number,
                    original_text=line,
                )

    @classmethod
    def _strip_bracket_cues(cls, text: str) -> str:
        blocks = re.split(r"\r?\n[ \t]*\r?\n", text)
        kept: list[str] = []
        for block in blocks:
            lines = block.splitlines()
            rebuilt: list[str] = []
            dialogue_before = 0
            dialogue_after = 0
            for line in lines:
                if "-->" in line or line.strip().isdigit():
                    rebuilt.append(line)
                    continue
                dialogue_before += 1
                cleaned = cls._BRACKET_CUE_PATTERN.sub("", line)
                cleaned = re.sub(r"[ \t]{2,}", " ", cleaned).strip()
                if cleaned:
                    dialogue_after += 1
                    rebuilt.append(cleaned)
            # Cue je bio samo zvučna oznaka u zagradama → izbaci ceo cue.
            if dialogue_before > 0 and dialogue_after == 0:
                continue
            trimmed = "\n".join(rebuilt).strip("\r\n")
            if trimmed:
                kept.append(trimmed)
        result = "\n\n".join(kept)
        return result + "\n" if result else result

    @classmethod
    def _strip_credits(cls, text: str) -> str:
        blocks = re.split(r"\r?\n[ \t]*\r?\n", text)
        kept: list[str] = []
        for block in blocks:
            lines = block.splitlines()
            text_lines = [
                line
                for line in lines
                if "-->" not in line and not line.strip().isdigit()
            ]
            combined = cls._TAG_RE.sub(" ", " ".join(text_lines))
            if text_lines and cls._CREDIT_PATTERN.search(combined):
                continue
            trimmed = block.strip("\r\n")
            if trimmed:
                kept.append(trimmed)
        result = "\n\n".join(kept)
        return result + "\n" if result else result

    @classmethod
    def _block_dialogue(cls, block: str) -> str:
        """Vraća čist dijalog jednog SRT bloka (bez indeksa/vremena/tagova)."""

        text_lines = [
            line
            for line in block.splitlines()
            if "-->" not in line and not line.strip().isdigit()
        ]
        combined = cls._TAG_RE.sub(" ", " ".join(text_lines))
        return re.sub(r"\s+", " ", combined).strip()

    @classmethod
    def _detect_watermark_runs(
        cls,
        dialogues: list[str],
    ) -> set[int]:
        """
        Indeksi blokova koji pripadaju „typewriter" potpisu.

        Niz je prihvaćen kao potpis ako počinje vrlo kratkim dijalogom
        (≤ START_MAX_LEN znakova) i dužina raste kroz najmanje MIN_RUN
        uzastopnih blokova (uz toleranciju na sitne padove — prevod menja
        reči — i uz ograničenje maksimalnog skoka po koraku).
        """

        lengths = [len(text) for text in dialogues]
        flagged: set[int] = set()
        i = 0
        n = len(lengths)

        while i < n:
            if lengths[i] == 0 or lengths[i] > cls._WATERMARK_START_MAX_LEN:
                i += 1
                continue

            running_max = lengths[i]
            j = i
            while j + 1 < n:
                nxt = lengths[j + 1]
                if nxt == 0:
                    break
                # Sitan pad ispod dostignutog maksimuma je dozvoljen; veći
                # pad ili preveliki skok naviše prekida niz.
                if nxt < running_max - cls._WATERMARK_DIP_TOLERANCE:
                    break
                if nxt > running_max + cls._WATERMARK_MAX_STEP:
                    break
                running_max = max(running_max, nxt)
                j += 1

            run_len = j - i + 1
            if (
                run_len >= cls._WATERMARK_MIN_RUN
                and running_max >= cls._WATERMARK_MIN_FINAL_LEN
            ):
                flagged.update(range(i, j + 1))
                i = j + 1
            else:
                i += 1

        return flagged

    @classmethod
    def _find_watermark_sequence_issues(cls, text: str):
        blocks = re.split(r"\r?\n[ \t]*\r?\n", text)
        dialogues = [cls._block_dialogue(block) for block in blocks]
        flagged = cls._detect_watermark_runs(dialogues)
        if not flagged:
            return
        first = min(flagged)
        yield SubtitleIssue(
            issue_type=SubtitleIssueType.PROGRESSIVE_WATERMARK,
            severity=SubtitleIssueSeverity.WARNING,
            message=(
                "Prevod sadrži potpis ispisan slovo-po-slovo kroz niz "
                "cue-ova (vodeni žig); ceo niz će biti uklonjen."
            ),
            original_text=dialogues[max(flagged)] or None,
            line_number=None if not blocks else first + 1,
        )

    @classmethod
    def _strip_watermark_sequences(cls, text: str) -> str:
        blocks = re.split(r"\r?\n[ \t]*\r?\n", text)
        dialogues = [cls._block_dialogue(block) for block in blocks]
        flagged = cls._detect_watermark_runs(dialogues)
        if not flagged:
            return text
        kept = [
            block.strip("\r\n")
            for index, block in enumerate(blocks)
            if index not in flagged and block.strip("\r\n")
        ]
        result = "\n\n".join(kept)
        return result + "\n" if result else result

    @classmethod
    def _repair_known_mojibake(cls, text: str) -> str:
        repaired = text

        # Da li tekst sadrzi bar jedan NEDVOSMISLEN mojibake marker
        # (Å¡, Å¾, Ä‡, Å + NBSP, ...)? Bez markera ne diramo "Å " (obican
        # razmak) da ne pokvarimo legitiman norveski "Å " (npr. "Å ja").
        has_marker = any(key in text for key in cls._MOJIBAKE_REPLACEMENTS)

        for broken, correct in cls._MOJIBAKE_REPLACEMENTS.items():
            repaired = repaired.replace(broken, correct)

        for control, correct in cls._CP1252_C1.items():
            repaired = repaired.replace(control, correct)

        # Kapitalno Š (C5 A0) u mojibake obliku je "Å" + NBSP (0xA0). Kada
        # editor normalizuje NBSP u obican razmak dobijemo "Å ", sto mapa
        # gore ne hvata. Popravljamo SAMO ako je linija vec mojibake.
        if has_marker:
            repaired = repaired.replace("Å ", "Š")

        return repaired

    @classmethod
    def _decoding_score(cls, text: str) -> int:
        score = 0
        score += sum(
            text.count(character) * 4
            for character in "šđčćžŠĐČĆŽ"
        )
        score -= sum(
            text.count(character) * 8
            for character in ("\ufffd", "\x00")
        )
        score -= sum(
            text.count(marker) * 3
            for marker in cls._MOJIBAKE_REPLACEMENTS
        )
        return score

    @classmethod
    def _has_valid_srt_structure(cls, text: str) -> bool:
        return any(
            cls._TIMESTAMP_PATTERN.match(line)
            for line in text.splitlines()
        )

    @classmethod
    def _detect_language(
        cls,
        text: str,
    ) -> tuple[str | None, float]:
        dialogue_lines = [
            line
            for line in text.splitlines()
            if line.strip()
            and not line.strip().isdigit()
            and not cls._TIMESTAMP_PATTERN.match(line)
        ]
        words = re.findall(
            r"[A-Za-zČĆŽŠĐčćžšđ]+",
            " ".join(dialogue_lines).lower(),
        )

        if not words:
            return None, 0.0

        matches = sum(word in cls._SERBIAN_WORDS for word in words)
        diacritics = sum(
            any(character in word for character in "čćžšđ")
            for word in words
        )
        evidence = matches + min(diacritics, 5)
        confidence = min(1.0, evidence / max(5, len(words) * 0.22))

        if evidence < 2:
            return None, round(confidence, 2)

        return "sr-Latn", round(confidence, 2)
