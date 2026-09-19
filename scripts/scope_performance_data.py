#!/usr/bin/env python3
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "src/performance_engineering/design/scope_performance_data.py"

for candidate in (
    str(TARGET.parent),
    str(ROOT / "scripts"),
):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

_spec = spec_from_file_location(
    "_compat_scope_performance_data",
    TARGET,
)

if _spec is None or _spec.loader is None:
    raise RuntimeError(
        "Unable to load implementation: " + str(TARGET)
    )

_module = module_from_spec(_spec)
_spec.loader.exec_module(_module)

for _name in dir(_module):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_module, _name)

if __name__ == "__main__":
    _main = getattr(_module, "main", None)
    if _main is None:
        raise SystemExit(
            "Implementation does not expose main(): "
            + str(TARGET)
        )

    raise SystemExit(_main())
