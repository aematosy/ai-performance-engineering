#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path


class PatchError(RuntimeError):
    pass


def backup(path: Path) -> Path:
    backup_path = path.with_suffix(path.suffix + '.before-entrypoint-hardening')
    if not backup_path.exists():
        shutil.copy2(path, backup_path)
    return backup_path


def find_target_block(text: str, target: str) -> tuple[int, int]:
    lines = text.splitlines(keepends=True)
    start = None
    end = None
    offset = 0
    target_pattern = re.compile(rf'^{re.escape(target)}\s*:')
    any_target_pattern = re.compile(r'^[A-Za-z0-9_.-]+\s*:')

    for line in lines:
        if start is None and target_pattern.match(line):
            start = offset
        elif start is not None and any_target_pattern.match(line):
            end = offset
            break
        offset += len(line)

    if start is None:
        raise PatchError(f'Target not found in Makefile: {target}')
    if end is None:
        end = len(text)
    return start, end


def replace_target_block(text: str, target: str, replacement: str) -> str:
    start, end = find_target_block(text, target)
    if not replacement.endswith('\n'):
        replacement += '\n'
    return text[:start] + replacement + text[end:]


def insert_variable_once(text: str, variable_line: str) -> str:
    variable_name = variable_line.split('?=', 1)[0].strip()
    if re.search(rf'^{re.escape(variable_name)}\s*\?=', text, flags=re.MULTILINE):
        return text
    matches = list(re.finditer(r'^(?:PLAN|JMX)\s*\?=.*$', text, flags=re.MULTILINE))
    if not matches:
        raise PatchError('Could not find PLAN/JMX variable section in Makefile.')
    anchor = matches[-1]
    return text[:anchor.end()] + '\n' + variable_line + text[anchor.end():]


def patch_makefile(path: Path) -> None:
    text = path.read_text(encoding='utf-8')
    backup(path)
    text = insert_variable_once(text, 'PROFILE ?= config/execution-profiles/baseline.yaml')
    text = insert_variable_once(text, 'RUN_MANIFEST ?= work/pre-execution/make-run-demo.json')

    new_run_demo = (
        'run-demo: validate-jmx\n'
        '\t$(PYTHON) scripts/run_approved_plan.py \\\n'
        '\t\t--plan "$(PLAN)" \\\n'
        '\t\t--profile "$(PROFILE)" \\\n'
        '\t\t--jmx "$(JMX)" \\\n'
        '\t\t--manifest "$(RUN_MANIFEST)" \\\n'
        '\t\t--execute\n\n'
    )
    text = replace_target_block(text, 'run-demo', new_run_demo)

    if not re.search(r'^preflight-demo\s*:', text, flags=re.MULTILINE):
        _, run_end = find_target_block(text, 'run-demo')
        block = (
            'preflight-demo: validate-jmx\n'
            '\t$(PYTHON) scripts/run_approved_plan.py \\\n'
            '\t\t--plan "$(PLAN)" \\\n'
            '\t\t--profile "$(PROFILE)" \\\n'
            '\t\t--jmx "$(JMX)" \\\n'
            '\t\t--manifest "$(RUN_MANIFEST)" \\\n'
            '\t\t--preflight\n\n'
        )
        text = text[:run_end] + block + text[run_end:]

    if not re.search(r'^authorize-demo\s*:', text, flags=re.MULTILINE):
        _, preflight_end = find_target_block(text, 'preflight-demo')
        block = (
            'authorize-demo:\n'
            '\t@if [ -z "$(AUTHORIZED_BY)" ]; then echo \'ERROR: use make authorize-demo AUTHORIZED_BY="Nombre Apellido"\'; exit 2; fi\n'
            '\t$(PYTHON) scripts/authorize_execution.py \\\n'
            '\t\t--plan "$(PLAN)" \\\n'
            '\t\t--authorized-by "$(AUTHORIZED_BY)" \\\n'
            '\t\t--notes "Authorized through controlled Makefile workflow."\n'
            '\t@echo ""\n'
            '\t@echo "Authorization changes the plan hash."\n'
            '\t@echo "Run: make generate-jmx SCENARIO=$(SCENARIO)"\n\n'
        )
        text = text[:preflight_end] + block + text[preflight_end:]

    if re.search(r'run_approved_plan\.py[^\n]*--authorized', text, flags=re.IGNORECASE):
        raise PatchError('Legacy public --authorized flow remains in Makefile.')
    if 'Type RUN to authorize exactly' in text:
        raise PatchError('Legacy Makefile confirmation still claims to authorize execution.')

    path.write_text(text, encoding='utf-8')


