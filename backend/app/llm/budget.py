"""Search and token budgets for a single validation run.

Gemini 3 bills per search query the model decides to execute, and one request
may trigger several. A prompt saying "use at most 6 searches" is a suggestion;
this is the enforcement. Exceeding the run budget raises, which ADK's retry
machinery surfaces as a node failure rather than a silent overspend.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field


class SearchBudgetExceeded(RuntimeError):
    """Raised when an agent or run exhausts its allotted searches."""


@dataclass
class RunBudget:
    """Thread-safe counters for one run.

    Research nodes execute concurrently under the workflow's max_concurrency,
    so the counters are mutated under a lock.
    """

    max_per_agent: int
    max_per_run: int

    _per_agent: dict[str, int] = field(default_factory=dict)
    _total_searches: int = 0
    _input_tokens: int = 0
    _output_tokens: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def charge_searches(self, agent: str, count: int) -> None:
        """Record searches already executed, raising if either cap is passed.

        Charged after the fact because the model decides how many queries to
        run; the cap therefore stops the *next* call, not the current one.
        """
        if count <= 0:
            return
        with self._lock:
            used = self._per_agent.get(agent, 0) + count
            self._per_agent[agent] = used
            self._total_searches += count
            total = self._total_searches

        if used > self.max_per_agent:
            raise SearchBudgetExceeded(
                f"Agent {agent!r} used {used} searches, over its cap of "
                f"{self.max_per_agent}."
            )
        if total > self.max_per_run:
            raise SearchBudgetExceeded(
                f"Run used {total} searches, over the run cap of {self.max_per_run}."
            )

    def check_before(self, agent: str) -> None:
        """Refuse to start another grounded call when a cap is already spent."""
        with self._lock:
            used = self._per_agent.get(agent, 0)
            total = self._total_searches
        if used >= self.max_per_agent:
            raise SearchBudgetExceeded(
                f"Agent {agent!r} has exhausted its {self.max_per_agent}-search budget."
            )
        if total >= self.max_per_run:
            raise SearchBudgetExceeded(
                f"Run has exhausted its {self.max_per_run}-search budget."
            )

    def charge_tokens(self, input_tokens: int, output_tokens: int) -> None:
        with self._lock:
            self._input_tokens += input_tokens
            self._output_tokens += output_tokens

    @property
    def searches_remaining(self) -> int:
        with self._lock:
            return max(0, self.max_per_run - self._total_searches)

    def snapshot(self) -> dict[str, int | dict[str, int]]:
        """Usage so far, for persisting onto the run row and showing in the UI."""
        with self._lock:
            return {
                "total_searches": self._total_searches,
                "input_tokens": self._input_tokens,
                "output_tokens": self._output_tokens,
                "per_agent_searches": dict(self._per_agent),
            }
