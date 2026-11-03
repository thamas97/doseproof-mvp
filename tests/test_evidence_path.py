"""Real generated model events through intake, storage, rule and read-only API."""
import base64
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3

import pytest

from monitor.api_app import create_app as api_app
from monitor.collector_app import create_app as collector_app
from monitor.storage import EvidenceStore, open_read_only
from plant.config import load_baseline
from plant.events import EventFactory, plant_feedback, sensor_observation
from plant.model import PlantModel
from plant.sensors import SensorAdapter


@pytest.fixture
def path(tmp_path):
    return tmp_path / 'doseproof.db'


@pytest.fixture
def clients(path):
    collector = collector_app(path)
    return collector.test_client(), api_app(path).test_client()


def generated(run='actual-test-model-run', step=1):
    baseline = load_baseline()
    model = PlantModel(baseline)
    for _ in range(step):
        state = model.step()
    factory = EventFactory(run)
    a, b = SensorAdapter(baseline.sensor_a), SensorAdapter(baseline.sensor_b)
    return [plant_feedback(factory, state), sensor_observation(factory, a.sample(state.modeled_residual_mg_l, step)),
            sensor_observation(factory, b.sample(state.modeled_residual_mg_l, step))]


def post(client, event):
    return client.post('/intake/events', data=json.dumps(event).encode(), content_type='application/json')


def test_actual_generated_events_are_traceable_through_all_stages(clients, path):
    collector, api = clients
    originals = generated()
    receipts = [post(collector, event).json for event in originals]
    assert all(r['processing'] == 'created' for r in receipts)
    events = api.get('/api/events').json['items']
    assert len(events) == 3
    assert {r['event']['event_id'] for r in events} == {e['event_id'] for e in originals}
    assert all(r['event']['change_id'] is None for r in events)
    for item in events:
        raw = api.get('/api/receipts/'+item['receipt_id']).json
        assert json.loads(base64.b64decode(raw['original_body_base64'])) == item['event']
        assert raw['received_at_utc'] == item['received_at_utc']
    finding = api.get('/api/findings').json['items'][0]
    assert finding['status'] == 'PASS'
    assert len(finding['supporting_records']) == 3
    assert 'approval' in finding['scope']
    assert all(s['state'] == 'fresh' for s in api.get('/api/sources').json['items'])
    # All six categories were actually used, with no invented initialization approval.
    with open_read_only(path) as conn:
        assert conn.execute('SELECT count(*) FROM linked_evidence').fetchone()[0] == 1
        assert conn.execute('SELECT count(*) FROM source_health').fetchone()[0] == 3
    # A new API instance observes the same persisted IDs after connection restart.
    assert api_app(path).test_client().get('/api/events').json == api.get('/api/events').json


@pytest.mark.parametrize('fault', ['unit', 'source', 'quality', 'negative', 'oversized_integer', 'invalid_unicode', 'missing_field', 'non_utc', 'future', 'time_order', 'nan', 'duplicate_key', 'binary'])
def test_invalid_original_is_retained_without_normalization(clients, path, fault):
    collector, api = clients
    event = generated()[1]
    if fault == 'unit': event['payload']['unit'] = 'ppm-unsupported'
    if fault == 'source': event['source_id'] = 'controller'
    if fault == 'quality': event['payload']['quality'] = 'invented'
    if fault == 'negative': event['payload']['value'] = -1
    if fault == 'oversized_integer': event['payload']['value'] = 10 ** 400
    if fault == 'invalid_unicode': event['payload']['equipment_id'] = '\ud800'
    if fault == 'missing_field': del event['payload']['value']
    if fault == 'non_utc': event['source_timestamp_utc'] = '2026-10-31T10:00:00+02:00'
    if fault == 'future': event['emitted_at_utc'] = (datetime.now(timezone.utc)+timedelta(days=1)).isoformat()
    if fault == 'time_order': event['source_timestamp_utc'] = (datetime.now(timezone.utc)+timedelta(seconds=2)).isoformat()
    body = json.dumps(event).encode()
    if fault == 'nan': body = body.replace(b'"value":', b'"value": NaN, "unused":')
    if fault == 'duplicate_key': body = b'{"run_id":"one","run_id":"two"}'
    if fault == 'binary': body = b'\xff\x00'
    response = collector.post('/intake/events', data=body, content_type='application/json')
    assert response.status_code == 422
    raw = api.get('/api/receipts/'+response.json['receipt_id']).json
    assert base64.b64decode(raw['original_body_base64']) == body
    assert raw['validation_errors']
    assert api.get('/api/events').json['items'] == []
    assert api.get('/api/findings').json['items'] == []


def test_duplicate_and_conflicting_identity_keep_receipts(clients):
    collector, api = clients
    event = generated()[1]
    assert post(collector,event).status_code == 201
    assert post(collector,event).json['processing'] == 'duplicate'
    event['payload']['value'] += 0.4
    assert post(collector,event).status_code == 409
    assert api.get('/api/health').json['counts']['raw_events'] == 3
    assert len(api.get('/api/events').json['items']) == 1
    assert api.get('/api/errors').json['items'][0]['code'] == 'event_identity_conflict'


