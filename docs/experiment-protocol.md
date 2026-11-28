# Comparative evaluation protocol

## Question

Does explicit separation of rider preferences and mediation improve joint arrival outcomes under the same local model and timetable? This comparison evaluates the coordinator. It uses the same deterministic route engine, constraints, verifier, notice inputs, and 10-call and two-round maximum per incident. A model call can read only its role view. The single coordinator receives the information required to emit both rider decisions. The rules baseline interprets a transparent finite notice grammar and accepts the highest ranked valid pair.

## Frozen partitions

There are 24 development cases and 60 locked cases, balanced between Turkish and English within each partition. Six families cover interchanges, other platforms, cancellation, delay, ambiguity, and a tight window. The generator seeds and SHA-256 manifest are committed with this protocol. The 12 premarked locked cases from the interchange and platform strata receive a second five-role run with counteroffers disabled.

The locked partition is evaluated after the development decision. The runner verifies each checksum, serializes runs, and resumes from completed JSONL rows. Current runs record the Git revision, any development worktree diff digest, prompt version, inference mode, base and optional Operator model digests, seed, and timetable hashes. Use a fresh output directory when changing any condition. Run the locked evaluation from a clean checkout. Replay is a development smoke mode.

The output directory admits one writer per split. Completed rows end in a newline and are flushed to disk. Resume truncates a torn final record, retains completed pairs, and starts a fresh run for each missing pair so its wall-clock measurement reflects actual execution.

## Metrics and decision rule

The primary denominator is cases where a joint plan exists after applying the reference incident. A success requires an exact incident match and a verified offer that also passes the independent verifier against the reference overlay. Expected clarification and completed infeasibility contribute to the separate outcome accuracy. A verified route that fails the reference verifier counts as a hard violation. Recovery delay compares the verified and initial meeting times. Optimality gap compares the verified meeting with the earliest valid reference pair. Report raw counts, mean tokens and calls, p95 elapsed time, and paired 2,000-resample percentile bootstrap intervals for success differences versus rules.

The five-role variant can become the default only if it improves development success by at least five percentage points, produces zero hard violations, and stays within five seconds of baseline p95. Otherwise keep rules as the default. Record the decision before the locked run. The exhaustive small-network routing oracle lives in the property tests. The real-network feasibility labels use the pinned deterministic search with the gold overlay and are subject to its documented scope.

## Related experiments

MultiAgentBench compares communication and collaboration protocols across tasks. Sentinel studies decentralized cooperative meeting and navigation under dynamic spatial constraints. This study tests a smaller timetable problem and makes hard constraint verification and incident accuracy explicit. [MultiAgentBench](https://aclanthology.org/2025.acl-long.421/) · [Sentinel](https://arxiv.org/abs/2605.26239).
