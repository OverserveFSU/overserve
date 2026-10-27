# Auto-imported by Python at interpreter startup when this file's directory (the repo
# root) is discoverable at site-initialization time -- e.g. `python -c ...`, `python -m ...`,
# a REPL started in the repo root, or any run with the repo root on PYTHONPATH.
#
# It puts the relocated source directories (src/search, src/recon, src/attack_server) on
# sys.path so the flat module names used across the codebase keep resolving after the
# repository reorganization. It is intentionally self-contained (does NOT import
# overserve_paths) because at site-init time the current working directory is not yet on
# sys.path, so a sibling import would fail.
import os
import sys

try:
    _ROOT = os.path.dirname(os.path.abspath(__file__))
    for _s in ("", "src/search", "src/recon", "src/attack_server"):
        _d = os.path.join(_ROOT, _s) if _s else _ROOT
        if os.path.isdir(_d) and _d not in sys.path:
            sys.path.insert(0, _d)
except Exception:
    pass
