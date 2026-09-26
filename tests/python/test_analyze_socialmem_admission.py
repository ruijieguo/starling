import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import analyze_socialmem_admission as analysis
import eval_socialmem_admission as admission


@pytest.mark.parametrize("wrapper", ["{}", "```json\n{}\n```", "```\r\n{}\r\n```"])
def test_only_envelope_changes_without_changing_decisions(wrapper):
    case = {"holder": "Mina", "passage": "Mina: I believe Jules owns deployments."}
    candidate = {"holder": "Mina", "subject": "Mina", "subject_kind": "cognizer",
                 "predicate": "trusts", "object": "Jules with deployments", "polarity": "POS",
                 "holder_perspective": "FIRST_PERSON", "modality": "BELIEVES", "nesting_depth": 0}
    raw = json.dumps([{"index": 0, "decision": "reject", "reason": "wrong_relation", "quotes": []}])
    expected = admission.apply_decisions(case, [candidate], raw)
    assert admission.apply_decisions(case, [candidate], analysis.envelope_payload(wrapper.format(raw))) == expected


@pytest.mark.parametrize("raw", ['[]\n[]', '```json\n[]\n```\n```json\n[]\n```',
                                  'Here is the result:\n```json\n[]\n```', '```json\n[\n```'])
def test_multiple_arrays_prose_and_malformed_json_are_not_repaired(raw):
    result = admission.apply_decisions({"holder": "Mina", "passage": "source"}, [],
                                      analysis.envelope_payload(raw))
    assert not result["ok"]
