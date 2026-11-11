"""Fetch pinned municipal GTFS archives and refuse unexpected versions."""

from pathlib import Path
from tempfile import NamedTemporaryFile

import httpx
from trl.gtfs import DATA_ROOT, checked_archive, feed_specs


def main() -> None:
    root = DATA_ROOT / "gtfs"
    for feed in feed_specs(root):
        target = root / f"{feed.id}.zip"
        if target.exists():
            checked_archive(target, feed.sha256)
            print(f"{target.name}: verified")
            continue
        response = httpx.get(
            feed.url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=30,
            follow_redirects=True,
        )
        response.raise_for_status()
        with NamedTemporaryFile(dir=root, delete=False) as file:
            candidate = Path(file.name)
            file.write(response.content)
        try:
            checked_archive(candidate, feed.sha256)
            candidate.replace(target)
        finally:
            candidate.unlink(missing_ok=True)
        print(f"{target.name}: downloaded and verified")


if __name__ == "__main__":
    main()
