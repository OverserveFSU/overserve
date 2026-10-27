"""Central sys.path bootstrap for the reorganized OverServe repo.

Importing this module (directly, or auto-loaded via the repo-root ``sitecustomize.py``)
puts the relocated source directories on ``sys.path`` so the flat module names used
across the codebase (e.g. ``import toolatk_search_v5``, ``import recon_analyzer``) keep
resolving after the move into ``src/search``, ``src/recon`` and ``src/attack_server``.

Entry scripts that live in subdirectories (``scripts/``, ``benchmarks/<x>/`` ...) can make
these imports work regardless of where they are launched from with::

    import os, sys
    _d = os.path.dirname(os.path.abspath(__file__))
    while _d != os.path.dirname(_d) and not os.path.exists(os.path.join(_d, "overserve_paths.py")):
        _d = os.path.dirname(_d)
    sys.path.insert(0, _d); import overserve_paths  # noqa
"""
import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))

_DIRS = [
    _ROOT,
    os.path.join(_ROOT, "src", "search"),
    os.path.join(_ROOT, "src", "recon"),
    os.path.join(_ROOT, "src", "attack_server"),
]

for _d in _DIRS:
    if os.path.isdir(_d) and _d not in sys.path:
        sys.path.insert(0, _d)
