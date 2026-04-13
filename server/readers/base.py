"""
MORBION SCADA Server — Base Reader
Abstract contract. Provides Modbus TCP read and common utilities.
"""

from abc import ABC, abstractmethod
from typing import Optional
import logging

from modbus.client import ModbusClient, ModbusError

log = logging.getLogger(__name__)


class BaseReader(ABC):
    """
    Base reader. Handles Modbus TCP connection lifecycle.
    Subclasses define register map and scaling only.
    """

    def __init__(self, host: str, port: int, timeout: float = 3.0):
        if not host:
            raise ValueError("host must be a non-empty string")
        if not (1 <= port <= 65535):
            raise ValueError(f"port {port} out of range 1-65535")

        self.host    = host
        self.port    = port
        self.timeout = timeout
        self.process_name = "unknown"

    @abstractmethod
    def read(self) -> dict:
        """
        Read process data from device.
        Returns dict with keys matching register map.
        Must handle offline devices gracefully.
        """

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _safe_read(self, count: int) -> Optional[list[int]]:
        """
        Read registers, returning None on any failure.
        Never raises. Logs errors.
        """
        try:
            client = ModbusClient(self.host, self.port, self.timeout)
            return client.read_registers(start=0, count=count)
        except ModbusError as e:
            log.warning("%s read failed: %s", self.process_name, e)
            return None
        except Exception as e:
            log.error("%s read unexpected error: %s", self.process_name, e)
            return None

    def _offline(self) -> dict:
        """Return standard offline dict for this process."""
        return {
            "online":   False,
            "process":  self.process_name,
            "label":    self.process_name.replace("_", " ").title(),
            "port":     self.port,
        }