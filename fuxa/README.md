# FUXA process view

Install with npm.cmd --prefix fuxa ci. FUXA 1.3.4 is pinned from the existing reviewed starter; this does not constitute a configured MVP screen.

Before first startup create project-local state/_appdata/settings.js that imports ../../node_modules/@frangoteam/fuxa/settings.default.js and sets uiHost to 127.0.0.1 and uiPort to 1881. Do not overwrite an existing state folder. Use npm.cmd --prefix fuxa start afterward. Tranos must verify loopback binding in actual startup output.

Enable the Modbus driver if required. Connect localhost port 1502, device 1, holding registers and poll every 1000 ms. Check the address offset with independent readback; the reviewed 1.3.4 starter uses protocol address 0 as UI address 1. Apply division by 100 once for scaled values.

Use display widgets only. The observer server itself must reject single/multiple register writes. Save Project and export JSON into this folder after actual configuration; no export or screenshot has been fabricated here.
