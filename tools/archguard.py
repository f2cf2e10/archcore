"""ArchGuard: deterministic read-only Python project scanner and layer checker."""
import argparse
import ast
import json
import subprocess
import sys
from pathlib import Path

from archcore_contract import validate

EXCLUDED = {'.git', '.venv', 'venv', '__pycache__', '.mypy_cache', '.pytest_cache', '.ruff_cache', 'node_modules', 'build', 'dist'}


def within(path, root):
    return path == root or path.startswith(root + '/')


def scan(root, catalog):
    root = root.resolve()
    contract, profile, layers = validate(root / 'architecture.yaml', catalog)
    layer_rules = profile['layers']
    issues = []
    files = []
    module_index = {}
    py_files = []
    for path in sorted(root.rglob('*')):
        if any(part in EXCLUDED for part in path.relative_to(root).parts):
            continue
        if path.is_symlink():
            issues.append({'rule': 'symlink_skipped', 'severity': 'warning', 'file': path.relative_to(root).as_posix(), 'message': 'Symlink not followed'})
            continue
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        layer = next((name for name, prefix in layers.items() if within(rel, prefix)), None)
        files.append({'path': rel, 'layer': layer or 'unclassified'})
        if path.suffix == '.py':
            py_files.append((path, rel, layer))
            # Root-relative module name and src-layout import name.
            parts = rel[:-3].split('/')
            if parts[-1] == '__init__':
                parts.pop()
            if parts:
                module_index.setdefault('.'.join(parts), rel)
                if parts[0] == 'src' and len(parts) > 1:
                    module_index.setdefault('.'.join(parts[1:]), rel)
    edges = {}
    reported = set()
    dynamic = set()
    forbidden_imports = profile.get("forbidden_imports", {})
    conventions = profile.get("conventions", {})
    for path, rel, source_layer in py_files:
        try:
            tree = ast.parse(path.read_text(encoding='utf-8'), filename=rel)
        except (SyntaxError, UnicodeError) as exc:
            issues.append({'rule': 'parse_error', 'severity': 'error', 'file': rel, 'message': str(exc)})
            continue
        # Import paths are resolved only against project modules, avoiding guesses about external packages.
        parts = rel[:-3].split('/')
        if parts[-1] == '__init__':
            parts.pop()
            package_parts = parts
        else:
            package_parts = parts[:-1]
        for node in ast.walk(tree):
            requested = []
            if isinstance(node, ast.Import):
                requested = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    if node.level > len(package_parts):
                        issues.append({'rule': 'invalid_relative_import', 'severity': 'error', 'file': rel, 'line': node.lineno, 'message': 'Relative import escapes package root'})
                        continue
                    base = package_parts[:len(package_parts) - node.level + 1]
                    target = '.'.join(base + (node.module.split('.') if node.module else []))
                else:
                    target = node.module or ''
                requested = [target + '.' + alias.name if target else alias.name for alias in node.names if alias.name != '*']
                requested.append(target)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == '__import__':
                dynamic.add(rel)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'import_module':
                dynamic.add(rel)
            for name in requested:
                for prefix in forbidden_imports.get(source_layer, []) if source_layer else []:
                    if name == prefix or name.startswith(prefix + "."):
                        issues.append({"rule": "forbidden_framework_import", "severity": "error", "file": rel, "line": node.lineno, "message": f"{source_layer} must not import {prefix} ({name})"})
                match = name
                while match and match not in module_index:
                    match = match.rpartition('.')[0]
                if not match:
                    continue
                target_file = module_index[match]
                if target_file == rel:
                    continue
                target_layer = next((name for name, prefix in layers.items() if within(target_file, prefix)), None)
                edges.setdefault((rel, target_file, node.lineno), name)
                if source_layer and target_layer and source_layer != target_layer:
                    allowed = layer_rules[source_layer].get('dependencies', [])
                    if target_layer not in allowed and (rel, target_file, node.lineno) not in reported:
                        reported.add((rel, target_file, node.lineno))
                        issues.append({'rule': 'forbidden_layer_dependency', 'severity': 'error', 'file': rel, 'line': node.lineno, 'target': target_file, 'message': f'{source_layer} must not import {target_layer}'})
    # Detect transitive dependencies that pass through project modules.
    adjacency = {}
    for a, b, _ in edges:
        adjacency.setdefault(a, set()).add(b)
    by_file = {f["path"]: f["layer"] for f in files}
    for source in sorted(adjacency):
        source_layer = by_file[source]
        if source_layer == "unclassified":
            continue
        queue = [(n, [source, n]) for n in sorted(adjacency[source])]
        visited = {source}
        while queue:
            node, chain = queue.pop(0)
            if node in visited:
                continue
            visited.add(node)
            target_layer = by_file.get(node, "unclassified")
            if target_layer not in (source_layer, "unclassified") and target_layer not in layer_rules[source_layer].get("dependencies", []):
                if len(chain) > 2:
                    issues.append({"rule": "indirect_layer_dependency", "severity": "error", "file": source, "target": node, "message": "Forbidden transitive dependency: " + " -> ".join(chain)})
            for next_node in sorted(adjacency.get(node, [])):
                if next_node not in visited:
                    queue.append((next_node, chain + [next_node]))
    # Purely path-based placement checks, with conventions explicitly defined in the profile.
    for kind, marker in (("ports", "port"), ("adapters", "adapter")):
        owner = conventions.get(kind)
        if owner:
            for entry in files:
                if not entry["path"].endswith(".py"):
                    continue
                # Check explicit ports/ and adapters/ directory segments only; never guess semantics from class names.
                if kind in entry["path"].split("/") and entry["layer"] != owner:
                    issues.append({"rule": "misplaced_" + kind, "severity": "error", "file": entry["path"], "message": f"{kind}/ directory must be in {owner} layer"})
    for rel in sorted(dynamic):
        issues.append({'rule': 'dynamic_import', 'severity': 'warning', 'file': rel, 'message': 'Dynamic import detected; static graph may be incomplete'})
    present = {f['layer'] for f in files}
    for layer, location in layers.items():
        if not (root / location).is_dir():
            issues.append({'rule': 'missing_layer_directory', 'severity': 'error', 'file': location, 'message': f'Declared {layer} directory does not exist'})
    issues.sort(key=lambda i: (i['file'], i.get('line', 0), i['rule']))
    return {'root': str(root), 'architecture': profile['id'], 'layers': layers, 'allowed_dependencies': {k: v.get('dependencies', []) for k, v in layer_rules.items()}, 'files': files, 'edges': [{'source': a, 'target': b, 'import': edges[(a, b, d)], 'line': d} for a, b, d in sorted(edges)], 'issues': issues, 'summary': {'files': len(files), 'python_files': len(py_files), 'edges': len(edges), 'errors': sum(i['severity'] == 'error' for i in issues), 'warnings': sum(i['severity'] == 'warning' for i in issues)}}


