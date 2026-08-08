"""Sets matplotlib's backend to Agg (headless, no display — this process
only ever saves PNGs) before pyplot is imported anywhere in the process.

Must be its own module, imported before `import matplotlib.pyplot`: the
backend selection has no effect once pyplot has already been imported once,
and an inline `matplotlib.use("Agg")` call in the calling script (a plain
statement, not an import) would sit between that script's own import
lines, which is exactly the ordering pylint's wrong-import-position check
exists to catch elsewhere — this makes the ordering requirement real
(enforced by import machinery) rather than something a comment has to
explain and a disable has to excuse.
"""

import matplotlib

BACKEND = "Agg"
matplotlib.use(BACKEND)
