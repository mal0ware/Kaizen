---
name: verification-loop
description: After making a change, run the smallest check that proves the change works before reporting it as done.
source: authored
status: active
---

# Verification loop

A change isn't done when the diff compiles — it's done when something
observable confirms the new behaviour.

## When to use

- You just edited code, config, or a doc that other code depends on.
- A test, type-check, or lint pass could catch a mistake in seconds.
- You are about to tell the user "done" without having seen the new behaviour.

## Procedure

1. Pick the cheapest check that would fail if your change is wrong:
   - Unit test for the touched function.
   - `ruff` / `mypy` for surface-level breakage.
   - A `python -c` smoke test or a one-line repl call for runtime wiring.
2. Run it. Read the output.
3. If it fails, fix and loop. If it passes, note *what you ran* in the reply so
   the user can reproduce.

## Anti-patterns

- "Should work" without running anything.
- Reporting success after a build passes but the feature was never exercised.
- Skipping verification because "it's a small change" — small changes break
  invariants too.
