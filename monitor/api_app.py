"""Read-only evidence queries and local dashboard; no plant imports/credentials."""
import base64
from contextlib import closing
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flask import Flask, abort, jsonify, request, send_from_directory
from werkzeug.serving import make_server

from monitor.storage import open_read_only
from monitor.validation import utc_time
from monitor.assurance import ACTION_RULE, ACTION_TYPES, FAULT_RULE, evidence_rows, reference, step_observations
from monitor.processing import RULE

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ('plant-model', 'sensor-a', 'sensor-b')


def create_app(path=None):
    app = Flask(__name__, static_folder=None)
    app.config['DATABASE'] = Path(path or os.environ.get('MVP_DATABASE', ROOT / 'doseproof.db')).resolve()

    @app.before_request
    def read_only():
        if request.method not in ('GET', 'HEAD'):
            return jsonify(error='read_only_api'), 405

    @app.after_request
    def headers(response):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'"
        return response

    @app.errorhandler(sqlite3.Error)
    def unavailable(_error):
        return jsonify(error='evidence_database_unavailable', meaning='No evidence conclusion can be drawn'), 503

    @app.errorhandler(400)
    def invalid(error):
        return jsonify(error='invalid_query', reason=error.description), 400

    def filters(allowed=('run_id', 'limit')):
        if set(request.args) - set(allowed) or any(len(request.args.getlist(k)) != 1 for k in request.args):
            abort(400, 'Unknown or repeated query parameter')
        for k, value in request.args.items():
            if not value.strip() or len(value) > 200:
                abort(400, f'Invalid {k}')
        try:
            limit = int(request.args.get('limit', '50'))
        except ValueError:
            abort(400, 'limit must be an integer')
        if not 1 <= limit <= 200:
            abort(400, 'limit must be 1–200')
        return request.args.get('run_id'), limit

    def selected_run(conn, run_id):
        if run_id:
            return run_id
        row = conn.execute('SELECT n.run_id FROM normalized_events n JOIN raw_events r ON r.receipt_id=n.first_receipt_id ORDER BY r.received_at_utc DESC LIMIT 1').fetchone()
        return row['run_id'] if row else None

    @app.get('/')
    def dashboard():
        return send_from_directory(ROOT / 'dashboard', 'index.html')

    @app.get('/assets/<name>')
    def asset(name):
        if name not in ('app.js', 'style.css'):
            abort(404)
        return send_from_directory(ROOT / 'dashboard', name)

    @app.get('/api/health')
    def health():
        filters(())
        with closing(open_read_only(app.config['DATABASE'])) as conn:
            counts = {table: conn.execute(f'SELECT count(*) FROM {table}').fetchone()[0] for table in
                      ('raw_events', 'normalized_events', 'validation_errors', 'verdicts')}
        return jsonify(service='read-only evidence API', database='readable', counts=counts,
                       meaning='Service health is not plant health or approval', server_time_utc=datetime.now(timezone.utc).isoformat())

    @app.get('/api/runs')
    def runs():
        _, limit = filters(('limit',))
        with closing(open_read_only(app.config['DATABASE'])) as conn:
            rows = conn.execute('SELECT n.run_id, count(*) AS event_count, max(r.received_at_utc) AS last_received_at_utc FROM normalized_events n JOIN raw_events r ON r.receipt_id=n.first_receipt_id GROUP BY n.run_id ORDER BY last_received_at_utc DESC LIMIT ?', (limit,)).fetchall()
        return jsonify(items=[dict(r) for r in rows])

    @app.get('/api/events')
    def events():
        run_id, limit = filters(('run_id', 'source_id', 'change_id', 'limit'))
        with closing(open_read_only(app.config['DATABASE'])) as conn:
            run_id = selected_run(conn, run_id)
            clauses, values = ['n.run_id=?'], [run_id]
            for name in ('source_id', 'change_id'):
                if name in request.args:
                    clauses.append(f'n.{name}=?'); values.append(request.args[name])
            rows = conn.execute('SELECT n.normalized_id,n.first_receipt_id,n.event_json,r.received_at_utc FROM normalized_events n JOIN raw_events r ON r.receipt_id=n.first_receipt_id WHERE ' + ' AND '.join(clauses) + ' ORDER BY r.received_at_utc DESC LIMIT ?', (*values, limit)).fetchall()
        return jsonify(run_id=run_id, items=[{'normalized_id':r['normalized_id'], 'receipt_id':r['first_receipt_id'],
                       'received_at_utc':r['received_at_utc'], 'event':json.loads(r['event_json'])} for r in rows])

    @app.get('/api/receipts/<receipt_id>')
    def receipt(receipt_id):
        filters(())
        with closing(open_read_only(app.config['DATABASE'])) as conn:
            row = conn.execute('SELECT * FROM raw_events WHERE receipt_id=?', (receipt_id,)).fetchone()
            if not row:
                abort(404)
            errors = [dict(r) for r in conn.execute('SELECT error_id,stage,code,message FROM validation_errors WHERE receipt_id=?', (receipt_id,))]
        return jsonify(receipt_id=receipt_id, received_at_utc=row['received_at_utc'], content_type=row['content_type'],
                       body_sha256=row['body_sha256'], body_encoding='base64', original_body_base64=base64.b64encode(row['body']).decode(),
                       normalized_id=row['normalized_id'], validation_errors=errors)

    @app.get('/api/errors')
    def errors():
        _, limit = filters(('limit',))
        with closing(open_read_only(app.config['DATABASE'])) as conn:
            rows = conn.execute('SELECT * FROM validation_errors ORDER BY recorded_at_utc DESC LIMIT ?', (limit,)).fetchall()
        return jsonify(items=[dict(r) for r in rows], scope='All retained receipts; some invalid records have no trustworthy run identity')

    @app.get('/api/findings')
    def findings():
        run_id, limit = filters()
        with closing(open_read_only(app.config['DATABASE'])) as conn:
            run_id = selected_run(conn, run_id)
            rows = conn.execute('SELECT recorded_at_utc,finding_json FROM verdicts WHERE run_id=? AND rule_id=? ORDER BY recorded_at_utc DESC LIMIT ?', (run_id, RULE, limit)).fetchall()
        return jsonify(run_id=run_id, items=[dict(json.loads(r['finding_json']), recorded_at_utc=r['recorded_at_utc']) for r in rows],
                       scope='Same-step sensor/model consistency. Action and fault findings are available under /api/changes.')

    @app.get('/api/changes')
    def changes():
        run_id, limit = filters()
        with closing(open_read_only(app.config['DATABASE'])) as conn:
            run_id = selected_run(conn, run_id)
            rows = conn.execute('SELECT recorded_at_utc,finding_json FROM verdicts WHERE run_id=? '
                                'AND rule_id IN (?,?) ORDER BY recorded_at_utc DESC, verdict_id LIMIT ?',
                                (run_id, ACTION_RULE, FAULT_RULE, limit)).fetchall()
            items = []
            for row in rows:
                finding = json.loads(row['finding_json'])
                records = evidence_rows(conn, 'WHERE n.run_id=? AND n.change_id=? ORDER BY r.received_at_utc',
                                        (run_id, finding['change_id']))
                records = [record for record in records if record['event']['event_type'] in ACTION_TYPES]
                anchors = [r['event'] for r in records if r['event']['event_type'] == (
                    'acknowledgement' if finding['rule_id'] == ACTION_RULE else 'lab_action')]
                observations = []
                if len(anchors) == 1:
                    first = int(anchors[0]['sim_step']) + 1
                    window = 8 if finding['rule_id'] == ACTION_RULE else 10
                    observations = step_observations(conn, run_id, first, first + window - 1)
                items.append({**finding, 'recorded_at_utc': row['recorded_at_utc'],
                              'actions': [{**reference(r), 'event': r['event']} for r in records],
                              'observations': [{**reference(r), 'event': r['event']} for r in observations]})
        return jsonify(run_id=run_id, items=items,
                       observation_scope='Same-run observations after the anchor step. They retain their original identities and do not establish causation.')

    @app.get('/api/sources')
    def sources():
        run_id, _limit = filters()
        now = datetime.now(timezone.utc)
        items = []
        with closing(open_read_only(app.config['DATABASE'])) as conn:
            run_id = selected_run(conn, run_id)
            for source in SOURCES:
                row = conn.execute("SELECT n.event_json,n.first_receipt_id,r.received_at_utc FROM normalized_events n JOIN raw_events r ON r.receipt_id=n.first_receipt_id WHERE n.run_id=? AND n.source_id=? AND json_extract(n.event_json,'$.event_type') IN ('plant_feedback','sensor_observation') ORDER BY julianday(n.source_timestamp_utc) DESC LIMIT 1", (run_id, source)).fetchone()
                if row is None:
                    items.append({'source_id':source, 'state':'unavailable', 'age_seconds':None, 'sample':None})
                    continue
                event = json.loads(row['event_json'])
                signed_age = (now - utc_time(event['source_timestamp_utc'])).total_seconds()
                age = max(0, signed_age)
                quality = event['payload'].get('quality', 'not_applicable')
                state = 'clock_skew' if signed_age < -1 else 'unavailable' if age >= 10 else 'stale' if age >= 3 else 'unreliable' if quality in ('bad', 'uncertain') else 'fresh'
                items.append({'source_id':source, 'state':state, 'age_seconds':round(age, 3),
                              'sample':event, 'receipt_id':row['first_receipt_id'], 'received_at_utc':row['received_at_utc']})
        return jsonify(run_id=run_id, checked_at_utc=now.isoformat(), items=items,
                       policy='Freshness uses original source UTC time: stale at 3 seconds, unavailable at 10; proposal for team review')

    return app


def main():
    server = make_server('127.0.0.1', int(os.environ.get('MVP_API_PORT', '5002')), create_app(), threaded=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
