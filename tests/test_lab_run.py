"""Exercise the lab desk, private controller, original records and intake together."""
import asyncio
import json
from pathlib import Path
import subprocess
import sys

import pytest

from monitor.collector_app import create_app as create_collector
from monitor.api_app import create_app as create_api
from plant.app import Plant
from plant.config import ServiceSettings
from plant.desk_web import create_desk_app


def desk_client(app, user_id):
    client = app.test_client()
    with client.session_transaction() as session:
        session.update(user_id=user_id, csrf='test-token')
    return client


@pytest.mark.parametrize('lab', [False, True], ids=['approved', 'lab-unapproved'])
def test_reset_to_step_zero_then_apply_change_and_export(tmp_path, monkeypatch, lab):
    monkeypatch.setenv('MVP_LAB_MODE', '1' if lab else '0')
    evidence = tmp_path / 'evidence'
    settings = ServiceSettings('127.0.0.1', 0, 15025, 0, 'http://127.0.0.1:9/none', evidence)
    plant = Plant('run-earlier', settings=settings)
    plant.tick()
    old_source = plant.publisher.jsonl_path
    old_bytes = old_source.read_bytes()
    app = create_desk_app(plant.desk, plant.model.state, control=plant._control_run,
                          run_state=lambda: (plant.run_id, plant.paused))
    operator = desk_client(app, 'tranos')
    requester = desk_client(app, 'emmanuel')
    approver = desk_client(app, 'thabani')

    def post(client, route, **fields):
        return client.post(route, data={'csrf': 'test-token', **fields}, follow_redirects=True)

    def exercise_desk():
        control = '/simulation/control'
        route = '/simulation/lab-unapproved'
        assert b'Only the operator' in post(requester, control, action='reset', run_id=plant.run_id).data
        assert b'Lab-unapproved changes require' in post(requester, route, requested_feed_mg_s='20', reason='test').data
        assert b'Paused' in post(operator, control, action='reset', run_id=plant.run_id).data
        assert plant.paused and plant.run_id != 'run-earlier' and plant.model.sim_step == 0
        assert plant.observer.snapshot[8:13] == [3, 3, 65535, 65535, 0]
        assert b'The run changed' in post(operator, control, action='reset', run_id='run-earlier').data
        if lab:
            assert b'Enter a lab reason' in post(operator, route, requested_feed_mg_s='20', reason=' ').data
            assert b'Lab command cmd-' in post(operator, route, requested_feed_mg_s='20', reason='AC-02 demo').data
        else:
            assert b'Lab-unapproved changes require' in post(operator, route, requested_feed_mg_s='20', reason='test').data
            assert b'recorded' in post(requester, '/requests', requested_feed_mg_s='20').data
            req = next(iter(plant.desk.requests.values()))
            assert b'an approval is required' in post(operator, f'/requests/{req.request_id}/execute').data
            assert b'approved' in post(approver, f'/requests/{req.request_id}/approve').data
            assert b'status: acknowledged' in post(operator, f'/requests/{req.request_id}/execute').data
        assert plant.model.sim_step == 0 and plant.model.accepted_feed_mg_s == 20
        assert b'Running' in post(operator, control, action='resume', run_id=plant.run_id).data

    async def run_controller():
        task = asyncio.create_task(plant.controller.serve())
        try:
            await asyncio.sleep(0.35)
            await asyncio.to_thread(exercise_desk)
        finally:
            await plant.controller.shutdown()
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    try:
        asyncio.run(run_controller())
        residuals = []
        for _ in range(8):
            plant.tick()
            residuals.append(plant.model.residual_mg_l)
        assert residuals == pytest.approx([1, 1, 1, 1, 1.1, 1.18, 1.244, 1.2952])
        assert old_source.read_bytes() == old_bytes
        records = plant.publisher.jsonl_path.read_bytes()
        events = [json.loads(line) for line in records.splitlines()]
        kinds = [event['event_type'] for event in events if event['change_id']]
        assert kinds == (['lab_action', 'command', 'acknowledgement'] if lab else
                         ['dose_request', 'dose_approval', 'command', 'acknowledgement'])
        if lab:
            assert events[0]['payload']['actor_id'] == 'tranos' and events[0]['payload']['approved'] is False
            assert events[1]['payload']['request_id'] is None and events[1]['payload']['approval_id'] is None
        collector = create_collector(tmp_path / 'doseproof.db').test_client()
        for line in records.splitlines():
            response = collector.post('/intake/events', data=line, content_type='application/json')
            assert response.status_code == 201, response.json
        api = create_api(tmp_path / 'doseproof.db').test_client()
        finding, = api.get('/api/changes').json['items']
        assert finding['status'] == ('FAIL' if lab else 'PASS')
        assert [row['event']['event_type'] for row in finding['actions']] == kinds
        assert len(finding['observations']) == 24
        assert all(row['event']['change_id'] is None for row in finding['observations'])
        assert all(api.get('/api/receipts/' + row['receipt_id']).status_code == 200 for row in finding['actions'])
        assert api.post('/api/changes').status_code == 405
        check = 'AC-02' if lab else 'AC-01'
        script = Path(__file__).resolve().parents[1] / 'scripts' / 'export-check.py'
        command = [sys.executable, str(script), '--run-id', plant.run_id, '--check-id', check,
                   '--evidence-dir', str(evidence)]
        subprocess.run(command, check=True, capture_output=True)
        output = evidence / plant.run_id / 'checks' / check
        assert (output / 'source-records.jsonl').read_bytes() == records
        assert 'Runtime acceptance: Not run' in (output / 'result.md').read_text(encoding='utf-8')
        assert subprocess.run(command, capture_output=True).returncode != 0
    finally:
        plant.publisher.close()
        for publisher in plant.replay_publishers:
            publisher.close()
