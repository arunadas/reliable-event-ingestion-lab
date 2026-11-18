from __future__ import annotations

import sys
import threading
from typing import TextIO

from reliable_ingestion.consumer.envelope import SourceRecord

AFTER_DB_COMMIT = "after_db_commit"
SYNC_LINE_PREFIX = "SYNC_POINT"


class SyncPoints:
    """Test-only pause points. Disabled unless a point name is configured.

    When the configured point is reached, one line is written and flushed,
    then the calling thread blocks until the process is killed.
    """

    def __init__(
        self,
        enabled_point: str | None = None,
        only_at: tuple[int, int] | None = None,
        stream: TextIO | None = None,
    ) -> None:
        self._enabled_point = enabled_point
        self._only_at = only_at
        self._stream = stream

    def reached(self, name: str, record: SourceRecord) -> None:
        if self._enabled_point is None or name != self._enabled_point:
            return
        if self._only_at is not None and self._only_at != (
            record.partition,
            record.offset,
        ):
            return
        stream = self._stream if self._stream is not None else sys.stdout
        stream.write(
            f"{SYNC_LINE_PREFIX} {name} {record.topic} "
            f"{record.partition} {record.offset}\n"
        )
        stream.flush()
        self._block()

    def _block(self) -> None:
        threading.Event().wait()
