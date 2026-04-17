"""
MORBION SCADA Server — Modbus TCP Client
Pure socket. No external libraries. FC03 read, FC06 write.
One responsibility: frame construction, transmission, response parsing.

Register addressing: 0-based (register 40001 = index 0).
All values returned as raw 16-bit unsigned integers.
Scaling to engineering units is the reader's responsibility.
"""

import socket
import struct
import logging

log = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

_TRANSACTION_ID = 0x0001
_PROTOCOL_ID    = 0x0000
_UNIT_ID        = 0x01
_MBAP_SIZE      = 7       # bytes in Modbus TCP header


class ModbusError(Exception):
    """Raised on Modbus exception responses or communication failure."""


class ModbusClient:
    """
    Minimal, correct Modbus TCP client.

    Each call opens a fresh TCP connection and closes it after.
    No persistent connection — OT field devices are not HTTP servers.
    Connection failures are isolated per call.
    """

    def __init__(self, host: str, port: int, timeout: float = 3.0):
        if not host:
            raise ValueError("host must be a non-empty string")
        if not (1 <= port <= 65535):
            raise ValueError(f"port {port} out of range 1-65535")
        if timeout <= 0:
            raise ValueError("timeout must be positive")

        self.host    = host
        self.port    = port
        self.timeout = timeout

    # ── Internal ──────────────────────────────────────────────────────────────

    def _build_request(self, pdu: bytes) -> bytes:
        """Wrap PDU in MBAP header."""
        length = 1 + len(pdu)   # unit_id byte + PDU
        header = struct.pack('>HHHB',
                             _TRANSACTION_ID,
                             _PROTOCOL_ID,
                             length,
                             _UNIT_ID)
        return header + pdu

    def _transact(self, request: bytes) -> bytes:
        """
        Open TCP connection, send request, receive full response, close.
        Reads MBAP header first to determine exact response length.
        Then reads exactly that many bytes — works for FC03 and FC06.
        """
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(self.timeout)
            s.connect((self.host, self.port))
            s.sendall(request)
    
            # Read MBAP header — always exactly 7 bytes
            header = b''
            while len(header) < _MBAP_SIZE:
                chunk = s.recv(_MBAP_SIZE - len(header))
                if not chunk:
                    raise ModbusError(
                        "Connection closed during header read")
                header += chunk
    
            # MBAP length field tells us exactly how many more bytes
            # length = number of bytes following (unit_id + PDU)
            _, _, length, _ = struct.unpack('>HHHB', header)
            remaining = length - 1   # subtract unit_id already in header
    
            payload = b''
            while len(payload) < remaining:
                chunk = s.recv(remaining - len(payload))
                if not chunk:
                    raise ModbusError(
                        "Connection closed during payload read")
                payload += chunk
    
            s.close()
            return header + payload
    
        except ModbusError:
            raise
        except socket.timeout:
            raise ModbusError(
                f"Timeout after {self.timeout}s "
                f"connecting to {self.host}:{self.port}")
        except ConnectionRefusedError:
            raise ModbusError(
                f"Connection refused — "
                f"{self.host}:{self.port} not listening")
        except OSError as e:
            raise ModbusError(f"Network error: {e}")
        finally:
            try:
                s.close()
            except Exception:
                pass
    def _check_exception(self, response: bytes, expected_fc: int) -> None:
        """
        Check if response is a Modbus exception response.
        Exception responses have function code = requested_fc | 0x80.
        """
        if len(response) < _MBAP_SIZE + 1:
            raise ModbusError(f"Response too short: {len(response)} bytes")
        response_fc = response[_MBAP_SIZE]
        if response_fc == (expected_fc | 0x80):
            exception_code = response[_MBAP_SIZE + 1] if len(response) > _MBAP_SIZE + 1 else 0
            raise ModbusError(f"Modbus exception code {exception_code} for FC{expected_fc:02X}")

    # ── Public API ────────────────────────────────────────────────────────────

    def read_registers(self, start: int, count: int) -> list[int]:
        """
        FC03 — Read Holding Registers.
        start : 0-based register index (40001 = 0)
        count : number of registers to read (1-125)
        Returns list of raw 16-bit unsigned integers.
        Raises ModbusError on failure.
        """
        if not (0 <= start <= 65535):
            raise ValueError(f"start {start} out of range")
        if not (1 <= count <= 125):
            raise ValueError(f"count {count} must be 1-125")

        pdu      = struct.pack('>BHH', 0x03, start, count)
        request  = self._build_request(pdu)
        response = self._transact(request)

        self._check_exception(response, 0x03)

        # Expected: MBAP(7) + FC(1) + byte_count(1) + data(count*2)
        expected = _MBAP_SIZE + 1 + 1 + count * 2
        if len(response) < expected:
            raise ModbusError(
                f"FC03 response too short: got {len(response)}, expected {expected}")

        byte_count = response[_MBAP_SIZE + 1]
        if byte_count != count * 2:
            raise ModbusError(
                f"FC03 byte count mismatch: got {byte_count}, expected {count * 2}")

        data_start = _MBAP_SIZE + 2
        values = list(struct.unpack(f'>{count}H', response[data_start:data_start + count * 2]))
        return values

    def write_register(self, register: int, value: int) -> bool:
        """
        FC06 — Write Single Register.
        register : 0-based register index
        value    : 16-bit unsigned integer (0-65535)
        Returns True if write confirmed by echo response.
        Raises ModbusError on communication failure.
        """
        if not (0 <= register <= 65535):
            raise ValueError(f"register {register} out of range")
        if not (0 <= value <= 65535):
            raise ValueError(f"value {value} out of range 0-65535")

        pdu      = struct.pack('>BHH', 0x06, register, value)
        request  = self._build_request(pdu)
        response = self._transact(request)

        self._check_exception(response, 0x06)

        # FC06 echo: response should mirror the request PDU
        if len(response) < _MBAP_SIZE + 5:
            raise ModbusError(f"FC06 response too short: {len(response)} bytes")

        echo_fc  = response[_MBAP_SIZE]
        echo_reg = struct.unpack('>H', response[_MBAP_SIZE + 1:_MBAP_SIZE + 3])[0]
        echo_val = struct.unpack('>H', response[_MBAP_SIZE + 3:_MBAP_SIZE + 5])[0]

        confirmed = (echo_fc == 0x06 and echo_reg == register and echo_val == value)
        if not confirmed:
            log.warning("FC06 echo mismatch: fc=%02X reg=%d val=%d", echo_fc, echo_reg, echo_val)
        return confirmed
