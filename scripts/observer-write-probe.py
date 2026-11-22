"""DPM-21 evidence: try to write to the running observer and show every attempt is refused.

Usage (plant running):  .\\.venv\\Scripts\\python.exe scripts\\observer-write-probe.py
Targets ONLY the read-only observer (default 127.0.0.1:1502). It never touches the
private controller. Writes would set requested/accepted feed to 99.99 mg/s; the check
passes when every write is refused and those registers keep their real values.
"""
import argparse
import sys
from datetime import datetime, timezone

from pymodbus.client import ModbusTcpClient

FEED_REGISTERS = {3: 'requested_feed', 4: 'accepted_feed', 5: 'actual_delivery'}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=1502)
    args = parser.parse_args()

    client = ModbusTcpClient(args.host, port=args.port, timeout=3)
    if not client.connect():
        print(f'Observer not reachable on {args.host}:{args.port}. Is the plant running?')
        return 2
    try:
        print(f'Observer write probe {datetime.now(timezone.utc).isoformat(timespec="seconds")} '
              f'on {args.host}:{args.port}, device 1')
        before = client.read_holding_registers(0, count=13, device_id=1).registers
        print('Before:', ', '.join(f'{name}={before[r] / 100:.2f}' for r, name in FEED_REGISTERS.items()),
              f'tick={before[12]}')
        attempts = [
            ('FC6  single write, register 4 = 9999', lambda: client.write_register(4, 9999, device_id=1)),
            ('FC16 multiple write, registers 3-5', lambda: client.write_registers(3, [9999] * 3, device_id=1)),
            ('FC16 write all 13 registers', lambda: client.write_registers(0, [9999] * 13, device_id=1)),
            ('FC23 read/write, write register 4', lambda: client.readwrite_registers(
                read_address=0, read_count=1, write_address=4, values=[9999], device_id=1)),
        ]
        all_refused = True
        for label, attempt in attempts:
            reply = attempt()
            refused = reply.isError()
            all_refused &= refused
            code = getattr(reply, 'exception_code', None)
            print(f'  {label:<38} -> {"REFUSED" if refused else "ACCEPTED"}'
                  + (f' (Modbus exception {code})' if code else ''))
        after = client.read_holding_registers(0, count=13, device_id=1).registers
        print('After: ', ', '.join(f'{name}={after[r] / 100:.2f}' for r, name in FEED_REGISTERS.items()),
              f'tick={after[12]}')
        untouched = all(after[r] != 9999 for r in FEED_REGISTERS)
        ok = all_refused and untouched
        print('RESULT:', 'PASS - every write refused; feed registers keep real plant values'
              if ok else 'FAIL - a write was accepted or a register shows the written value')
        return 0 if ok else 1
    finally:
        client.close()


if __name__ == '__main__':
    sys.exit(main())
