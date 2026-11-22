"""DPM-24: a fresh checkout can be started from the written instructions alone.

Automated part of the independent-startup check. The person-led startup on another
member's laptop is recorded separately in plant/STARTUP-CHECKLIST.md.
"""
import json
import re
from pathlib import Path

import pytest

from plant import desk_users
from plant.app import Plant
from plant.config import ServiceSettings, load_service_settings
from plant.evidence_manifest import build_manifest, main as manifest_main

ROOT = Path(__file__).resolve().parents[1]
CHECKLIST = ROOT / 'plant' / 'STARTUP-CHECKLIST.md'
FUXA_EXPORT = ROOT / 'fuxa' / 'doseproof-observer-project.json'
REGISTER_NAMES = [
    'sensor_a_mg_l', 'sensor_b_mg_l', 'flow_l_s', 'requested_feed_mg_s', 'accepted_feed_mg_s',
    'actual_delivery_mg_s', 'pump_running', 'ack_counter', 'sensor_a_quality', 'sensor_b_quality',
    'sensor_a_age_s', 'sensor_b_age_s', 'tick_counter',
]


def test_checklist_names_only_files_and_services_that_exist():
    text = CHECKLIST.read_text(encoding='utf-8')
    scripts = set(re.findall(r'scripts\\([\w.-]+\.(?:py|ps1))', text))
    assert {'setup-python.ps1', 'start-mvp.ps1', 'observer-readback.py', 'observer-write-probe.py'} <= scripts
    for name in scripts:
        assert (ROOT / 'scripts' / name).is_file(), name
    start = (ROOT / 'scripts' / 'start-mvp.ps1').read_text(encoding='utf-8')
    for service in re.findall(r'-Service (\w+)', text):
        assert f"'{service}'" in start, service
    assert 'fuxa\\doseproof-observer-project.json' in text and FUXA_EXPORT.is_file()
    assert "uiHost: '127.0.0.1'" in text                      # loopback FUXA before first start
    assert '-m plant.desk_users set' in text and 'Actual' in text


def test_fresh_checkout_defaults_are_loopback_and_need_no_shared_password(tmp_path, monkeypatch):
    for name in ('MVP_BIND_HOST', 'MVP_OBSERVER_PORT', 'MVP_CONTROLLER_PORT', 'MVP_DESK_PORT', 'MVP_LAB_MODE'):
        monkeypatch.delenv(name, raising=False)
    settings = load_service_settings()
    assert settings.bind_host == '127.0.0.1'
    assert (settings.observer_port, settings.controller_port, settings.desk_port) == (1502, 1503, 5000)
    assert settings.collector_url.startswith('http://127.0.0.1:')

    empty = tmp_path / '.env.desk-users.json'                 # a fresh laptop has no password file
    for user in desk_users.USERS:
        assert desk_users.authenticate(user, 'any-guess-1234', empty) is None
    assert '.env.*' in (ROOT / '.gitignore').read_text(encoding='utf-8').splitlines()

    plant = Plant('run-fresh', settings=ServiceSettings('127.0.0.1', 0, 0, 0, 'http://127.0.0.1:9/none', tmp_path))
    try:
        assert plant.tick()[2:7] == [1000, 1500, 1500, 1500, 1]   # baseline straight after a clean start
    finally:
        plant.publisher.close()
        for publisher in plant.replay_publishers:
            publisher.close()


def test_saved_fuxa_export_matches_the_observer_contract():
    project = json.loads(FUXA_EXPORT.read_text(encoding='utf-8'))
    observers = [d for d in project['devices'].values() if d.get('type') == 'ModbusTCP']
    assert len(observers) == 1
    device = observers[0]
    assert device['property']['address'] == '127.0.0.1:1502'
    assert str(device['property']['slaveid']) == '1' and device['polling'] == 1000
    tags = sorted(device['tags'].values(), key=lambda t: int(t['address']))
    assert [t['name'] for t in tags] == REGISTER_NAMES          # contract names, lower-case l for litres
    assert [int(t['address']) for t in tags] == list(range(1, 14))  # UI address = protocol address + 1
    assert {t['memaddress'] for t in tags} == {'400000'}         # holding registers only
    assert {t['type'] for t in tags} == {'UInt16'}
    scaled = [t['name'] for t in tags if str(t.get('divisor') or '') == '100']
    assert scaled == REGISTER_NAMES[:6]                          # divide by 100 once, only scaled values


def test_source_record_manifest_fingerprints_original_records(tmp_path, monkeypatch):
    monkeypatch.setenv('MVP_LAB_MODE', '1')
    plant = Plant('run-manifest', settings=ServiceSettings('127.0.0.1', 0, 0, 0, 'http://127.0.0.1:9/none', tmp_path))
    try:
        for _ in range(4):
            plant.tick()
        plant._control_run(desk_users.USERS['tranos'], 'stop-pump', plant.run_id)
        plant.tick()
    finally:
        plant.publisher.close()
        for publisher in plant.replay_publishers:
            publisher.close()
    records = tmp_path / 'run-manifest' / 'plant-source-records.jsonl'
    (tmp_path / 'run-manifest' / 'checks' / 'AC-03').mkdir(parents=True)
    before = records.read_bytes()

    manifest = build_manifest(tmp_path, ['run-manifest', 'run-missing'])
    assert records.read_bytes() == before                         # read-only
    (run,) = manifest['runs']
    import hashlib
    assert run['sha256'] == hashlib.sha256(before).hexdigest() and run['bytes'] == len(before)
    assert run['records'] == len(before.splitlines()) and run['invalid_lines'] == 0
    assert run['sim_steps'] == [1, 5] and run['checks'] == ['AC-03']
    assert run['by_source']['plant-model'] == 5
    assert [a['action'] for a in run['lab_actions']] == ['stop-pump']
    assert manifest['missing'] == ['run-missing']

    out = tmp_path / 'proof' / 'manifest.json'
    assert manifest_main(['--evidence-dir', str(tmp_path), '--run', 'run-manifest', '--out', str(out)]) == 0
    assert json.loads(out.read_text(encoding='utf-8'))['runs'][0]['sha256'] == run['sha256']


@pytest.mark.parametrize('bad', ['not json', ''])
def test_manifest_counts_damaged_lines_instead_of_hiding_them(tmp_path, bad):
    run_dir = tmp_path / 'run-damaged'
    run_dir.mkdir()
    (run_dir / 'plant-source-records.jsonl').write_text(
        json.dumps({'source_id': 'sensor-b', 'event_type': 'sensor_observation', 'sim_step': 1, 'payload': {}})
        + '\n' + bad + '\n', encoding='utf-8')
    (run,) = build_manifest(tmp_path)['runs']
    assert run['records'] == 1 and run['invalid_lines'] == (1 if bad else 0)
