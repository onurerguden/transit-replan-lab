# Timetable sources

Schedule archives are published by İzmir Metropolitan Municipality and its transit operators. The [official dataset](https://acikveri.bizizmir.com/en/dataset/toplu-ulasim-gtfs-verileri) and [municipal license page](https://acikveri.bizizmir.com/en/license) identify the data license as [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). These records describe archive bytes verified on 2026-11-11.

| Feed | Official archive | SHA-256 | Service-calendar bounds |
| --- | --- | --- | --- |
| İzmir Metro | [rail-metro-gtfs.zip](https://www.izmirmetro.com.tr/gtfs/rail-metro-gtfs.zip) | `c1a86738dac8de3749aff96f0ce92f432be6a4e9ce67769c2854a530f92ce5fd` | 2026-07-09 through 2027-07-09 |
| İzmir Tram | [rail-tramizmir-gtfs.zip](https://www.tramizmir.com/gtfs/rail-tramizmir-gtfs.zip) | `9af3877eb5d567ebe54a634f2f7188e66c8192fcbea96a89ca0496bf11a214fe` | 2026-07-16 through 2027-07-16 |

Attribution for reuse is **İzmir Metropolitan Municipality · Public Transportation GTFS Data · CC BY 4.0**. Transit Replan Lab will extract Metro M1 and Konak Tram and apply synthetic disruptions without modifying the archived data.

The demo service date is 2026-10-21 in Europe/Istanbul. Both feeds schedule weekday service that day. The archived feeds do not provide shapes or stop-level wheelchair fields. Map geometry uses stop sequences and straight segments. The two documented interchanges use an assumed eight-minute walk in each direction, with unknown accessibility.

Run `uv run --locked --project backend python scripts/fetch_gtfs.py` to verify the pinned archives or recover missing copies from upstream if those exact bytes remain available.

## Full-network archives (v2)

Checked 2026-11-13 against the [official dataset](https://acikveri.bizizmir.com/en/dataset/toplu-ulasim-gtfs-verileri). License: CC BY 4.0 per the portal license page. Health report: `health.json` (`trl feeds --write`).

| Feed | Archive | SHA-256 | Status for 2026-10-21 |
| --- | --- | --- | --- |
| ESHOT bus | `bus.zip` | `c3d9fa3818d375ee69b18a6ad4cfc84f1de34cfa141de6a2ce6537c102f679d0` | Calendar ends 2026-10-09. The weekly pattern is projected onto the service day (assumption). |
| İZBAN | `izban.zip` | `cb2424f4a61b7bfbee78d3ff764a1b6d8e752cc787b04cc724b1ce2b0b3682aa` | Calendar ends 2025-01-01 and the data is from 2023. The weekly pattern is projected (assumption). |
| İzdeniz ferry | none | none | The official URL returns an HTML page, not an archive. Skipped. |

Generated footpaths are assumptions: 1.2 m/s, detour 1.3, 60 s buffer, links up to 600 s. The two documented Metro–Tram interchanges keep 480 s.
