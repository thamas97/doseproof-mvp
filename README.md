# DoseProof MVP

Private three-person educational workspace for Thabani, Tranos and Emmanuel. Target: 3 November 2026; professor review: 4 November. Four hours per person each day from 29 October through 3 November, including the weekend: 72 total team-hours.

## Current status

This workspace includes the [DPM-11 SQLite storage implementation and handoff](docs/dpm-11-storage.md). It does not yet contain a runnable treatment plant, collector, evidence API or dashboard. Storage checks pass with labelled fixtures; genuine source/collector integration and human acceptance are pending. Full MVP runtime acceptance remains **Not run**.

## Start here

- [Complete runbook](docs/runbook.md)
- [Word runbook](docs/DoseProof_Three_Person_MVP_Runbook.docx) and [matching PDF](docs/DoseProof_Three_Person_MVP_Runbook.pdf)
- [Confluence runbook and downloads](https://mail-team-bpbflevn.atlassian.net/wiki/spaces/D/pages/4161538)
- [Daily task index](docs/task-index.md)
- [AI prompt pack](docs/ai-prompts.md)
- [Shared contract brief](contracts/README.md)
- [Jira board](https://mail-team-bpbflevn.atlassian.net/jira/software/projects/DPM/boards/2) and [timeline](https://mail-team-bpbflevn.atlassian.net/jira/software/projects/DPM/boards/2/timeline)
- [Contribution workflow](CONTRIBUTING.md)

## Ownership

Tranos: layer 1 and FUXA. Emmanuel: layers 2 to 5. Thabani: layers 6 to 8 and integration. Human review rotates: Thabani reviews Tranos; Tranos reviews Emmanuel; Emmanuel reviews Thabani.

## Repository structure

plant/ holds operator/controller/model/sensor and publisher work; monitor/ holds collection, validation, linking, health, rules, SQLite and GET API; dashboard/ holds the evidence display; contracts/ holds shared interfaces; tests/ holds checks; fuxa/ holds saved exports; scripts/ holds local helpers; docs/ holds the runbook; evidence/ documents local captures ignored by Git.

## Boundaries

All equipment is simulated. DoseProof consumes copies and sends no dosing commands. FUXA is a read-only process view. Shared software sensors and one host are not independent physical measurements or production isolation. Teaching values are not real treatment operating limits.

The original [DoseProof repository](https://github.com/thamas97/doseproof) and DOS Jira project are unchanged. No license is selected for this private MVP repository.