def dot_graph(report, level):
    lines = ['digraph ArchCore {', '  rankdir=LR;']
    if level == 'layers':
        layers = report['layers']
        for layer in layers:
            lines.append(f'  {json.dumps(layer)};')
        seen = set()
        by_file = {f['path']: f['layer'] for f in report['files']}
        for edge in report['edges']:
            a, b = by_file[edge['source']], by_file[edge['target']]
            if (a, b) not in seen:
                lines.append(f'  {json.dumps(a)} -> {json.dumps(b)};')
                seen.add((a, b))
    else:
        for entry in report['files']:
            if entry['path'].endswith('.py'):
                lines.append(f'  {json.dumps(entry["path"])} [label={json.dumps(entry["path"])}];')
        for edge in report['edges']:
            lines.append(f'  {json.dumps(edge["source"])} -> {json.dumps(edge["target"])};')
    lines.append('}')
    return '\n'.join(lines) + '\n'


def changed_paths(root, base):
    """Get staged, unstaged, and untracked changes; fail closed outside Git."""
    def git(*args):
        result = subprocess.run(['git', '-C', str(root), *args], capture_output=True, text=True)
        if result.returncode:
            raise ValueError('Git change detection unavailable: ' + (result.stderr.strip() or 'not a repository'))
        return result.stdout
    top = Path(git('rev-parse', '--show-toplevel').strip()).resolve()
    if top != root.resolve():
        raise ValueError('project must be Git repository root for --changed')
    paths = set()
    for args in [('diff', '--name-only', '--no-renames', '-z'), ('diff', '--cached', '--name-only', '--no-renames', '-z'), ('ls-files', '--others', '--exclude-standard', '-z')]:
        paths.update(p for p in git(*args).split('\0') if p)
    if base:
        paths.update(p for p in git('diff', '--name-only', '--no-renames', '-z', base).split('\0') if p)
    return sorted(paths)


