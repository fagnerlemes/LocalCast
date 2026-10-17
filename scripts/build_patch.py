"""Generate a small file-replacement patch against a known onedir distribution.

Only existing installed files may change: the original uninstaller stays valid.
By Fagner Lemes.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath


def hashes(directory):
    return {p.relative_to(directory).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(directory.rglob('*')) if p.is_file()}


def validate(base, current):
    if set(base) != set(current):
        raise ValueError('O conjunto de dependências mudou. Gere o instalador completo.')
    for name, digest in [*base.items(), *current.items()]:
        path = PurePosixPath(name)
        if (path.is_absolute() or '..' in path.parts or '\\' in name or ':' in name
                or "'" in name or '"' in name or '{' in name or '}' in name
                or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest)):
            raise ValueError('Caminho ou hash inválido no manifesto.')
    changed = [name for name in base if base[name] != current[name]]
    if not changed:
        raise ValueError('Nenhum arquivo mudou.')
    return changed


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument('--revision', type=int, choices=(1, 2), default=2)
    parser.add_argument('--base', type=Path)
    parser.add_argument('--current', type=Path, default=root / 'dist/LocalCast')
    args = parser.parse_args()
    number = f'{args.revision:02d}'
    base_path = args.base or root / 'installer' / (
        'base-0.2.0.json' if args.revision == 1 else 'base-0.2.0-patch01.json')
    base = json.loads(base_path.read_text(encoding='utf-8'))['files']
    current = hashes(args.current)
    changed = validate(base, current)
    output = root / ('build/patch' + number)
    output.mkdir(parents=True, exist_ok=True)
    files = []
    checks = []
    for name in changed:
        path = args.current.resolve() / name
        relative_parent = str(PurePosixPath(name).parent).replace('/', '\\')
        target = '{app}' + ('\\' + relative_parent if relative_parent != '.' else '')
        files.append(f'Source: "{path}"; DestDir: "{target}"; Flags: ignoreversion')
    for name in base:
        checks.append("  if not CheckFile('" + name.replace('/', '\\') + "', '" + base[name]
                      + "', '" + current[name] + "') then Exit;")
    (output / 'files.iss').write_text('\n'.join(files) + '\n', encoding='utf-8-sig')
    (output / 'checks.iss').write_text('\n'.join(checks) + '\n', encoding='utf-8-sig')
    (output / 'manifest.json').write_text(json.dumps({
        'version': '0.2.0', 'build': '020-patch' + number, 'changed_files': changed,
        'files': {name: {'before': base[name], 'after': current[name]} for name in changed},
        'payload_bytes': sum((args.current / name).stat().st_size for name in changed),
    }, indent=2), encoding='utf-8')
    print(f'Patch preparado: {len(changed)} arquivos. Compile installer/LocalCast-patch.iss.')


if __name__ == '__main__':
    main()
