#!/usr/bin/env python3

import sys
from pathlib import Path

_PROJECT_ROOT = (
    Path(__file__).resolve().parents[1]
)

_SRC_ROOT = (
    _PROJECT_ROOT
    / "src"
)

# Public runtime bootstrap:
# callers must never need to configure PYTHONPATH manually.
if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(_SRC_ROOT),
    )

_TARGET = (
    _SRC_ROOT
    / "performance_engineering"
    / "execution"
    / "governed_engine_runner.py"
)

_SOURCE = _TARGET.read_text(
    encoding="utf-8"
)

exec(
    compile(
        _SOURCE,
        str(Path(__file__).resolve()),
        "exec",
    ),
    globals(),
    globals(),
)
