"""Pure, display-free state machine for Mochi.

Everything in this module is plain Python (no Qt), so it is easy to reason
about and to unit test.  The renderer asks :class:`PetBrain` for a
:class:`Status` on every frame; the IPC layer feeds it events coming from the
opencode plugin.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class State(str, Enum):
    LISTENING = "listening"
    THINKING = "thinking"
    THINKING_HARD = "thinking_hard"
    WORKING = "working"
    FINISHED = "finished"
    ERROR = "error"
    PAT = "pat"
    SURPRISED = "surprised"
    SLEEP = "sleep"


#: Event kinds the opencode plugin (or the CLI) can emit.
EVENT_KINDS = frozenset(
    {
        "thinking",
        "working",
        "tool_result",
        "finished",
        "error",
        "activity",
        "pat",
        "flick",
        "wake",
        "sleep",
        "summon",
        "outfit",
        "skin",
        "ask",
        "theme",
    }
)


@dataclass
class Status:
    state: State
    detail: str = ""
    bubble: str = ""
    bubble_age: float = 0.0
    state_age: float = 0.0
    asleep: bool = False


class PetBrain:
    """Turns a stream of opencode events into a visual :class:`Status`."""

    def __init__(
        self,
        *,
        sleep_after: float = 120.0,
        hard_thinking_after: float = 600.0,
        finished_bubble_for: float = 5.0,
        stale_after: float = 300.0,
        pat_for: float = 1.4,
        surprised_for: float = 0.9,
    ) -> None:
        self.sleep_after = sleep_after
        self.hard_thinking_after = hard_thinking_after
        self.finished_bubble_for = finished_bubble_for
        self.stale_after = stale_after
        self.pat_for = pat_for
        self.surprised_for = surprised_for

        self.now: float = 0.0
        self.last_event_at: float = 0.0
        self._base: State = State.LISTENING
        self._base_since: float = 0.0
        self._thinking_since: Optional[float] = None
        self._sleeping: bool = False
        self._transient: Optional[State] = None
        self._transient_since: float = 0.0
        self._transient_for: float = 0.0
        self._detail: str = ""
        self._bubble: str = ""
        self._bubble_since: float = 0.0

    # ------------------------------------------------------------------ events
    def handle(self, kind: str, detail: str = "", ts: Optional[float] = None) -> None:
        if kind not in EVENT_KINDS:
            return
        if ts is None:
            ts = self.now
        self.now = ts
        self.last_event_at = ts

        if kind not in ("wake", "summon"):
            self._sleeping = False

        if kind == "thinking":
            if self._base != State.THINKING:
                self._base = State.THINKING
                self._base_since = ts
                self._thinking_since = ts
            self._detail = ""
            self._set_bubble("\u2026", ts)
        elif kind == "working":
            self._base = State.WORKING
            self._base_since = ts
            self._thinking_since = None
            self._detail = detail
            self._set_bubble(detail, ts)
        elif kind == "tool_result":
            # phase 2: proud / coffee / panic reactions hook in here
            self._detail = detail
        elif kind == "finished":
            self._base = State.FINISHED
            self._base_since = ts
            self._thinking_since = None
            self._detail = ""
            self._set_bubble("Finished thinking", ts)
        elif kind == "error":
            self._base = State.ERROR
            self._base_since = ts
            self._thinking_since = None
            self._set_bubble("!", ts)
        elif kind == "pat":
            self._trigger(State.PAT, self.pat_for, ts)
        elif kind in ("flick", "summon"):
            self._trigger(State.SURPRISED, self.surprised_for, ts)
            self._sleeping = False
        elif kind == "wake":
            self._sleeping = False
            self._base = State.LISTENING
            self._base_since = ts
            self._set_bubble("", ts)
            self._trigger(State.SURPRISED, self.surprised_for, ts)
        elif kind == "sleep":
            self._sleeping = True
        # "activity" only refreshes last_event_at

    def _trigger(self, state: State, duration: float, ts: float) -> None:
        self._transient = state
        self._transient_since = ts
        self._transient_for = duration

    def set_bubble(self, text: str, ts: Optional[float] = None) -> None:
        self._set_bubble(text, self.now if ts is None else ts)

    def _set_bubble(self, text: str, ts: float) -> None:
        self._bubble = text
        self._bubble_since = ts

    # ------------------------------------------------------------------ status
    def status(self, now: Optional[float] = None) -> Status:
        if now is not None:
            self.now = now
        now = self.now

        if self._transient is not None:
            age = now - self._transient_since
            if age < self._transient_for:
                return self._mk(self._transient, now)
            self._transient = None

        idle_for = now - self.last_event_at
        if self._sleeping or idle_for >= self.sleep_after:
            self._sleeping = idle_for >= self.sleep_after or self._sleeping
            return self._mk(State.SLEEP, now)

        if self._base == State.FINISHED:
            if now - self._base_since <= self.finished_bubble_for:
                return self._mk(State.FINISHED, now)
            return self._mk(State.LISTENING, now)

        # A dead session should not pin us in "thinking" forever.
        if self._base in (State.THINKING, State.WORKING) and idle_for >= self.stale_after:
            return self._mk(State.LISTENING, now)

        if self._base == State.THINKING and self._thinking_since is not None:
            if now - self._thinking_since >= self.hard_thinking_after:
                return self._mk(State.THINKING_HARD, now)

        return self._mk(self._base, now)

    def _mk(self, state: State, now: float) -> Status:
        bubble = ""
        bubble_age = 0.0
        if self._bubble and state not in (State.LISTENING, State.SLEEP):
            bubble = self._bubble
            bubble_age = now - self._bubble_since
        return Status(
            state=state,
            detail=self._detail,
            bubble=bubble,
            bubble_age=bubble_age,
            state_age=now - self._base_since,
            asleep=state == State.SLEEP,
        )
