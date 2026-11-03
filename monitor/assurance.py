"""Assess action records and labelled demo faults using saved evidence only."""
from datetime import datetime, timedelta, timezone
import json

from monitor.storage import _utc_now
from monitor.validation import utc_time

ACTION_RULE = 'approval-response-v1'
FAULT_RULE = 'lab-fault-response-v1'
ACTION_TYPES = ('dose_request', 'dose_approval', 'command', 'acknowledgement', 'lab_action')
FAULTS = ('stop-pump', 'suppress-a')
EVENT_ROWS = '''
    SELECT n.normalized_id, n.first_receipt_id, n.event_json, r.received_at_utc
    FROM normalized_events n JOIN raw_events r ON r.receipt_id=n.first_receipt_id
'''


def evidence_rows(conn, query, params):
    return [{**dict(row), 'event': json.loads(row['event_json'])}
            for row in conn.execute(EVENT_ROWS + query, params)]


def reference(row):
    event = row['event']
    return {'event_id': event['event_id'], 'source_id': event['source_id'],
            'receipt_id': row['first_receipt_id'], 'normalized_id': row['normalized_id']}


def conflict_receipts(conn, rows):
    identities = {(r['event']['run_id'], r['event']['source_id'], r['event']['event_id']) for r in rows}
    receipts = []
    for row in conn.execute('SELECT DISTINCT r.receipt_id, r.body FROM validation_errors e '
                            'JOIN raw_events r ON r.receipt_id=e.receipt_id WHERE e.code=?',
                            ('event_identity_conflict',)):
        event = json.loads(row['body'])
        if (event['run_id'], event['source_id'], event['event_id']) in identities:
            receipts.append({'receipt_id': row['receipt_id'], 'source_id': event['source_id'],
                             'event_id': event['event_id'], 'meaning': 'Conflicting source identity'})
    return receipts


def save(conn, rule, run_id, change_id, rows, outcome, *, scope, deadline=None, conflicts=()):
    status, reason = outcome
    identifier = rule + ':' + json.dumps([run_id, change_id], separators=(',', ':'))
    references = [reference(row) for row in rows] + list(conflicts)
    finding = {'rule_id': rule, 'run_id': run_id, 'change_id': change_id, 'status': status,
               'reason': reason, 'scope': scope, 'deadline_utc': deadline.isoformat() if deadline else None,
               'supporting_records': references, 'urgency': 'attention' if status in ('FAIL', 'UNVERIFIED') else 'information',
               'confidence': 'supported' if status in ('PASS', 'FAIL') else 'insufficient'}
    content = json.dumps(finding)
    previous = conn.execute('SELECT finding_json FROM verdicts WHERE verdict_id=?', (identifier,)).fetchone()
    if previous and previous['finding_json'] == content:
        return
    now = _utc_now()
    with conn:
        conn.execute('INSERT INTO linked_evidence VALUES (?,?,?,?,?,?) ON CONFLICT(evidence_id) '
                     'DO UPDATE SET recorded_at_utc=excluded.recorded_at_utc,evidence_json=excluded.evidence_json',
                     (identifier, run_id, change_id, rows[0]['first_receipt_id'], now, json.dumps(references)))
        conn.execute('INSERT INTO verdicts VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(verdict_id) '
                     'DO UPDATE SET status=excluded.status,reason=excluded.reason,recorded_at_utc=excluded.recorded_at_utc,'
                     'finding_json=excluded.finding_json',
                     (identifier, run_id, rule, status, reason, identifier, now, content))


