"""DPM-12 checks: named desk, separation of duties, private command path."""

import asyncio
import json
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from pymodbus.client import ModbusTcpClient
from pymodbus.constants import ExcCodes

from plant.app import Plant
from plant.config import ServiceSettings
from plant.controller import CommandRegistry, ControllerServer
from plant.desk import Desk, DeskError, _now
from plant.desk_users import USERS, authenticate, set_password
from plant.desk_web import create_desk_app

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = Draft202012Validator(
    json.loads((ROOT / "contracts/event-envelope.schema.json").read_text()), format_checker=FormatChecker())
EMMANUEL, THABANI, TRANOS = USERS["emmanuel"], USERS["thabani"], USERS["tranos"]


# --- desk rules without any network ------------------------------------------------------
class FakeClock:
    def __init__(self):
        self.t = _now()

    def __call__(self):
        return self.t


@pytest.fixture
def desk(tmp_path):
    events, sent = [], []
    clock = FakeClock()
    d = Desk(lambda et, p, c: events.append((et, p, c)), lambda *a: sent.append(a),
             tmp_path / "audit.jsonl", clock=clock)
    d.events, d.sent, d.clock = events, sent, clock
    return d


def test_self_approval_is_refused(desk):
    req = desk.create_request(EMMANUEL, 20)
    approver_with_same_identity = USERS["emmanuel"].__class__("emmanuel", "Emmanuel", "approver")
    with pytest.raises(DeskError, match="Self-approval"):
        desk.approve(approver_with_same_identity, req.request_id)
    assert req.status == "requested"
    audit = [json.loads(l) for l in desk.audit_path.read_text().splitlines()]
    assert audit[-1]["outcome"] == "refused" and "Self-approval" in audit[-1]["detail"]


def test_roles_are_enforced(desk):
    with pytest.raises(DeskError):
        desk.create_request(THABANI, 20)          # approver cannot request
    req = desk.create_request(EMMANUEL, 20)
    with pytest.raises(DeskError):
        desk.approve(TRANOS, req.request_id)      # operator cannot approve
    with pytest.raises(DeskError):
        desk.execute(EMMANUEL, req.request_id)    # no approval yet
    assert desk.sent == []


@pytest.mark.parametrize("bad", ["abc", "0", "0.001", "-5", "41", "nan", "inf"])
def test_invalid_values_are_refused(desk, bad):
    with pytest.raises(DeskError):
        desk.create_request(EMMANUEL, bad)


def test_execution_requires_matching_unexpired_approval(desk):
    req = desk.create_request(EMMANUEL, 20)
    desk.approve(THABANI, req.request_id)
    req.requested_feed_mg_s = 25.0                # tampered after approval
    with pytest.raises(DeskError, match="value"):
        desk.execute(TRANOS, req.request_id)
    req.requested_feed_mg_s = 20.0
    desk.clock.t += timedelta(minutes=11)         # approval window passed
    with pytest.raises(DeskError, match="expired"):
        desk.execute(TRANOS, req.request_id)
    assert desk.sent == []


def test_failed_approval_record_does_not_authorize_execution(desk, monkeypatch):
    req = desk.create_request(EMMANUEL, 20)
    emit = desk._emit

    def fail_approval_record(event_type, payload, change_id):
        if event_type == "dose_approval":
            raise OSError("approval record could not be saved")
        return emit(event_type, payload, change_id)

    monkeypatch.setattr(desk, "_emit", fail_approval_record)
    with pytest.raises(OSError, match="approval record"):
        desk.approve(THABANI, req.request_id)
    with pytest.raises(DeskError, match="approval is required"):
        desk.execute(TRANOS, req.request_id)
    assert req.status == "requested" and req.approval is None
    assert [event[0] for event in desk.events] == ["dose_request"]
    assert desk.sent == []

    monkeypatch.setattr(desk, "_emit", emit)
    desk.approve(THABANI, req.request_id)
    desk.execute(TRANOS, req.request_id)
    assert [event[0] for event in desk.events] == ["dose_request", "dose_approval", "command"]
    assert len(desk.sent) == 1


def test_records_are_separate_and_share_change_id(desk):
    req = desk.create_request(EMMANUEL, 20)
    desk.approve(THABANI, req.request_id)
    desk.execute(TRANOS, req.request_id)
    assert [e[0] for e in desk.events] == ["dose_request", "dose_approval", "command"]
    assert {e[2] for e in desk.events} == {req.change_id}
    assert desk.events[2][1]["approval_id"] == req.approval["approval_id"]
    expires_at = datetime.fromisoformat(req.approval["expires_at_utc"])
    assert desk.sent == [(req.command["command_id"], req.change_id, 20.0, expires_at)]


# --- passwords -----------------------------------------------------------------------------
def test_passwords_are_hashed_and_checked(tmp_path):
    path = tmp_path / ".env.desk-users.json"
    set_password("thabani", "correct-horse-1", path)
    assert "correct-horse-1" not in path.read_text()
    assert authenticate("thabani", "correct-horse-1", path) == THABANI
    assert authenticate("thabani", "wrong-password", path) is None
    assert authenticate("emmanuel", "correct-horse-1", path) is None   # no hash set
    with pytest.raises(ValueError):
        set_password("thabani", "short", path)


