"""Authoritative episodic-extraction prompt (single source).

remember() runs TWO independent extraction passes over the same passage:

1. EXTRACTION_PROMPT (prompts.py) — the belief/conversation pass: who asserts
   what they believe / commit / require. Conversation-framed.
2. EPISODIC_EXTRACTION_PROMPT (this file) — the episodic pass: the sequence of
   physical events that actually HAPPENED in a narrative ("Sally puts her ball
   in the basket and leaves the room. Anne moves the ball to the box."), turned
   into ordered OCCURRED events.

Both are injected into their C++ extractor (EpisodicExtractor here) and filled
by LITERAL replacement of the single `{passage}` placeholder (str.replace, NOT
str.format) — so the JSON examples below use plain single braces and the bytes
sent are exactly what is written here.

Output is a JSON array of event objects in NARRATIVE ORDER:
  {"actor": str, "action": str, "theme": str, "location": str|null,
   "participants": [str], "time": str|null}
"""
from __future__ import annotations

EPISODIC_EXTRACTION_PROMPT = """You are an episodic-event extractor for a memory system.

Given a narrative passage, extract the ordered sequence of PHYSICAL EVENTS that happen. Output ONLY a JSON array of event objects, in NARRATIVE ORDER (the order they occur in the passage).

Each event: {"actor": str, "action": str, "theme": str, "location": str|null, "participants": [str], "time": str|null}

RULES:
- Extract EVERY physical event/action — object manipulations AND movements of people.
- PRESENCE-CHANGES ARE EVENTS. Emit enter / leave / arrive / return as their OWN events. A departure is exactly what makes a LATER event unwitnessed by the person who left, so it MUST NOT be dropped. Never skip a "leaves the room" / "comes back" / "walks out" — give each its own array element in order.
- actor = the cognizer (person) performing the action.
- action = the verb. PREFER one of: put, place, move, take, give, remove, transfer, leave, open, close when it fits the event. For enter/arrive/return use the closest verb ("enter", "return"); for leave/exit/walk-out use "leave".
- theme = the object acted on. For a presence-change (leave/enter/arrive/return), theme = the PLACE (e.g. "room").
- location = the object's RESULTING place after the action (where the theme ends up), or null for a non-spatial action. For "put the ball in the basket", location = "basket". For "leaves the room" (non-spatial w.r.t. an object), location = null.
- participants = ONLY the cognizers NAMED in THAT event. Do NOT infer who else is present, watching, or in the room. If the event names one person, participants has exactly that one person.
- time = an explicit timestamp/clock phrase if the event states one, else null.
- Array order = narrative order. One JSON object per event.
- If nothing physical happens, output [].

WORKED EXAMPLE 1:

Passage:
  Sally puts her ball in the basket and leaves the room. Anne moves the ball to the box.
JSON array:
[
  {"actor":"Sally","action":"put","theme":"ball","location":"basket","participants":["Sally"],"time":null},
  {"actor":"Sally","action":"leave","theme":"room","location":null,"participants":["Sally"],"time":null},
  {"actor":"Anne","action":"move","theme":"ball","location":"box","participants":["Anne"],"time":null}
]
(Three events. Sally's departure is its OWN event — that is what makes Anne's move unwitnessed by Sally. participants lists only the actor named in each event; we do NOT assume Anne saw Sally leave or that anyone watched Anne.)

WORKED EXAMPLE 2:

Passage:
  At 9am, Tom took the keys from the drawer. He left the office. Later, Mary returned and placed a letter on the desk.
JSON array:
[
  {"actor":"Tom","action":"take","theme":"keys","location":null,"participants":["Tom"],"time":"9am"},
  {"actor":"Tom","action":"leave","theme":"office","location":null,"participants":["Tom"],"time":null},
  {"actor":"Mary","action":"return","theme":"office","location":null,"participants":["Mary"],"time":null},
  {"actor":"Mary","action":"place","theme":"letter","location":"desk","participants":["Mary"],"time":null}
]
(Tom's "left the office" and Mary's "returned" are emitted as their own presence-change events. "took the keys" has location=null — taking is a transfer of custody, no resulting place is named.)

Passage:
{passage}

JSON array:"""
