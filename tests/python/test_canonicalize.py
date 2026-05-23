import math
import uuid
from datetime import datetime, timezone, timedelta
import pytest
from starling.schema.value import canonicalize_object
from starling.schema.refs import CognizerRef, EntityRef, StatementRef


def _hash_of(canon: str) -> str:
    import hashlib
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


# bool ----------------------------------------------------------------------
def test_bool_true():
    canon, h = canonicalize_object(True)
    assert canon == "true"
    assert h == _hash_of("true")


def test_bool_false():
    canon, _ = canonicalize_object(False)
    assert canon == "false"


# int -----------------------------------------------------------------------
def test_int_positive():
    assert canonicalize_object(42)[0] == "42"


def test_int_negative():
    assert canonicalize_object(-17)[0] == "-17"


def test_int_zero():
    assert canonicalize_object(0)[0] == "0"


def test_int_no_grouping():
    assert canonicalize_object(1_000_000)[0] == "1000000"


def test_bool_not_int():
    # bool subclasses int in Python — guard against silent dispatch.
    assert canonicalize_object(True)[0] == "true"
    assert canonicalize_object(1)[0] == "1"


# float ---------------------------------------------------------------------
def test_float_six_decimals():
    assert canonicalize_object(1.5)[0] == "1.500000"


def test_float_negative_zero_collapses():
    assert canonicalize_object(-0.0)[0] == "0.000000"


def test_float_nan_rejected():
    with pytest.raises(ValueError, match="schema_invalid"):
        canonicalize_object(float("nan"))


def test_float_inf_rejected():
    with pytest.raises(ValueError, match="schema_invalid"):
        canonicalize_object(float("inf"))


# str -----------------------------------------------------------------------
def test_str_nfc():
    # composed (1 codepoint) vs decomposed (e + combining acute) must canonicalize equal.
    composed = "café"            # café (1 codepoint U+00E9)
    decomposed = "café"          # café (e + combining acute)
    assert canonicalize_object(composed) == canonicalize_object(decomposed)


def test_str_trim_and_fold_whitespace():
    assert canonicalize_object("  hello   world  \n")[0] == "hello world"


def test_str_lowercase():
    assert canonicalize_object("Hello World")[0] == "hello world"


def test_str_cjk_unchanged():
    assert canonicalize_object("北京")[0] == "北京"


# datetime ------------------------------------------------------------------
def test_datetime_utc():
    dt = datetime(2026, 5, 23, 12, 30, 45, tzinfo=timezone.utc)
    assert canonicalize_object(dt)[0] == "2026-05-23T12:30:45Z"


def test_datetime_tz_converted_to_utc():
    tz_plus_8 = timezone(timedelta(hours=8))
    dt = datetime(2026, 5, 23, 20, 30, 45, tzinfo=tz_plus_8)
    assert canonicalize_object(dt)[0] == "2026-05-23T12:30:45Z"


def test_datetime_naive_rejected():
    with pytest.raises(ValueError, match="schema_invalid"):
        canonicalize_object(datetime(2026, 5, 23, 12, 0, 0))


# Refs ----------------------------------------------------------------------
def test_cognizer_ref():
    u = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
    canon, _ = canonicalize_object(CognizerRef(u))
    assert canon == "CognizerRef:550e8400e29b41d4a716446655440000"


def test_entity_ref_distinct():
    u = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
    assert canonicalize_object(EntityRef(u))[0] != canonicalize_object(CognizerRef(u))[0]


def test_statement_ref():
    u = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
    canon, _ = canonicalize_object(StatementRef(u))
    assert canon.startswith("StatementRef:")


# rejected ------------------------------------------------------------------
def test_list_rejected():
    with pytest.raises(ValueError, match="schema_invalid"):
        canonicalize_object([1, 2, 3])


def test_dict_rejected():
    with pytest.raises(ValueError, match="schema_invalid"):
        canonicalize_object({"a": 1})


def test_none_rejected():
    with pytest.raises(ValueError, match="schema_invalid"):
        canonicalize_object(None)


# hash determinism ----------------------------------------------------------
def test_hash_is_sha256_hex():
    _, h = canonicalize_object("hello")
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


def test_same_input_same_hash():
    a = canonicalize_object("Hello World")
    b = canonicalize_object("hello   world")  # lowered + folded should match
    assert a == b
