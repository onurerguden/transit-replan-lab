"""Generate walking links between stops. Every duration is an assumption.

A link exists between two stops when the straight distance times a detour factor, at walking
speed, plus a fixed buffer stays within `max_s`. Because the buffer is paid on every link,
walking through an intermediate stop is never faster than the direct link, so the table is
closed under the triangle inequality that range-based routing relies on. Documented
interchanges keep their published assumption and replace the generated duration.
"""

import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

EARTH_RADIUS_M = 6_371_000.0


@dataclass(frozen=True)
class FootpathParams:
    speed_mps: float = 1.2
    detour: float = 1.3
    buffer_s: int = 60
    max_s: int = 600
    version: str = "fp-v1"

    @property
    def max_distance_m(self) -> float:
        return (self.max_s - self.buffer_s) * self.speed_mps / self.detour

    def seconds(self, distance_m: float) -> int:
        return math.ceil(distance_m * self.detour / self.speed_mps) + self.buffer_s


@dataclass(frozen=True)
class Footpaths:
    """Compressed sparse rows: links of stop `i` are `[pointer[i], pointer[i + 1])`."""

    pointer: NDArray[np.int32]
    destination: NDArray[np.int32]
    seconds: NDArray[np.int32]
    params: FootpathParams

    def links(self, stop: int) -> list[tuple[int, int]]:
        low, high = int(self.pointer[stop]), int(self.pointer[stop + 1])
        return [(int(self.destination[k]), int(self.seconds[k])) for k in range(low, high)]

    @property
    def count(self) -> int:
        return int(self.destination.size)


def haversine(
    lon: float, lat: float, others_lon: NDArray[np.float64], others_lat: NDArray[np.float64]
) -> NDArray[np.float64]:
    phi, others = math.radians(lat), np.radians(others_lat)
    delta_phi = others - phi
    delta_lambda = np.radians(others_lon - lon)
    a = np.sin(delta_phi / 2) ** 2 + math.cos(phi) * np.cos(others) * np.sin(delta_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_M * np.arcsin(np.sqrt(a))


def generate(
    ids: Sequence[str],
    longitudes: Sequence[float],
    latitudes: Sequence[float],
    params: FootpathParams | None = None,
    documented: Mapping[tuple[str, str], int] | None = None,
) -> Footpaths:
    params = params or FootpathParams()
    lon = np.asarray(longitudes, dtype=np.float64)
    lat = np.asarray(latitudes, dtype=np.float64)
    size = len(ids)
    # Bucket by a grid at least as wide as the link range so neighbors sit in adjacent cells.
    step = params.max_distance_m
    mean_lat = float(np.mean(lat)) if size else 0.0
    metres_x = np.radians(lon) * EARTH_RADIUS_M * math.cos(math.radians(mean_lat))
    metres_y = np.radians(lat) * EARTH_RADIUS_M
    cells = np.stack([np.floor(metres_x / step), np.floor(metres_y / step)], axis=1).astype(
        np.int64
    )
    buckets: dict[tuple[int, int], list[int]] = defaultdict(list)
    for index, (cx, cy) in enumerate(cells):
        buckets[int(cx), int(cy)].append(index)
    rows: list[tuple[int, int, int]] = []
    for index in range(size):
        cx, cy = int(cells[index, 0]), int(cells[index, 1])
        near = [
            other
            for dx in (-1, 0, 1)
            for dy in (-1, 0, 1)
            for other in buckets.get((cx + dx, cy + dy), ())
            if other != index
        ]
        if not near:
            continue
        candidates = np.asarray(near, dtype=np.int64)
        distance = haversine(float(lon[index]), float(lat[index]), lon[candidates], lat[candidates])
        for other, metres in zip(candidates, distance, strict=True):
            if metres <= step:
                rows.append((index, int(other), params.seconds(float(metres))))
    position = {name: index for index, name in enumerate(ids)}
    overrides = {
        (position[a], position[b]): seconds
        for (a, b), seconds in (documented or {}).items()
        if a in position and b in position
    }
    merged = {(a, b): seconds for a, b, seconds in rows} | overrides
    ordered = sorted(merged.items())
    pointer = np.zeros(size + 1, dtype=np.int32)
    for (origin, _), _seconds in ordered:
        pointer[origin + 1] += 1
    np.cumsum(pointer, out=pointer)
    return Footpaths(
        pointer=pointer,
        destination=np.asarray([b for (_, b), _ in ordered], dtype=np.int32),
        seconds=np.asarray([seconds for _, seconds in ordered], dtype=np.int32),
        params=params,
    )


def from_transfers(ids: Sequence[str], transfers: Mapping[tuple[str, str], int]) -> Footpaths:
    """Footpaths made only of documented links, for the core network."""
    return generate(ids, [0.0] * len(ids), [0.0] * len(ids), FootpathParams(max_s=0), transfers)
