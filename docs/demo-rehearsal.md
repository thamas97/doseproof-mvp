# DoseProof five-scenario rehearsal

Use the review candidate on a demo laptop. Keep the commit SHA, run ID, and check ID together when capturing evidence. Each run starts from the teaching baseline.

## Independent startup

1. Check out the candidate commit. With Python 3.12, create a local virtual environment and install the pinned dependencies with `python -m pip install -r requirements.lock.txt` using that environment's Python.
2. Have Emmanuel, Thabani, and Tranos set their own local desk credentials using `python -m plant.desk_users set <name>`. Use separate sessions or sign out before switching actors.
3. Start `python -m monitor.collector_app`, `python -m monitor.api_app`, and `python -m plant.app` in separate terminals from the checkout. For the labelled fault rehearsal, set `$env:MVP_LAB_MODE = '1'` in the plant terminal. The default desk is on `127.0.0.1:5000` and evidence dashboard on `127.0.0.1:5002`.
4. Open the dashboard and confirm all three sources are fresh. For FUXA, import the rehearsal package's display project and set its evidence API device address to the current API listener's `/api/sources` endpoint. The FUXA view follows the latest active run. The dashboard can select historical runs.

## Five demo checks

| Check | What to do | What to show |
| --- | --- | --- |
| AC-00 | Reset and resume. Let ten steps run. | Flow 10 L/s, delivery 15 mg/s, residual 1.00 mg/L, and separate A/B samples. |
| AC-01 | Reset to step zero. Emmanuel requests 20 mg/s, Thabani approves, and Tranos executes. Resume. | The saved approval and response finding is PASS. Delivery is 20 mg/s. Show steps 1–4 at 1.00 mg/L and steps 5–8 at 1.10, 1.18, 1.244 and 1.2952 mg/L. |
| AC-02 | Reset. Tranos uses the labelled lab command with a reason and resumes. | The lab action, command and acknowledgement appear with original links. The approval finding is FAIL because the lab command deliberately has no approval. |
| AC-03 | Repeat AC-01 through 64 steps, then select **Lab: stop pump**. | The setting stays at 20 mg/s and actual delivery is 0 mg/s. Show the saved fault FAIL and the delayed modeled residual decrease. |
| AC-04 | Reset and resume until both sensors have sampled. Select **Lab: suppress Sensor A** and allow ten steps. | A's last sample ages to unavailable, B remains fresh, and the saved fault is UNVERIFIED. |

Use **Change and fault evidence** for action and fault findings. Use **Explained check** for sensor/model consistency. Open the original action and sample links so the audience can see producer and receipt times separately. Observations retain their own identities and provide context for the action window.

## Evidence and sign-off

Save each run's original JSONL, the selected finding and receipts, and a real dashboard or FUXA capture. Restart the collector and evidence API and retrieve the same receipt again. Capture the exact candidate commit and record the reviewer and actual outcome in the acceptance register.

Tranos performs an independent startup. Emmanuel checks approval and fault explanations against original records. Thabani confirms the demo package and presents the two views. For remote viewers, verify the Tailscale link from their own devices before the session. Keep screenshots and saved evidence available for an offline walkthrough.
