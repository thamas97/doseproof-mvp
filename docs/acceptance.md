# MVP acceptance register

The table tracks formal acceptance. Candidate verification observations are recorded below. Human acceptance is pending.

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

## Five-scenario candidate verification (3 November 2026)

A local run at implementation commit a6b0b44 exercised the real HTTP, Modbus,
and SQLite path. The recorded outcomes below await teammate review.

| Check | Observed result |
| --- | --- |
| AC-00 | Ten baseline steps at 10 L/s flow, 15 mg/s delivery and 1.00 mg/L modeled residual, with distinct A/B samples. |
| AC-01 | Approval and controller response PASS. Delivery reached 20 mg/s and the modeled residual first rose at step 5. |
| AC-02 | Labelled lab command produced an approval FAIL with the command and acknowledgement visible and no approval event. |
| AC-03 | Accepted setting stayed at 20 mg/s while delivery fell to zero. The saved pump fault was FAIL. |
| AC-04 | Sensor A became unavailable while B stayed fresh. The saved missing-evidence finding was UNVERIFIED. |
| AC-07 | An original acknowledgement receipt matched the source bytes after the collector and API restarted. |
| AC-08 | POST, PUT, PATCH, and DELETE requests to the evidence changes endpoint returned 405. |

The rehearsal steps are in the [five-scenario guide](demo-rehearsal.md).
Original records, captures and the verification manifest are retained locally.
Independent startup, teammate access and human acceptance remain pending.
