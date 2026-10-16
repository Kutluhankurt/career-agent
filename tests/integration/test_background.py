"""Real start/stop of the detached background process on this OS."""

import os
import subprocess
import sys


def career(home, *args):
    env = {**os.environ, "CAREER_AGENT_HOME": str(home.home)}
    return subprocess.run([sys.executable, "-m", "career", *args], capture_output=True, text=True, env=env, timeout=30,
                          stdin=subprocess.DEVNULL)


def test_start_status_stop(home):
    try:
        started = career(home, "start")
        assert started.returncode == 0, started.stdout + started.stderr
        assert "started" in started.stdout
        assert home.config.exists()

        again = career(home, "start")
        assert "already running" in again.stdout

        status = career(home, "status")
        assert "RUNNING" in status.stdout
    finally:
        stopped = career(home, "stop")
    assert "stopped" in stopped.stdout
    assert "stopped" in career(home, "status").stdout
    assert not home.pid_file.exists()
