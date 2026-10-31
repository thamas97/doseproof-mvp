# Implementation responsibility

Tranos owns the operator desk, private command/controller path, plant model, separate sensors and source publishers. `python plant/app.py` now runs the plant, read-only observer and named desk. The event publisher uses a durable JSONL cursor and retries against the separate collector. See [the integrated path guide](../docs/integrated-evidence-path.md); configure local passwords privately before using the desk. The evidence dashboard has no treatment controls.
