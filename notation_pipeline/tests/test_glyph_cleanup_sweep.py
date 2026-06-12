import sys, os
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from glyph_cleanup_sweep import apply_dilation, score_abc_accuracy


def _thin_line_image():
    """3-pixel-wide vertical dark line on white background, 30×30."""
    img = np.full((30, 30, 3), 255, dtype=np.uint8)
    img[:, 13:16, :] = 0  # 3-px dark column
    return img


def test_apply_dilation_increases_dark_pixels():
    img = _thin_line_image()
    dark_before = np.sum(img == 0)
    result = apply_dilation(img, kernel_size=3)
    dark_after = np.sum(result == 0)
    assert dark_after > dark_before, "dilation should add dark pixels"


def test_apply_dilation_kernel2_smaller_than_kernel4():
    img = _thin_line_image()
    r2 = apply_dilation(img, kernel_size=2)
    r4 = apply_dilation(img, kernel_size=4)
    assert np.sum(r4 == 0) > np.sum(r2 == 0), "larger kernel → more dark pixels"


def test_apply_dilation_returns_same_shape():
    img = _thin_line_image()
    result = apply_dilation(img, kernel_size=3)
    assert result.shape == img.shape


GOLD_DIR = os.path.join(os.path.dirname(__file__), "..", "abc")


def test_score_abc_accuracy_self_match():
    gold = os.path.join(GOLD_DIR, "Arkansas Traveler-gold.abc")
    matched, total = score_abc_accuracy(gold, gold)
    assert matched == total
    assert total == 18


def test_score_abc_accuracy_self_match_soldiers_joy():
    gold = os.path.join(GOLD_DIR, "Soldier's Joy-gold.abc")
    matched, total = score_abc_accuracy(gold, gold)
    assert matched == total
    assert total == 18
