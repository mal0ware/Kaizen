# ADR 0013 — Infrastructure & hardware

- **Status:** Accepted
- **Date:** 2026-05-26

## Context

Concrete buy-list for the deployment topology (ADR 0007), sized for the scale in ADR 0012.

## Decision

**VPS (always-on core):** Hetzner **CPX41** — 8 vCPU / 16 GB RAM / ~240 GB disk (~€28–30/mo) — in the **Ashburn, VA (us-east)** location for low latency to the operator and Discord users. The 16 GB is specifically so the pgvector HNSW index + Postgres + Redis sit in RAM. Acceptable to start on **CPX31** (4 vCPU / 8 GB, ~€15/mo) and resize up — Hetzner resizing is trivial. (ARM/CAX plans are cheaper but EU-only → skipped for US latency.)

**Wake relay:** a **Raspberry Pi 5 (4 GB, ~$60)** — does the relay job (Tailscale + WoL sender on the home LAN) with headroom to host other always-on light duties later. A **Pi Zero 2 W (~$15)** suffices for a *pure* relay. Boot from a **USB SSD** (not microSD) for reliability; add the official USB-C PSU + case.

**Pi modularity note:** Raspberry Pis are SoC boards — CPU/GPU/RAM are soldered and **not upgradeable** (the integration is what makes them small/cheap/low-power). For a *growable* always-on home node, prefer a **mini PC with SODIMM + M.2 slots** (upgrade RAM/storage) or a **Mini-ITX x86 build / Framework Desktop** (full modularity, can add a GPU). The Raspberry Pi *Compute Module + carrier* is the modular-I/O middle ground.

## Topology (recap, ADR 0007)

VPS (internet-facing core + Discord + Postgres/pgvector/Redis) ↔ **Tailscale** ↔ { home desktop GPU worker (RTX 3080 10GB), Pi relay }. The Pi wakes the desktop on demand; cloud is the always-available floor + heavy thinker.

## Consequences

- ~€28–30/mo VPS + a one-time ~$60 Pi gets the full topology standable.
- Clear upgrade paths: VPS resize for RAM; mini-PC/SFF if a modular home node is ever wanted.
