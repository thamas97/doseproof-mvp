"""Narrow first assurance check: same-step sensor/model consistency, not approval."""
import json

from monitor.storage import _utc_now

EXPECTED = ('plant-model', 'sensor-a', 'sensor-b')
RULE = 'sensor-model-consistency-v1'


def process_snapshot(store, event):
    if event['source_id'] not in EXPECTED or event['event_type'] not in ('plant_feedback', 'sensor_observation'):
        return
    conn = store._conn  # Internal processing shares the collector's sole writer.
    run_id, step = event['run_id'], event['sim_step']
    now = _utc_now()
    with conn:
        latest = conn.execute(
            "SELECT first_receipt_id, source_timestamp_utc FROM normalized_events WHERE run_id=? AND source_id=? AND json_extract(event_json,'$.event_type') IN ('plant_feedback','sensor_observation') ORDER BY julianday(source_timestamp_utc) DESC LIMIT 1",
            (run_id, event['source_id']),
        ).fetchone()
        health_id = f'{run_id}:{event["source_id"]}'
        conn.execute(
            'INSERT INTO source_health VALUES (?,?,?,?,?,?) ON CONFLICT(health_id) DO UPDATE SET checked_at_utc=excluded.checked_at_utc,last_receipt_id=excluded.last_receipt_id,health_json=excluded.health_json',
            (health_id, run_id, event['source_id'], now, latest['first_receipt_id'],
             json.dumps({'last_sample_time': latest['source_timestamp_utc'], 'meaning': 'Last retained observation; freshness is evaluated at read time'})),
        )
    rows = conn.execute(
        "SELECT normalized_id,first_receipt_id,event_json FROM normalized_events WHERE run_id=? AND source_id IN ('plant-model','sensor-a','sensor-b') AND json_extract(event_json,'$.event_type') IN ('plant_feedback','sensor_observation') AND json_extract(event_json,'$.sim_step')=?",
        (run_id, step),
    ).fetchall()
    grouped = {}
    for row in rows:
        item = json.loads(row['event_json'])
        grouped.setdefault(item['source_id'], []).append((row, item))
    if any(source not in grouped for source in EXPECTED):
        return  # No complete observation set; do not invent a PASS.
    ambiguous = any(len(grouped[s]) != 1 for s in EXPECTED)
    conflicts = []
    for conflict in conn.execute("SELECT r.receipt_id,r.body FROM validation_errors e JOIN raw_events r ON r.receipt_id=e.receipt_id WHERE e.code='event_identity_conflict'"):
        original = json.loads(conflict['body'])
        if original['run_id'] == run_id and original['sim_step'] == step and original['source_id'] in EXPECTED:
            conflicts.append({'event_id':original['event_id'], 'source_id':original['source_id'],
                              'receipt_id':conflict['receipt_id'], 'meaning':'Conflicting source identity'})
    chosen = [grouped[s][-1] for s in EXPECTED]
    plant, a, b = [item['payload'] for row, item in chosen]
    usable = not ambiguous and not conflicts and plant['equipment_id'] == 'dosing-pump-1' and all(
        sample['equipment_id'] == 'contact-tank' and sample['quality'] == 'good' for sample in (a, b))
    residual = plant['modeled_residual_mg_l']
    status = 'UNVERIFIED' if not usable else 'PASS' if all(abs(s['value'] - residual) <= 0.010000001 for s in (a, b)) else 'FAIL'
    reason = ('Same-run, same-step A/B measurements match modeled water within ±0.01 mg/L.' if status == 'PASS' else
              'At least one same-step sensor differs from modeled water by more than ±0.01 mg/L.' if status == 'FAIL' else
              'Ambiguous/conflicting observations, unexpected equipment or non-good sample quality prevent verification.')
    references = [{'event_id': item['event_id'], 'source_id': item['source_id'], 'normalized_id': row['normalized_id'],
                   'receipt_id': row['first_receipt_id']} for group in grouped.values() for row, item in group] + conflicts
    evidence_id = f'{RULE}:{run_id}:{step}'
    finding = {'rule_id': RULE, 'run_id': run_id, 'sim_step': step, 'status': status, 'reason': reason,
               'supporting_records': references, 'scope': 'Simulation sensor/model consistency only; no approval or drinking-water safety claim',
               'urgency': 'attention' if status != 'PASS' else 'information',
               'confidence': 'insufficient' if status == 'UNVERIFIED' else 'supported'}
    with conn:
        conn.execute('INSERT INTO linked_evidence VALUES (?,?,?,?,?,?) ON CONFLICT(evidence_id) DO UPDATE SET recorded_at_utc=excluded.recorded_at_utc,evidence_json=excluded.evidence_json',
                     (evidence_id, run_id, None, chosen[0][0]['first_receipt_id'], now, json.dumps(references)))
        conn.execute('INSERT INTO verdicts VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(verdict_id) DO UPDATE SET status=excluded.status,reason=excluded.reason,recorded_at_utc=excluded.recorded_at_utc,finding_json=excluded.finding_json',
                     (evidence_id, run_id, RULE, status, reason, evidence_id, now, json.dumps(finding)))