def assess_action(events, deadline, now):
    command = events.get('command')
    lab = events.get('lab_action')
    is_lab = bool(lab or (command and command['payload'].get('lab_unapproved') is True))
    expected = ('lab_action', 'command', 'acknowledgement') if is_lab else (
        'dose_request', 'dose_approval', 'command', 'acknowledgement')
    if is_lab and any(kind in events for kind in ('dose_request', 'dose_approval')):
        return 'FAIL', 'The lab change unexpectedly contains a request or approval record.'
    if any(kind not in events for kind in expected):
        missing = ', '.join(kind.replace('_', ' ') for kind in expected if kind not in events)
        return ('PENDING', f'Waiting for {missing} within the evidence window.') if now < deadline else (
            'UNVERIFIED', f'The evidence window ended with no matching {missing}.')
    ordered = [events[kind] for kind in expected]
    if any(utc_time(a['source_timestamp_utc']) > utc_time(b['source_timestamp_utc']) or a['sim_step'] > b['sim_step']
           for a, b in zip(ordered, ordered[1:])):
        return 'FAIL', 'The original timestamps or steps contradict the action sequence.'
    c, ack = command['payload'], events['acknowledgement']['payload']
    if c['command_id'] != ack['command_id'] or not ack['accepted'] or c['requested_feed_mg_s'] != ack['accepted_feed_mg_s']:
        return 'FAIL', 'The controller response rejects or does not match the command and its requested feed.'
    if utc_time(events['acknowledgement']['source_timestamp_utc']) - utc_time(command['source_timestamp_utc']) > timedelta(seconds=10):
        return 'FAIL', 'The original acknowledgement arrived outside the ten-second response window.'
    if is_lab:
        marker = lab['payload']
        if (marker.get('action') == 'lab_unapproved_change' and marker.get('approved') is False
                and c.get('lab_unapproved') is True and c['request_id'] is None and c['approval_id'] is None
                and all(marker.get(key) == c[key] for key in ('command_id', 'actor_id', 'equipment_id', 'requested_feed_mg_s'))):
            return 'FAIL', 'The controller accepted a labelled lab change with no approval. This is the expected lab finding.'
        return 'UNVERIFIED', 'The lab action and command records do not establish a matching labelled lab change.'
    req, approval = events['dose_request']['payload'], events['dose_approval']['payload']
    if (req['request_id'] != approval['request_id'] or req['request_id'] != c['request_id']
            or approval['approval_id'] != c['approval_id'] or req['actor_id'] == approval['approver_id']
            or any(req.get(key) != approval.get(key) for key in ('equipment_id', 'chemical', 'target'))
            or not req.get('target') or req['equipment_id'] != c['equipment_id']
            or req['requested_feed_mg_s'] != approval['approved_feed_mg_s']
            or req['requested_feed_mg_s'] != c['requested_feed_mg_s']
            or utc_time(command['source_timestamp_utc']) >= utc_time(approval['expires_at_utc'])):
        return 'FAIL', 'The command does not match a separate, unexpired approval for the requested setting.'
    return 'PASS', 'The request, separate approval, command and controller response agree within the approval window.'


def evaluate_change(conn, run_id, change_id, now=None):
    now = now or datetime.now(timezone.utc)
    rows = evidence_rows(conn, 'WHERE n.run_id=? AND n.change_id=? ORDER BY r.received_at_utc', (run_id, change_id))
    rows = [row for row in rows if row['event']['event_type'] in ACTION_TYPES]
    if not rows:
        return
    events = {r['event']['event_type']: r['event'] for r in rows}
    marker = next((r for r in rows if r['event']['event_type'] == 'lab_action'
                   and r['event']['payload']['action'] in FAULTS), None)
    if marker:
        return evaluate_fault(conn, run_id, change_id, marker, rows, now)
    anchor = next((r for r in rows if r['event']['event_type'] == 'command'), rows[0])
    deadline = utc_time(anchor['received_at_utc']) + timedelta(seconds=10 if 'command' in events else 600)
    conflicts = conflict_receipts(conn, rows)
    if conflicts or len(rows) != len(events):
        outcome = 'UNVERIFIED', 'Conflicting or ambiguous records prevent verification of this action chain.'
    else:
        outcome = assess_action(events, deadline, now)
    save(conn, ACTION_RULE, run_id, change_id, rows, outcome, deadline=deadline, conflicts=conflicts,
         scope='Copied approval and controller response evidence. Delivery and water measurements are separate.')


def step_observations(conn, run_id, first, last):
    return evidence_rows(conn, "WHERE n.run_id=? AND json_extract(n.event_json,'$.sim_step') BETWEEN ? AND ? "
                         "AND json_extract(n.event_json,'$.event_type') IN ('plant_feedback','sensor_observation') "
                         "ORDER BY json_extract(n.event_json,'$.sim_step'), n.source_id", (run_id, first, last))