def test_web_login_and_csrf(tmp_path, monkeypatch):
    path = tmp_path / ".env.desk-users.json"
    monkeypatch.setenv("MVP_DESK_USERS_FILE", str(path))
    set_password("emmanuel", "emmanuel-pass-1", path)
    d = Desk(lambda *a: None, lambda *a: None, tmp_path / "audit.jsonl")

    class S:  # minimal plant state for the page
        sim_step = 1; flow_l_s = 10.0; requested_feed_mg_s = 15.0; accepted_feed_mg_s = 15.0
        actual_delivery_mg_s = 15.0; pump_running = True; modeled_residual_mg_l = 1.0

    client = create_desk_app(d, lambda: S).test_client()
    assert client.get("/").status_code == 302                       # must sign in
    page = client.get("/login").get_data(as_text=True)
    token = page.split('name="csrf" value="')[1].split('"')[0]
    assert client.post("/login", data={"user_id": "emmanuel", "password": "x"}).status_code == 400  # no token
    assert client.post("/login", data={"csrf": token, "user_id": "emmanuel", "password": "bad"}).status_code == 401
    assert client.post("/login", data={"csrf": token, "user_id": "emmanuel", "password": "emmanuel-pass-1"}).status_code == 302
    assert "Signed in as <b>Emmanuel</b>" in client.get("/").get_data(as_text=True)


# --- full path over the private Modbus controller --------------------------------------------
@pytest.mark.parametrize("failed_connection", [True, False], ids=["offline", "write-timeout"])
def test_failed_send_revokes_pending_command(tmp_path, monkeypatch, failed_connection):
    settings = ServiceSettings("127.0.0.1", 0, 0, 0, "http://127.0.0.1:9/none", tmp_path)
    plant = Plant(run_id="test-run", settings=settings)
    client = Mock()
    client.connect.return_value = not failed_connection
    client.write_registers.side_effect = TimeoutError("no Modbus response")
    monkeypatch.setattr("plant.app.ModbusTcpClient", Mock(return_value=client))
    req = plant.desk.create_request(EMMANUEL, 20)
    plant.desk.approve(THABANI, req.request_id)

    with pytest.raises(DeskError):
        plant.desk.execute(TRANOS, req.request_id)
    result = asyncio.run(plant.controller._on_request(16, 0, 0, 2, None, [1, 2000]))

    assert result == ExcCodes.ILLEGAL_VALUE
    assert plant.model.accepted_feed_mg_s == 15.0
    assert req.status == "not acknowledged" and req.acknowledgement is None


def test_controller_refuses_expired_pending_command():
    accepted = []
    registry = CommandRegistry()
    controller = ControllerServer("127.0.0.1", 0, registry, accepted.append)
    pending = registry.register("cmd-expired", "chg-expired", 20, _now() - timedelta(seconds=1))

    result = asyncio.run(controller._on_request(16, 0, 0, 2, None, [pending.seq, 2000]))

    assert result == ExcCodes.ILLEGAL_VALUE and accepted == []
    assert registry.take(pending.seq, 2000) is None


def test_approved_change_runs_through_private_controller(tmp_path):
    settings = ServiceSettings("127.0.0.1", 15022, 15023, 15024, "http://127.0.0.1:9/none", tmp_path)
    plant = Plant(run_id="test-run", settings=settings)
    loop = asyncio.new_event_loop()
    task = loop.create_task(plant.controller.serve())
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()
    time.sleep(0.4)
    try:
        for _ in range(3):
            plant.tick()
        req = plant.desk.create_request(EMMANUEL, 20)
        plant.desk.approve(THABANI, req.request_id)
        plant.desk.execute(TRANOS, req.request_id)

        assert req.status == "acknowledged"
        assert plant.model.accepted_feed_mg_s == 20.0
        assert plant.ack_counter == 1
        # acknowledgement is not delivery or a sensor change: residual unchanged right now
        assert plant.model.residual_mg_l == pytest.approx(1.0)

        # a rogue write (not registered by the desk) is refused and changes nothing
        rogue = ModbusTcpClient("127.0.0.1", port=15023)
        rogue.connect()
        assert rogue.write_registers(0, [999, 3000], device_id=1).exception_code == ExcCodes.ILLEGAL_VALUE
        assert rogue.write_register(1, 3000, device_id=1).exception_code == ExcCodes.ILLEGAL_VALUE
        rogue.close()
        assert plant.model.accepted_feed_mg_s == 20.0

        snap = plant.tick()                               # observer updates on the next tick
        assert snap[3] == 2000 and snap[4] == 2000 and snap[5] == 2000 and snap[7] == 1
        residuals = [plant.tick() and plant.model.residual_mg_l for _ in range(4)]
        assert residuals[-1] > 1.0                        # water responds only after the delay

        records = [json.loads(l) for l in plant.publisher.jsonl_path.read_text().splitlines()]
        for r in records:
            VALIDATOR.validate(r)
        chain = [r for r in records if r["change_id"] == req.change_id]
        assert [(r["source_id"], r["event_type"]) for r in chain] == [
            ("operator-desk", "dose_request"), ("operator-desk", "dose_approval"),
            ("operator-desk", "command"), ("controller", "acknowledgement")]
        ack = chain[-1]["payload"]
        assert ack["accepted"] is True and "actual_delivery_mg_s" not in ack
    finally:
        asyncio.run_coroutine_threadsafe(plant.controller.shutdown(), loop).result(timeout=3)
        loop.call_soon_threadsafe(task.cancel)
        time.sleep(0.2)
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=2)