def check_changes(root, report, contract, base=None, scope=None):
    changed = changed_paths(root, base)
    gov = contract['governance']
    classification = {f['path']: f['layer'] for f in report['files']}
    protected = set(gov['protected_files'])
    issues = []
    for rel in changed:
        if scope is not None and not any(within(rel, prefix) for prefix in scope):
            issues.append({'rule': 'out_of_scope_change', 'severity': 'error', 'file': rel, 'message': 'Changed file is outside the requested scope'})
        layer = classification.get(rel)
        if layer is None:
            layer = next((name for name, prefix in report['layers'].items() if within(rel, prefix)), 'unclassified')
        protection = gov['protection'].get(layer, gov['unclassified'])
        if rel in protected:
            protection = 'forbidden'  # Policy files are never approved by an agent or inline contract.
        if protection != 'allowed_within_scope':
            issues.append({'rule': 'protected_change', 'severity': 'error', 'file': rel, 'message': f'Changed path requires {protection}; trusted approval is not configured'})
    return changed, issues


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['scan', 'check', 'explain'])
    parser.add_argument('--project', type=Path, default=Path('.'))
    parser.add_argument('--catalog', type=Path, default=Path.home() / '.codex' / 'archcore')
    parser.add_argument('--format', choices=['text', 'json', 'dot'], default='text')
    parser.add_argument('--graph-level', choices=['layers', 'files'], default='layers')
    parser.add_argument('--changed', action='store_true', help='validate Git changed paths (requires repository root)')
    parser.add_argument('--base', help='optional Git base revision for change detection')
    parser.add_argument('--scope', action='append', help='permitted changed path prefix; repeatable, requires --changed (not proof of authorization)')
    args = parser.parse_args(argv)
    if args.scope and not args.changed:
        parser.error('--scope requires --changed')
    if args.scope and any(not v or v.startswith('/') or '\\' in v or any(p in ('.', '..') for p in v.split('/')) for v in args.scope):
        parser.error('--scope values must be safe relative paths')
    try:
        if args.command == 'explain':
            print('ArchGuard: scan reports project facts, check validates architecture; --changed checks Git changes. Approval is deliberately fail-closed. Exit codes: 0 success, 1 violation, 2 configuration/Git failure.')
            return 0
        report = scan(args.project, args.catalog)
        if args.changed:
            contract, _, _ = validate(args.project.resolve() / 'architecture.yaml', args.catalog)
            changed, extra = check_changes(args.project.resolve(), report, contract, args.base, args.scope)
            report['changed_files'] = changed
            report['issues'].extend(extra)
            report['summary']['errors'] += sum(i['severity'] == 'error' for i in extra)
            report['issues'].sort(key=lambda i: (i['file'], i.get('line', 0), i['rule']))
    except (ValueError, OSError) as exc:
        print(f'ArchGuard configuration error: {exc}', file=sys.stderr)
        return 2
    if args.format == 'json':
        print(json.dumps(report, indent=2))
    elif args.format == 'dot':
        print(dot_graph(report, args.graph_level), end='')
    else:
        s = report['summary']
        print(f'ArchGuard {args.command}: {report["architecture"]} | {s["files"]} files | {s["edges"]} imports | {s["errors"]} errors | {s["warnings"]} warnings')
        for layer, path in report['layers'].items():
            print(f'  {layer}: {path} -> {", ".join(report["allowed_dependencies"][layer]) or "no other layers"}')
        for issue in report['issues']:
            print(f'  {issue["severity"].upper()} [{issue["rule"]}] {issue["file"]}:{issue.get("line", "-")} {issue["message"]}')
    return 1 if args.command == 'check' and report['summary']['errors'] else 0


if __name__ == '__main__':
    sys.exit(main())
