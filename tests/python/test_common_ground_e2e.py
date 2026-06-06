import tempfile
from starling.memory import Memory, make_stub_llm

# Stub returns the SAME proposition regardless of text → same canonical_object_hash;
# remember's holder param overrides the statement holder. Two DISTINCT texts avoid
# engram-content idempotency so both turns extract (the second isn't deduped).
_JSON = '[{"holder":"self","holder_perspective":"FIRST_PERSON","subject":"Bob","predicate":"responsible_for","object":"auth","modality":"BELIEVES","polarity":"POS","nesting_depth":0}]'


def test_grounding_end_to_end():
    db = tempfile.mktemp(suffix=".db")
    m = Memory.open(db, agent="self", tenant_id="default",
                    llm=make_stub_llm(default_response=_JSON))
    # self asserts (statement.written queued; holder=self, scope_parties={bob,self})
    m.remember("I think Bob is responsible for auth.", interlocutor="bob")
    # bob restates the SAME proposition with DISTINCT text (holder=bob → other party)
    m.remember("Yes, Bob handles authentication.", holder="bob", interlocutor="self")
    # flush the subscriber: S1 assert(asserted_unack) → S2 same-prop other-party → acknowledge(grounded) + rebuild
    m.tick("2026-06-06T10:00:00Z")
    ws = m.render_working_set("bob")
    # ws is a ContextBlock with .blocks (list of WorkingBlock) and .render() method.
    # Check the rendered string and each block's content for common-ground text.
    rendered = ws.render()
    cg_blocks = [b.content for b in ws.blocks if b.label == "common_ground"]
    blob = rendered + " ".join(cg_blocks)
    assert "auth" in blob, f"common ground 'auth' 应出现在 working set: rendered={rendered!r}, blocks={ws.blocks!r}"
