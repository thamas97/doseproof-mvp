"""Validate copied facts, without treating source claims as authorization."""
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from monitor.storage import _decode

SCHEMA = json.loads((Path(__file__).resolve().parents[1] / 'contracts/event-envelope.schema.json').read_text())
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())
PRODUCERS = {
    'dose_request': {'operator-desk'}, 'dose_approval': {'operator-desk'},
    'command': {'operator-desk'}, 'acknowledgement': {'controller'},
    'plant_feedback': {'plant-model'}, 'sensor_observation': {'sensor-a', 'sensor-b'},
    'lab_action': {'operator-desk'},
}


class InvalidEvent(ValueError):
    pass


def utc_time(value):
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if result.tzinfo is None or result.utcoffset() != timedelta(0):
            raise ValueError()
        return result
    except (ValueError, TypeError, AttributeError):
        raise InvalidEvent('Timestamp must include UTC (Z or +00:00)') from None


def validate_event(body: bytes, received_at_utc: str) -> dict:
    try:
        event = _decode(body)
        # Refuse overflow-to-infinity too; Python's JSON decoder allows 1e999.
        json.dumps(event, ensure_ascii=False, allow_nan=False).encode('utf-8')
    except (ValueError, UnicodeError, RecursionError):
        raise InvalidEvent('Invalid UTF-8/JSON, duplicate key, excessive nesting or non-finite number') from None
    errors = sorted(VALIDATOR.iter_errors(event), key=lambda e: str(list(e.path)))
    if errors:
        error = errors[0]
        raise InvalidEvent(f"Envelope field {'/'.join(map(str, error.path)) or '/'}: {error.validator} check failed")
    for name in ('run_id', 'event_id', 'source_id'):
        if not event[name].strip() or len(event[name]) > 200:
            raise InvalidEvent(f'{name} must contain 1–200 nonblank characters')
    if event['change_id'] is not None and (not event['change_id'].strip() or len(event['change_id']) > 200):
        raise InvalidEvent('change_id must be null or 1–200 nonblank characters')
    source_time = utc_time(event['source_timestamp_utc'])
    emitted_time = utc_time(event['emitted_at_utc'])
    if source_time > emitted_time:
        raise InvalidEvent('Sample/source time must not be later than emission time')
    if emitted_time > utc_time(received_at_utc) + timedelta(seconds=5):
        raise InvalidEvent('Emission time is over five seconds ahead of collector UTC')
    kind, source, payload = event['event_type'], event['source_id'], event['payload']
    if kind in PRODUCERS and source not in PRODUCERS[kind]:
        raise InvalidEvent('Source identity does not match this event type')

    def text(*names):
        for name in names:
            if not isinstance(payload.get(name), str) or not payload[name].strip() or len(payload[name]) > 1000:
                raise InvalidEvent(f'payload.{name} must be nonblank text (maximum 1000 characters)')

    def number(*names):
        for name in names:
            value = payload.get(name)
            try:
                if type(value) in (float, int) and value >= 0 and math.isfinite(value):
                    continue
            except OverflowError:
                pass  # A JSON integer can exceed the floating-point range.
            raise InvalidEvent(f'payload.{name} must be a finite nonnegative number')

    def boolean(name):
        if not isinstance(payload.get(name), bool):
            raise InvalidEvent(f'payload.{name} must be boolean')

    if kind == 'sensor_observation':
        text('equipment_id'); number('value')
        # Unit/quality are enforced by the unchanged shared envelope schema.
    elif kind == 'plant_feedback':
        text('equipment_id'); boolean('pump_running')
        number('flow_l_s', 'actual_delivery_mg_s', 'modeled_residual_mg_l')
        if 'accepted_feed_mg_s' in payload:
            number('accepted_feed_mg_s')
    elif kind == 'dose_request':
        text('request_id', 'actor_id', 'equipment_id', 'chemical'); number('requested_feed_mg_s')
    elif kind == 'dose_approval':
        text('approval_id', 'request_id', 'approver_id', 'equipment_id', 'chemical', 'expires_at_utc')
        number('approved_feed_mg_s'); utc_time(payload['expires_at_utc'])
    elif kind == 'command':
        text('command_id', 'actor_id', 'equipment_id'); number('requested_feed_mg_s')
        if payload.get('lab_unapproved') is True:
            if 'request_id' not in payload or payload['request_id'] is not None or payload.get('approval_id') is not None:
                raise InvalidEvent('Labelled lab commands must have null request and approval IDs')
        else:
            text('request_id')
        if 'approval_id' not in payload or (payload['approval_id'] is not None and not isinstance(payload['approval_id'], str)):
            raise InvalidEvent('payload.approval_id must be nullable text')
        if isinstance(payload['approval_id'], str) and not payload['approval_id'].strip():
            raise InvalidEvent('payload.approval_id must not be blank')
    elif kind == 'acknowledgement':
        text('command_id', 'reason'); boolean('accepted'); number('accepted_feed_mg_s')
    elif kind == 'lab_action':
        text('actor_id', 'equipment_id', 'action', 'reason')
    if kind in ('dose_request', 'dose_approval', 'command', 'acknowledgement', 'lab_action') and event['change_id'] is None:
        raise InvalidEvent('Action events require an explicit change_id')
    return event
