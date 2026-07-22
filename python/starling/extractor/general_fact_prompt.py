"""Authoritative general-fact extraction prompt (single source) — sub-project C.

remember()'s THIRD pass. Captures standalone DECLARATIVE world-facts (definitions,
properties, quantities, relationships) that the belief pass (focal-speaker mental
states) and episodic pass (physical events) skip, as self-held BELIEVES claims.

Reuses the belief Extractor: this emits the SAME claim-JSON schema as
prompts.py (EXTRACTION_PROMPT). TWO placeholders, both filled by LITERAL
str.replace (NOT str.format): {self} (MemoryCore fills it with the agent name so
holder=self.agent -> recallable by the default recall) and {convo} (the C++
Extractor fills it with the passage). Keep the predicate vocabulary in sync with
kGeneralFactPredicates in include/starling/extractor/predicate_registry.hpp.
"""
from __future__ import annotations

GENERAL_FACT_EXTRACTION_PROMPT = """You are a general-fact extractor for a Statement-based memory system.

Given a passage, extract ALL standalone DECLARATIVE FACTS about the world — definitions, properties, quantities, and relationships stated as true. Output ONLY a JSON array.

Each Statement: {"holder": str, "holder_perspective": "FIRST_PERSON", "subject": str, "subject_kind": "cognizer"|"entity", "cognizer_kind": "self"|"human"|"agent"|"group"|"role"|"external", "predicate": str, "object": str, "modality": "BELIEVES", "polarity": "POS"|"NEG", "nesting_depth": 0}
(cognizer_kind is REQUIRED only when subject_kind="cognizer"; omit it for entities.)

For EVERY fact: holder is "{self}" (the memory's own agent, which records the fact), holder_perspective is "FIRST_PERSON", modality is "BELIEVES", nesting_depth is 0.

predicate must be one of: is_a, instance_of, has_property, has_value, part_of, related_to, depends_on, reports_to, located_at, member_of. Pick the closest underscore form — never free-form English. Guidance:
- is_a / instance_of — definitions/types: "Postgres is a relational database" -> is_a(Postgres, relational database)
- has_property — attributes: "the server is rack-mounted" -> has_property(server, rack-mounted)
- has_value — quantities/measurements: "the budget is $40k" -> has_value(budget, $40k)
- part_of — composition: "the API is part of the platform" -> part_of(API, platform)
- depends_on — dependencies: "auth depends on the token service" -> depends_on(auth, token service)
- reports_to — org relations: "Alice reports to Bob" -> reports_to(Alice, Bob)
- located_at — location of a thing: "the server room is on floor 3" -> located_at(server room, floor 3)
- member_of — membership: "Alice is on the platform team" -> member_of(Alice, platform team)

subject = the entity the fact is about (canonical short noun). object = the value/type/target (canonical short noun, or a number/string for quantities). Drop hedges and modifiers ("the", "service", "system").

SUBJECT_KIND (CRITICAL): for EVERY fact, classify the subject.
- entity: technical things, products, libraries, devices, models, metrics, quantities, abstract concepts — anything that CANNOT hold a belief. MOST general facts are about entities. Examples: "Postgres", "H800 memory", "deploy budget", "FLA kernel", "TE 2.14.1", "ToMBench run time" are ALL entity.
- cognizer: a person (human), AI agent (group), team/org (group), role, or the narrator itself (self) — only when the fact is about a belief-bearing subject, e.g. "Alice reports_to Bob" (both people) or "Alice member_of platform team".
When in doubt, choose entity — a general-fact subject is far more often a thing than a person. Only give cognizer_kind when subject_kind="cognizer".

DO NOT extract (output nothing for these — other passes own them):
- A person's voiced opinion / belief / commitment / preference / promise in conversation ("I think...", "I'll do X", "Alice prefers Python"). Those are mental-state claims, NOT general facts.
- A physical event or action ("Sally put the ball in the basket", "Tom left the room"). Those are events, NOT general facts.
- If the passage has only conversational claims or physical events with no standalone declarative fact, output [].

WORKED EXAMPLE 1:
Passage:
  Postgres is a relational database. The deploy budget is $40k. Alice reports to Bob.
JSON array:
[
  {"holder":"{self}","holder_perspective":"FIRST_PERSON","subject":"Postgres","subject_kind":"entity","predicate":"is_a","object":"relational database","modality":"BELIEVES","polarity":"POS","nesting_depth":0},
  {"holder":"{self}","holder_perspective":"FIRST_PERSON","subject":"deploy budget","subject_kind":"entity","predicate":"has_value","object":"$40k","modality":"BELIEVES","polarity":"POS","nesting_depth":0},
  {"holder":"{self}","holder_perspective":"FIRST_PERSON","subject":"Alice","subject_kind":"cognizer","cognizer_kind":"human","predicate":"reports_to","object":"Bob","modality":"BELIEVES","polarity":"POS","nesting_depth":0}
]

WORKED EXAMPLE 2 (no general facts):
Passage:
  Alice: I think Bob should handle auth. Then she put the report on the desk.
JSON array:
[]
(A voiced opinion ("I think...") belongs to the belief pass; "put the report on the desk" is a physical event for the episodic pass. Neither is a standalone declarative world-fact, so output [].)

Passage:
{convo}

JSON array:"""
