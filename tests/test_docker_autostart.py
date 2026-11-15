import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest


SCRIPT = Path(os.environ.get(
    "DOCKER_AUTOSTART_SCRIPT",
    Path(__file__).resolve().parents[1] / "scripts" / "docker-autostart.sh",
))


class DockerAutostartTests(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory(prefix="docker startup ")
        self.root = Path(self.workspace.name)
        self.home = self.root / "user home"
        self.home.mkdir()
        self.link = self.root / "docker.sock"
        self.target = self.home / ".docker" / "run" / "docker.sock"
        self.launched = self.root / "opened"
        self.commands = self.root / "commands"
        self.commands.mkdir()
        opener = self.commands / "open"
        opener.write_text(
            '#!/bin/sh\nprintf "%s\\n" "$@" >> "$OPEN_RECORD"\n'
            'exit "${OPEN_EXIT_CODE:-0}"\n',
            encoding="utf-8",
        )
        opener.chmod(0o755)
        self.environment = dict(
            os.environ,
            HOME=str(self.home),
            DOCKER_SOCKET_LINK=str(self.link),
            OPEN_RECORD=str(self.launched),
            PATH=str(self.commands) + os.pathsep + os.environ.get("PATH", ""),
        )
        self.process = None

    def tearDown(self):
        if self.process is not None:
            if self.process.poll() is None:
                self.process.terminate()
            try:
                self.process.communicate(timeout=4)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.communicate(timeout=4)
        self.workspace.cleanup()

    def start(self):
        self.process = subprocess.Popen(
            ["/bin/sh", str(SCRIPT)],
            env=self.environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

    def assert_waiting(self):
        time.sleep(0.25)
        self.assertFalse(self.launched.exists(), "Docker opened before the link was ready")
        self.assertIsNone(self.process.poll(), "The startup task must keep waiting")

    def assert_opened_once(self):
        output, _ = self.process.communicate(timeout=6)
        self.assertEqual(self.process.returncode, 0, output)
        self.assertEqual(
            self.launched.read_text(encoding="utf-8").splitlines(),
            ["-g", "-a", "Docker"],
        )

    def test_correct_dangling_link_starts_docker(self):
        self.link.symlink_to(self.target)
        self.assertFalse(self.target.exists())
        self.start()
        self.assert_opened_once()

    def test_missing_link_waits_then_starts_when_link_appears(self):
        self.start()
        self.assert_waiting()
        self.link.symlink_to(self.target)
        self.assert_opened_once()

    def test_wrong_target_waits_until_corrected(self):
        wrong_target = self.root / "another.sock"
        self.link.symlink_to(wrong_target)
        self.start()
        self.assert_waiting()
        self.assertEqual(self.link.readlink(), wrong_target)
        self.link.unlink()
        self.link.symlink_to(self.target)
        self.assert_opened_once()

    def test_regular_file_keeps_docker_waiting(self):
        self.link.write_text("not a socket link", encoding="utf-8")
        self.start()
        self.assert_waiting()
        self.assertEqual(self.link.read_text(encoding="utf-8"), "not a socket link")

    def test_opener_failure_reaches_launchd(self):
        self.link.symlink_to(self.target)
        self.environment["OPEN_EXIT_CODE"] = "7"
        self.start()
        output, _ = self.process.communicate(timeout=6)
        self.assertEqual(self.process.returncode, 7, output)
        self.assertTrue(self.launched.exists())


if __name__ == "__main__":
    unittest.main()
