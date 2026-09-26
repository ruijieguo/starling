"""Prompt examples must agree with the native desire-subject contract."""
import json

from starling.extractor.prompts import EXTRACTION_PROMPT


def test_preference_examples_use_the_attitude_bearer_as_subject():
    examples = []
    decoder = json.JSONDecoder()
    for line in EXTRACTION_PROMPT.splitlines():
        marker = line.find('-> {"holder"')
        if marker >= 0:
            value, _ = decoder.raw_decode(line[marker + 3:])
            if value.get("predicate") == "prefers":
                examples.append(value)
    assert examples, "expected worked preference examples"
    for example in examples:
        assert example["subject_kind"] == "cognizer", example
        if example["holder_perspective"] == "FIRST_PERSON":
            assert example["subject"] == example["holder"], example
