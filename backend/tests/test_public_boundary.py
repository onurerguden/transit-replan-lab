import subprocess
import sys
from pathlib import Path
from uuid import uuid4

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/check_public_boundary.py"


def test_public_boundary_checks_staged_snapshots_messages_and_history(tmp_path: Path) -> None:
    def git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    def boundary(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=tmp_path,
            check=False,
            capture_output=True,
            text=True,
        )

    git("init", "-q")
    git("config", "user.name", "Test Fixture")
    git("config", "user.email", "test@example.invalid")
    git("config", "commit.gpgsign", "false")
    token = uuid4().hex
    (tmp_path / ".gitignore").write_text(".private-denylist\n")
    assert boundary("--staged", "--require-denylist").returncode == 2
    (tmp_path / ".private-denylist").write_text(token)
    content = tmp_path / "test.txt"
    content.write_text(token.upper())
    git("add", ".gitignore", "test.txt")
    content.write_text("Timetable fixture")
    assert boundary("--require-denylist").returncode == 0
    result = boundary("--staged", "--require-denylist")
    assert result.returncode == 1
    assert token not in result.stderr

    message = tmp_path / ".git/message"
    message.write_text(token)
    assert boundary("--message-file", str(message)).returncode == 1
    git("commit", "-qm", token)
    git("add", "test.txt")
    git("commit", "-qm", "Replace fixture")
    assert boundary("--staged").returncode == 0
    result = boundary("--staged", "--history")
    assert result.returncode == 1
    assert "Git blob" in result.stderr
    assert "commit message" in result.stderr
