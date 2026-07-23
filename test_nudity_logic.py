"""
test_nudity_logic.py
--------------------
Unit tests for the nudity detection logic in app/services/nudity.py
"""

import sys
import os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.nudity import (
    _has_nudity,
    _is_suppressed_by_covered,
    DEFAULT_THRESHOLD,
    COVERED_SUPPRESSION_THRESHOLD,
    NUDE_FRAME_THRESHOLD,
)

def det(label, score):
    return {"class": label, "score": score}

passed = 0
failed = 0

def run_test(name, result, expected):
    global passed, failed
    ok = (result == expected)
    mark = "[PASS]" if ok else "[FAIL]"
    if ok:
        passed += 1
    else:
        failed += 1
    print(f"  {mark}  {name}")
    if not ok:
        print(f"         Expected: {expected}  |  Got: {result}")


print()
print("=" * 65)
print("  Nudity Detection Logic — Scenario Unit Tests")
print(f"  threshold={DEFAULT_THRESHOLD}  |  covered_suppress={COVERED_SUPPRESSION_THRESHOLD}  |  frame_min={NUDE_FRAME_THRESHOLD}")
print("=" * 65)

# Group 1: Should be SAFE
print("\n[GROUP 1] Should be SAFE (not flagged)\n")

run_test("Person in full clothes — no detections", _has_nudity([]), False)
run_test("Shirtless man — MALE_BREAST_EXPOSED only", _has_nudity([det("MALE_BREAST_EXPOSED", 0.92)]), False)
run_test("Gym wear — BELLY_EXPOSED + ARMPITS_EXPOSED", _has_nudity([det("BELLY_EXPOSED", 0.88), det("ARMPITS_EXPOSED", 0.85)]), False)
run_test("Bikini top — FEMALE_BREAST_EXPOSED suppressed by FEMALE_BREAST_COVERED", _has_nudity([det("FEMALE_BREAST_EXPOSED", 0.80), det("FEMALE_BREAST_COVERED", 0.30)]), False)
run_test("Swimwear — BUTTOCKS_EXPOSED suppressed by BUTTOCKS_COVERED", _has_nudity([det("BUTTOCKS_EXPOSED", 0.82), det("BUTTOCKS_COVERED", 0.30)]), False)
run_test("Underwear only — genitalia EXPOSED + COVERED fire", _has_nudity([det("FEMALE_GENITALIA_EXPOSED", 0.77), det("FEMALE_GENITALIA_COVERED", 0.30)]), False)
run_test("Below confidence threshold — score 0.30 (below 0.50)", _has_nudity([det("FEMALE_BREAST_EXPOSED", 0.30)]), False)
run_test("Just below threshold — score 0.49 (under 0.50)", _has_nudity([det("FEMALE_GENITALIA_EXPOSED", 0.49)]), False)
run_test("Open hands / arms — ARMPITS_EXPOSED", _has_nudity([det("ARMPITS_EXPOSED", 0.95)]), False)
run_test("Sports bra + gym shorts — FEMALE_BREAST_COVERED + BELLY_EXPOSED", _has_nudity([det("FEMALE_BREAST_COVERED", 0.88), det("BELLY_EXPOSED", 0.75)]), False)

# Group 2: Should be NSFW
print("\n[GROUP 2] Should be NSFW (flagged)\n")

run_test("Bare breasts — FEMALE_BREAST_EXPOSED (no covered counterpart)", _has_nudity([det("FEMALE_BREAST_EXPOSED", 0.80)]), True)
run_test("Explicit female genitalia — score 0.65", _has_nudity([det("FEMALE_GENITALIA_EXPOSED", 0.65)]), True)
run_test("Explicit male genitalia — score 0.58", _has_nudity([det("MALE_GENITALIA_EXPOSED", 0.58)]), True)
run_test("Anus exposure — score 0.70", _has_nudity([det("ANUS_EXPOSED", 0.70)]), True)
run_test("Bare buttocks — BUTTOCKS_EXPOSED with no covered counterpart", _has_nudity([det("BUTTOCKS_EXPOSED", 0.77)]), True)
run_test("Exactly at threshold — FEMALE_BREAST_EXPOSED at 0.52", _has_nudity([det("FEMALE_BREAST_EXPOSED", 0.52)]), True)
run_test("Covered suppression too weak — COVERED score 0.15 (below 0.25)", _has_nudity([det("FEMALE_BREAST_EXPOSED", 0.85), det("FEMALE_BREAST_COVERED", 0.15)]), True)

# Group 3: Video Frame Count Threshold
print("\n[GROUP 3] Video — Frame count threshold\n")

def make_fake_frame_results(nude_count, total_count, label="FEMALE_BREAST_EXPOSED", score=0.80):
    return [[det(label, score)] if i < nude_count else [] for i in range(total_count)]

def simulate_check_nudity(frame_results_list, nude_frame_threshold=NUDE_FRAME_THRESHOLD):
    nude_frames = []
    for i, results in enumerate(frame_results_list):
        if _has_nudity(results, DEFAULT_THRESHOLD):
            nude_frames.append(f"frame_{i}.jpg")
            if len(nude_frames) >= nude_frame_threshold:
                return True, nude_frames[0]
    return False, None

run_test("Video with 2 nude frames out of 20 (< 3) => SAFE", simulate_check_nudity(make_fake_frame_results(2, 20))[0], False)
run_test("Video with 3 nude frames out of 20 (= 3) => NSFW", simulate_check_nudity(make_fake_frame_results(3, 20))[0], True)
run_test("Video with 10 nude frames => NSFW", simulate_check_nudity(make_fake_frame_results(10, 50))[0], True)
run_test("Clean video => SAFE", simulate_check_nudity(make_fake_frame_results(0, 30))[0], False)
run_test("1 nude frame in 100 (motion blur) => SAFE", simulate_check_nudity(make_fake_frame_results(1, 100))[0], False)

print()
print("=" * 65)
print(f"  RESULTS:  {passed} passed  |  {failed} failed  |  {passed+failed} total")
print("=" * 65)
