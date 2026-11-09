"""DPM-18 checks: stopped pump (AC-03) and missing Sensor A (AC-04)."""

import asyncio
import json
import threading
import time
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from plant.app import Plant
from plant.config import ServiceSettings
from plant.desk import DeskError
from plant.desk_users import USERS

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = Draft202012Validator(
    json.loads((ROOT / "contracts/event-envelope.schema.json").read_text()), format_checker=FormatChecker())
EMMANUEL, THABANI, TRANOS = USERS["emmanuel"], USERS["thabani"], USERS["tranos"]
TOL = 0.000001
QUALITY = {0: "good", 1: "uncertain", 2: "bad", 3: "unavailable"}


@pytest.fixture
def plant_factory(tmp_path):
    started = []

    def make(port_base: int):
        settings = ServiceSettings("127.0.0.1", port_base, port_base + 1, port_base + 2,
                                   "http://127.0.0.1:9/none", tmp_path)
        plant = Plant(run_id="first-run", settings=settings)
        loop = asyncio.new_event_loop()
        task = loop.create_task(plant.controller.serve())
        thread = threading.Thread(target=loop.run_forever, daemon=True)
        thread.start()
        time.sleep(0.4)
        started.append((plant, loop, task, thread))
        return plant

    yield make
    for plant, loop, task, thread in started:
        asyncio.run_coroutine_threadsafe(plant.controller.shutdown(), loop).result(timeout=3)
        loop.call_soon_threadsafe(task.cancel)
        time.sleep(0.2)
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=2)


def records(plant):
    path = plant.publisher.jsonl_path
    return [json.loads(l) for l in path.read_text().splitlines()] if path.exists() else []


def approved_20(plant):
    plant.reset()
    req = plant.desk.create_request(EMMANUEL, 20)
    plant.desk.approve(THABANI, req.request_id)
    plant.desk.execute(EMMANUEL, req.request_id)
    plant.resume()
    return req


def test_ac03_stopped_pump_keeps_setting_but_delivers_zero(plant_factory):
    plant = plant_factory(15090)
    approved_20(plant)
    for _ in range(64):
        plant.tick()
    assert abs(plant.model.residual_mg_l - 1.50) <= TOL               # settled before the fault

    change_id = plant.set_fault(TRANOS, "pump_stopped", True, "AC-03 stopped pump")
    residual_at_stop = plant.model.residual_mg_l
    snap = plant.observer.snapshot
    assert snap[4] == 2000 and snap[5] == 0 and snap[6] == 0           # accepted 20, delivery 0, pump off

    residuals = []
    for _ in range(6):
        state = plant.tick()
        residuals.append(plant.model.residual_mg_l)
        assert plant.model.accepted_feed_mg_s == 20.0                  # setting not confused with delivery
    assert all(abs(r - residual_at_stop) < 0.00001 for r in residuals[:4])  # water still reflects delivered dose
    assert residuals[4] == pytest.approx(residual_at_stop * 0.8)      # then follows the delayed model (target 0)
    assert residuals[5] < residuals[4]

    recs = records(plant)
    for r in recs:
        VALIDATOR.validate(r)
    fb = [r for r in recs if r["event_type"] == "plant_feedback" and r["sim_step"] > 64]
    assert all(r["payload"]["pump_running"] is False and r["payload"]["actual_delivery_mg_s"] == 0.0 for r in fb)
    lab = [r for r in recs if r["change_id"] == change_id]
    assert lab[0]["event_type"] == "lab_action" and lab[0]["payload"]["actor_id"] == "tranos"
    assert lab[0]["payload"]["action"] == "simulate_pump_stopped" and lab[0]["payload"]["simulated_fault"] is True

    plant.set_fault(TRANOS, "pump_stopped", False, "restore healthy pump")   # restore
    assert plant.tick()[5] == 2000 and plant.model.pump_running
    restore = [r for r in records(plant) if r["change_id"] == change_id]
    assert [r["payload"]["action"] for r in restore] == ["simulate_pump_stopped", "restore_pump_stopped"]


def test_ac04_missing_sensor_a_ages_without_invented_values(plant_factory):
    plant = plant_factory(15100)
    plant.reset()
    plant.resume()
    for _ in range(3):
        plant.tick()
    retained = plant.sensor_a.last_sample
    start_step = plant.model.sim_step
    change_id = plant.set_fault(TRANOS, "sensor_a_missing", True, "AC-04 missing Sensor A")

    qualities = []
    for i in range(1, 11):
        snap = plant.tick()
        assert snap[0] == round(retained.value_mg_l * 100)              # last real A value retained
        assert snap[10] == i                                            # A age grows
        assert snap[9] == 0 and snap[11] == 0                           # B stays good and fresh
        qualities.append(QUALITY[snap[8]])
    assert qualities[:2] == ["good", "good"]
    assert set(qualities[2:9]) == {"uncertain"}                         # stale after 3 steps
    assert qualities[-1] == "unavailable"                               # unavailable by end of window

    recs = records(plant)
    for r in recs:
        VALIDATOR.validate(r)
    window = range(start_step + 1, start_step + 11)
    assert not [r for r in recs if r["source_id"] == "sensor-a" and r["sim_step"] in window]  # no A records
    assert len([r for r in recs if r["source_id"] == "sensor-b" and r["sim_step"] in window]) == 10
    assert len([r for r in recs if r["event_type"] == "plant_feedback" and r["sim_step"] in window]) == 10
    assert not [r for r in recs if r["source_id"] == "sensor-a" and r["payload"]["value"] == 0]

    plant.set_fault(TRANOS, "sensor_a_missing", False, "restore Sensor A")
    snap = plant.tick()
    assert snap[8] == 0 and snap[10] == 0                               # healthy again
    assert [r["payload"]["action"] for r in records(plant) if r["change_id"] == change_id] == [
        "simulate_sensor_a_missing", "restore_sensor_a_missing"]


def test_only_operator_can_simulate_faults_and_reset_restores_health(plant_factory):
    plant = plant_factory(15110)
    with pytest.raises(DeskError):
        plant.set_fault(EMMANUEL, "pump_stopped", True, "not allowed")
    assert plant.model.pump_running
    plant.set_fault(TRANOS, "pump_stopped", True, "x")
    plant.set_fault(TRANOS, "sensor_a_missing", True, "x")
    plant.reset()
    assert plant.faults == {} and plant.model.pump_running and not plant.sensor_a.suppressed
