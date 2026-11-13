"""List every stop of a network profile without loading its trips."""

import csv
import io
from pathlib import Path
from zipfile import ZipFile

from trl.domain import Stop
from trl.gtfs import Profile, accessibility, checked_archive, feed_specs


def load_catalogue(root: Path, profile: Profile = "full") -> dict[str, Stop]:
    """Stops of every available archive in the profile, keyed `feed:stop_id`.

    An archive that is unavailable is skipped. `trl feeds` reports why.
    """
    stops: dict[str, Stop] = {}
    for feed in feed_specs(root):
        path = root / f"{feed.id}.zip"
        if profile not in feed.profiles or feed.sha256 is None or not path.exists():
            continue
        data = checked_archive(path, feed.sha256)
        with ZipFile(io.BytesIO(data)) as archive:
            stream = io.TextIOWrapper(archive.open("stops.txt"), encoding="utf-8-sig", newline="")
            for row in csv.DictReader(stream):
                key = f"{feed.id}:{row['stop_id']}"
                stops[key] = Stop(
                    id=key,
                    name=row["stop_name"].strip(),
                    longitude=float(row["stop_lon"]),
                    latitude=float(row["stop_lat"]),
                    accessible=accessibility(row.get("wheelchair_boarding")),
                )
    return stops
