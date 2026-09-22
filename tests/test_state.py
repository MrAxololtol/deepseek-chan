"""Deterministic public-API tests: no clocks, sleeps, or Qt application."""
import pytest

from deepseek_chan.state import PetBrain, State


def test_thinking_threshold_and_heartbeat():
    brain = PetBrain(hard_thinking_after=10, sleep_after=100, stale_after=50)
    brain.handle("thinking", ts=1)
    brain.handle("thinking", ts=8)
    assert brain.status(10.999).state == State.THINKING
    assert brain.status(11).state == State.THINKING_HARD
    brain.handle("working", "pytest", ts=12)
    brain.handle("thinking", ts=13)
    assert brain.status(22).state == State.THINKING
    assert brain.status(23).state == State.THINKING_HARD


def test_finished_bubble_expiry():
    brain = PetBrain(finished_bubble_for=5)
    brain.handle("finished", ts=10)
    status = brain.status(15)
    assert status.state == State.FINISHED
    assert status.bubble == "Finished thinking"
    assert status.bubble_age == 5
    status = brain.status(15.001)
    assert status.state == State.LISTENING
    assert status.bubble == ""


@pytest.mark.parametrize("event,state,duration", [
    ("pat", State.PAT, 2), ("flick", State.SURPRISED, 3),
])
def test_transient_restores_work(event, state, duration):
    brain = PetBrain(pat_for=2, surprised_for=3)
    brain.handle("working", "pytest", ts=1)
    brain.handle(event, ts=2)
    assert brain.status(2 + duration - 0.001).state == state
    status = brain.status(2 + duration)
    assert status.state == State.WORKING
    assert status.detail == "pytest"


def test_idle_sleep_and_activity_deadline():
    brain = PetBrain(sleep_after=10)
    brain.handle("activity", ts=5)
    assert not brain.status(14.999).asleep
    status = brain.status(15)
    assert status.state == State.SLEEP
    assert status.asleep
    assert status.bubble == ""


def test_wake_resets_base_bubble_and_idle_timer():
    brain = PetBrain(sleep_after=10, surprised_for=1, hard_thinking_after=2)
    brain.handle("thinking", ts=1)
    assert brain.status(11).asleep
    brain.handle("wake", ts=12)
    status = brain.status(12)
    assert status.state == State.SURPRISED
    assert not status.asleep
    assert status.bubble == ""
    assert brain.status(13).state == State.LISTENING
    brain.handle("thinking", ts=14)
    assert brain.status(15).state == State.THINKING
    assert brain.status(16).state == State.THINKING_HARD


@pytest.mark.parametrize("event", ["thinking", "working"])
def test_stale_session_fallback_and_recovery(event):
    brain = PetBrain(stale_after=5, sleep_after=100)
    brain.handle(event, ts=10)
    assert brain.status(14.999).state.value == event
    status = brain.status(15)
    assert status.state == State.LISTENING
    assert status.bubble == ""
    brain.handle("working", "build", ts=16)
    assert brain.status(16).state == State.WORKING


def test_sleep_takes_priority_over_stale_fallback():
    brain = PetBrain(stale_after=5, sleep_after=5)
    brain.handle("working", ts=1)
    assert brain.status(6).state == State.SLEEP
