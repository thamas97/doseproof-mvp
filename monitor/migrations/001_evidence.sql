-- DPM-11: six record categories. Original receipts are immutable.
CREATE TABLE raw_events (
    receipt_id TEXT PRIMARY KEY,
    received_at_utc TEXT NOT NULL,
    body BLOB NOT NULL CHECK (typeof(body) = 'blob'),
    body_sha256 TEXT NOT NULL CHECK (length(body_sha256) = 64),
    content_type TEXT,
    normalized_id TEXT REFERENCES normalized_events(normalized_id)
);

CREATE TABLE normalized_events (
    normalized_id TEXT PRIMARY KEY,
    first_receipt_id TEXT NOT NULL UNIQUE REFERENCES raw_events(receipt_id),
    run_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    event_id TEXT NOT NULL,
    source_timestamp_utc TEXT NOT NULL,
    emitted_at_utc TEXT NOT NULL,
    change_id TEXT,
    event_json TEXT NOT NULL,
    UNIQUE (run_id, source_id, event_id)
);

CREATE TABLE validation_errors (
    error_id TEXT PRIMARY KEY,
    receipt_id TEXT NOT NULL REFERENCES raw_events(receipt_id),
    recorded_at_utc TEXT NOT NULL,
    stage TEXT NOT NULL,
    code TEXT NOT NULL,
    message TEXT NOT NULL
);

-- Later layers own the contents of these three categories. No results are seeded.
CREATE TABLE linked_evidence (
    evidence_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    change_id TEXT,
    anchor_receipt_id TEXT NOT NULL REFERENCES raw_events(receipt_id),
    recorded_at_utc TEXT NOT NULL,
    evidence_json TEXT NOT NULL
);

CREATE TABLE source_health (
    health_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    checked_at_utc TEXT NOT NULL,
    last_receipt_id TEXT REFERENCES raw_events(receipt_id),
    health_json TEXT NOT NULL
);

CREATE TABLE verdicts (
    verdict_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    rule_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('PASS', 'FAIL', 'PENDING', 'UNVERIFIED')),
    reason TEXT NOT NULL,
    evidence_id TEXT NOT NULL REFERENCES linked_evidence(evidence_id),
    recorded_at_utc TEXT NOT NULL,
    finding_json TEXT NOT NULL
);

CREATE INDEX raw_events_received ON raw_events(received_at_utc);
CREATE INDEX raw_events_normalized ON raw_events(normalized_id);
CREATE INDEX normalized_events_run_source ON normalized_events(run_id, source_id);
CREATE INDEX normalized_events_change ON normalized_events(run_id, change_id);
CREATE INDEX validation_errors_receipt ON validation_errors(receipt_id);

CREATE TRIGGER raw_events_no_rewrite
BEFORE UPDATE OF receipt_id, received_at_utc, body, body_sha256, content_type ON raw_events
BEGIN
    SELECT RAISE(ABORT, 'original receipts are immutable');
END;

CREATE TRIGGER raw_events_no_delete BEFORE DELETE ON raw_events
BEGIN
    SELECT RAISE(ABORT, 'original receipts are retained');
END;

CREATE TRIGGER raw_events_no_relink BEFORE UPDATE OF normalized_id ON raw_events
WHEN OLD.normalized_id IS NOT NULL AND NEW.normalized_id IS NOT OLD.normalized_id
BEGIN
    SELECT RAISE(ABORT, 'receipt already linked');
END;

CREATE TRIGGER normalized_events_no_rewrite BEFORE UPDATE ON normalized_events
BEGIN
    SELECT RAISE(ABORT, 'normalized evidence is immutable');
END;

CREATE TRIGGER normalized_events_no_delete BEFORE DELETE ON normalized_events
BEGIN
    SELECT RAISE(ABORT, 'normalized evidence is retained');
END;
