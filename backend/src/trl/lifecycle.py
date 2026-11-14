"""Run statuses, the transitions between them, and failure classification.

Commands move a run into planning. Workers move a planning run to a settled status. Nothing
else changes a status, and `storage` rejects any write that this table does not list.
"""

from typing import Final, get_args

from trl.domain import Status

ALL: Final[frozenset[Status]] = frozenset(get_args(Status))
SETTLED: Final[frozenset[Status]] = frozenset(
    {
        "abstained",
        "verified",
        "no_agreement",
        "infeasible",
        "search_incomplete",
        "model_error",
        "system_error",
        "verification_failed",
    }
)

# Statuses a command may start from. A new report supersedes any status, including planning.
COMMAND_SOURCES: Final[dict[str, frozenset[Status]]] = {
    "disrupt": ALL,
    "retract": ALL,
    "clarify": frozenset({"clarification"}),
    "retry": frozenset({"model_error", "system_error", "search_incomplete"}),
}

# What a worker may write while a run is planning.
WORKER_TARGETS: Final[frozenset[Status]] = frozenset({"planning", "clarification", *SETTLED})

# Machine-readable failure codes and whether repeating the same command can succeed.
RETRYABLE_CODES: Final[frozenset[str]] = frozenset(
    {
        "model_unavailable",
        "model_timeout",
        "search_deadline",
        "upgrade_interrupted",
        "internal_error",
        "worker_error",
    }
)


class IllegalTransition(ValueError):
    """A write that the transition table does not allow."""


def check_worker_transition(old: Status, new: Status) -> None:
    if old != "planning":
        raise IllegalTransition(f"Workers only write planning runs, not {old}.")
    if new not in WORKER_TARGETS:
        raise IllegalTransition(f"A worker cannot move a run to {new}.")


def check_command(command: str, status: Status) -> None:
    if status not in COMMAND_SOURCES[command]:
        raise IllegalTransition(f"The {command} command is not allowed while {status}.")


def retryable(status: Status, error: str | None) -> bool:
    if status == "search_incomplete":
        return True
    return status in {"model_error", "system_error"} and (error or "") in RETRYABLE_CODES
