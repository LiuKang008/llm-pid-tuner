#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hw/rtt_bridge.py - SEGGER J-Link RTT Telnet bridge.

This module intentionally mirrors the small interface used by SerialBridge:
    connect()
    disconnect()
    read_line()
    send_command(cmd)
    parse_data(line)

It is meant to be used first by tools/rtt_comm_test.py.  After the RTT link is
verified, tuner.py can switch from SerialBridge to this bridge with minimal
changes.
"""

from __future__ import annotations

import socket
import time
from typing import Dict, Optional


class RttTelnetBridge:
    """Simple line-oriented bridge for J-Link RTT Telnet channel 0.

    Typical port:
        127.0.0.1:19021

    One J-Link/Ozone/GDB/JLinkExe session must already expose the RTT Telnet
    server.  If J-Link RTT Client can read the target output on your PC, this
    bridge should normally be able to read from the same host/port after the
    competing client is closed.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 19021,
        timeout: float = 1.0,
        emit_console: bool = True,
    ) -> None:
        self.host = host
        self.port = int(port)
        self.timeout = float(timeout)
        self.emit_console = emit_console
        self.sock: Optional[socket.socket] = None
        self.rx_buf = b""
        self.last_error = ""

    @property
    def is_open(self) -> bool:
        return self.sock is not None

    def connect(self) -> bool:
        try:
            self.sock = socket.create_connection(
                (self.host, self.port),
                timeout=self.timeout,
            )
            self.sock.settimeout(self.timeout)
            self.rx_buf = b""
            self.last_error = ""
            if self.emit_console:
                print(f"[INFO] Connected to J-Link RTT Telnet {self.host}:{self.port}")
            return True
        except Exception as exc:  # pragma: no cover - depends on local hardware
            self.sock = None
            self.last_error = str(exc)
            if self.emit_console:
                print(f"[ERROR] RTT connection failed: {exc}")
            return False

    def disconnect(self) -> None:
        if self.sock is not None:
            try:
                self.sock.close()
            except Exception:
                pass
        self.sock = None
        self.rx_buf = b""

    def read_line(self) -> Optional[str]:
        """Read one '\n'-terminated RTT line.

        Returns:
            str: decoded line without CR/LF
            None: no complete line before timeout, or disconnected
        """
        if self.sock is None:
            self.last_error = "RTT bridge is not connected"
            return None

        try:
            while b"\n" not in self.rx_buf:
                chunk = self.sock.recv(1024)
                if not chunk:
                    time.sleep(0.01)
                    return None
                self.rx_buf += chunk

            line, self.rx_buf = self.rx_buf.split(b"\n", 1)
            self.last_error = ""
            return line.decode("utf-8", errors="ignore").replace("\x00", "").strip()
        except socket.timeout:
            return None
        except Exception as exc:  # pragma: no cover - depends on local hardware
            self.last_error = str(exc)
            if self.emit_console:
                print(f"[ERROR] RTT read failed: {exc}")
            return None

    def send_command(self, cmd: str) -> bool:
        """Send one text command to RTT down channel 0."""
        if self.sock is None:
            self.last_error = "RTT bridge is not connected"
            return False

        try:
            payload = (cmd.strip() + "\n").encode("utf-8")
            self.sock.sendall(payload)
            self.last_error = ""
            if self.emit_console:
                print(f"[CMD] Sent via RTT: {cmd}")
            return True
        except Exception as exc:  # pragma: no cover - depends on local hardware
            self.last_error = str(exc)
            if self.emit_console:
                print(f"[ERROR] RTT write failed: {exc}")
            return False

    def parse_data(self, line: str) -> Optional[Dict[str, float]]:
        """Parse the same CSV format used by SerialBridge.

        Expected format:
            timestamp_ms,setpoint,input,pwm,error,p,i,d
        """
        if not line or line.startswith("#"):
            return None

        parts = line.split(",")
        if len(parts) < 5:
            return None

        try:
            return {
                "timestamp": float(parts[0]),
                "setpoint": float(parts[1]),
                "input": float(parts[2]),
                "pwm": float(parts[3]),
                "error": float(parts[4]),
                "p": float(parts[5]) if len(parts) > 5 else 1.0,
                "i": float(parts[6]) if len(parts) > 6 else 0.1,
                "d": float(parts[7]) if len(parts) > 7 else 0.05,
            }
        except Exception:
            return None
