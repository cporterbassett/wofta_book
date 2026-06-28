import os
import sys
from fractions import Fraction

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # bin/
import lint_abc


SINGLE = """X:1
T:Test Tune
L:1/8
M:4/4
K:G
V:1 treble
V:1
 G2 A2 B2 c2 | d4 d4 |
"""

MULTI_X = """X:1
T:Main
L:1/8
M:4/4
K:A
A2 A2 A2 A2 |
X:2
T:
M:none
K:A
f2 fg a2 b2 |
"""


def test_parse_single_block_collapses_repeated_voice():
    blocks = lint_abc.parse_tune_blocks(SINGLE)
    assert len(blocks) == 1
    b = blocks[0]
    assert b.title == "Test Tune"
    assert b.unit == Fraction(1, 8)
    assert b.meter == "4/4"
    assert b.key == "G"
    assert b.voice_order == ["1"]              # V:1 treble + V:1 collapse to one
    assert "G2 A2 B2 c2" in b.voices["1"]


def test_parse_two_x_blocks():
    blocks = lint_abc.parse_tune_blocks(MULTI_X)
    assert len(blocks) == 2
    assert blocks[1].meter == "none"


def test_clean_body_line_strips_decorations_keeps_accidentals():
    line = '"D" (F2[Fd]2) ^f2 !trill!e2 {ag}d2 $'
    out = lint_abc.clean_body_line(line)
    assert '"' not in out and '!' not in out and '{' not in out and '$' not in out
    assert '^f2' in out


def test_meter_to_barlen():
    assert lint_abc.meter_to_barlen("4/4") == Fraction(1)
    assert lint_abc.meter_to_barlen("6/8") == Fraction(3, 4)
    assert lint_abc.meter_to_barlen("2/2") == Fraction(1)
    assert lint_abc.meter_to_barlen("C") == Fraction(1)
    assert lint_abc.meter_to_barlen("C|") == Fraction(1)
    assert lint_abc.meter_to_barlen("none") is None
    assert lint_abc.meter_to_barlen("") is None


def test_is_compound():
    assert lint_abc.is_compound("6/8") is True
    assert lint_abc.is_compound("9/8") is True
    assert lint_abc.is_compound("4/4") is False
    assert lint_abc.is_compound("3/4") is False     # 3 is not > 3
    assert lint_abc.is_compound("C") is False


def test_check_time_signature():
    b = lint_abc.TuneBlock(meter="")
    assert len(lint_abc.check_time_signature(b, None)) == 1
    # When a barlen was supplied (real or inherited), no missing-meter error:
    assert lint_abc.check_time_signature(b, Fraction(1)) == []
