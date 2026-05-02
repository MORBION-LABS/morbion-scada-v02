"""
history.py — MSL Command History Manager
MORBION SCADA v02

Handles persistence and retrieval of terminal commands.
Saves history to disk to allow recall across sessions.
"""

import os
import json
import logging

log = logging.getLogger("history")

HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".morbion_history")
MAX_HISTORY = 500

class CommandHistory:
    def __init__(self):
        self._commands = []
        self._index = -1
        self.load()

    def append(self, command: str):
        """Add a new command to history and persist to disk."""
        cmd = command.strip()
        if not cmd:
            return

        # Don't duplicate the immediate last command
        if self._commands and self._commands[-1] == cmd:
            self._index = -1
            return

        self._commands.append(cmd)
        
        # Keep within buffer limits
        if len(self._commands) > MAX_HISTORY:
            self._commands.pop(0)

        self._index = -1
        self.save()

    def get_all(self, limit: int = None) -> list:
        """Return all history items, optionally limited to last N."""
        if limit:
            return self._commands[-limit:]
        return self._commands

    def search(self, term: str) -> list:
        """Search history for a specific term."""
        return [cmd for cmd in self._commands if term.lower() in cmd.lower()]

    def clear(self):
        """Purge all history."""
        self._commands = []
        self._index = -1
        self.save()

    # ── Persistence ──────────────────────────────────────────────────────────

    def load(self):
        """Load history from hidden disk file."""
        if not os.path.exists(HISTORY_FILE):
            self._commands = []
            return

        try:
            with open(HISTORY_FILE, "r") as f:
                self._commands = json.load(f)
            log.info(f"Loaded {len(self._commands)} history items.")
        except Exception as e:
            log.warning(f"Failed to load history: {e}")
            self._commands = []

    def save(self):
        """Save history to hidden disk file."""
        try:
            with open(HISTORY_FILE, "w") as f:
                json.dump(self._commands, f)
        except Exception as e:
            log.error(f"Failed to save history: {e}")

    # ── Navigation (for TUI Input) ───────────────────────────────────────────

    def get_next(self) -> str:
        """Navigate 'down' the history stack (towards newer)."""
        if not self._commands:
            return ""
        
        if self._index < len(self._commands) - 1:
            self._index += 1
            return self._commands[self._index]
        else:
            self._index = -1 # Reset to empty prompt
            return ""

    def get_prev(self) -> str:
        """Navigate 'up' the history stack (towards older)."""
        if not self._commands:
            return ""

        if self._index == -1:
            self._index = len(self._commands) - 1
        elif self._index > 0:
            self._index -= 1
            
        return self._commands[self._index]
