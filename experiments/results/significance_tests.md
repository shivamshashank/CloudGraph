# Significance tests (paired bootstrap CI + Wilcoxon)

n=36 scenarios. Confidence intervals are wide at this sample size — treat every result below as an interval, not a precise point estimate.

### GPCS vs. self-consistency unsupported-rate delta (positive = GPCS flags MORE unsupported than self-consistency)

n = 36 paired observations
mean delta = +0.1185
95% bootstrap CI = [+0.0729, +0.1632]
Wilcoxon signed-rank: statistic=77.00, p=0.0000
significant at alpha=0.05: yes

### hybrid vs. raw-context claim-agreement-rate delta (positive = hybrid agrees with self-consistency more often)

n = 36 paired observations
mean delta = +0.0240
95% bootstrap CI = [-0.0280, +0.0773]
Wilcoxon signed-rank: statistic=252.00, p=0.3021
significant at alpha=0.05: no

### hybrid vs. keyword retrieval tag-recall delta (positive = hybrid recovers more expected tags; this is recall, not full F1 -- see module docstring)

n = 36 paired observations
mean delta = +0.1898
95% bootstrap CI = [+0.1157, +0.2685]
Wilcoxon signed-rank: statistic=0.00, p=0.0003
significant at alpha=0.05: yes

### SENSITIVITY -- GPCS vs. self-consistency, excluding the 4 scenarios containing a rule-based-fallback generation (rcaeval-02, rcaeval-04, rcaeval-05, rcaeval-36)

n = 32 paired observations
mean delta = +0.1255
95% bootstrap CI = [+0.0801, +0.1724]
Wilcoxon signed-rank: statistic=49.00, p=0.0000
significant at alpha=0.05: yes
