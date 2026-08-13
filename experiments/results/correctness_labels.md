# Automatic correctness labelling

Labels derive from RCAEval's own case metadata (faulted service and
injected fault type). Only causal claims are labelled; descriptive
claims are `unverifiable` and excluded from the metrics below. This
is a conservative proxy for human judgement, not a replacement.

- claims total: 3685
- consistent: 49
- contradicted: 106
- unverifiable (excluded): 3530
- **evaluable subset: 155 (4.2% of claims)**

## Detecting incorrect claims (positive class = contradicted)

| verifier | precision | recall | F1 | specificity |
|---|---|---|---|---|
| GPCS | 0.681 | 0.604 | 0.640 | 0.388 |
| Self-consistency | 0.681 | 0.726 | 0.703 | 0.265 |

## Does either flag actually track correctness?

Precision near the base rate is what flagging everything would score,
so the discriminating question is whether the flag rate *differs*
between correct and incorrect claims.

| verifier | flags contradicted | flags consistent | gap |
|---|---|---|---|
| GPCS | 60.4% | 61.2% | -0.8 pp |
| Self-consistency | 72.6% | 73.5% | -0.8 pp |

Base rate of contradicted claims: 68.4%.
