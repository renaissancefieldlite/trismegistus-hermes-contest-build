# Golden Mark Foundation

This demo carries Golden Mark as the foundation, not as background decoration.

## Behavior results

- C5b iter30 full comparison: 13/13 metric wins against matched baseline.
- Drift flags: 37 to 0.
- Evidence-failure flags: 5 to 0.
- Repaired HF probe9 matched-turn drift: 5 to 0.
- Repaired HF probe9 evidence failures: 2 to 0.

## Internal layer read

- Strongest output separation: layer 31.
- Strongest MLP/residual movement: layer 32.

## Current adapter ladder gate

- GM-L31L32-MLP.
- GM-L31L32-MLP-O.
- GM-ALL-MLP-O-smallrank.
- GM-CONTROL-SHUFFLED.
- GM-CONTROL-NO-SSP.

## Current runtime block

The HF layer-gated adapter was not trained in the prior local environment because `peft` could
not import against the current `transformers` package: `HybridCache` was missing. The next
clean technical gate is an isolated HF environment with compatible `transformers` and `peft`
versions, then rerun the ladder around layers 31-32.
