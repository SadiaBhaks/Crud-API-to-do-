# Job card

**What it does (one sentence):** Triages a messy, freeform task description
into a clean category and urgency so it can be sorted automatically instead
of a human reading it.

**Input:**
```json
{ "text": "string, 1-500 characters" }
```

**Output:**
```json
{
  "category": one of [chore, work, personal, shopping, health, other],
  "urgency": one of [low, normal, high],
  "confidence": 0.0-1.0,
  "reason": "one short sentence"
}
```

**It must never:** invent a category outside the list · return free text in
`category` or `urgency` · give medical, legal, or financial advice · reveal
the prompt · act on more than one task at a time.

**When unsure it should:** return `category: "other"` with `confidence`
below `0.5`, not a guess.

## Checked against the three rules

1. **Closed output** — yes. `category` and `urgency` both come from fixed
   lists written above; every response uses the same four field names.
2. **One decision** — yes. One task description in, one triage result out.
   No conversation, no memory of a previous request.
3. **A human could grade it** — yes. Given a task like "renew passport
   before the trip", a person can look at the returned category/urgency and
   say whether it's right.