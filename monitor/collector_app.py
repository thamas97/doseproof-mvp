"""Single-writer HTTP intake. Raw receipt commits precede all validation."""
from pathlib import Path
import logging
import os
import sqlite3
import sys
import threading

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flask import Flask, jsonify, request
from werkzeug.serving import make_server

from monitor.processing import process_snapshot, recheck_conflicts
from monitor.assurance import evaluate_change, process_assurance, sweep_pending
from monitor.storage import EvidenceStore
from monitor.validation import InvalidEvent, validate_event

ROOT = Path(__file__).resolve().parents[1]


def database_path():
    return Path(os.environ.get('MVP_DATABASE', ROOT / 'doseproof.db')).resolve()


def create_app(path=None):
    app = Flask(__name__)
    app.config['DATABASE'] = Path(path or database_path()).resolve()
    app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024
    app.extensions['write_lock'] = threading.Lock()
    with EvidenceStore(app.config['DATABASE']) as store:
        recheck_conflicts(store)
        for row in store._conn.execute('SELECT DISTINCT run_id, change_id FROM normalized_events '
                                       'WHERE change_id IS NOT NULL').fetchall():
            evaluate_change(store._conn, row['run_id'], row['change_id'])

    @app.post('/intake/events')
    def intake():
        body = request.get_data(cache=False, as_text=False)
        receipt = None
        try:
            # Even if the WSGI server is replaced, only one request writes at a time.
            with app.extensions['write_lock'], EvidenceStore(app.config['DATABASE']) as store:
                receipt = store.write_raw(body, content_type=request.content_type)
                try:
                    if request.mimetype != 'application/json':
                        raise InvalidEvent('Expected application/json')
                    event = validate_event(body, receipt.received_at_utc)
                except InvalidEvent as exc:
                    error_id = store.write_validation_error(receipt.receipt_id, code='invalid_event', message=str(exc))
                    return jsonify(receipt_id=receipt.receipt_id, processing='rejected', error_id=error_id, reason=str(exc)), 422
                outcome = store.write_normalized(receipt.receipt_id, event)
                if outcome.outcome == 'conflict':
                    recheck_conflicts(store, receipt.receipt_id)
                    return jsonify(receipt_id=receipt.receipt_id, processing='conflict', error_id=outcome.error_id), 409
                # Also retries may finish derived processing after an earlier failure.
                process_snapshot(store, event)
                process_assurance(store, event)
                return jsonify(receipt_id=receipt.receipt_id, normalized_id=outcome.normalized_id,
                               processing=outcome.outcome, meaning='Evidence received; no authorization or safety verdict implied'), 201 if outcome.outcome == 'created' else 200
        except (sqlite3.Error, OSError):
            app.logger.exception('Evidence persistence failed')
            return jsonify(error='persistence_unavailable', receipt_id=receipt.receipt_id if receipt else None,
                           retry=True), 503

    @app.errorhandler(413)
    def too_large(_error):
        return jsonify(error='body_too_large', limit_bytes=app.config['MAX_CONTENT_LENGTH'],
                       retained=False), 413

    return app


def main():
    logging.basicConfig(level=logging.INFO)
    # Monitoring listeners always bind loopback; no inherited plant control host.
    app = create_app()
    server = make_server('127.0.0.1', int(os.environ.get('MVP_COLLECTOR_PORT', '5001')), app, threaded=False)
    stopped = threading.Event()

    def check_deadlines():
        while not stopped.wait(1):
            try:
                with app.extensions['write_lock'], EvidenceStore(app.config['DATABASE']) as store:
                    sweep_pending(store)
            except (sqlite3.Error, OSError):
                app.logger.exception('Could not refresh evidence deadlines')

    worker = threading.Thread(target=check_deadlines, daemon=True)
    worker.start()
    try:
        server.serve_forever()
    finally:
        stopped.set()
        server.server_close()
        worker.join(timeout=6)


if __name__ == '__main__':
    main()
