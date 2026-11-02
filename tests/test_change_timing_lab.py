"""DPM-15 checks: approved-change timing (AC-01) and labelled lab-unapproved change (AC-02)."""

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
EXPECTED_5_TO_8 = [1.10, 1.18, 1.244, 1.2952]
TOL = 0.000001  # runbook model arithmetic tolerance


@pytest.fixture
def plant_factory(tmp_path):
    started = []

    def make(lab_mode: bool, port_base: int):
        settings = ServiceSettings("127.0.0.1", port_base, port_base + 1, port_base + 2,
                                   "http://127.0.0.1:9/none", tmp_path, lab_mode=lab_mode)
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


def test_reset_starts_new_paused_run_and_keeps_old_evidence(plant_factory):
    plant = plant_factory(False, 15030)
    plant.tick(); plant.tick()
    old_file = plant.publisher.jsonl_path
    new_run = plant.reset()
    assert new_run != "first-run" and plant.paused
    assert plant.model.sim_step == 0 and plant.model.accepted_feed_mg_s == 15.0
    assert old_file.exists() and len(old_file.read_text().splitlines()) == 6   # earlier run kept
    assert plant.observer.snapshot[8] == 3 and plant.observer.snapshot[12] == 0  # no sample yet: unavailable


def test_ac01_approved_change_before_step_1_follows_delay(plant_factory):
    plant = plant_factory(False, 15040)
    plant.reset()
    req = plant.desk.create_request(EMMANUEL, 20)
    plant.desk.approve(THABANI, req.request_id)
    plant.desk.execute(EMMANUEL, req.request_id)   # requester executes the approved change
    assert req.status == "acknowledged" and plant.model.sim_step == 0
    plant.resume()
    residuals = [None]
    for _ in range(8):
        plant.tick()
        residuals.append(plant.model.residual_mg_l)
    assert all(abs(r - 1.0) <= TOL for r in residuals[1:5])                 # steps 1-4 unchanged
    assert all(abs(r - e) <= TOL for r, e in zip(residuals[5:], EXPECTED_5_TO_8))  # steps 5-8

    recs = records(plant)
    for r in recs:
        VALIDATOR.validate(r)
    chain = [(r["source_id"], r["event_type"], r["sim_step"]) for r in recs if r["change_id"] == req.change_id]
    assert chain == [("operator-desk", "dose_request", 0), ("operator-desk", "dose_approval", 0),
                     ("operator-desk", "command", 0), ("controller", "acknowledgement", 0)]
    assert not any(r["event_type"] == "lab_action" for r in recs)


def test_lab_path_is_disabled_by_default(plant_factory):
    plant = plant_factory(False, 15050)
    with pytest.raises(DeskError, match="disabled"):
        plant.desk.lab_apply(TRANOS, 20, "lab demonstration")
    assert plant.model.accepted_feed_mg_s == 15.0
    assert not any(r["event_type"] in ("lab_action", "command") for r in records(plant))


def test_ac02_lab_unapproved_change_is_labelled_and_distinguishable(plant_factory):
    plant = plant_factory(True, 15060)
    plant.reset()
    with pytest.raises(DeskError):
        plant.desk.lab_apply(EMMANUEL, 20, "not the operator")   # only Tranos
    with pytest.raises(DeskError):
        plant.desk.lab_apply(TRANOS, 20, "")                      # reason required
    lab = plant.desk.lab_apply(TRANOS, 20, "AC-02 labelled lab demonstration")
    assert lab.status == "acknowledged" and plant.model.accepted_feed_mg_s == 20.0
    plant.resume()
    for _ in range(8):
        plant.tick()
    assert abs(plant.model.residual_mg_l - 1.2952) <= TOL           # actual effect preserved

    recs = records(plant)
    for r in recs:
        VALIDATOR.validate(r)
    chain = [r for r in recs if r["change_id"] == lab.change_id]
    assert [(r["source_id"], r["event_type"]) for r in chain] == [
        ("operator-desk", "lab_action"), ("operator-desk", "command"), ("controller", "acknowledgement")]
    assert chain[0]["payload"]["actor_id"] == "tranos" and chain[0]["payload"]["approved"] is False
    assert chain[1]["payload"]["approval_id"] is None and chain[1]["payload"]["request_id"] is None
    assert not any(r["event_type"] == "dose_approval" for r in recs)  # no fabricated approval


def test_normal_workflow_still_enforced_with_lab_mode_on(plant_factory):
    plant = plant_factory(True, 15070)
    req = plant.desk.create_request(EMMANUEL, 25)
    with pytest.raises(DeskError):
        plant.desk.execute(TRANOS, req.request_id)                  # no approval
    with pytest.raises(DeskError):
        plant.desk.approve(TRANOS, req.request_id)                  # operator cannot approve
    assert plant.model.accepted_feed_mg_s == 15.0


def test_pause_stops_steps(plant_factory):
    plant = plant_factory(False, 15080)
    plant.pause()
    step = plant.model.sim_step

    async def one_loop_pass():
        if not plant.paused:
            plant.tick()

    asyncio.run(one_loop_pass())
    assert plant.model.sim_step == step
