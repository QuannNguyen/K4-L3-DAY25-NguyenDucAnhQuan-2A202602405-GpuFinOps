# NimbusAI — GPU Cost Optimization Report

**Period:** monthly
**Baseline spend:** $27,133
**Optimized spend:** $14,627
**Projected savings:** $12,506  (**46%**)

## Savings by lever

| Lever | Savings (USD) |
|---|---|
| Inference (cascade/cache/batch) | $1,211 |
| Purchasing (spot/reserved) | $10,040 |
| Right-size util-lies | $655 |
| Kill idle GPUs | $600 |

## Sustainability

- Energy per query: 0.24 Wh
- Carbon per query: 0.091 gCO2e
- Electricity cost per query: $0.00002880
- Cleanest region: europe-north1

## Inference unit economics and lever attribution

| Measure | Baseline | Optimized |
|---|---:|---:|
| Spend per day | $48.87 | $8.49 |
| Cost per 1M tokens | $6.488 | $1.128 |

Inference savings by sequentially applied lever (monthly):

| Lever | Savings (USD/month) |
|---|---:|
| Cascade | $1,122.00 |
| Cache | $35.70 |
| Batch | $53.70 |

Cache write premiums are amortized in optimized spend ($0.0093/day). Caching is enabled only when observed reads per shared prompt prefix exceed the modeled break-even (write premium / cached-read saving).

| Model tier | Observed reads/prefix | Break-even reads | Cache policy |
|---|---:|---:|---|
| small | 678.0 | 1.39 | enabled |
| large | 678.0 | 1.39 | enabled |

### Reasoning budget

Reasoning represents 8.38% of requests, 16.46% of optimized inference spend, and 94.04% of modeled inference energy (29,787.74 Wh/day).
A 10% traffic cap would save $0.00/day and 0.00 Wh/day under this dataset; it is a ceiling, not a mandate to increase reasoning traffic.

## Carbon-aware scheduling extension

Interruptible workloads use 1,789.00 kWh in the modeled period.
Moving them from us-east-1 to the cleanest region avoids 626.15 kgCO2e; moving to the cheapest-electricity region saves $116.29 in electricity. These electricity costs are separate from GPU rental charges.

| Region | Electricity (USD) | Carbon (kgCO2e) |
|---|---:|---:|
| us-east-1 | $214.68 | 679.82 |
| us-west-2 | $125.23 | 214.68 |
| europe-north1 | $161.01 | 53.67 |
| europe-central2 | $322.02 | 1,180.74 |
| us-east-wa | $98.39 | 161.01 |

Cheapest: **us-east-wa**; cleanest: **europe-north1**; equal-weight cost/carbon choice: **us-east-wa**. Validate latency and data-residency constraints before moving production jobs.

## Interpretation and actions

1. Start with purchasing commitments: this is the largest measured monthly lever. Keep only stable, high-duty-cycle demand reserved; checkpoint interruptible training for spot capacity.
2. Route easy requests to the small model and use batch for deferrable jobs; the inference unit metric falls because savings are measured per token, not per GPU-hour.
3. Investigate high-util/low-MFU GPUs before buying more capacity. Memory stalls, small kernels, synchronization, or launch overhead can keep a device active while tensor throughput remains low.
4. Shut down scheduled idle capacity and move only latency-tolerant training to cleaner/cheaper regions after a latency and data-residency review.

_Figures are June-2026 as-of snapshots; re-baseline before acting._