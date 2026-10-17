import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('build_patch', Path(__file__).parents[1] / 'scripts/build_patch.py')
patch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patch)


def test_patch_contains_only_changed_existing_files():
    base = {'LocalCast.exe': 'a' * 64, '_internal/tool.dll': 'b' * 64}
    current = {**base, 'LocalCast.exe': 'c' * 64}
    assert patch.validate(base, current) == ['LocalCast.exe']
    with pytest.raises(ValueError, match='dependências'):
        patch.validate(base, {**current, 'new.dll': 'd' * 64})
    with pytest.raises(ValueError, match='Nenhum'):
        patch.validate(base, base)


@pytest.mark.parametrize('name', ['../user.db', '/absolute', 'C:/video', "file'", 'file{app}'])
def test_patch_manifest_rejects_unsafe_paths(name):
    with pytest.raises(ValueError, match='inválido'):
        patch.validate({name: 'a' * 64}, {name: 'b' * 64})
