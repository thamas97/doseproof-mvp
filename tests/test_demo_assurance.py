from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json

import pytest

from monitor.api_app import create_app as api_app
from monitor.assurance import evaluate_change
from monitor.collector_app import create_app as collector_app
from monitor.storage import EvidenceStore
from plant.app import Plant
from plant.config import ServiceSettings
from plant.desk import DeskError
from plant.desk_users import USERS
from plant.events import EventFactory


@pytest.mark.parametrize('fault', ['stop-pump', 'suppress-a'])
def test_lab_fault_source_records_and_findings(tmp_path, monkeypatch, fault):
    monkeypatch.setenv('MVP_LAB_MODE', '0')
    settings = ServiceSettings('127.0.0.1', 0, 0, 0, 'http://127.0.0.1:9/none', tmp_path)
    plant = Plant('run-fault', settings=settings)
    try:
        with pytest.raises(DeskError, match='Enable local lab'):
            plant._control_run(USERS['tranos'], fault, plant.run_id)
        plant.desk.lab_mode = True
        with pytest.raises(DeskError, match='Only the operator'):
            plant._control_run(USERS['emmanuel'], fault, plant.run_id)
        plant.tick()
        last_a = plant.sensor_a.last_sample
        plant._control_run(USERS['tranos'], fault, plant.run_id)
        with pytest.raises(DeskError, match='already active'):
            plant._control_run(USERS['tranos'], fault, plant.run_id)
        for _ in range(10):
            snap = plant.tick()
        if fault == 'stop-pump':
            assert snap[4:7] == [1500, 0, 0]
        else:
            assert plant.sensor_a.last_sample is last_a
            assert snap[8:12] == [3, 0, 10, 0]
        raw = plant.publisher.jsonl_path.read_bytes()
        db = tmp_path / 'test.db'
        client, api = collector_app(db).test_client(), api_app(db).test_client()
        for line in raw.splitlines():
            reply = client.post('/intake/events', data=line, content_type='application/json')
            assert reply.status_code == 201, reply.json
        finding, = api.get('/api/changes?run_id=run-fault').json['items']
        assert finding['status'] == ('FAIL' if fault == 'stop-pump' else 'UNVERIFIED')
        assert len(finding['supporting_records']) >= 2
        if fault == 'suppress-a':
            sources = [r['event']['source_id'] for r in finding['observations']]
            assert sources.count('sensor-b') == 10 and 'sensor-a' not in sources
        plant._control_run(USERS['tranos'], 'reset', 'run-fault')
        assert plant.model.pump_running and not plant.sensor_a_suppressed
        assert plant.replay_publishers[-1].jsonl_path.read_bytes() == raw
    finally:
        plant.publisher.close()
        for publisher in plant.replay_publishers:
            publisher.close()


def test_action_deadline_and_identity_conflict(tmp_path):
    db = tmp_path / 'test.db'
    client, api = collector_app(db).test_client(), api_app(db).test_client()
    events = EventFactory('run-action')
    base = {'equipment_id': 'dosing-pump-1', 'request_id': 'req', 'requested_feed_mg_s': 20}
    command = events.make('operator-desk', 'command', 0, {**base, 'actor_id': 'tranos',
                          'command_id': 'cmd', 'approval_id': 'approval'}, change_id='change')
    assert client.post('/intake/events', json=command).status_code == 201
    assert api.get('/api/changes').json['items'][0]['status'] == 'PENDING'
    with EvidenceStore(db) as store:
        evaluate_change(store._conn, 'run-action', 'change', now=datetime.now(timezone.utc) + timedelta(seconds=12))
    assert api.get('/api/changes').json['items'][0]['status'] == 'UNVERIFIED'
    conflict = deepcopy(command)
    conflict['change_id'] = 'wrong-change'
    conflict['payload']['requested_feed_mg_s'] = 21
    response = client.post('/intake/events', json=conflict)
    assert response.status_code == 409
    result, = api.get('/api/changes').json['items']
    assert result['change_id'] == 'change' and result['status'] == 'UNVERIFIED'
    assert response.json['receipt_id'] in {record['receipt_id'] for record in result['supporting_records']}
