"""Working Set — assemble a prompt-ready ContextBlock from memory (P2.e)."""
from __future__ import annotations
from dataclasses import dataclass, field

def _est(text: str) -> int:        # approximate token = char // 4
    return max(1, len(text) // 4)

@dataclass
class WorkingBlock:
    label: str
    content: str
    token_estimate: int = 0
    def __post_init__(self):
        if not self.token_estimate:
            self.token_estimate = _est(self.content)

@dataclass
class ContextBlock:
    blocks: list = field(default_factory=list)
    truncated: list = field(default_factory=list)
    def render(self) -> str:
        titles = {"persona": "## About me", "common_ground": "## What we share",
                  "relevant_memories": "## Relevant memories",
                  "pending_commitments": "## Pending commitments", "affect": "## Current tone"}
        parts = []
        for b in self.blocks:
            if b.content.strip():
                parts.append(titles.get(b.label, "## " + b.label) + "\n" + b.content)
        return "\n\n".join(parts)

# Priority: action-critical first; memories take the bulk of the remainder.
_PRIORITY = ["pending_commitments", "persona", "common_ground", "relevant_memories", "affect"]

def assemble(sections: dict, token_budget: int) -> ContextBlock:
    """sections: label -> content str. Allocate budget by priority; truncate overflow (by char), record in truncated."""
    cb = ContextBlock()
    remaining = token_budget
    for label in _PRIORITY:
        content = sections.get(label, "")
        if not content:
            continue
        est = _est(content)
        if est <= remaining:
            cb.blocks.append(WorkingBlock(label, content))
            remaining -= est
        else:
            keep_chars = max(0, remaining) * 4
            cb.blocks.append(WorkingBlock(label, content[:keep_chars]))
            cb.truncated.append(label)
            remaining = 0
    return cb
