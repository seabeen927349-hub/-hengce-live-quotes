"""Static health/producer boundary audit. Reads source only; executes no producer."""
import ast
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
INFRASTRUCTURE = frozenset({
    '.github/workflows/hengce-system-health.yml',
    'scripts/hengce_system_health.py',
    'scripts/hengce_health_collect_runs.py',
    'scripts/hengce_publish.py',
    'config/hengce_health_v1.json',
})
CODE_SUFFIXES = {'.py', '.sh', '.bash', '.js', '.ts', '.mjs', '.cjs', '.yml', '.yaml'}
FORBIDDEN = re.compile(r'hengce[/\\]+health\b|[/\\]health(?:[/\\]|$)|'
                       r'hengce_system_health|hengce_health_collect_runs|'
                       r'hengce_health_v1', re.IGNORECASE)
HEALTH_COMPONENT = re.compile(r'''["']health["']''', re.IGNORECASE)


def test_or_document(path):
    return path.startswith(('tests/', 'docs/')) or (
        path.startswith('scripts/') and Path(path).name.startswith('test_'))


def source_path(path):
    return Path(path).suffix in CODE_SUFFIXES or (
        Path(path).suffix == '.json' and (path.startswith('config/') or
        (path.startswith('hengce/') and path.count('/') == 1)))


def constant_string(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = constant_string(node.left), constant_string(node.right)
        if left is not None and right is not None:
            return left + right
    return None


def audit(sources, inventoried_workflows=()):
    """Injectable path->source map; errors require explicit dependency re-audit.

    Conservative superset: all non-test repository code/config is audited, not
    just the frozen inventory. Test helpers lose their exemption when imported
    by production code or invoked by a producer workflow. Infrastructure remains
    a narrow, exact-path allowlist, never a scripts/** exemption.
    """
    errors = []
    for path in inventoried_workflows:
        if path not in sources:
            errors.append(path + ': INVENTORIED_PRODUCER_SOURCE_MISSING')
    modules = {}
    for path in sources:
        if path.endswith('.py'):
            modules.setdefault(Path(path).stem, set()).add(path)
    pending = [p for p in sources if source_path(p) and not test_or_document(p)]
    visited = set()
    while pending:
        path = pending.pop()
        if path in visited or path in INFRASTRUCTURE:
            continue
        visited.add(path)
        text = sources[path]
        if FORBIDDEN.search(text) or (Path(path).suffix != '.json' and HEALTH_COMPONENT.search(text)):
            errors.append(path + ': HEALTH_PRODUCER_DEPENDENCY_REQUIRES_PROFILE_REAUDIT')
        if path.endswith('.json'):
            try:
                values = [json.loads(text)]
                while values:
                    value = values.pop()
                    if isinstance(value, dict):
                        values.extend(value.values())
                    elif isinstance(value, list):
                        values.extend(value)
                    elif isinstance(value, str) and value.lower() == 'health':
                        errors.append(path + ': HEALTH_LITERAL_REQUIRES_PROFILE_REAUDIT')
            except ValueError:
                errors.append(path + ': UNPARSEABLE_PRODUCER_CONTRACT')
        # Audit test/helper source called from any existing or newly introduced
        # publisher workflow too; ordinary CI test jobs are not producer roots.
        if path.startswith('.github/workflows/') and (
                path in inventoried_workflows or 'hengce_publish.py' in text or
                re.search(r'git\s+push.*\bmain\b', text)):
            for candidate in sources:
                module = candidate.removesuffix('.py').replace('/', '.')
                if test_or_document(candidate) and source_path(candidate) and (
                        candidate in text or (candidate.endswith('.py') and module in text)):
                    pending.append(candidate)
        if not path.endswith('.py'):
            continue
        try:
            parsed = ast.parse(text, filename=path)
        except SyntaxError:
            errors.append(path + ': UNPARSEABLE_PRODUCER_SOURCE')
            continue
        for node in ast.walk(parsed):
            value = constant_string(node)
            if value is not None and (value.lower() == 'health' or FORBIDDEN.search(value)):
                errors.append(path + ': HEALTH_LITERAL_REQUIRES_PROFILE_REAUDIT')
            imported = []
            if isinstance(node, ast.Import):
                imported = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                imported = [node.module or ''] + [a.name for a in node.names]
            elif isinstance(node, ast.Call) and node.args and (
                    isinstance(node.func, ast.Name) and node.func.id == '__import__' or
                    isinstance(node.func, ast.Attribute) and node.func.attr == 'import_module'):
                name = constant_string(node.args[0])
                imported = [name] if name is not None else []
            # Follow all matching local modules; ambiguity is conservative.
            for name in imported:
                pending.extend(modules.get(name.rsplit('.', 1)[-1], ()))
    return sorted(set(errors)), sorted(visited)


def repository_sources(root=ROOT):
    paths = subprocess.check_output(['git', '-C', str(root), 'ls-files', '-z'], text=True).split('\0')
    # Only source/contracts, not market data, histories, outcomes or holdouts.
    return {p: (root / p).read_text(encoding='utf-8') for p in paths if p and source_path(p)}


def main():
    import json
    inventory = json.loads((ROOT / 'docs/engineering/writer-topology.json').read_text())
    workflows = {w['workflow'] for w in inventory['writers']}
    errors, checked = audit(repository_sources(), workflows)
    if errors:
        print('\n'.join(errors))
        return 1
    print(f'PASS: {len(workflows)} inventoried producer workflows; {len(checked)} sources audited; no health dependency')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