@pytest.mark.parametrize('step_shift', [0, 1])
def test_later_conflict_invalidates_supported_result_and_replay_cannot_hide_it(clients, step_shift):
    collector,api=clients
    events=generated()
    for event in events:post(collector,event)
    assert api.get('/api/findings').json['items'][0]['status']=='PASS'
    changed=json.loads(json.dumps(events[1]));changed['payload']['value']+=0.4
    changed['sim_step'] += step_shift
    assert post(collector,changed).status_code==409
    assert api.get('/api/findings').json['items'][0]['status']=='UNVERIFIED'
    post(collector,events[1])
    assert api.get('/api/findings').json['items'][0]['status']=='UNVERIFIED'


def test_startup_rechecks_a_conflict_retained_by_an_older_collector(clients, path):
    collector, api = clients
    events = generated()
    for event in events:
        post(collector, event)
    changed = json.loads(json.dumps(events[1]))
    changed['sim_step'] += 1
    with EvidenceStore(path) as store:
        receipt = store.write_raw(json.dumps(changed).encode(), content_type='application/json')
        assert store.write_normalized(receipt.receipt_id, changed).outcome == 'conflict'
    assert api.get('/api/findings').json['items'][0]['status'] == 'PASS'
    collector_app(path)
    finding = api.get('/api/findings').json['items'][0]
    assert finding['status'] == 'UNVERIFIED' and finding['sim_step'] == 1
    assert receipt.receipt_id in {record['receipt_id'] for record in finding['supporting_records']}
    post(collector,events[1])
    assert api.get('/api/findings').json['items'][0]['status']=='UNVERIFIED'


def test_missing_or_cross_run_observations_cannot_produce_a_pass(clients):
    collector, api = clients
    p, a, _b = generated('one')
    post(collector,p);post(collector,a)
    post(collector,generated('two')[2])
    assert api.get('/api/findings?run_id=one').json['items'] == []
    sources = api.get('/api/sources?run_id=one').json['items']
    assert next(s for s in sources if s['source_id']=='sensor-b')['state'] == 'unavailable'


@pytest.mark.parametrize('quality,delta,result',[('good',0.4,'FAIL'),('bad',0,'UNVERIFIED'),('uncertain',0,'UNVERIFIED')])
def test_rules_explain_disagreement_or_uncertainty(clients, quality, delta, result):
    collector,api=clients
    events=generated()
    events[1]['payload']['quality']=quality
    events[1]['payload']['value']+=delta
    for e in events: assert post(collector,e).status_code==201
    assert api.get('/api/findings').json['items'][0]['status']==result


def test_old_sample_is_not_made_fresh_by_recent_collection(clients):
    collector,api=clients
    event=generated()[1]
    old=(datetime.now(timezone.utc)-timedelta(seconds=11)).isoformat()
    event['source_timestamp_utc']=old
    assert post(collector,event).status_code==201
    source=next(s for s in api.get('/api/sources').json['items'] if s['source_id']=='sensor-a')
    assert source['state']=='unavailable'
    assert source['age_seconds']>=10
    assert source['sample']['payload']['value']!=0


@pytest.mark.parametrize('query',['limit=0','limit=201','limit=abc','limit=1&limit=2','unknown=yes','run_id=','source_id=x%27%20OR%201=1--'])
def test_query_bounds_and_parameterization(clients,query):
    collector,api=clients
    post(collector,generated()[0])
    response=api.get('/api/events?'+query)
    if query.startswith('source_id='):
        assert response.status_code==200 and response.json['items']==[]
    else:
        assert response.status_code==400


@pytest.mark.parametrize('method',['post','put','patch','delete','options'])
def test_evidence_listener_cannot_mutate_or_control(clients,method):
    collector,api=clients
    before=api.get('/api/health').json['counts']
    for endpoint in ('/api/events','/intake/events','/commands','/requests/x/execute'):
        assert getattr(api,method)(endpoint,json={}).status_code==405
    assert api.get('/api/health').json['counts']==before


def test_api_does_not_initialize_database_and_dashboard_has_no_fake_values(tmp_path):
    path=tmp_path/'missing.db'
    api=api_app(path).test_client()
    assert api.get('/api/health').status_code==503
    assert not path.exists()
    page=api.get('/')
    assert page.status_code==200
    assert b'Waiting for captured events' in page.data
    assert 'frame-ancestors' in page.headers['Content-Security-Policy']
    assert api.get('/assets/app.js').status_code==200


def test_oversize_body_is_explicitly_not_retained(clients):
    collector,api=clients
    response=collector.post('/intake/events',data=b'x'*(1024*1024+1),content_type='application/json')
    assert response.status_code==413 and response.json['retained'] is False
    assert api.get('/api/health').json['counts']['raw_events']==0
