"""Starter document/schema checks only. These do not exercise an MVP runtime."""
import json
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker

ROOT=Path(__file__).resolve().parents[1]
def test_illustrative_envelope_matches_schema():
    schema=json.loads((ROOT/'contracts/event-envelope.schema.json').read_text())
    example=json.loads((ROOT/'contracts/illustrative-observation.json').read_text())
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema,format_checker=FormatChecker()).validate(example)
    assert 'illustrative' in example['run_id']
    assert example['change_id'] is None

def test_baseline_teaching_arithmetic():
    b=json.loads((ROOT/'contracts/baseline.json').read_text())
    assert max(0,b['accepted_feed_mg_s']/b['flow_l_s']-b['demand_mg_l'])==1.0
    residual=1.0
    observed=[]
    for step in range(1,9):
        if step>4: residual+=0.2*(1.5-residual)
        observed.append(residual)
    assert observed[:4]==[1.0]*4
    assert all(abs(a-b)<1e-12 for a,b in zip(observed[4:],[1.1,1.18,1.244,1.2952]))
