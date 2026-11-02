"""Export one run's ORIGINAL source records into the runbook evidence layout.

Usage:
  .\\.venv\\Scripts\\python.exe scripts\\export-check.py <run_id> <check_id>
  e.g.  scripts\\export-check.py run-20261101T030000Z-ab12cd AC-01

Creates evidence/<run_id>/checks/<check_id>/
  source-records.jsonl  - unmodified copy of the run's plant/desk/controller records
  result-draft.md       - observed timing table + change records, for YOU to complete
It never writes a result: Result and Reviewer stay "Not run" / "Pending" until a human fills them in.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

EXPECTED = {1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0, 5: 1.10, 6: 1.18, 7: 1.244, 8: 1.2952}


def main(run_id: str, check_id: str) -> None:
    run_dir = ROOT / "evidence" / run_id
    source = run_dir / "plant-source-records.jsonl"
    if not source.exists():
        raise SystemExit(f"No records found at {source}")
    out = run_dir / "checks" / check_id
    out.mkdir(parents=True, exist_ok=True)
    raw = source.read_bytes()
    (out / "source-records.jsonl").write_bytes(raw)  # byte-for-byte original export

    records = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
    feedback = {r["sim_step"]: r for r in records if r["event_type"] == "plant_feedback"}
    samples = {}
    for r in records:
        if r["event_type"] == "sensor_observation":
            samples.setdefault(r["sim_step"], {})[r["source_id"]] = r["payload"]["value"]
    actions = [r for r in records if r["change_id"]]

    lines = [
        f"# {check_id} result draft (run {run_id})",
        "",
        "Source records: source-records.jsonl in this folder (original export, unmodified).",
        "",
        "## Actions (original records with a change_id)",
        "",
        "| sim_step | source_id | event_type | event_id | change_id | key fields |",
        "|---|---|---|---|---|---|",
    ]
    for r in actions:
        p = r["payload"]
        key = {k: p[k] for k in ("actor_id", "approver_id", "request_id", "approval_id", "lab_action_id",
                                 "accepted", "requested_feed_mg_s", "accepted_feed_mg_s", "reason") if k in p}
        lines.append(f"| {r['sim_step']} | {r['source_id']} | {r['event_type']} | {r['event_id']} | {r['change_id']} | {json.dumps(key)} |")
    lines += [
        "",
        "## Observed timing (modeled residual vs teaching expectation for a command before step 1)",
        "",
        "| step | delivery mg/s | modeled residual | expected | diff | Sensor A | Sensor B |",
        "|---|---|---|---|---|---|---|",
    ]
    for step in range(1, 9):
        fb = feedback.get(step)
        if fb is None:
            lines.append(f"| {step} | not recorded | | {EXPECTED[step]} | | | |")
            continue
        res = fb["payload"]["modeled_residual_mg_l"]
        s = samples.get(step, {})
        fmt = lambda v: f"{v:.4f}" if isinstance(v, (int, float)) else "missing"
        lines.append(
            f"| {step} | {fb['payload']['actual_delivery_mg_s']} | {res:.6f} | {EXPECTED[step]} | "
            f"{abs(res - EXPECTED[step]):.6f} | {fmt(s.get('sensor-a'))} | {fmt(s.get('sensor-b'))} |"
        )
    lines += [
        "",
        "## To complete by a person",
        "",
        "- Commit: ",
        "- Settings/seeds: contracts/baseline.json (sensor-a 101, sensor-b 202)",
        "- Screenshot: screen.png (captured from the actual run)",
        "- Result: Not run",
        "- Reviewer: Pending",
        "- Cleanup: ",
    ]
    (out / "result-draft.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Exported {len(records)} original records and a draft to {out}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Usage: export-check.py <run_id> <check_id>")
    main(sys.argv[1], sys.argv[2])
