"""ArchCore project contract validator. No change/approval enforcement."""
import argparse
from pathlib import Path, PurePosixPath
import sys
import yaml

PROTECTION = {'allowed_within_scope': 0, 'human_approval': 1, 'forbidden': 2}
TOP = {'architecture', 'methodologies', 'principles', 'patterns', 'governance'}


def fail(msg):
    raise ValueError(msg)


def mapping(obj, field):
    if not isinstance(obj, dict): fail(f'{field} must be a mapping')
    return obj


def keys(obj, valid, field):
    extras = set(obj) - set(valid)
    if extras: fail(f'{field}: unsupported keys: {", ".join(sorted(map(str, extras)))}')


def path(value, field):
    if not isinstance(value, str) or not value or '\\' in value or value.startswith('/'):
        fail(f'{field} must be a relative POSIX path')
    p = PurePosixPath(value)
    if any(s in ('.', '..') for s in value.split('/')) or str(p) in ('', '.') or ':' in value or '*' in value:
        fail(f'{field} has unsafe or unsupported components')
    return str(p)


def valid_id(name):
    return isinstance(name, str) and bool(name) and name[0].isalpha() and all(ch.islower() or ch.isdigit() or ch == '-' for ch in name)


def load_yaml(p):
    if not p.is_file(): fail(f'file missing: {p}')
    data = yaml.safe_load(p.read_text(encoding='utf-8'))
    return mapping(data, str(p))


def validate(contract, catalog):
    c = load_yaml(contract)
    keys(c, TOP, 'contract')
    a = mapping(c.get('architecture'), 'architecture')
    keys(a, {'style', 'layers'}, 'architecture')
    style = a.get('style')
    if not isinstance(style, str) or not valid_id(style):
        fail('architecture.style must identify a catalog module by stable name')
    profile = load_yaml(catalog / 'architectures' / f'{style}.yaml')
    if profile.get('id') != style or profile.get('kind') != 'architecture': fail('architecture profile identity mismatch')
    expected = mapping(profile.get('layers'), 'profile.layers')
    layers = mapping(a.get('layers'), 'architecture.layers')
    if set(layers) != set(expected): fail('architecture.layers must map exactly the profile layers: ' + ', '.join(expected))
    normalized = {k: path(v, f'architecture.layers.{k}') for k, v in layers.items()}
    paths = list(normalized.values())
    if len(set(paths)) != len(paths): fail('layer paths must be unique')
    for i, p in enumerate(paths):
        for other in paths[i+1:]:
            if p.startswith(other + '/') or other.startswith(p + '/'):
                fail('layer paths must not overlap')
    methods = c.get('methodologies', [])
    if not isinstance(methods, list) or any(not isinstance(m, str) for m in methods): fail('methodologies must be a string list')
    if len(set(methods)) != len(methods): fail('duplicate methodology')
    for m in methods:
        if not valid_id(m): fail(f'invalid methodology: {m}')
        mod = load_yaml(catalog / 'methodologies' / f'{m}.yaml')
        if mod.get('kind') != 'methodology' or mod.get('id') != m: fail(f'methodology module identity mismatch: {m}')
    # Optional knowledge selections are advisory, not mandatory code structures.
    # All identifiers must resolve to the central catalog and never be dangling.
    for field, directory, kind in (
        ('principles', 'principles', 'principle'),
        ('patterns', 'patterns', 'pattern'),
    ):
        selected = c.get(field, [])
        if not isinstance(selected, list) or any(not isinstance(item, str) for item in selected):
            fail(f'{field} must be a string list')
        if len(set(selected)) != len(selected): fail(f'duplicate {kind}')
        for item in selected:
            if not valid_id(item): fail(f'invalid {kind}: {item}')
            module = load_yaml(catalog / directory / f'{item}.yaml')
            if module.get('kind') != kind or module.get('id') != item:
                fail(f'{kind} module identity mismatch: {item}')
    gov = mapping(c.get('governance'), 'governance')
    keys(gov, {'protection', 'unclassified', 'protected_files', 'exceptions'}, 'governance')
    protection = mapping(gov.get('protection'), 'governance.protection')
    if set(protection) != set(expected): fail('protection must specify exactly the architecture layers')
    for layer, status in protection.items():
        floor = mapping(expected[layer], f'profile.layers.{layer}').get('protection_floor')
        if status not in PROTECTION or floor not in PROTECTION: fail(f'invalid protection status for {layer}')
        if PROTECTION[status] < PROTECTION[floor]: fail(f'{layer} weakens profile protection floor {floor}')
    if gov.get('unclassified') not in ('human_approval', 'forbidden'):
        fail('unclassified must be human_approval or forbidden (fail closed)')
    files = gov.get('protected_files')
    if not isinstance(files, list) or 'architecture.yaml' not in files:
        fail('protected_files must include architecture.yaml')
    if len(set(files)) != len(files): fail('duplicate protected file')
    for idx, f in enumerate(files): path(f, f'protected_files[{idx}]')
    exceptions = gov.get('exceptions', [])
    if exceptions != []: fail('exceptions are not supported; use []')
    return c, profile, normalized


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    check = sub.add_parser('validate', help='validate configuration (not code changes)')
    check.add_argument('contract', type=Path)
    check.add_argument('--catalog', type=Path, default=Path.home() / '.codex' / 'archcore')
    args = p.parse_args(argv)
    try:
        c, profile, layer_paths = validate(args.contract, args.catalog)
        print(f'VALID contract | architecture: {profile["id"]} | methodologies: {", ".join(c.get("methodologies", [])) or "none"}')
        print(f'  principles: {", ".join(c.get("principles", [])) or "none"} | patterns: {", ".join(c.get("patterns", [])) or "none"}')
        for name, location in layer_paths.items():
            print(f'  {name}: {location} | {c["governance"]["protection"][name]}')
        print(f'  unclassified: {c["governance"]["unclassified"]}')
        print('NOTE: contract validation only; approvals, imports, and Git diffs were not checked.')
        return 0
    except (ValueError, OSError, yaml.YAMLError) as exc:
        print(f'INVALID: {exc}', file=sys.stderr)
        return 1

if __name__ == '__main__':
    sys.exit(main())
