# FUXA process view

Install with npm.cmd --prefix fuxa ci. FUXA 1.3.4 is pinned from the existing reviewed starter; this does not constitute a configured MVP screen.

Before first startup create project-local state/_appdata/settings.js that imports ../../node_modules/@frangoteam/fuxa/settings.default.js and sets uiHost to 127.0.0.1 and uiPort to 1881. Do not overwrite an existing state folder. Use npm.cmd --prefix fuxa start afterward. Tranos must verify loopback binding in actual startup output.

Enable the Modbus driver if required. Connect localhost port 1502, device 1, holding registers and poll every 1000 ms. Check the address offset with independent readback; the reviewed 1.3.4 starter uses protocol address 0 as UI address 1. Apply division by 100 once for scaled values.

Use display widgets only. The observer server itself must reject single/multiple register writes. Save Project and export JSON into this folder after actual configuration; no export or screenshot has been fabricated here.

## DoseProof process overview

Import [the process overview](doseproof-process-overview.fuxap) into the demo FUXA instance after exporting its current project. The overview is a read-only mimic of the inlet, chlorine dosing pump, contact tank, two virtual sensors and outlet.

The supplied project polls the demo evidence service at `http://127.0.0.1:25202/api/sources`. For another local setup, edit the **DoseProof Evidence API** device address to point to that setup's read-only `/api/sources` endpoint. Start the matching simulator, collector and evidence API before checking the display. The controller accepted feed requires the newer plant feedback field of that name. Freshness labels show whether displayed readings still describe current samples.

The pump and tank drawings provide process context. The tank fill graphic does not measure water level. Check that the simulation step advances, flow is reported in L/s, delivered and accepted feed in mg/s, and both sensor readings in mg/L. During the missing-A rehearsal, the retained A reading turns uncertain at age 3 and unavailable at age 10 while B remains fresh.

## Interactive scenario console

Import [the scenario console](doseproof-scenario-console.fuxap) for the combined plant view and Operator Desk. The local demo uses FUXA on port 1883, the evidence reader on port 25202, and the Operator Desk on port 25200. For another local setup, update both the **DoseProof Evidence API** address and the **DoseProof Operator Desk** iframe address, plus the full-tab link. Keep the control panel on the demo laptop.

The panel runs the same Operator Desk forms and role checks used in the standalone desk. Tranos can pause, resume, reset and run the labelled lab cases. For an approved change, Emmanuel requests, Thabani approves and Tranos executes. The label "read only" applies to the process display on the left.

The local rehearsal initially used temporary test identities. If a teammate has yet to configure their password for this instance, run the following from the demo checkout. Replace `tranos` with `emmanuel` or `thabani` for the other accounts. Each member enters their own password at the terminal prompt. The running desk reads the configured file at sign-in.

```powershell
$env:MVP_DESK_USERS_FILE = (Resolve-Path 'evidence/candidate-five-20261103-181902/.env.desk-users.json').Path
$env:PYTHONPATH = (Resolve-Path '../.capability-review/.venv-runtime').Path
python -m plant.desk_users set tranos
```

Start each scenario from a fresh run. Use [the five-scenario rehearsal](../docs/demo-rehearsal.md) for the actions and expected results. The Operator Desk full-tab link gives the requests table more room if needed.
