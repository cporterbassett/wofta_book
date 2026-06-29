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
    assert '"' not in out and '!' not in out and '$' not in out
    assert '^f2' in out
    assert '{ag}' in out   # grace notes kept (needed for accidental analysis)


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


U8 = Fraction(1, 8)


def test_measure_duration_simple():
    # 8 eighth-notes in 4/4 == 1 whole note
    assert lint_abc.measure_duration("G2 A2 B2 c2", U8, False) == Fraction(1)
    assert lint_abc.measure_duration("d4 d4", U8, False) == Fraction(1)


def test_measure_duration_chord_counts_once():
    # [EA]2 [ce]2 [ce]2 [Ae][Be]  in L:1/16 -> (2+2+2+1+1)/16 = 8/16 = 1/2
    assert lint_abc.measure_duration("[EA]2[ce]2 [ce]2[Ae][Be]", Fraction(1, 16), False) == Fraction(1, 2)


def test_measure_duration_triplet():
    # (3abc in L:1/8 simple meter: 3 eighths in time of 2 -> 2/8 = 1/4
    assert lint_abc.measure_duration("(3abc", U8, False) == Fraction(1, 4)


def test_measure_duration_broken_rhythm_unchanged():
    # a>b == a3/2 + b1/2 ; same total as a b
    assert lint_abc.measure_duration("a>b", U8, False) == lint_abc.measure_duration("a b", U8, False)


def test_check_beats_flags_interior_only():
    # measure 2 (interior) is short -> 1 issue; pickup edges ignored
    body = "dB | A2 B2 | A2 B2 d3 A | A3"   # m1 short(edge ok), m2 short(FAIL), m3 full, m4 short(edge ok)
    issues = lint_abc.check_beats("", body, U8, Fraction(1), False)
    assert len(issues) == 1
    assert issues[0].measure == 2


def test_check_beats_too_long_pickup_flagged():
    body = "A2 B2 d3 A2 | A2 B2 d3 A"    # m1 edge but 9/8 > 8/8 -> FAIL
    issues = lint_abc.check_beats("", body, U8, Fraction(1), False)
    assert any(i.measure == 1 for i in issues)


def test_check_beats_internal_pickup_pair_not_flagged():
    # Blueberry Jig 6/8: interior 5/8 + 1/8 pair sums to a full bar (section-boundary pickup)
    body = "dAF DFA | dfb a2 f | dfe d2 | f/g/ | a2 d a2 d | a3 b2 a"
    assert lint_abc.check_beats("", body, U8, Fraction(3, 4), True) == []


def test_check_beats_lone_short_interior_still_flagged():
    # a short interior measure with no compensating neighbor IS flagged
    body = "a2 d a2 d | dfe d2 | a2 d a2 d"   # m2 = 5/8, neighbors full
    issues = lint_abc.check_beats("", body, U8, Fraction(3, 4), True)
    assert len(issues) == 1 and issues[0].measure == 2


def test_measure_duration_skips_volta_bracket_residue():
    # clean_body_line leaves a stray '[' from volta annotations; must not zero the bar
    assert lint_abc.measure_duration("[ A3 B A2 dB", U8, False) == Fraction(1)


def test_measure_duration_tuplet_compound_differs():
    # (5 uses q=2 in simple meter but q=3 in compound -> different totals
    assert lint_abc.measure_duration("(5ABcde", U8, False) == Fraction(1, 4)
    assert lint_abc.measure_duration("(5ABcde", U8, True) == Fraction(3, 8)


def test_key_accidentals():
    assert lint_abc.key_accidentals("G") == {"F": "#"}
    assert lint_abc.key_accidentals("D") == {"F": "#", "C": "#"}
    assert lint_abc.key_accidentals("F") == {"B": "b"}
    assert lint_abc.key_accidentals("Em") == {"F": "#"}        # E minor == 1 sharp
    assert lint_abc.key_accidentals("Ador") == {"F": "#"}  # A dorian == 1 sharp (notes of G major)
    assert lint_abc.key_accidentals("C") == {}


