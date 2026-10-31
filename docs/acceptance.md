# MVP acceptance register

All runtime checks are Not run. Human acceptance is pending.

| Check | Meaning | Runtime result | Review |
| --- | --- | --- | --- |
| AC-00 | Baseline consistency | Not run | Pending |
| AC-01 | Approved change | Not run | Pending |
| AC-02 | Labelled lab unapproved change | Not run | Pending |
| AC-03 | Stopped pump | Not run | Pending |
| AC-04 | Missing Sensor A | Not run | Pending |
| AC-05 | Malformed and invalid input | Not run | Pending |
| AC-06 | Duplicate and conflicting event identity | Not run | Pending |
| AC-07 | Retry and restart integrity | Not run | Pending |
| AC-08 | Passive boundary | Not run | Pending |
| AC-09 | Reset and repeatability | Not run | Pending |
| AC-10 | Independent startup and presentation | Not run | Pending |

## DPM-11 storage component check

Implemented for review: [storage handoff and actual verification](dpm-11-storage.md).
28 automated checks passed, including the original two starter checks. The
labelled fixture survived storage reconnect; SQLite integrity/foreign-key checks
passed. These component checks do not mark any full MVP scenario above passed.
Genuine plant/collector capture: Not run. Shared contract agreement: Pending.
Emmanuel acceptance: Pending. Tranos source confirmation: Pending.

## Integrated baseline evidence path — 31 October 2026

The integration branch passed **84 tests** including real HTTP/Modbus network
checks, publisher retry/restart, validation, traceability, narrow explained
findings and API write refusal. A real plant process generated run
`run-20261031T125051Z-594461` at implementation commit `bea931e`.
The captured trace contained 15 genuine source events after collector restart
and replay; original bytes matched the source outbox, invalid input was retained
and POST on the evidence API was refused. See [the verification report](milestone-verification.md).
These observations do not sign off the full scenario matrix above. Full approval/
fault assurance, visual dashboard inspection and all human acceptance remain pending.
