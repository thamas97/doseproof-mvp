# Implementation responsibility

Emmanuel owns collection, validation, normalization, linking, health and rules. Thabani owns storage and the read-only API. `python -m monitor.collector_app` and `python -m monitor.api_app` now run separate loopback listeners. See [the integration guide](../docs/integrated-evidence-path.md).

DPM-11 supplies `storage.py`, migration 001 and `python -m monitor.check_storage`.
Read the [storage handoff](../docs/dpm-11-storage.md) for inputs, transaction order,
uniqueness, retry/conflict handling and pending agreement. Preserve original bytes
with `write_raw` before parsing. The fixture check is not plant/collector acceptance.
