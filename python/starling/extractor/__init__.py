"""Starling extractor package (M0.4).

The C++ side owns the heavy work (XML parser, StatementWriter, orchestrator).
This package re-exports the bound types plus pure-Python helpers.
"""
from starling.extractor._keys import compute_extraction_span_key

__all__ = ["compute_extraction_span_key"]
