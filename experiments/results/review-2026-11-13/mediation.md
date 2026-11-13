# vNext mediation evaluation

Model digest `c2b626cf44dd0760ec533ab4c95adb4876c26e7b9ee3d90c0e59990aa1317341`.
Source digest `633bab184ba1be1daff573aa3e7d577b9c50042dbf423dbce15d623f6b8afebc`.

Preference pairs and raw regret appear in JSONL. Raw units follow each preference.
Rank regret counts distinct cost levels above each rider’s best displayed option.

| Arm | Agreement | Mean worst rider rank regret | Calls | p95 (s) | Hard violations |
| --- | ---: | ---: | ---: | ---: | ---: |
| rules | 8/8 | 1.00 | 0 | 0.57 | 0 |
| single | 7/8 | 1.00 | 8 | 4.12 | 0 |
| five | 8/8 | 1.00 | 68 | 26.95 | 0 |
| five-no-counter | 1/8 | 1.00 | 47 | 17.29 | 0 |
