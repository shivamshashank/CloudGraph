"""Adds services/api to sys.path so scripts/*.py can import the app
package directly, without installing it as a package first.

`import _bootstrap` as the very first line of a scripts/*.py file, before
any `from app... import ...` line — since it's an import statement itself
(not an inline sys.path.insert() call in the calling script), the calling
script's own imports stay contiguous from the top of the file, so
pylint's wrong-import-position check has nothing to flag. Works because
running `python scripts/foo.py` puts foo.py's own directory (scripts/)
at sys.path[0] automatically, so this sibling module resolves before
services/api itself is on the path.

Also exposes API_ROOT/REPO_ROOT so callers don't each need their own
fragile `Path(__file__).resolve().parent.parent.parent.parent` chain to
find experiment-1-benchmark/results/.
"""

import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = API_ROOT.parent.parent

if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))
