# Bug fix prompt

Fix the reported bug with the smallest safe change that addresses the root cause.

## Expectations

- Reproduce or characterize the failure before changing code.
- Add a regression test that fails before the fix and passes after it.
- Avoid broad exception swallowing or success-shaped fallbacks.
- Validate with `python -m ruff check .`, `python -m mypy`, and `python -m pytest`.

