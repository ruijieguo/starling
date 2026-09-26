"""Fixed admission labels must stay attached to the original candidate."""
import json
from collections import Counter
from pathlib import Path


DATA = Path(__file__).resolve().parents[1] / "data"


def test_control_cohort_keeps_archived_semantics_and_balanced_new_contrasts():
    path = DATA / "eval_socialmem_claim_controls.json"
    assert path.exists(), "the approved fixed control cohort has not been frozen"
    controls = json.loads(path.read_text())
    assert len(controls) == len({c["id"] for c in controls}) == 64
    old = json.loads((DATA / "eval_socialmem_admission_controls.json").read_text())
    archived = {c["id"]: c for c in controls if c["origin"] == "archived"}
    assert len(archived) == 32
    for c in old:
        current = archived[c["id"]]
        assert all(current[k] == c[k] for k in ("passage", "expected_keep", "language", "category"))
        assert all(current["candidate"][k] == v for k, v in c["candidate"].items())
    new = [c for c in controls if c["origin"] == "new"]
    assert Counter((c["language"], c["expected_keep"]) for c in new) == {
        ("en", True): 8, ("en", False): 8, ("zh", True): 8, ("zh", False): 8}
    for c in controls:
        row = c["candidate"]
        assert row["holder"] == c["holder"]
        assert row["evidence"]["clause_id"] == "c0"
        assert "event_time" in row["evidence"] and "time_text" in row["evidence"]
        assert not {"expected_keep", "question", "answer", "source_time", "source_span"} & row.keys()
        assert not {"source_time", "source_span", "payload_hash"} & row["evidence"].keys()
