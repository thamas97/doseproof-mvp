"""Capture a genuine local plant -> HTTP -> SQLite -> API demonstration.

No fixture events, accounts, approval history or screenshots are synthesized.
The optional serving window lets a person inspect/capture the actual dashboard.
"""
import argparse
import base64
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from werkzeug.serving import make_server
from monitor.api_app import create_app as api_app
from monitor.collector_app import create_app as collector_app


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def start(app, port):
    server = make_server('127.0.0.1', port, app, threaded=False)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def stop(server, thread):
    server.shutdown(); server.server_close(); thread.join(3)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--serve-seconds', type=int, default=0)
    parser.add_argument('--api-port', type=int, default=0)
    args = parser.parse_args()
    if not 0 <= args.serve_seconds <= 3600:
        parser.error('serve-seconds must be 0–3600')
    output = args.output.resolve(); output.mkdir(parents=True, exist_ok=False)
    db = output / 'doseproof.db'
    collector_port, api_port = free_port(), args.api_port or free_port()
    desk_port, controller_port, observer_port = free_port(), free_port(), free_port()
    collector, collector_thread = start(collector_app(db), collector_port)
    api, api_thread = start(api_app(db), api_port)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def request(path, data=None, method=None, collector=False):
        port = collector_port if collector else api_port
        req = urllib.request.Request(f'http://127.0.0.1:{port}{path}', data=data, method=method,
                                     headers={'Content-Type':'application/json'} if data is not None else {})
        try:
            with opener.open(req, timeout=4) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as exc:
            with exc:
                return exc.code, json.loads(exc.read())

    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', MVP_BIND_HOST='127.0.0.1',
               MVP_COLLECTOR_PORT=str(collector_port), MVP_DESK_PORT=str(desk_port),
               MVP_CONTROLLER_PORT=str(controller_port), MVP_OBSERVER_PORT=str(observer_port))
    log = (output / 'plant.log').open('w', encoding='utf-8')
    plant = subprocess.Popen([sys.executable, 'plant/app.py'], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)

    def wait_for(minimum):
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            if plant.poll() is not None:
                raise RuntimeError('Plant process stopped; inspect plant.log')
            response = request('/api/events?limit=200')[1]
            if len(response['items']) >= minimum and request('/api/findings?limit=1')[1]['items']:
                return response
            time.sleep(0.2)
        raise RuntimeError('Evidence path did not complete within 25 seconds')

    try:
        initial = wait_for(6)
        initial_count = len(initial['items'])
        stop(collector, collector_thread)
        time.sleep(2.5)  # Plant remains running and spools original events.
        collector, collector_thread = start(collector_app(db), collector_port)
        captured = wait_for(initial_count + 9)
        run_id = captured['run_id']
        findings = request('/api/findings?limit=10')[1]
        sources = request('/api/sources')[1]
        first = captured['items'][0]
        receipt = request('/api/receipts/' + first['receipt_id'])[1]
        source_file = ROOT / 'evidence' / run_id / 'plant-source-records.jsonl'
        source_bytes = source_file.read_bytes()
        lines = {json.loads(line)['event_id']:line for line in source_bytes.splitlines() if line}
        original = base64.b64decode(receipt['original_body_base64'])
        assert original == lines[first['event']['event_id']]
        bad_status, bad = request('/intake/events', data=b'{"invalid_probe":', collector=True)
        assert bad_status == 422
        retained_bad = request('/api/receipts/' + bad['receipt_id'])[1]
        assert base64.b64decode(retained_bad['original_body_base64']) == b'{"invalid_probe":'
        mutation_status, _ = request('/api/events', data=b'{}', method='POST')
        assert mutation_status == 405
        commit = subprocess.run(['git','rev-parse','HEAD'], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
        summary = {
            'kind':'actual_local_plant_execution', 'run_id':run_id, 'commit':commit,
            'captured_at_utc':datetime.now(timezone.utc).isoformat(),
            'event_count_at_capture':len(captured['items']), 'collector_restart_replay':'Observed',
            'original_wire_bytes_match_source_outbox':True,
            'sample_time':first['event']['source_timestamp_utc'], 'receipt_time':receipt['received_at_utc'],
            'validation_probe_retained':True, 'evidence_api_post_refused':True,
            'latest_finding':findings['items'][0],
            'dashboard_url':f'http://127.0.0.1:{api_port}', 'database':str(db),
            'collector_port':collector_port, 'observer_port':observer_port,
            'human_review':'Pending', 'visual_browser_check':'Pending actual browser inspection',
            'scope':'Baseline evidence path only; approved/lab-unapproved/fault scenario acceptance not claimed',
        }
        (output / 'source-records.jsonl').write_bytes(source_bytes)
        (output / 'trace.json').write_text(json.dumps({'summary':summary,'events':captured,'findings':findings,'sources':sources,'original_receipt':receipt,'invalid_probe':retained_bad},indent=2),encoding='utf-8')
        (output / 'result.md').write_text('# Actual evidence-path capture\n\n'+json.dumps(summary,indent=2)+'\n\nNo approval history, human acceptance or process screenshot was manufactured.\n',encoding='utf-8')
        print(json.dumps(summary,indent=2),flush=True)
        if args.serve_seconds:
            print(f'Dashboard remains available for {args.serve_seconds} seconds.',flush=True)
            time.sleep(args.serve_seconds)
    finally:
        plant.terminate()
        try: plant.wait(timeout=5)
        except subprocess.TimeoutExpired: plant.kill(); plant.wait(timeout=5)
        log.close()
        stop(collector, collector_thread); stop(api, api_thread)


if __name__ == '__main__':
    main()
