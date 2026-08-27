# Experiment 1 — GPCS and Self-Consistency, Side by Side

Both verifiers score **the same claims**, from the same extraction, from the
same generation. Only the mechanism differs, which is what makes the
comparison fair. 1,950 claims across 54 runs.

> All figures are descriptive. No inferential statistics are computed.

## Agreement structure

### `NONE` — 628 claims

| | SC supported | SC unsupported |
|---|---:|---:|
| **GPCS supported** | 103 | 33 |
| **GPCS unsupported** | 167 | 325 |

Concordance 428/628 = **68.2%**. GPCS-only rejections: **167** (26.6%) — the strictness gap made visible.

### `RAW` — 703 claims

| | SC supported | SC unsupported |
|---|---:|---:|
| **GPCS supported** | 113 | 27 |
| **GPCS unsupported** | 244 | 319 |

Concordance 432/703 = **61.5%**. GPCS-only rejections: **244** (34.7%) — the strictness gap made visible.

### `HYBRID` — 619 claims

| | SC supported | SC unsupported |
|---|---:|---:|
| **GPCS supported** | 92 | 36 |
| **GPCS unsupported** | 197 | 294 |

Concordance 386/619 = **62.4%**. GPCS-only rejections: **197** (31.8%) — the strictness gap made visible.

### Pooled — 1,950 claims

| | SC supported | SC unsupported |
|---|---:|---:|
| **GPCS supported** | 308 | 96 |
| **GPCS unsupported** | 608 | 938 |

Concordance 1246/1950 = **63.9%**.

## Per-scenario evaluable coverage

| Scenario | Fault | NONE | RAW | HYBRID |
|---|---|---:|---:|---:|
| `rcaeval-03` | cpu | 2/38 | 3/41 | 2/35 |
| `rcaeval-14` | memory | 3/27 | 0/52 | 3/36 |
| `rcaeval-07` | disk | 1/48 | 0/42 | 2/33 |
| `rcaeval-04` | network | 1/34 | 0/31 | 1/33 |
| `rcaeval-29` | packet | 0/41 | 0/40 | 0/33 |
| `rcaeval-18` | socket | 0/30 | 1/35 | 3/32 |
| `rcaeval-01` | cpu | 2/32 | 1/42 | 4/36 |
| `rcaeval-13` | memory | 0/34 | 2/30 | 3/39 |
| `rcaeval-10` | packet | 0/27 | 0/42 | 0/36 |
| `rcaeval-16` | socket | 0/46 | 1/32 | 2/41 |
| `rcaeval-02` | cpu | 5/37 | 2/34 | 1/9 |
| `rcaeval-08` | disk | 5/33 | 2/38 | 0/35 |
| `rcaeval-05` | network | 1/27 | 0/38 | 5/35 |
| `rcaeval-17` | socket | 4/36 | 6/44 | 2/38 |
| `rcaeval-15` | memory | 2/38 | 1/41 | 4/41 |
| `rcaeval-09` | disk | 2/36 | 1/32 | 2/40 |
| `rcaeval-06` | network | 0/31 | 0/53 | 1/40 |
| `rcaeval-12` | packet | 2/33 | 5/36 | 3/27 |

Pooled: **93/1950 = 4.8%** adjudicable.

## What the joint filter buys

Requiring **both** verifiers to accept keeps **308** of 1950 claims
(**15.8%**) — a 84.2% reduction in claim volume.

**The surviving set is more precise — on six claims.** Among the 93 adjudicable
claims, the joint filter accepts **4 of 36** correct and **2 of 57** incorrect,
so the survivors are **4/6 = 0.667** correct against a base rate of **0.387**.
That points the right way, and it is the only positive correctness signal
anywhere in this evaluation.

**It is also six claims.** Two claims moving would erase it, and the same filter
discards 32 of the 36 correct claims it was given — an 89% false-rejection rate
on true statements. Treat it as a hypothesis worth testing on a larger labelled
set, not as a result. It does not rescue H5: neither verifier *individually*
tracks correctness, and the joint filter's apparent gain rests on a sample far
too small to carry it.

## Caveat

Concordance is **not** accuracy. Both verifiers can be wrong about the same
claim and it still counts on the diagonal. Run-to-run variance on an identical
configuration reached 25.7 pp, so per-scenario cells above are indicative only.