def evaluate_fault(conn, run_id, change_id, marker_row, markers, now):
    marker = marker_row['event']
    pump = marker['payload']['action'] == 'stop-pump'
    first = int(marker['sim_step']) + 1
    last = first if pump else first + 9
    observations = step_observations(conn, run_id, first, last)
    rows = markers + observations
    conflicts = conflict_receipts(conn, rows)
    deadline = utc_time(marker_row['received_at_utc']) + timedelta(seconds=25)
    grouped = {(r['event']['source_id'], r['event']['sim_step']): r['event']['payload'] for r in observations}
    expected = [('plant-model', step) for step in range(first, last + 1)]
    if not pump:
        expected += [('sensor-b', step) for step in range(first, last + 1)]
    if conflicts or len(markers) != 1 or len(grouped) != len(observations):
        outcome = 'UNVERIFIED', 'Conflicting or ambiguous records prevent verification of this fault window.'
    elif pump and expected[0] in grouped:
        p = grouped[expected[0]]
        if p['equipment_id'] == 'dosing-pump-1' and not p['pump_running'] and p['actual_delivery_mg_s'] == 0 and p.get('accepted_feed_mg_s', 0) > 0:
            outcome = 'FAIL', f"Pump stopped: accepted setting {p['accepted_feed_mg_s']:g} mg/s, actual delivery 0 mg/s."
        else:
            outcome = 'UNVERIFIED', 'Feedback does not establish the expected stopped pump and delivery discrepancy.'
    elif not pump and any(source == 'sensor-a' for source, _step in grouped):
        outcome = 'UNVERIFIED', 'Sensor A records appeared during the requested suppression window.'
    elif not pump and all(key in grouped for key in expected):
        continuous = all(grouped['sensor-b', step]['quality'] == 'good' and
                         grouped['sensor-b', step]['equipment_id'] == 'contact-tank' and
                         grouped['plant-model', step]['equipment_id'] == 'dosing-pump-1'
                         for step in range(first, last + 1))
        reason = ('Sensor A has no sample for ten observed steps; plant and Sensor B continued.' if continuous else
                  'Sensor B or plant evidence is unreliable during the ten-step window.')
        outcome = 'UNVERIFIED', reason
    else:
        outcome = ('PENDING', 'Waiting for the fault observation window.') if now < deadline else (
            'UNVERIFIED', 'The fault observation window ended without enough corroborating records.')
    save(conn, FAULT_RULE, run_id, change_id, rows, outcome, deadline=deadline, conflicts=conflicts,
         scope='Labelled simulation fault and its bounded observation window.')


def process_assurance(store, event):
    conn = store._conn
    run_id = event['run_id']
    if event['change_id'] and event['event_type'] in ACTION_TYPES:
        evaluate_change(conn, run_id, event['change_id'])
    elif event['event_type'] in ('plant_feedback', 'sensor_observation'):
        for row in conn.execute("SELECT DISTINCT change_id FROM normalized_events WHERE run_id=? AND change_id IS NOT NULL AND "
                                "json_extract(event_json,'$.event_type')='lab_action' AND "
                                "json_extract(event_json,'$.payload.action') IN ('stop-pump','suppress-a') AND "
                                "? BETWEEN json_extract(event_json,'$.sim_step')+1 AND json_extract(event_json,'$.sim_step')+10",
                                (run_id, event['sim_step'])).fetchall():
            evaluate_change(conn, run_id, row['change_id'])


def sweep_pending(store):
    conn = store._conn
    for row in conn.execute("SELECT run_id, json_extract(finding_json,'$.change_id') AS change_id FROM verdicts "
                            "WHERE rule_id IN (?,?) AND status='PENDING' AND "
                            "julianday(json_extract(finding_json,'$.deadline_utc')) <= julianday('now')",
                            (ACTION_RULE, FAULT_RULE)).fetchall():
        evaluate_change(conn, row['run_id'], row['change_id'])
