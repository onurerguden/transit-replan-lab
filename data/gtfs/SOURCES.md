# Timetable sources

Schedule archives are published by İzmir Metropolitan Municipality and its transit operators. The [official dataset](https://acikveri.bizizmir.com/en/dataset/toplu-ulasim-gtfs-verileri) and [municipal license page](https://acikveri.bizizmir.com/en/license) identify the data license as [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). These records describe archive bytes verified on 2026-11-11.

| Feed | Official archive | SHA-256 | Service-calendar bounds |
| --- | --- | --- | --- |
| İzmir Metro | [rail-metro-gtfs.zip](https://www.izmirmetro.com.tr/gtfs/rail-metro-gtfs.zip) | `c1a86738dac8de3749aff96f0ce92f432be6a4e9ce67769c2854a530f92ce5fd` | 2026-07-09 through 2027-07-09 |
| İzmir Tram | [rail-tramizmir-gtfs.zip](https://www.tramizmir.com/gtfs/rail-tramizmir-gtfs.zip) | `9af3877eb5d567ebe54a634f2f7188e66c8192fcbea96a89ca0496bf11a214fe` | 2026-07-16 through 2027-07-16 |

Attribution for reuse is **İzmir Metropolitan Municipality · Public Transportation GTFS Data · CC BY 4.0**. Transit Replan Lab will extract Metro M1 and Konak Tram and apply synthetic disruptions without modifying the archived data.

The demo service date is 2026-10-21 in Europe/Istanbul. Both feeds schedule weekday service that day. The archived feeds do not provide shapes or stop-level wheelchair fields. Map geometry uses stop sequences and straight segments. The two documented interchanges use an assumed eight-minute walk in each direction, with unknown accessibility.

Run `uv run --locked --project backend python scripts/fetch_gtfs.py` to verify the pinned archives or recover missing copies from upstream if those exact bytes remain available.
