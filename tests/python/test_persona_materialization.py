"""P3.c PersonaSubscriber — full-journey e2e.

Proves the live pipeline: remember(self-fact) → tick consolidates →
statement.derived fires → persona tick stage (after replay_idle) rebuilds
PersonaContainer → render_working_set surfaces ## About me block.

API conventions mirror test_grounding_resolution_e2e.py and
test_tick_stage_timings.py.
"""
import starling


# Stub extraction: holder=self, subject=self → self_model_anchor → ## About me.
_CANNED = (
    '[{"holder":"self","holder_perspective":"FIRST_PERSON",'
    '"subject":"self","predicate":"trait_curiosity","object":"high",'
    '"modality":"BELIEVES","polarity":"POS","nesting_depth":0}]'
)


def test_remember_then_tick_populates_about_me(tmp_path):
    fake = starling.make_stub_llm(default_response=_CANNED)
    mem = starling.Memory.open(str(tmp_path / "persona.db"), agent="self",
                               tenant_id="default", llm=fake)
    mem.remember("I am deeply curious.", now="2026-07-01T00:00:00Z")
    # Ticks drive replay consolidation → statement.derived → the persona tick
    # stage (after replay_idle) rebuilds self's PersonaContainer in the SAME tick.
    # Empirically verified: 1 tick consolidates; 30 is far more than enough.
    for _ in range(30):
        mem.tick("2026-07-01T00:05:00Z")
    cb = mem.render_working_set(interlocutor="other", goal="who am I")
    rendered = cb.render()
    # The persona ## About me block is populated (empty before this slice) —
    # assert the About-me section specifically, distinct from Relevant memories.
    assert "## About me" in rendered, (
        f"Expected '## About me' in rendered working set.\nGot:\n{rendered!r}")
    assert "trait_curiosity" in rendered, (
        f"Expected 'trait_curiosity' in rendered working set.\nGot:\n{rendered!r}")
    assert "## Relevant memories" not in rendered or rendered.index("## About me") < rendered.index("## Relevant memories"), (
        "## About me must appear before ## Relevant memories (priority ordering)")
    labels = [b.label for b in cb.blocks]
    assert "persona" in labels, f"Expected 'persona' block in {labels}"
    persona_block = next(b for b in cb.blocks if b.label == "persona")
    # Airtight consumer proof: the anchor VALUE must be in the persona block
    # specifically — not merely somewhere in the render (trait_curiosity also
    # leaks into ## Relevant memories, so an in-`rendered` check alone is
    # satisfiable without materialization). This ties the value to the block
    # the persona tick stage rebuilt.
    assert "trait_curiosity" in persona_block.content, (
        f"persona block must contain the materialized anchor value; "
        f"got {persona_block.content!r}")
    mem.close()
