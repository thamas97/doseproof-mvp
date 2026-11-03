-- REPLACE can bypass delete triggers when recursive_triggers is off.
CREATE TRIGGER raw_events_no_replace BEFORE INSERT ON raw_events
WHEN EXISTS (SELECT 1 FROM raw_events WHERE receipt_id = NEW.receipt_id)
BEGIN
    SELECT RAISE(ABORT, 'original receipts are immutable');
END;

CREATE TRIGGER normalized_events_no_replace BEFORE INSERT ON normalized_events
WHEN EXISTS (
    SELECT 1 FROM normalized_events
    WHERE normalized_id = NEW.normalized_id OR first_receipt_id = NEW.first_receipt_id
       OR (run_id = NEW.run_id AND source_id = NEW.source_id AND event_id = NEW.event_id)
)
BEGIN
    SELECT RAISE(ABORT, 'normalized evidence is immutable');
END;
