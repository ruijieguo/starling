"""Helpers for building canonical_key strings per event_type (§3.10)."""


def canonical_key_for_statement_created(statement_id: str) -> str:
    return f"statement_id={statement_id}"


def canonical_key_for_statement_superseded(superseded_id: str, supersede_id: str) -> str:
    return f"superseded={superseded_id};by={supersede_id}"


def canonical_key_for_engram_appended(content_hash: str, holder_id: str) -> str:
    return f"engram_content={content_hash};holder={holder_id}"


def causation_root(causation_chain: tuple[str, ...]) -> str:
    return causation_chain[0] if causation_chain else ""
