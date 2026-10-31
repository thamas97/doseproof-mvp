"""DPM-9 baseline plant checks (Layer 1). Educational simulation only."""

import asyncio
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from pymodbus.client import AsyncModbusTcpClient

from plant.config import load_baseline
from plant.events import EventFactory, plant_feedback, sensor_observation
from plant.model import PlantModel
from plant.observer import ObserverServer, build_snapshot
from plant.sensors import SensorAdapter

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "contracts/event-envelope.schema.json").read_text())
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())
TEST_PORT = 15020  # not 1502, so a running plant is never disturbed


def test_baseline_holds_steady_at_one():
    model = PlantModel(load_baseline())
    for _ in range(10):
        state = model.step()
        assert state.modeled_residual_mg_l == pytest.approx(1.0)
        assert state.actual_delivery_mg_s == pytest.approx(15.0)


def test_accepted_change_follows_contract_arithmetic():
    model = PlantModel(load_baseline())
    model.set_accepted_feed(20.0)
    residuals = [model.step().modeled_residual_mg_l for _ in range(8)]
    assert residuals[:4] == pytest.approx([1.0] * 4)          # 4-tick delay
    assert residuals[4:] == pytest.approx([1.10, 1.18, 1.244, 1.2952])
    for _ in range(56):
        state = model.step()
    assert state.modeled_residual_mg_l == pytest.approx(1.50, abs=0.01)


def test_stopped_pump_delivers_zero_and_no_flow_never_divides():
    model = PlantModel(load_baseline())
    model.set_pump_running(False)
    assert model.step().actual_delivery_mg_s == 0.0
    model.flow_l_s = 0.0
    before = model.residual_mg_l
    assert model.step().modeled_residual_mg_l == before   # held, not invented


def test_sensors_are_separate_and_sample_modeled_water():
    b = load_baseline()
    a, s_b = SensorAdapter(b.sensor_a), SensorAdapter(b.sensor_b)
    assert a.source_id == "sensor-a" and s_b.source_id == "sensor-b"
    va = [a.sample(1.0, i).value_mg_l for i in range(20)]
    vb = [s_b.sample(1.0, i).value_mg_l for i in range(20)]
    assert va != vb                                     # different seeds
    assert all(abs(v - 1.0) <= 0.01 for v in va + vb)   # within noise bound
    a.reset()
    assert [a.sample(1.0, i).value_mg_l for i in range(20)] == va  # repeatable


def test_snapshot_scales_once_by_100():
    b = load_baseline()
    model = PlantModel(b)
    state = model.step()
    a = SensorAdapter(b.sensor_a).sample(state.modeled_residual_mg_l, state.sim_step)
    s_b = SensorAdapter(b.sensor_b).sample(state.modeled_residual_mg_l, state.sim_step)
    snap = build_snapshot(state, a, s_b, "good", "good", 0, 0, 0)
    assert len(snap) == 13
    assert snap[2:7] == [1000, 1500, 1500, 1500, 1]
    assert snap[0] == round(a.value_mg_l * 100) and snap[1] == round(s_b.value_mg_l * 100)
    assert snap[8:13] == [0, 0, 0, 0, 1]


def test_events_match_shared_contract():
    b = load_baseline()
    model = PlantModel(b)
    factory = EventFactory("test-run")
    state = model.step()
    sample = SensorAdapter(b.sensor_a).sample(state.modeled_residual_mg_l, state.sim_step)
    for event in (plant_feedback(factory, state), sensor_observation(factory, sample)):
        VALIDATOR.validate(event)
        assert event["change_id"] is None   # baseline is not an approved change


def test_observer_serves_reads_and_refuses_network_writes():
    async def scenario():
        observer = ObserverServer("127.0.0.1", TEST_PORT)
        observer.update(list(range(100, 113)))
        task = asyncio.create_task(observer.serve())
        await asyncio.sleep(0.3)
        client = AsyncModbusTcpClient("127.0.0.1", port=TEST_PORT)
        await client.connect()
        try:
            read = await client.read_holding_registers(0, count=13, device_id=1)
            assert read.registers == list(range(100, 113))
            observer.update([7] * 13)                       # internal update still works
            read = await client.read_holding_registers(0, count=13, device_id=1)
            assert read.registers == [7] * 13
            w6 = await client.write_register(3, 9999, device_id=1)
            w16 = await client.write_registers(3, [1, 2], device_id=1)
            w23 = await client.readwrite_registers(
                read_address=0, read_count=1, write_address=3, values=[5], device_id=1)
            assert w6.isError() and w16.isError() and w23.isError()
            assert observer.snapshot == [7] * 13            # nothing changed
            assert observer.refused_writes == 3
        finally:
            client.close()
            await observer.shutdown()
            task.cancel()

    asyncio.run(scenario())
