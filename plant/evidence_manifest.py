"""Source-record manifest for the demonstration package (DPM-24). Read-only.

Lists each run's original plant source-record file with its SHA-256, size, record
count, simulation-step range, records per source and event type, lab actions and
exported check folders, so a reviewer can confirm the files were not changed.

Usage (repository root):
  .\\.venv\\Scripts\\python.exe -m plant.evidence_manifest                    # all runs
  .\\.venv\\Scripts\\python.exe -m plant.evidence_manifest --run <run_id> ...   # chosen runs
  ... --out C:\\dp\\dpm24-proof\\source-record-manifest.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECORD_FILE = 'plant-source-records.jsonl'


def git_commit(root: Path = ROOT) -> str | None:
    try:
        return subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=root, capture_output=True,
                              text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def describe_run(run_dir: Path) -> dict | None:
    path = run_dir / RECORD_FILE
    if not path.is_file():
        return None
    data = path.read_bytes()
    sources, types, lab_actions, steps, invalid = Counter(), Counter(), [], [], 0
    for line in data.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            invalid += 1
            continue
        sources[event.get('source_id')] += 1
        types[event.get('event_type')] += 1
        if isinstance(event.get('sim_step'), int):
            steps.append(event['sim_step'])
        if event.get('event_type') == 'lab_action':
            payload = event.get('payload') or {}
            lab_actions.append({'sim_step': event.get('sim_step'), 'actor_id': payload.get('actor_id'),
                                'action': payload.get('action'), 'event_id': event.get('event_id')})
    checks = sorted(p.name for p in (run_dir / 'checks').iterdir() if p.is_dir()) \
        if (run_dir / 'checks').is_dir() else []
    return {
        'run_id': run_dir.name,
        'file': f'{run_dir.name}/{RECORD_FILE}',
        'sha256': hashlib.sha256(data).hexdigest(),
        'bytes': len(data),
        'records': sum(sources.values()),
        'invalid_lines': invalid,
        'sim_steps': [min(steps), max(steps)] if steps else None,
        'by_source': dict(sorted(sources.items())),
        'by_event_type': dict(sorted(types.items())),
        'lab_actions': lab_actions,
        'checks': checks,
    }


def build_manifest(evidence_dir: Path, run_ids: list[str] | None = None) -> dict:
    dirs = [evidence_dir / r for r in run_ids] if run_ids else \
        sorted(p for p in evidence_dir.glob('run-*') if p.is_dir())
    runs, missing = [], []
    for run_dir in dirs:
        entry = describe_run(run_dir)
        (runs.append(entry) if entry else missing.append(run_dir.name))
    return {
        'generated_utc': datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z'),
        'commit': git_commit(),
        'evidence_dir': str(evidence_dir),
        'runs': runs,
        'missing': missing,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--evidence-dir', type=Path, default=ROOT / 'evidence')
    parser.add_argument('--run', action='append', dest='runs', help='run ID (repeatable)')
    parser.add_argument('--out', type=Path, help='write the manifest JSON here')
    args = parser.parse_args(argv)
    manifest = build_manifest(args.evidence_dir, args.runs)
    print(f"Commit {manifest['commit'] or 'unknown'} · {len(manifest['runs'])} run(s)")
    for run in manifest['runs']:
        steps = '-'.join(map(str, run['sim_steps'])) if run['sim_steps'] else 'none'
        actions = ', '.join(f"{a['action']}@{a['sim_step']}" for a in run['lab_actions']) or 'none'
        print(f"  {run['run_id']}  records={run['records']}  steps={steps}  checks={','.join(run['checks']) or '-'}"
              f"  lab={actions}\n    sha256={run['sha256']}")
    for name in manifest['missing']:
        print(f'  {name}: no {RECORD_FILE} found')
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
        print(f'Manifest written to {args.out}')
    return 1 if manifest['missing'] else 0


if __name__ == '__main__':
    sys.exit(main())
