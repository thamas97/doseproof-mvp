"""DPM-18: stopped pump (AC-03) and missing Sensor A (AC-04) at the plant source."""
import asyncio
import json

import pytest

from plant.app import Plant
from plant.config import ServiceSettings
from plant.desk_users import USERS
from plant.desk_web import create_desk_app

TOL = 0.000001
QUALITY = {0: 'good', 1: 'uncertain', 2: 'bad', 3: 'unavailable'}


def desk_client(app, user_id):
    client = app.test_client()
    with client.session_transaction() as session:
        session.update(user_id=user_id, csrf='test-token')
    return client


def records(plant):
    return [json.loads(line) for line in plant.publisher.jsonl_path.read_bytes().splitlines()]


def close(plant):
    plant.publisher.close()
    for publisher in plant.replay_publishers:
        publisher.close()


def test_ac03_stopped_pump_keeps_setting_but_delivers_zero(tmp_path, monkeypatch):
    monkeypatch.setenv('MVP_LAB_MODE', '1')
    settings = ServiceSettings('127.0.0.1', 0, 15041, 0, 'http://127.0.0.1:9/none', tmp_path)
    plant = Plant('run-ac03', settings=settings)
    app = create_desk_app(plant.desk, plant.model.state, control=plant._control_run,
                          run_state=lambda: (plant.run_id, plant.paused))
    requester, approver, operator = (desk_client(app, u) for u in ('emmanuel', 'thabani', 'tranos'))

    def post(client, route, **fields):
        return client.post(route, data={'csrf': 'test-token', **fields}, follow_redirects=True)

    def approved_20():
        post(operator, '/simulation/control', action='reset', run_id=plant.run_id)
        assert b'recorded' in post(requester, '/requests', requested_feed_mg_s='20').data
        req = next(iter(plant.desk.requests.values()))
        assert b'approved' in post(approver, f'/requests/{req.request_id}/approve').data
        assert b'status: acknowledged' in post(operator, f'/requests/{req.request_id}/execute').data

    async def run_controller():
        task = asyncio.create_task(plant.controller.serve())
        try:
            await asyncio.sleep(0.35)
            await asyncio.to_thread(approved_20)
        finally:
            await plant.controller.shutdown()
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    try:
        asyncio.run(run_controller())
        for _ in range(64):
            plant.tick()
        assert abs(plant.model.residual_mg_l - 1.50) <= TOL          # settled before the fault
        stop_step = plant.model.sim_step
        plant._control_run(USERS['tranos'], 'stop-pump', plant.run_id)

        residuals = []
        for _ in range(7):
            snap = plant.tick()
            residuals.append(plant.model.residual_mg_l)
            assert snap[4:7] == [2000, 0, 0]                          # accepted 20, delivery 0, pump off
            assert plant.model.accepted_feed_mg_s == 20.0             # setting not confused with delivery
        assert residuals[:4] == pytest.approx([1.5] * 4, abs=0.00001)  # already-dosed water still arriving
        assert residuals[4:] == pytest.approx([1.2, 0.96, 0.768], abs=0.00001)  # then the delayed model

        events = records(plant)
        fault = [e for e in events if e['event_type'] == 'lab_action' and e['payload']['action'] == 'stop-pump']
        assert len(fault) == 1 and fault[0]['payload']['actor_id'] == 'tranos'
        assert fault[0]['sim_step'] == stop_step
        after = [e for e in events if e['event_type'] == 'plant_feedback' and e['sim_step'] > stop_step]
        assert len(after) == 7
        assert all(not e['payload']['pump_running'] and e['payload']['actual_delivery_mg_s'] == 0 for e in after)

        plant._control_run(USERS['tranos'], 'reset', plant.run_id)   # restore healthy settings
        assert plant.model.pump_running and plant.model.accepted_feed_mg_s == 15.0
    finally:
        close(plant)


def test_ac04_missing_sensor_a_ages_without_invented_values(tmp_path, monkeypatch):
    monkeypatch.setenv('MVP_LAB_MODE', '1')
    settings = ServiceSettings('127.0.0.1', 0, 0, 0, 'http://127.0.0.1:9/none', tmp_path)
    plant = Plant('run-ac04', settings=settings)
    try:
        for _ in range(3):
            plant.tick()
        retained = plant.sensor_a.last_sample
        start = plant.model.sim_step
        plant._control_run(USERS['tranos'], 'suppress-a', plant.run_id)

        qualities = []
        for age in range(1, 11):
            snap = plant.tick()
            assert snap[0] == round(retained.value_mg_l * 100)       # last real A value retained, never 0
            assert snap[10] == age                                    # A age counts up
            assert snap[9] == 0 and snap[11] == 0                     # B stays good and fresh
            qualities.append(QUALITY[snap[8]])
        assert qualities[:2] == ['good', 'good']
        assert set(qualities[2:9]) == {'uncertain'}                   # stale from age 3
        assert qualities[9] == 'unavailable'                          # unavailable at age 10

        window = range(start + 1, start + 11)
        events = records(plant)
        assert not [e for e in events if e['source_id'] == 'sensor-a' and e['sim_step'] in window]
        assert len([e for e in events if e['source_id'] == 'sensor-b' and e['sim_step'] in window]) == 10
        assert len([e for e in events if e['event_type'] == 'plant_feedback' and e['sim_step'] in window]) == 10
        assert not [e for e in events if e['source_id'] == 'sensor-a' and e['payload']['value'] == 0]

        plant._control_run(USERS['tranos'], 'reset', plant.run_id)   # restore healthy settings
        plant._control_run(USERS['tranos'], 'resume', plant.run_id)
        snap = plant.tick()
        assert not plant.sensor_a_suppressed and snap[8] == 0 and snap[10] == 0
    finally:
        close(plant)


def test_healthy_sensors_report_good_quality(tmp_path):
    settings = ServiceSettings('127.0.0.1', 0, 0, 0, 'http://127.0.0.1:9/none', tmp_path)
    plant = Plant('run-healthy', settings=settings)
    try:
        for _ in range(5):
            snap = plant.tick()
            assert snap[8:12] == [0, 0, 0, 0]
    finally:
        close(plant)
