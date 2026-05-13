---
updated_at: 2026-05-13T10:40:00-05:00
focus_area: emm_logging shipped — awaiting next direction
active_issues: []
---

# What We're Focused On

✅ **Shipped (commit c69941d):** `emm_logging` reusable Python logging module.
- Public API: `LoggingSettings` (LOG_* env prefix), `configure_logging()`, `LoggingResult`.
- Console (JSON via python-json-logger), Seq (CLEF/HTTP per-event), Azure Monitor (azure-monitor-opentelemetry).
- Optional extras `[seq]` and `[azure]` keep the base install lean.
- FastAPI app migrated to delegate via `src/copilot_python_app/telemetry.py`.
- 135 tests, 98.35% branch coverage on `emm_logging`. Ripley's 31-item reviewer gate passed.

**Open follow-ups (non-blocking):**
1. README usage example for `emm_logging` (Ripley's non-blocking suggestion).
2. PyPI publication strategy / split to its own repo (deferred from round-1 — when the API stabilizes).
3. Other Python apps — port them to `emm_logging` once it's stable.

**Awaiting Emmanuel's direction for the next focus.**
