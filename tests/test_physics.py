"""Scruff-grab spring physics."""

from deepseek_chan.anim import Spring
from deepseek_chan.config import Config


def test_spring_flings_past_centre_and_settles():
    spring = Spring(stiffness=90.0, damping=7.0)
    for _ in range(6):
        spring.update(0.08, -48.0)
    assert spring.x < 0
    history = [spring.update(0.08, 0.0) for _ in range(200)]
    assert max(history) > 0.0          # overshoots past centre
    assert abs(spring.x) < 0.5         # damped back to rest


def test_spring_is_frame_rate_independent():
    slow = Spring()
    fast = Spring()
    for _ in range(20):
        slow.update(0.08, 20.0)
    for _ in range(80):
        fast.update(0.02, 20.0)
    assert abs(slow.x - fast.x) < 1.0


def test_physics_defaults_present():
    cfg = Config()
    assert cfg.physics.enabled is True
    assert cfg.physics.max_swing_deg == 22.0
    assert cfg.physics.stiffness > 0 and cfg.physics.damping > 0
