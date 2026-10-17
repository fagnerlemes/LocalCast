import os
import subprocess
import sys

import pytest

from localcast.storage import ProfileLease


def test_profile_lock_prevents_second_writer_and_releases(tmp_path):
    first = ProfileLease(tmp_path)
    try:
        with pytest.raises(RuntimeError, match='já está aberto'):
            ProfileLease(tmp_path)
    finally:
        first.close()
    second = ProfileLease(tmp_path)
    second.close()


def test_stale_profile_lock_recovers_after_crash(tmp_path):
    env = os.environ.copy()
    env['PYTHONPATH'] = os.pathsep.join(sys.path)
    code = ('import os,sys; from localcast.storage import ProfileLease; '
            'lease=ProfileLease(sys.argv[1]); os._exit(0)')
    subprocess.run([sys.executable, '-B', '-c', code, str(tmp_path)],
                   env=env, check=True, timeout=10)
    lease = ProfileLease(tmp_path)
    lease.close()
