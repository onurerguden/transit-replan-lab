# ADR 0003 · Preserve attributed timetable snapshots

Date 2026-11-11 · Accepted

The İzmir Metropolitan Municipality open data portal lists both rail feeds and licenses its materials under CC BY 4.0 unless otherwise stated. Its license page permits copying and distribution with attribution. The listed resources do not display a different license.

Keep the checksum-verified archive snapshots with the project in the schedule phase, accompanied by their attribution and license. Operator endpoints can replace the file at an unchanged URL, so a fetch-only installation cannot guarantee a historical snapshot remains available. Keep the fetch and checksum checks for provenance and recovery. The source license applies to the data.

Sources [Official GTFS dataset](https://acikveri.bizizmir.com/en/dataset/toplu-ulasim-gtfs-verileri) · [Municipality license](https://acikveri.bizizmir.com/en/license) · [Pinned feed metadata](../../data/gtfs/SOURCES.md).
