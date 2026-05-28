---
name: search-first
description: Before answering a non-trivial question about a codebase or any external system, search for evidence before writing or recommending changes.
source: authored
status: active
---

# Search-first

When a question touches code you haven't read, an API you haven't called, or a
fact you can't quote from memory: **look before you leap**.

## When to use

- A user references a file, function, flag, or symbol you have not loaded.
- You're about to recommend an edit that depends on the surrounding code.
- The answer hinges on "what is X doing today?" rather than "what should X do?"

## Procedure

1. Identify the smallest concrete artifact (file, symbol, config key) the
   question depends on.
2. Find it — grep, read, or call a search tool. Read enough surrounding context
   to understand the contract, not just the line.
3. Quote the evidence in your answer (path + line, exact symbol name). If you
   can't find evidence, say so explicitly rather than inferring.
4. Only then propose changes.

## Anti-patterns

- Inferring a function's behaviour from its name.
- Recommending an edit to a file you haven't opened.
- Citing memory of "how this codebase works" without verifying it still does.
