"""Filesystem watching utilities built on watchfiles (Rust notify backend).

This module provides a clean API over watchfiles for monitoring directories.
The processor uses watchfiles directly for its main loop, but this module
exposes reusable primitives for any consumer that needs directory watching.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from watchfiles import Change, watch


EventKind = Literal["created", "modified", "deleted"]

_CHANGE_TO_KIND: dict[Change, EventKind] = {
    Change.added: "created",
    Change.modified: "modified",
    Change.deleted: "deleted",
}


@dataclass(frozen=True)
class FileEvent:
    kind: EventKind
    path: Path


def watch_directory(
    directory: Path,
    *,
    on_created: Callable[[Path], None] | None = None,
    on_modified: Callable[[Path], None] | None = None,
    on_deleted: Callable[[Path], None] | None = None,
    stop_event: threading.Event | None = None,
    debounce_ms: int = 500,
    step_ms: int = 250,
    recursive: bool = False,
) -> None:
    """Watch a directory and dispatch callbacks for file events.

    Blocks until *stop_event* is set or the process is interrupted.
    """
    handlers: dict[EventKind, Callable[[Path], None]] = {}
    if on_created is not None:
        handlers["created"] = on_created
    if on_modified is not None:
        handlers["modified"] = on_modified
    if on_deleted is not None:
        handlers["deleted"] = on_deleted

    for changes in watch(
        str(directory),
        stop_event=stop_event,
        debounce=debounce_ms,
        step=step_ms,
        recursive=recursive,
        yield_on_timeout=True,
    ):
        for change_type, path_str in changes:
            kind = _CHANGE_TO_KIND.get(change_type)
            if kind is not None and kind in handlers:
                handlers[kind](Path(path_str))


def iter_file_events(
    directory: Path,
    *,
    stop_event: threading.Event | None = None,
    debounce_ms: int = 500,
    step_ms: int = 250,
    recursive: bool = False,
) -> Iterator[FileEvent]:
    """Yield ``FileEvent`` instances as files change in *directory*.

    The iterator terminates when *stop_event* is set.
    """
    for changes in watch(
        str(directory),
        stop_event=stop_event,
        debounce=debounce_ms,
        step=step_ms,
        recursive=recursive,
        yield_on_timeout=True,
    ):
        for change_type, path_str in changes:
            kind = _CHANGE_TO_KIND.get(change_type)
            if kind is not None:
                yield FileEvent(kind=kind, path=Path(path_str))