def test_accidental_redundant_vs_key():
    km = lint_abc.key_accidentals("G")
    issues = lint_abc.check_accidentals("", "G2 ^f2 e2", km)   # F already sharp in G
    assert len(issues) == 1 and "redundant" in issues[0].message.lower()


def test_accidental_natural_then_sharp_is_ok():
    km = lint_abc.key_accidentals("G")
    assert lint_abc.check_accidentals("", "=f2 ^f2", km) == []  # natural cancels, ^f restores


def test_accidental_out_of_key_not_flagged():
    km = lint_abc.key_accidentals("G")
    assert lint_abc.check_accidentals("", "^g2 a2", km) == []   # G# not in key -> legit


def test_accidental_repeated_in_measure():
    km = lint_abc.key_accidentals("C")
    issues = lint_abc.check_accidentals("", "^c2 ^c2", km)      # 2nd ^c redundant
    assert len(issues) == 1


def test_accidental_resets_each_measure():
    km = lint_abc.key_accidentals("C")
    # ^c in m1, ^c in m2 -> each is the first in its measure, neither repeated
    assert lint_abc.check_accidentals("", "^c2 d2 | ^c2 d2", km) == []


def test_measure_duration_skips_grace_notes():
    # grace {ag} carries no metric duration; the measure is still one bar
    assert lint_abc.measure_duration("{ag}d2 e2 f2 g2", U8, False) == Fraction(1)


def test_accidental_grace_cancel_then_restore_ok():
    # {=f} cancels the key sharp, then ^f restores it -> not redundant
    km = lint_abc.key_accidentals("D")   # F# in key
    assert lint_abc.check_accidentals("", "a {=f}^f3 d2", km) == []


def test_repeats_balanced_ok():
    assert lint_abc.check_repeats("", "|: a b :| |: c d :|") == []


def test_repeats_leading_close_ok():
    # ":|" with no "|:" repeats from the start -> valid (implicit credit)
    assert lint_abc.check_repeats("", "a b :| c d") == []


def test_repeats_unclosed_open_fails():
    issues = lint_abc.check_repeats("", "|: a b | c d")
    assert len(issues) == 1 and "unclosed" in issues[0].message.lower()


def test_repeats_two_section_repeats_ok():
    # two :| closes with no |: opens -> valid section repeats (Arkansas Traveler)
    assert lint_abc.check_repeats("", "AB :| CD :|") == []


def test_repeats_double_colon_shorthand_ok():
    assert lint_abc.check_repeats("", "|: a b :: c d :|") == []


def test_repeats_duplicated_open_still_flagged():
    # Bill Cheatham: :| |: |: ... :|  leaves one |: unclosed
    assert len(lint_abc.check_repeats("", "a :| b |: c |: d | e :| f")) == 1


def _write(tmp_path, text):
    p = tmp_path / "T.abc"
    p.write_text(text)
    return str(p)


def test_lint_file_clean(tmp_path):
    path = _write(tmp_path, SINGLE)
    assert lint_abc.lint_file(path) == []


def test_lint_file_alt_block_inherits_meter(tmp_path):
    # 2nd block has M:none but inherits 4/4; its full bar passes, no missing-meter error
    path = _write(tmp_path, MULTI_X)
    issues = lint_abc.lint_file(path)
    assert [i for i in issues if i.check == 'meter'] == []


def test_lint_file_catches_bad_beats(tmp_path):
    bad = "X:1\nL:1/8\nM:4/4\nK:G\nG2 A2 B2 | d4 d3 | d4 d4 |\n"  # interior m2 short
    path = _write(tmp_path, bad)
    issues = lint_abc.lint_file(path)
    assert any(i.check == 'beats' for i in issues)


def test_smoke_all_verified_runs_without_crashing():
    paths = lint_abc.discover_all()
    assert paths, "expected verified ABC files in abc/"
    for p in paths:
        lint_abc.lint_file(p)   # must not raise


def test_parse_dur_trailing_slash():
    # ABC '3/' means 3/2 (trailing slash halves); real data: New Five Cent Piece.
    # Regression for a ValueError crash in compare_abc._parse_dur.
    assert lint_abc._parse_dur("3/") == Fraction(3, 2)
    assert lint_abc._parse_dur("/") == Fraction(1, 2)
