# Transit Replan Lab

Transit Replan Lab models how two riders can agree on a new meeting plan after a transit disruption in İzmir. It uses a frozen Metro M1 and Konak Tram timetable, with Alsancak Gar as the demo meeting point. A route proposal becomes verified only when both riders accept it and an independent verifier checks the trip legs and constraints.

The repository is in the foundation phase. The current build exposes the health endpoint and Vite shell. See the [phase checklist](docs/roadmap.md) for runnable milestones.

## Local development

Prerequisites are Python 3.12, uv, Node 24, Corepack 0.36 or later, and Git.

```sh
make setup
make check
make build
make hooks
```

Run `make dev-api` and `make dev-web` in separate terminals. Open the Vite URL and check the backend at `http://127.0.0.1:8000/healthz`.

## Design

- [Architecture](docs/architecture.md) and [decision records](docs/adr)
- [Timetable provenance and license](data/gtfs/SOURCES.md)
- [Milestone checklist](docs/roadmap.md)

Schedule data is attributed to İzmir Metropolitan Municipality under CC BY 4.0. Simulated incidents are synthetic.
