#!/usr/bin/env python3
from pathlib import Path

_TARGET = (
    Path(__file__).resolve().parents[1]
    / "src/performance_engineering/analysis/intelligence.py"
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
