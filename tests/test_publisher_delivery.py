"""Real loopback delivery, durable retry/restart and retained invalid evidence."""
import json
from pathlib import Path
import threading
import time

from werkzeug.serving import make_server

from monitor.collector_app import create_app
from monitor.storage import open_read_only
from plant.events import Publisher
from tests_support import generated_events


def until(predicate, timeout=8):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        if predicate(): return
        time.sleep(0.05)
    raise AssertionError('Delivery did not finish within bounded test window')


def server_for(app):
    server=make_server('127.0.0.1',0,app,threaded=False)
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    return server,thread,f'http://127.0.0.1:{server.server_port}/intake/events'


def stop(server,thread):
    server.shutdown();server.server_close();thread.join(2)


def test_lost_ack_retries_same_source_identity_without_duplicate_logical_evidence(tmp_path):
    path=tmp_path/'doseproof.db'; app=create_app(path)
    first=[True]
    def lost_ack(environ,start_response):
        if first[0]:
            first[0]=False
            result=list(app(environ,lambda *args: None))  # actual receipt committed, response lost
            start_response('503 Service Unavailable',[('Content-Type','application/json')])
            return [b'{"error":"test_lost_ack"}']
        return app(environ,start_response)
    server,thread,url=server_for(lost_ack)
    publisher=Publisher(url,tmp_path/'run'/'records.jsonl',timeout_s=0.5)
    event=generated_events()[0]
    try:
        publisher.publish(event)
        until(lambda:publisher.sent==1)
        assert publisher.failed>=1
        with open_read_only(path) as conn:
            assert conn.execute('SELECT count(*) FROM raw_events').fetchone()[0]==2
            assert conn.execute('SELECT count(*) FROM normalized_events').fetchone()[0]==1
            assert json.loads(conn.execute('SELECT event_json FROM normalized_events').fetchone()[0])==event
        assert json.loads(publisher.delivery_path.read_text())['processing']=='duplicate'
    finally:
        publisher.close();stop(server,thread)


def test_outbox_restarts_without_replacing_producer_ids_or_times(tmp_path):
    path=tmp_path/'doseproof.db';app=create_app(path); unavailable=[True]
    def switch(environ,start_response):
        if unavailable[0]:
            start_response('503 Service Unavailable',[('Content-Type','application/json')]);return [b'{}']
        return app(environ,start_response)
    server,thread,url=server_for(switch)
    spool=tmp_path/'run'/'records.jsonl';publisher=Publisher(url,spool,timeout_s=0.5)
    events=generated_events()
    try:
        for event in events:publisher.publish(event)
        until(lambda:publisher.failed>=1)
        publisher.close()
        unavailable[0]=False
        resumed=Publisher(url,spool,timeout_s=0.5)
        try:
            until(lambda:resumed.sent==3)
            with open_read_only(path) as conn:
                saved=[json.loads(r[0]) for r in conn.execute('SELECT event_json FROM normalized_events')]
                assert {e['event_id'] for e in saved}=={e['event_id'] for e in events}
                assert all(next(v for v in saved if v['event_id']==e['event_id'])==e for e in events)
        finally:resumed.close()
    finally:publisher.close();stop(server,thread)


def test_rejected_event_is_retained_and_delivery_log_explains_terminal_rejection(tmp_path):
    path=tmp_path/'doseproof.db';server,thread,url=server_for(create_app(path))
    publisher=Publisher(url,tmp_path/'run'/'records.jsonl',timeout_s=0.5)
    event=generated_events()[1];event['payload']['unit']='wrong-unit'
    try:
        publisher.publish(event);until(lambda:publisher.sent==1)
        reply=json.loads(publisher.delivery_path.read_text())
        assert reply['http_status']==422 and reply['processing']=='rejected'
        with open_read_only(path) as conn:
            assert conn.execute('SELECT count(*) FROM raw_events').fetchone()[0]==1
            assert conn.execute('SELECT count(*) FROM normalized_events').fetchone()[0]==0
    finally:publisher.close();stop(server,thread)
