# ADR 0001 — Python-first orchestration, native hot paths later

- **Status:** Accepted (updated 2026-05-26)
- **Date:** 2026-05-26

## Context

Kaizen mixes cloud and local models. A reasonable instinct is to build it in C++/Rust for speed — especially for local models on the GPU. We needed to decide the implementation language for the agent/orchestration layer, and the policy for when native code is warranted.

## Decision

Build orchestration in **Python**. Use **Rust/C++ for specific hot paths**, added via bindings (PyO3 / pybind11), **batched at the boundary**, and only **after profiling** identifies them. Rust is the preferred native language for new modules (memory safety, clean PyO3, already used in the Hermes trading platform).

## Rationale

1. **A harness is I/O-bound, not CPU-bound.** Its loop is decide → dispatch → wait, and the wait (network round-trip or GPU compute) dwarfs any orchestration logic — ~99.9% of wall-clock time is spent blocked. Harness language has negligible effect on throughput.
2. **Local-model speed lives in the inference engine, which is already native.** llama.cpp (C++), vLLM (CUDA), TensorRT-LLM, Ollama (Go over llama.cpp). Kaizen *calls* these and streams tokens; rewriting the harness in C++ yields zero extra tokens/sec. The real levers are engine, quantization, and hardware.
3. **Ecosystem & velocity.** The LLM/agent ecosystem is Python-first; building in Python ships far faster.
4. **In-process integration** with the Python-dominant Hermes trading platform.
5. **The FFI boundary has a cost.** Crossing Python↔native per call is not free. So the rule is *heavy CPU work per call, run often → native, and call it in batches* — never a tiny native function in a tight per-item Python loop.

## Consequences

- Orchestration, memory, identity, providers, surfaces: Python.
- `native/` exists but stays empty until profiling justifies a module.
- "Optimize later" is explicit policy: measure first. Likely first candidates — ambient ingestion/embedding, semantic search, real-time triage.

## Alternatives considered

- **Full C++/Rust harness** — rejected: optimizes an I/O-bound layer, worse ecosystem, no inference-speed gain, slower to ship.
- **Rust orchestration + Python tooling** — deferred: same I/O-bound irrelevance to inference speed; revisit only if orchestration ever becomes a measured bottleneck.
