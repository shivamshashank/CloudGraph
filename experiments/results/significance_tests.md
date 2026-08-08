# Significance tests (paired bootstrap CI + Wilcoxon)

n=25 scenarios gives wide confidence intervals by construction — treat every result below as such, not as a precise point estimate.

### GPCS vs. self-consistency unsupported-rate delta (positive = GPCS flags MORE unsupported than self-consistency)

n = 75 paired observations
mean delta = -0.0870
95% bootstrap CI = [-0.1185, -0.0552]
Wilcoxon signed-rank: statistic=272.00, p=0.0000
significant at alpha=0.05: yes

### hybrid vs. raw-context claim-agreement-rate delta (positive = hybrid agrees with self-consistency more often)

n = 25 paired observations
mean delta = +0.0496
95% bootstrap CI = [-0.0174, +0.1137]
Wilcoxon signed-rank: statistic=108.00, p=0.1485
significant at alpha=0.05: no

### hybrid vs. keyword retrieval tag-recall delta (positive = hybrid recovers more expected tags; this is recall, not full F1 -- see module docstring)

n = 25 paired observations
mean delta = +0.1500
95% bootstrap CI = [+0.0600, +0.2400]
Wilcoxon signed-rank: statistic=21.00, p=0.0055
significant at alpha=0.05: yes

### real 5-agent system vs. matched-compute single-LLM unsupported-rate delta (positive = the 5-agent system hallucinates MORE than a single LLM sampled the same number of times)

n = 25 paired observations
mean delta = +0.1273
95% bootstrap CI = [+0.0532, +0.2006]
Wilcoxon signed-rank: statistic=51.00, p=0.0018
significant at alpha=0.05: yes
