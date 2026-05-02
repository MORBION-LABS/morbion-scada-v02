"""
core/history.py — MORBION Command History
MORBION SCADA v02

Disk-persisted command history.
Supports up/down navigation, search, and deduplication.
History file defaults to ~/.morbion_history.
Max 500 entries — oldest trimmed automatically.
"""

import os
from typing import List, Optional


class CommandHistory:
    """
    Persistent command history with navigation.

    Usage:
        h = CommandHistory("~/.morbion_history")
        h.append("read boiler")
        h.prev()        # navigate backwards
        h.next()        # navigate forwards
        h.search("bo")  # search backward
    """

    MAX_ENTRIES = 500

    def __init__(self, filepath: str = "~/.morbion_history"):
        self._path    = os.path.expanduser(filepath)
        self._entries: List[str] = []
        self._pos:     int       = 0   # 0 = after last entry (current input)
        self._current: str       = ""  # buffer for current (unsaved) input
        self._load()

    # ── Load / Save ───────────────────────────────────────────────────────────

    def _load(self):
        """Load history from disk. Silently handles missing file."""
        if not os.path.exists(self._path):
            return
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                lines = [line.rstrip("\n") for line in f]
            self._entries = [l for l in lines if l.strip()]
            self._trim()
            self._pos = len(self._entries)
        except OSError:
            pass

    def save(self):
        """Write history to disk. Silently handles write errors."""
        try:
            os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
            with open(self._path, "w", encoding="utf-8") as f:
                for entry in self._entries:
                    f.write(entry + "\n")
        except OSError:
            pass

    def _trim(self):
        if len(self._entries) > self.MAX_ENTRIES:
            self._entries = self._entries[-self.MAX_ENTRIES:]

    # ── Append ────────────────────────────────────────────────────────────────

    def append(self, command: str):
        """
        Add a command to history.
        Deduplicates: if same as last entry, skip.
        Resets navigation to end.
        Saves to disk after every append.
        """
        command = command.strip()
        if not command:
            return
        # Dedup: remove previous identical entry, add at end
        if self._entries and self._entries[-1] == command:
            pass  # already last entry — skip
        else:
            self._entries.append(command)
            self._trim()
        self._pos = len(self._entries)
        self._current = ""
        self.save()

    # ── Navigation ────────────────────────────────────────────────────────────

    def set_current(self, text: str):
        """
        Store the current (unsaved) input before navigating.
        Call this with the current input line before calling prev() or next().
        """
        if self._pos == len(self._entries):
            self._current = text

    def prev(self) -> Optional[str]:
        """Navigate backwards (older). Returns entry string or None if at start."""
        if not self._entries:
            return None
        if self._pos > 0:
            self._pos -= 1
        return self._entries[self._pos]

    def next(self) -> Optional[str]:
        """Navigate forwards (newer). Returns entry or current buffer if at end."""
        if self._pos < len(self._entries):
            self._pos += 1
        if self._pos == len(self._entries):
            return self._current
        return self._entries[self._pos]

    def reset_navigation(self):
        """Reset navigation position to end (current input)."""
        self._pos = len(self._entries)

    # ── Search ────────────────────────────────────────────────────────────────

    def search(self, term: str, from_pos: Optional[int] = None) -> Optional[str]:
        """
        Search backwards from from_pos (default: current pos) for term.
        Returns matching entry or None.
        """
        term = term.lower()
        start = from_pos if from_pos is not None else self._pos
        for i in range(start - 1, -1, -1):
            if term in self._entries[i].lower():
                self._pos = i
                return self._entries[i]
        return None

    # ── Introspection ─────────────────────────────────────────────────────────

    def get_entries(self, n: Optional[int] = None) -> List[str]:
        """Return last n entries (all if n is None)."""
        if n is None:
            return list(self._entries)
        return list(self._entries[-n:])

    def search_entries(self, term: str) -> List[str]:
        """Return all entries containing term (case-insensitive)."""
        term = term.lower()
        return [e for e in self._entries if term in e.lower()]

    def __len__(self) -> int:
        return len(self._entries)
