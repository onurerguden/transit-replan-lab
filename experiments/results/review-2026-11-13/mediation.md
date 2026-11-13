# vNext mediation evaluation

Model digest `c2b626cf44dd0760ec533ab4c95adb4876c26e7b9ee3d90c0e59990aa1317341`.
Source digest `9ba086bdcd46c493afe65a6613c417df0a0896bdfb9bc13d6f68fac7214afec0`.

Preference pairs and raw regret appear in JSONL. Raw units follow each preference.
Rank regret counts distinct cost levels above each rider’s best displayed option.

| Arm | Agreement | Mean worst rider rank regret | Calls | p95 (s) | Hard violations |
| --- | ---: | ---: | ---: | ---: | ---: |
| rules | 7/7 | 1.00 | 0 | 0.39 | 0 |
| single | 6/7 | 1.00 | 7 | 4.24 | 0 |
| five | 7/7 | 1.00 | 62 | 28.92 | 0 |
| five-no-counter | 0/7 | — | 41 | 8.08 | 0 |
