"""Scan publication candidates against a locally maintained denylist."""

import argparse
import os
import subprocess
import sys
import unicodedata
from collections.abc import Iterable, Iterator
from pathlib import Path

DENYLIST = ".private-denylist"


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args])


def normalized(text: str) -> str:
    return unicodedata.normalize("NFKC", text).casefold()


def entries(data: bytes) -> Iterator[bytes]:
    return (item for item in data.split(b"\0") if item)


def index_blobs() -> Iterator[tuple[bytes, bytes]]:
    for entry in entries(git("ls-files", "--stage", "-z")):
        metadata, path = entry.split(b"\t", 1)
        mode, blob, stage = metadata.split()
        if mode != b"160000" and stage == b"0":
            yield path, blob


def history_blobs() -> Iterator[tuple[bytes, bytes]]:
    for commit in git("rev-list", "--all").splitlines():
        for entry in entries(git("ls-tree", "-rz", commit.decode("ascii"))):
            metadata, path = entry.split(b"\t", 1)
            _, kind, blob = metadata.split()
            if kind == b"blob":
                yield path, blob


def contains(data: bytes, terms: tuple[str, ...]) -> bool:
    text = normalized(data.decode("utf-8", errors="ignore"))
    return any(term in text for term in terms)


def flagged_blobs(
    files: Iterable[tuple[bytes, bytes]], terms: tuple[str, ...]
) -> Iterator[str]:
    seen: set[bytes] = set()
    for path, blob in files:
        if contains(path, terms) or os.fsdecode(path) == DENYLIST:
            yield "protected term or file in a Git path"
        if blob in seen:
            continue
        seen.add(blob)
        if contains(git("cat-file", "blob", blob.decode("ascii")), terms):
            yield f"protected text in Git blob {blob.decode('ascii')[:12]}"


def flagged_worktree(terms: tuple[str, ...]) -> Iterator[str]:
    paths = set(
        entries(git("ls-files", "--cached", "--others", "--exclude-standard", "-z"))
    )
    for path in sorted(paths):
        relative = os.fsdecode(path)
        candidate = Path(relative)
        if contains(path, terms) or relative == DENYLIST:
            yield "protected term or file in a working tree path"
            continue
        if candidate.is_symlink():
            content = os.fsencode(os.readlink(candidate))
        elif candidate.is_file():
            content = candidate.read_bytes()
        else:
            continue
        if contains(content, terms):
            yield f"protected text in {relative}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staged", action="store_true", help="scan the Git index")
    parser.add_argument(
        "--history", action="store_true", help="scan all reachable Git history"
    )
    parser.add_argument(
        "--message-file", type=Path, help="scan a proposed commit message"
    )
    parser.add_argument("--require-denylist", action="store_true")
    options = parser.parse_args()
    message = options.message_file.resolve() if options.message_file else None
    os.chdir(os.fsdecode(git("rev-parse", "--show-toplevel").rstrip(b"\n")))
    local = Path(DENYLIST)
    terms = (
        tuple(
            normalized(line)
            for raw in local.read_text(encoding="utf-8").splitlines()
            if (line := raw.strip()) and not line.startswith("#")
        )
        if local.is_file()
        else ()
    )
    if options.require_denylist and not terms:
        print(
            "A non-empty ignored .private-denylist is required for this check.",
            file=sys.stderr,
        )
        return 2

    findings: list[str] = []
    if message is not None:
        if contains(message.read_bytes(), terms):
            findings.append("protected text in proposed commit message")
    elif options.staged:
        findings.extend(flagged_blobs(index_blobs(), terms))
    else:
        findings.extend(flagged_worktree(terms))
    if options.history:
        findings.extend(flagged_blobs(history_blobs(), terms))
        for commit in git("rev-list", "--all").splitlines():
            revision = commit.decode("ascii")
            if contains(git("show", "-s", "--format=%B", revision), terms):
                findings.append(f"protected text in commit message {revision[:12]}")

    if findings:
        print("\n".join(dict.fromkeys(findings)), file=sys.stderr)
        return 1
    print("Public boundary check passed." if terms else "No local denylist configured.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
