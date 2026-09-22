import pytest

from deepseek_chan.colors import palette_color
from deepseek_chan.config import Palette


def test_default_bubble_color_has_expected_alpha():
    color = palette_color(Palette().bubble_bg)
    assert color.isValid()
    assert color.getRgb()[:3] == (10, 16, 32)
    assert color.alpha() == 217


@pytest.mark.parametrize("value", ["#4D6BFE", "blue", "rgba( 77, 107, 254, 1 )"])
def test_valid_colors(value):
    assert palette_color(value).isValid()


def test_explicit_alpha_override():
    assert palette_color("rgba(1,2,3,0.5)", alpha=40).alpha() == 40


@pytest.mark.parametrize("value", ["not-a-color", "rgba(256,0,0,1)", "rgba(1,2,3,1.5)"])
def test_invalid_colors(value):
    with pytest.raises(ValueError, match="palette color"):
        palette_color(value)
