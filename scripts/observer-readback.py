"""Independent readback of the observer registers (evidence helper, read-only).

Usage:  .\\.venv\\Scripts\\python.exe scripts\\observer-readback.py
Reads holding registers 0-12 from 127.0.0.1:1502 device 1 and prints
raw and engineering values. It never writes.
"""

from pymodbus.client import ModbusTcpClient

NAMES = [
    ("sensor_a_mg_l", 100), ("sensor_b_mg_l", 100), ("flow_l_s", 100),
    ("requested_feed_mg_s", 100), ("accepted_feed_mg_s", 100), ("actual_delivery_mg_s", 100),
    ("pump_running", 1), ("ack_counter", 1), ("sensor_a_quality", 1), ("sensor_b_quality", 1),
    ("sensor_a_age_s", 1), ("sensor_b_age_s", 1), ("tick_counter", 1),
]

client = ModbusTcpClient("127.0.0.1", port=1502)
if not client.connect():
    raise SystemExit("Observer not reachable on 127.0.0.1:1502 - is the plant running?")
try:
    result = client.read_holding_registers(0, count=13, device_id=1)
    if result.isError():
        raise SystemExit(f"Read failed: {result}")
    print(f"{'addr':>4} {'name':<22} {'raw':>6} {'value':>8}")
    for address, ((name, scale), raw) in enumerate(zip(NAMES, result.registers)):
        print(f"{address:>4} {name:<22} {raw:>6} {raw / scale:>8.2f}")
finally:
    client.close()
