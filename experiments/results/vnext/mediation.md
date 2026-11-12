# vNext mediation evaluation

Model digest `d8b0f5e9760cd1682034f292d7ef72ec46f432149be0df7574bf2d6e92e38c04`.
Source digest `2dc308f905c2e14d7c0e541ad4ff16e5560d1985bdff5f8be56fb12b827bff37`.

Rider A prefers earlier arrival. Rider B prefers less waiting at the meeting stop.
Preference regret is measured in seconds above each rider’s best displayed option.

| Arm | Agreement | A mean regret (s) | B mean regret (s) | Calls | p95 (s) | Hard violations |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| rules | 6/6 | 0.0 | 252.5 | 0 | 0.46 | 0 |
| single | 6/6 | 225.0 | 27.5 | 6 | 4.35 | 0 |
| five | 6/6 | 225.0 | 225.0 | 53 | 16.09 | 0 |
| five-no-counter | 0/6 | — | — | 35 | 8.90 | 0 |
