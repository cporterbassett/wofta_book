#!/usr/bin/env python3
"""
Ensemble voter: given a gold standard ABC and multiple candidate ABCs,
produce a new ABC by picking the best measure at each position.

Strategy: for each measure position, take the candidate answer that
appears most often across all variants (plurality vote). Ties go to
the highest-scoring variant's answer.

Usage:
  python3 ensemble_abc.py gold.abc candidate1.abc candidate2.abc ...
  python3 ensemble_abc.py gold.abc preprocessing_tests/abc/*.abc
"""

import sys
import difflib
from collections import Counter
from compare_abc import extract_body, split_measures, compare, TARGET_UNIT, get_unit, normalize_durations
import re


def align_to_gold(gold_measures, test_measures):
    """
    Use SequenceMatcher to align test measures to gold positions.
    Returns a list len(gold_measures) where each entry is the best
    matching test measure (or None if deleted/missing).
    """
    sm = difflib.SequenceMatcher(None, gold_measures, test_measures, autojunk=False)
    aligned = [None] * len(gold_measures)
    for op, g1, g2, t1, t2 in sm.get_opcodes():
        if op == 'equal':
            for i, j in zip(range(g1, g2), range(t1, t2)):
                aligned[i] = test_measures[j]
        elif op == 'replace':
            for i, j in zip(range(g1, g2), range(t1, t2)):
                aligned[i] = test_measures[j]
        # delete: aligned stays None
        # insert: extra test measures ignored
    return aligned


def ensemble(gold_path, candidate_paths):
    gold_text = open(gold_path).read()
    gold_measures = split_measures(extract_body(gold_text))
    n = len(gold_measures)

    # Align each candidate to gold positions
    all_aligned = []
    scores = []
    for path in candidate_paths:
        text = open(path).read()
        test_measures = split_measures(extract_body(text))
        aligned = align_to_gold(gold_measures, test_measures)
        all_aligned.append(aligned)
        matched = sum(1 for g, a in zip(gold_measures, aligned) if a == g)
        scores.append(matched)

    # For each position, pick by plurality; ties broken by highest-scoring variant
    result_measures = []
    for i in range(n):
        votes = [(aligned[i], score)
                 for aligned, score in zip(all_aligned, scores)
                 if aligned[i] is not None]

        if not votes:
            result_measures.append(gold_measures[i] + '???')  # unknown
            continue

        counts = Counter(v for v, _ in votes)
        # Sort: most votes first, then highest-scoring variant's preference
        best = max(counts, key=lambda m: (counts[m],
                   max(s for v, s in votes if v == m)))
        result_measures.append(best)

    return gold_measures, result_measures, scores


def score_result(gold_measures, result_measures):
    matched = sum(1 for g, r in zip(gold_measures, result_measures) if g == r)
    total = len(gold_measures)
    return matched, total


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} gold.abc candidate1.abc [candidate2.abc ...]")
        sys.exit(1)

    gold_path = sys.argv[1]
    candidate_paths = sys.argv[2:]

    print(f"Candidates: {len(candidate_paths)}")
    gold_measures, result_measures, scores = ensemble(gold_path, candidate_paths)

    matched, total = score_result(gold_measures, result_measures)
    print(f"Ensemble score: {matched}/{total} ({matched/total:.0%})")
    print(f"Best individual: {max(scores)}/{total} ({max(scores)/total:.0%})")
    print()

    for g, r in zip(gold_measures, result_measures):
        if g == r:
            print(f"  OK  {g}")
        else:
            print(f"  -- {g}")
            print(f"  ++ {r}")
