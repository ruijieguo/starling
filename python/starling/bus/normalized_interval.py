from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class NormalizedInterval:
    is_unknown: bool = False
    from_: str = ""       # ISO-8601 UTC; empty iff is_unknown
    to: str = ""          # ISO-8601 UTC; empty means open-ended
    to_is_open: bool = False

    def canonical_bytes(self) -> str:
        if self.is_unknown:
            return "UNKNOWN"
        if self.to_is_open or not self.to:
            return f"{self.from_}/OPEN"
        return f"{self.from_}/{self.to}"


UNKNOWN_INTERVAL = NormalizedInterval(is_unknown=True)


def normalize_interval(
    valid_from: Optional[str],
    valid_to: Optional[str],
    event_time: Optional[str],
) -> NormalizedInterval:
    if valid_from is not None:
        if valid_to is not None:
            return NormalizedInterval(from_=valid_from, to=valid_to, to_is_open=False)
        return NormalizedInterval(from_=valid_from, to_is_open=True)
    if event_time is not None:
        return NormalizedInterval(from_=event_time, to_is_open=True)
    return UNKNOWN_INTERVAL
