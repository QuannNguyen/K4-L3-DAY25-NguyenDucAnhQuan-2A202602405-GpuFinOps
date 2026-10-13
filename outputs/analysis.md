# NimbusAI GPU FinOps: Results and First Actions

**Scope:** June 2026 synthetic workload snapshot. All spend is modeled; GPU rental
prices, cache economics, energy intensity, and regional grid factors must be
re-baselined before production decisions.

## 1. Baseline vs. optimized

Across the modeled monthly GPU fleet and inference workloads, baseline spend is
**$27,133/month**. Applying the measured purchasing, inference, right-sizing,
and idle-capacity levers reduces modeled spend to **$14,627/month**, a saving
of **$12,506 (46.1%)**.

Inference unit economics improve from **$6.488 to $1.128 per 1M tokens**, an
**82.6% reduction**. This is a separate, workload-normalized metric: the
monthly totals also include GPU jobs and fleet changes, so the overall
monthly savings percentage should not be confused with the inference-only
$/1M-token reduction.

| Lever | Modeled monthly savings |
|---|---:|
| GPU purchasing (spot/reserved) | $10,040 |
| Inference (cascade, cache, batch) | $1,211 |
| Right-size high-util/low-MFU GPUs | $655 |
| Stop idle GPU time | $600 |
| **Total** | **$12,506** |

## 2. Which levers matter most?

Purchasing contributes the most: **$10,040/month, about 80% of total savings**.
The workloads show interruptible training that can use checkpointed spot
capacity, while steady, high-duty-cycle inference is a better reserved-tier
candidate. The estimate applies the catalog's 3-year reserved rate; it is
realizable only if NimbusAI has sufficiently durable demand and accepts that
commitment risk.

Inference is the next major lever. Cascade routing accounts for about
**$1,122/month**, compared with **$53.70/month** from batch and **$35.70/month**
net from cache after its write premium. Thus the key inference decision is
routing easy work to the small model; cache and batch are useful but smaller
for this data mix.

## 3. The GPU-Util lie

The expected outlier, **gpu-h100-4**, averages **98.2% GPU-Util but only 19.4%
MFU**. **gpu-a10g-1** is also flagged (96.9% utilization, 26.8% MFU). GPU-Util
measures time active, not useful tensor throughput: synchronization, small
kernel launches, stalls, or other pipeline inefficiencies can keep the device
busy while a small fraction of peak FLOPs is achieved. These are hypotheses
to validate with a profiler, not diagnoses established by this dataset.

At catalog on-demand prices, H100 time costs $2.50/GPU-hour and A10G costs
$1.00/GPU-hour. The report's one-tier right-sizing assumption (H100→A100,
A10G→L4) estimates **$655/month** saved across both flagged GPUs. Separately,
gpu-h100-5 has eight idle hours/day; shutting off that measured idle window
saves **$20/day or $600/month**. Confirm quality-of-service and throughput
before replacing hardware.

## 4. Extensions implemented and measured

1. **Cache break-even gate.** The new policy compares average observed reads
   per shared prompt prefix against the break-even of
   **1.25 / (1 − 0.10) = 1.39 reads** (write premium in uncached-read cost
   units; cached-read price is 10% of standard). The deterministic dataset
   records shared-prefix reads: both small and large tiers average **678
   reads/prefix**, so caching is enabled. The amortized write premium is
   **$0.0093/day**; cache saves **$1.19/day net** in the measured sequence.
   High reuse makes caching worthwhile, but cascade remains much more
   valuable.
2. **Reasoning budget.** Reasoning is **8.38% of requests**, **16.46% of
   optimized inference spend**, and **94.04% of modeled inference energy**.
   The energy estimate applies the lab's 80× reasoning multiplier. A 10%
   traffic ceiling saves **$0 and 0 Wh** on this snapshot because usage is
   already below the cap; the insight is to treat 10% as a maximum, not a
   target that invites additional reasoning traffic.
3. **Carbon-aware scheduling.** The interruptible jobs use **1,789 kWh** in
   the modeled period. Moving them from us-east-1 to europe-north1 reduces
   estimated emissions from **679.82 to 53.67 kgCO2e**, avoiding **626.15
   kgCO2e**. us-east-wa is cheapest for electricity (**$98.39** versus
   $214.68 in us-east-1); europe-north1 is cleanest (**$161.01**). These are
   power-only costs, not GPU rental costs. Latency, residency, and schedule
   constraints may outweigh the grid benefit.

## 5. First three actions as NimbusAI FinOps lead

1. **Pilot a purchasing policy:** move checkpointable training to spot and
   reserve only stable, high-utilization inference demand. Validate workload
   continuity and the 3-year commitment assumption before buying.
2. **Stop measurable waste and investigate utilization:** schedule shutdown
   for the idle H100 window, then profile gpu-h100-4 and gpu-a10g-1. Right-size
   only after verifying throughput, memory, and latency SLOs.
3. **Operationalize unit economics:** deploy small-model cascade and
   economically gated caching, keep reasoning below a 10% budget, and report
   cost per 1M tokens by team. Trial carbon-aware placement for interruptible
   jobs, using a latency/residency guardrail.

These results are decision-support estimates from a deterministic synthetic
dataset, not a cloud invoice or a production guarantee.
