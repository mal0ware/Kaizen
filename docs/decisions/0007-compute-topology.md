# ADR 0007 — Compute topology: always-on core + GPU worker pool + cloud tiers

- **Status:** Accepted
- **Date:** 2026-05-26

## Context

The operator's primary desktop is a capable GPU machine (RTX 3080 ~10GB, i9-13900k, 64GB RAM) but is **not always on**. We want free/private local inference on it while keeping the agent always available. The VPS is not yet purchased. Earlier (ADR 0004/architecture) the GPU placement was left open; this resolves it.

## Decision

**Split the always-on brain from the on-demand GPU; treat local compute as a bonus, never a dependency.**

- **Core (always-on):** small Hetzner Cloud instance, no GPU (CPX21 / CX32 class, ~4–8GB RAM). Runs the loop, router, Postgres + pgvector + Redis, Discord gateway. Sized in the architecture doc.
- **Home desktop = on-demand inference worker.** The RTX 3080 is **Tier 0**: local 7–8B (4-bit) models, embeddings, triage, the scribe, simple replies. Not a frontier reasoner.
- **Private networking:** Tailscale (WireGuard mesh) connects VPS ↔ home worker — no port-forwarding, nothing public.
- **Wake-on-LAN:** the core wakes the sleeping desktop on demand. A WoL magic packet is LAN-local, so a small **always-on wake relay** on the home LAN (router with WoL support, or a Raspberry Pi) receives the request over Tailscale and broadcasts the packet. The worker auto-starts on boot/wake and registers with the core. (Windows: enable WoL in BIOS + NIC; prefer S3 sleep over modern standby.)
- **Graceful fallback / latency hiding:** if the worker is asleep, unreachable, or still waking, respond **immediately via cloud** (never block the user) and **queue** heavy local-eligible jobs for when the worker is up.
- **Worker pool generalizes:** any machine running a worker can join and advertise capabilities; the router distributes **jobs**, not a single model's layers (no tensor/pipeline parallelism at this scale).

## Model routing tiers (ties ADR 0005 triage, ADR 0006 strategy)

- **Tier 0 — local (3080):** high-volume cheap tasks, embeddings, triage. Free.
- **Tier 1 — cheap cloud:** light tasks when local is insufficient or the box is asleep.
- **Tier 2 — frontier (e.g. Opus 4.7):** big, hard, high-stakes work only. Rare and deliberate.

## Consequences

- The agent never depends on the desktop being on; local is a cost/privacy accelerator when available.
- First-wake latency (seconds–tens of seconds) is hidden by cloud-first response + queued local jobs.
- No hardware purchase required to start. A dedicated always-on home server remains a *later* option if usage proves it out.

## Resolved details (2026-05-26)

- **3080 VRAM = 10GB** (PCI device ID `DEV_2216`, RTX 3080 10GB LHR; Dell OEM `SUBSYS …1028`). Local sweet spot: **7–8B 4-bit** models with room for context; ~13B only at tight quant + short context. Ideal for Tier-0 (triage, embeddings, scribe, simple replies).
- Host: `MAL0SS` — MSI MAG Z790 Tomahawk WiFi, i9-13900K (24c/32t), 64GB RAM, Win 11 Pro. Strong worker + plenty of headroom for core services / CPU fallback.
- **Wake relay = Raspberry Pi** (router WoL support unconfirmed; Pi is the reliable choice). Pi sits always-on on the home LAN, runs Tailscale, and broadcasts the WoL magic packet to the desktop NIC on request. BIOS/OS prep: enable Wake-on-LAN / "Resume by PCI-E," prefer S3 sleep, disable Fast Startup interference.

## Open items

- Pick the Hetzner plan at purchase time.
- Acquire the Pi and confirm BIOS WoL settings on the Tomahawk.
