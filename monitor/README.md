# Implementation responsibility

Emmanuel owns collection, validation, normalization, linking, health and rules. Thabani owns storage and the read-only API. Use collector_app.py and api_app.py as separate entrypoints; no runnable service is supplied yet. Agree storage function inputs before coding against them.