def patch_execution_contract(path: Path) -> None:
    backup(path)
    content = '''# Controlled execution contract

The only supported user-facing execution entry point is `run_approved_plan.py`.

Use `--preflight` for validation only and `--execute` for an already-authorized run.

`--execute` never grants authorization. The plan must already contain:

- `authorization.status: AUTHORIZED`
- an explicit `authorized_by`
- `authorized_at`
- `approval.execution_authorized: true`

The final `Type RUN` prompt is confirmation only.

Never expose `run_test.py --authorized` or `run_approved_plan.py --authorized` as public commands.

The low-level `run_test.py --authorized` flag is an internal compatibility handoff only.
'''
    path.write_text(content, encoding='utf-8')


def patch_runner_skill(path: Path) -> None:
    text = path.read_text(encoding='utf-8')
    backup(path)
    text = text.replace('run_approved_plan.py --authorized', 'run_approved_plan.py --execute')
    text = text.replace('solicitar autorización humana explícita', 'verificar autorización de ejecución ya registrada y solicitar confirmación humana final')
    if 'Type RUN' not in text:
        text += '\n\nEl prompt `Type RUN` es confirmación final, no autorización.\n'
    path.write_text(text, encoding='utf-8')


def patch_guidance_file(path: Path) -> None:
    if not path.exists():
        return
    text = path.read_text(encoding='utf-8')
    backup(path)
    marker = '## Controlled execution entry point'
    block = '''## Controlled execution entry point

Use `run_approved_plan.py --preflight` for validation and `run_approved_plan.py --execute` only after execution authorization is already recorded in the plan.

`Type RUN` is final confirmation only.

Never expose `run_test.py --authorized` or `run_approved_plan.py --authorized` as user-facing commands.
'''
    if marker not in text:
        text = text.rstrip() + '\n\n' + block + '\n'
    else:
        text = re.sub(r'## Controlled execution entry point.*?(?=\n## |\Z)', block.rstrip(), text, flags=re.DOTALL)
    path.write_text(text, encoding='utf-8')


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default='.')
    args = parser.parse_args()
    root = Path(args.root).expanduser().resolve()
    files = {
        'makefile': root / 'Makefile',
        'contract': root / '.axet' / 'skills' / 'performance-test-runner' / 'references' / 'execution-contract.md',
        'skill': root / '.axet' / 'skills' / 'performance-test-runner' / 'SKILL.md',
        'axet': root / 'AXET.md',
        'readme': root / 'README.md',
    }
    try:
        for key in ('makefile', 'contract', 'skill'):
            if not files[key].is_file():
                raise PatchError(f'Required file missing: {files[key]}')
        patch_makefile(files['makefile'])
        patch_execution_contract(files['contract'])
        patch_runner_skill(files['skill'])
        patch_guidance_file(files['axet'])
        patch_guidance_file(files['readme'])
    except (PatchError, OSError) as exc:
        print(f'ENTRYPOINT HARDENING ERROR: {exc}', file=sys.stderr)
        return 2
    print('=' * 72)
    print('EXECUTION ENTRYPOINT HARDENING v1.1')
    print('=' * 72)
    print('Makefile             : UPDATED')
    print('Runner contract      : UPDATED')
    print('Runner skill         : UPDATED')
    print('AXET.md guidance   : UPDATED')
    print('README.md guidance   : UPDATED')
    print('Public --authorized  : REMOVED FROM GUIDANCE')
    print('=' * 72)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
