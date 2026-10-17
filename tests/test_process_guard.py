import os
import subprocess
import sys
import time

import psutil
import pytest


@pytest.mark.skipif(os.name != 'nt', reason='Windows Job Object')
def test_abrupt_parent_exit_terminates_own_child(tmp_path):
    env = os.environ.copy()
    env['PYTHONPATH'] = os.pathsep.join(sys.path)
    pid_file = tmp_path / 'child-pid.txt'
    script = '''import os,sys,time
from pathlib import Path
from localcast.process_guard import ProcessGuard
guard=ProcessGuard()
child=guard.spawn([sys.executable,'-c','import time; time.sleep(90)'])
Path(sys.argv[1]).write_text(str(child.pid))
time.sleep(.2)
os._exit(0)
'''
    subprocess.run([sys.executable, '-B', '-c', script, str(pid_file)], env=env, check=True, timeout=10)
    pid = int(pid_file.read_text())
    deadline = time.monotonic() + 3
    while psutil.pid_exists(pid) and time.monotonic() < deadline:
        time.sleep(.05)
    assert not psutil.pid_exists(pid)
