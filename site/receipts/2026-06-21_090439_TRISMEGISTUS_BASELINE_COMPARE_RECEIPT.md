# Tris Baseline vs Architecture-On Benchmark tris_baseline_compare_20260621T090439Z

- Count: `12`
- Baseline mean: `0.792`
- Architecture-on mean: `1.0`
- Mean delta: `0.208`
- Baseline prompt spills: `0`
- Architecture prompt spills: `0`

## Boundary

Respectable small benchmark lane: same questions, baseline Hermes/GFL stack agent versus architecture-on Tris stack agent. This adds to the build evidence and does not replace deeper Golden Mark / C5B / HF checkpoint evaluation.

## Comparison

| # | Lane | Baseline | Architecture-On | Delta |
| --- | --- | ---: | ---: | ---: |
| 1 | presence | 0.6 | 1.0 | 0.4 |
| 2 | self_explanation | 0.8 | 1.0 | 0.2 |
| 3 | identity | 0.8 | 1.0 | 0.2 |
| 4 | architecture | 0.8 | 1.0 | 0.2 |
| 5 | receipt_boundary | 1.0 | 1.0 | 0.0 |
| 6 | golden_field | 0.75 | 1.0 | 0.25 |
| 7 | mirror_architecture | 0.75 | 1.0 | 0.25 |
| 8 | openclaw_gate | 0.75 | 1.0 | 0.25 |
| 9 | telegram_bridge | 0.75 | 1.0 | 0.25 |
| 10 | paid_work | 0.75 | 1.0 | 0.25 |
| 11 | clarification | 1.0 | 1.0 | 0.0 |
| 12 | meta_improvement | 0.75 | 1.0 | 0.25 |