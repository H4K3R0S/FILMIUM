"""SSE (Server-Sent Events) most za uvoz sa stvarnim per-fajl progresom.

Uvoz je sinhroni i koristi SQLite konekcije po operaciji. Zato ceo uvoz
radi u jednoj radnoj niti (sve konekcije nastaju u toj niti — bezbedno),
a progres se prenosi glavnoj niti preko ``queue.Queue``. Generator emituje
``event: progress`` po fajlu, pa ``event: done`` sa rezultatom ili
``event: error`` sa porukom.

Ovo je transport sloj (FastAPI); poslovna logika ostaje u servisima.
WebSocket se namerno ne uvodi — SSE pokriva jednosmerni progres.
"""

import json
import queue
import threading
from collections.abc import Callable, Iterator
from typing import Any

from fastapi.responses import StreamingResponse


def _sse(event: str, payload: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def import_progress_stream(
    run: Callable[[Callable[[int, int, int, int], None]], Any],
    serialize: Callable[[Any], dict[str, Any]],
) -> StreamingResponse:
    """
    Pokreće ``run(on_progress)`` u niti i strimuje progres kao SSE.

    ``run`` prima ``on_progress(fajlova_gotovo, fajlova_ukupno,
    bajtova_gotovo, bajtova_ukupno)`` i vraća rezultat uvoza. ``serialize``
    pretvara rezultat u JSON-friendly dict za ``done`` događaj.
    """

    events: queue.Queue[tuple[str, Any]] = queue.Queue()

    def worker() -> None:
        try:
            result = run(
                lambda files_done, files_total, file_done, file_total: (
                    events.put(
                        (
                            "progress",
                            {
                                "files_done": files_done,
                                "files_total": files_total,
                                "file_done": file_done,
                                "file_total": file_total,
                            },
                        )
                    )
                )
            )
            events.put(("done", serialize(result)))
        except Exception as error:  # noqa: BLE001 - poruka ide klijentu
            events.put(("error", {"message": str(error)}))
        finally:
            events.put(("__end__", None))

    threading.Thread(target=worker, daemon=True).start()

    def generate() -> Iterator[str]:
        while True:
            event, payload = events.get()
            if event == "__end__":
                break
            yield _sse(event, payload)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
