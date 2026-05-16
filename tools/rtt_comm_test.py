#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/rtt_comm_test.py - minimal J-Link RTT communication smoke test.

Purpose:
    1. Read text printed by the DAVE4/XMC target through RTT channel 0.
    2. Send a few test commands back to the target.
    3. Verify the target can receive commands and print ACK lines.

Before running:
    - The XMC4200 target firmware must include SEGGER RTT.
    - The target must be running.
    - A J-Link RTT Telnet server must be available, commonly 127.0.0.1:19021.
    - Close J-Link RTT Client / RTT Viewer if they occupy the same Telnet port.

Example:
    python tools/rtt_comm_test.py --host 127.0.0.1 --port 19021
    python tools/rtt_comm_test.py --cmd "PING" --cmd "SET P:1.2 I:0.03 D:0"
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from typing import List

# Allow running this file directly from the repository root or from tools/.
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from hw.rtt_bridge import RttTelnetBridge


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Test J-Link RTT text communication.")
    parser.add_argument("--host", default="127.0.0.1", help="RTT Telnet host, default 127.0.0.1")
    parser.add_argument("--port", type=int, default=19021, help="RTT Telnet port, default 19021")
    parser.add_argument("--timeout", type=float, default=1.0, help="Socket timeout seconds")
    parser.add_argument("--duration", type=float, default=15.0, help="Total test duration seconds")
    parser.add_argument(
        "--cmd",
        action="append",
        dest="commands",
        help="Command to send. Can be specified multiple times.",
    )
    parser.add_argument(
        "--send-period",
        type=float,
        default=2.0,
        help="Seconds between commands, default 2.0",
    )
    parser.add_argument(
        "--parse-csv",
        action="store_true",
        help="Also try to parse PID CSV lines with the SerialBridge-compatible parser.",
    )
    return parser


def main(argv: List[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    commands = args.commands or [
        "PING",
        "STATUS",
        "SET P:1.2000 I:0.0300 D:0.0000",
        "STATUS",
    ]

    bridge = RttTelnetBridge(
        host=args.host,
        port=args.port,
        timeout=args.timeout,
        emit_console=True,
    )

    if not bridge.connect():
        print(f"[FAIL] Cannot connect to RTT Telnet {args.host}:{args.port}: {bridge.last_error}")
        print("[HINT] Make sure the target is running and the RTT Telnet server is available.")
        print("[HINT] Close J-Link RTT Client/Viewer if it already occupies the same TCP port.")
        return 1

    print("[INFO] RTT communication test started.")
    print("[INFO] Press Ctrl+C to stop. Incoming RTT lines are shown as [RX].")

    start = time.time()
    next_send = start
    cmd_index = 0
    rx_count = 0
    tx_count = 0
    parsed_count = 0

    try:
        while (time.time() - start) < args.duration:
            now = time.time()

            if cmd_index < len(commands) and now >= next_send:
                cmd = commands[cmd_index]
                cmd_index += 1
                next_send = now + args.send_period
                if bridge.send_command(cmd):
                    tx_count += 1
                else:
                    print(f"[WARN] Send failed: {bridge.last_error}")

            line = bridge.read_line()
            if line is None:
                continue
            if not line:
                continue

            rx_count += 1
            print(f"[RX] {line}")

            if args.parse_csv:
                data = bridge.parse_data(line)
                if data is not None:
                    parsed_count += 1
                    print(
                        "[CSV] "
                        f"t={data['timestamp']:.0f}, sp={data['setpoint']:.3f}, "
                        f"in={data['input']:.3f}, out={data['pwm']:.3f}, "
                        f"err={data['error']:.3f}, p={data['p']:.4f}, "
                        f"i={data['i']:.4f}, d={data['d']:.4f}"
                    )

    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user.")
    finally:
        bridge.disconnect()

    print("\n========== RTT TEST SUMMARY ==========")
    print(f"TX commands : {tx_count}")
    print(f"RX lines    : {rx_count}")
    if args.parse_csv:
        print(f"CSV parsed  : {parsed_count}")

    if tx_count > 0 and rx_count > 0:
        print("[PASS] PC can send RTT commands and receive RTT text lines.")
        return 0

    print("[FAIL] RTT communication was not fully verified.")
    print("[HINT] If RX is 0, check target RTT output and Telnet port.")
    print("[HINT] If target cannot receive commands, add SEGGER_RTT_Read() processing on firmware side.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
