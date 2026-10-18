# Support levels (L1 / L2 / L3)

SOLVIA separates **priority** (how urgent) from **support level** (who should own the work).

| Field | Meaning | Values |
|---|---|---|
| `priority` | Urgency / business impact | `low`, `medium`, `high`, `critical` |
| `support_level` | Ownership / complexity tier | `L1`, `L2`, `L3` |

A password unlock can be `priority=critical` and still `support_level=L1`.
A quiet performance cliff can be `priority=medium` and still `support_level=L3`.

## Level definitions

### L1 — Service desk / known procedure
- Short, repeatable fixes with a runbook
- Examples: unlock user (SU01), password reset, known login checklist
- Typical resolution under ~1.5 hours

### L2 — Application / functional support
- Needs logs, role/config checks, or integration credentials
- Examples: SU53 authorization gaps, SM37 job failures, CPI OAuth issues, transport import errors
- Typical resolution a few hours

### L3 — Basis / expert
- Deep diagnosis, system change, upgrade/install, or SAP Note that alters the platform
- Examples: HANA memory, SUM/SWPM failures, ST03N expensive SQL, kernel/basis work
- Typical resolution longer (often 6–8+ hours)

## How classification works

1. **Manual override** — consultant sets `support_level` on ingest or as a search filter.
2. **Rule engine** (`backend/app/support_level.py`) — category, transactions, SAP Notes, phrases, and resolution time.
3. **Evidence vote** — top retrieved tickets’ levels can confirm the rule result.
4. **Gemini** — may suggest a level in structured output; rules + evidence still gate the final choice when the consultant did not filter.

On ticket ingest, if `support_level` is empty, SOLVIA auto-classifies and stores `support_level_reason`.

## Retrieval behaviour

- Optional search filter prefers matching Chroma metadata `support_level`.
- Filters relax progressively (same pattern as system/category) so useful evidence is not hidden.
- Matching level gets a score bonus; mismatch gets a small penalty.

## API / UI surfaces

- Search filter: Solution Finder → **Support level**
- Solution response fields: `support_level`, `support_level_reason`, `support_level_routing`
- Knowledge Library: optional level on ticket ingest; list shows the level
- Analytics usage rows store `query_support_level` and `suggested_support_level`

## Backfilling existing tickets

Restart the backend (schema columns are added automatically), then either:

- Re-ingest tickets from Knowledge Library, or
- Run `python backfill_support_levels.py` from `backend/`

New demo ticket `T-DEMO-011` is an explicit L1 unlock example.
