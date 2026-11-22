"""DPM-21: reset/restart repeatability and the read-only observer boundary."""
import asyncio
import json

from pymodbus.client import AsyncModbusTcpClient

from plant.app import Plant
from plant.config import ServiceSettings
from plant.desk_users import USERS

TRANOS = USERS['tranos']
IGNORED_PAYLOAD_KEYS = {'command_id'}  # random per run, like event_id and real UTC times


def close(plant):
    plant.publisher.close()
    for publisher in plant.replay_publishers:
        publisher.close()


def records(path):
    return [json.loads(line) for line in path.read_bytes().splitlines()]


def comparable(event):
    """What must repeat by simulation step; IDs and real times may differ."""
    payload = {k: v for k, v in event['payload'].items() if k not in IGNORED_PAYLOAD_KEYS}
    return (event['sim_step'], event['source_id'], event['event_type'], event['source_seq'],
            json.dumps(payload, sort_keys=True))


def test_reset_restores_baseline_and_preserves_earlier_records(tmp_path, monkeypatch):
    monkeypatch.setenv('MVP_LAB_MODE', '1')
    settings = ServiceSettings('127.0.0.1', 0, 0, 0, 'http://127.0.0.1:9/none', tmp_path)
    fresh = Plant('run-fresh', settings=settings)
    plant = Plant('run-dirty', settings=settings)
    try:
        expected_first = fresh.tick()
        plant.model.set_accepted_feed(25.0)               # leave the run in a changed, faulted state
        for _ in range(6):
            plant.tick()
        plant._control_run(TRANOS, 'stop-pump', plant.run_id)
        plant._control_run(TRANOS, 'suppress-a', plant.run_id)
        plant.tick()
        old_file = plant.publisher.jsonl_path
        old_bytes = old_file.read_bytes()

        plant._control_run(TRANOS, 'reset', 'run-dirty')
        assert plant.run_id != 'run-dirty' and plant.paused and plant.model.sim_step == 0
        assert plant.model.accepted_feed_mg_s == 15.0 and plant.model.pump_running
        assert list(plant.model._delayed) == [15.0] * 4    # delayed deliveries restored
        assert not plant.sensor_a_suppressed and plant.ack_counter == 0
        assert not plant.registry._pending and not plant.desk.requests
        assert old_file.read_bytes() == old_bytes          # earlier run kept byte for byte

        plant._control_run(TRANOS, 'resume', plant.run_id)
        assert plant.tick() == expected_first             # same seeds and baseline as a fresh plant
    finally:
        close(fresh)
        close(plant)


def test_repeated_runs_match_by_simulation_step(tmp_path, monkeypatch):
    monkeypatch.setenv('MVP_LAB_MODE', '1')
    settings = ServiceSettings('127.0.0.1', 0, 15061, 0, 'http://127.0.0.1:9/none', tmp_path)
    plant = Plant('run-before', settings=settings)

    def scenario():
        plant._control_run(TRANOS, 'reset', plant.run_id)
        plant.desk.execute_lab(TRANOS, 20, 'DPM-21 repeatability')
        plant._control_run(TRANOS, 'resume', plant.run_id)
        for _ in range(10):
            plant.tick()
        plant._control_run(TRANOS, 'suppress-a', plant.run_id)
        for _ in range(5):
            plant.tick()
        plant._control_run(TRANOS, 'stop-pump', plant.run_id)
        for _ in range(6):
            plant.tick()
        return plant.run_id, plant.publisher.jsonl_path

    async def run_twice():
        task = asyncio.create_task(plant.controller.serve())
        try:
            await asyncio.sleep(0.35)
            return [await asyncio.to_thread(scenario) for _ in range(2)]
        finally:
            await plant.controller.shutdown()
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    try:
        (run1, path1), (run2, path2) = asyncio.run(run_twice())
        first, second = records(path1), records(path2)
        assert run1 != run2 and path1 != path2
        assert {e['event_id'] for e in first}.isdisjoint(e['event_id'] for e in second)
        assert [comparable(e) for e in first] == [comparable(e) for e in second]
        # 21 steps of plant feedback and B, 10 of A (suppressed after step 10), plus lab records
        assert sum(e['source_id'] == 'sensor-a' for e in first) == 10
        assert sum(e['event_type'] == 'plant_feedback' for e in first) == 21
    finally:
        close(plant)


def test_observer_writes_cannot_change_running_plant(tmp_path):
    settings = ServiceSettings('127.0.0.1', 15071, 15072, 0, 'http://127.0.0.1:9/none', tmp_path)
    plant = Plant('run-boundary', settings=settings)

    async def scenario():
        observer = asyncio.create_task(plant.observer.serve())
        controller = asyncio.create_task(plant.controller.serve())
        await asyncio.sleep(0.35)
        for _ in range(3):
            plant.tick()
        state_before, snap_before = plant.model.state(), list(plant.observer.snapshot)
        client = AsyncModbusTcpClient('127.0.0.1', port=15071)
        await client.connect()
        try:
            replies = [await client.write_register(addr, 9999, device_id=1) for addr in range(13)]
            replies.append(await client.write_registers(0, [9999] * 13, device_id=1))
            replies.append(await client.write_registers(3, [3000, 3000, 3000], device_id=1))
            replies.append(await client.readwrite_registers(
                read_address=0, read_count=13, write_address=4, values=[4000], device_id=1))
            replies.append(await client.write_coil(0, True, device_id=1))
            assert all(r.isError() for r in replies)
            read = await client.read_holding_registers(0, count=13, device_id=1)
            assert read.registers == snap_before                     # observer state unchanged
        finally:
            client.close()

        # The private controller is a separate port and still refuses unregistered writes.
        rogue = AsyncModbusTcpClient('127.0.0.1', port=15072)
        await rogue.connect()
        try:
            assert (await rogue.write_registers(0, [1, 3000], device_id=1)).isError()
        finally:
            rogue.close()
        for server, task in ((plant.observer, observer), (plant.controller, controller)):
            await server.shutdown()
            task.cancel()
        await asyncio.gather(observer, controller, return_exceptions=True)
        return state_before, snap_before

    try:
        state_before, snap_before = asyncio.run(scenario())
        assert plant.model.state() == state_before                  # process state unchanged
        assert plant.observer.snapshot == snap_before
        assert plant.observer.refused_writes >= 16
    finally:
        close(plant)


def test_new_process_keeps_earlier_run_records(tmp_path):
    settings = ServiceSettings('127.0.0.1', 0, 0, 0, 'http://127.0.0.1:9/none', tmp_path)
    first = Plant('run-first', settings=settings)
    for _ in range(3):
        first.tick()
    old_path = first.publisher.jsonl_path
    old_bytes = old_path.read_bytes()
    close(first)

    second = Plant(settings=settings)                                # restart: a new process, new run
    try:
        assert second.run_id != 'run-first' and second.model.sim_step == 0
        assert old_path.read_bytes() == old_bytes
        assert old_path in [p.jsonl_path for p in second.replay_publishers]
    finally:
        close(second)
