"""Export original records for one simulation check and draft its result notes."""
import argparse
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory


def export_check(evidence_dir: Path, run_id: str, check_id: str) -> Path:
    if not re.fullmatch(r'run-[A-Za-z0-9-]+', run_id) or not re.fullmatch(r'AC-[A-Za-z0-9-]+', check_id):
        raise ValueError('Use a run ID beginning with run- and a check ID beginning with AC-.')
    run_dir = evidence_dir / run_id
    source = run_dir / 'plant-source-records.jsonl'
    original_lines = []
    events = []
    with source.open('rb') as records:
        for line in records:
            if not line.endswith(b'\n'):
                break  # A concurrent append may not have finished this line yet.
            event = json.loads(line)
            if event['run_id'] != run_id:
                raise ValueError('Source records contain a different run ID.')
            original_lines.append(line)
            events.append(event)
    if not events:
        raise ValueError('No complete source records are available for this run.')

    action_types = {'dose_request', 'dose_approval', 'lab_action', 'command', 'acknowledgement'}
    acknowledgement = next((event for event in events if event['event_type'] == 'acknowledgement'), None)
    anchor = acknowledgement['sim_step'] if acknowledgement else 0
    lines = [f'# {check_id} · {run_id}', '', f'Original records exported: {len(events)}.', '',
             'Runtime acceptance: Not run', 'Human reviewer: Pending', '', '## Recorded actions', '']
    lines.extend(f"- `{event['event_id']}` · {event['event_type']} · step {event['sim_step']} · `{event['change_id']}`"
                 for event in events if event['event_type'] in action_types)
    lines.extend(['', f'## Recorded observations for steps {anchor + 1}–{anchor + 8}', '',
                  '| Step | Source | Value (mg/L) | Event ID |', '| --- | --- | --- | --- |'])
    for event in events:
        if not anchor < event['sim_step'] <= anchor + 8:
            continue
        if event['event_type'] == 'plant_feedback':
            value = event['payload']['modeled_residual_mg_l']
        elif event['event_type'] == 'sensor_observation':
            value = event['payload']['value']
        else:
            continue
        lines.append(f"| {event['sim_step']} | {event['source_id']} | {value:.6f} | `{event['event_id']}` |")

    output = run_dir / 'checks' / check_id
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError(f'Check evidence already exists at {output}')
    with TemporaryDirectory(dir=output.parent, prefix='.export-') as temporary:
        staged = Path(temporary)
        (staged / 'source-records.jsonl').write_bytes(b''.join(original_lines))
        (staged / 'result.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
        staged.rename(output)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--check-id', required=True)
    parser.add_argument('--evidence-dir', type=Path, default=Path(__file__).resolve().parents[1] / 'evidence')
    args = parser.parse_args()
    try:
        print(export_check(args.evidence_dir, args.run_id, args.check_id))
    except (OSError, ValueError, KeyError) as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    main()
