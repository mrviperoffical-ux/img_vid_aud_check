# app/services/nudity.py
from nudenet import NudeDetector

_detector = None

def _get_detector():
    global _detector
    if _detector is None:
        from nudenet import NudeDetector
        _detector = NudeDetector()
    return _detector


# ─────────────────────────────────────────────────────────────────────────────
# STRICTLY NSFW: only truly explicit exposure counts as nudity.
# Bikinis, gym wear, sports bras, male bare torso/ornaments etc. are handled
# by covered-counterpart & windowed suppression logic below.
# ─────────────────────────────────────────────────────────────────────────────
NUDE_LABELS = {
    "FEMALE_GENITALIA_EXPOSED",
    "MALE_GENITALIA_EXPOSED",
    "ANUS_EXPOSED",
    "FEMALE_BREAST_EXPOSED",   # bare breasts — bikini/sports bra/male torso suppressed via COVERED logic
    "BUTTOCKS_EXPOSED",        # fully bare buttocks — swimwear suppressed via COVERED logic
}

# If a "covered" or context counterpart is detected with sufficient confidence,
# we treat it as a false-positive (e.g. bikini, sports bra, gym shorts, male torso ornaments).
COVERED_COUNTERPARTS = {
    "FEMALE_GENITALIA_EXPOSED": ["FEMALE_GENITALIA_COVERED", "BUTTOCKS_COVERED", "BELLY_EXPOSED"],
    "MALE_GENITALIA_EXPOSED":   ["MALE_GENITALIA_COVERED"],
    "ANUS_EXPOSED":             ["ANUS_COVERED", "BUTTOCKS_COVERED"],
    "BUTTOCKS_EXPOSED":         ["BUTTOCKS_COVERED", "FEMALE_GENITALIA_COVERED", "BELLY_EXPOSED"],
    "FEMALE_BREAST_EXPOSED":    ["FEMALE_BREAST_COVERED", "BELLY_EXPOSED", "ARMPITS_EXPOSED", "MALE_BREAST_EXPOSED"],
}

# Detection confidence threshold.
# 0.52 perfectly calibrates NudeNet across high-FPS (10+ FPS) and low-FPS extractions.
DEFAULT_THRESHOLD = 0.52

# Threshold above which a covered counterpart suppresses an exposed flag.
COVERED_SUPPRESSION_THRESHOLD = 0.25

# Minimum number of video frames that must be flagged as nude before the
# entire video is marked NSFW (default = 3).
NUDE_FRAME_THRESHOLD = 3


def _is_suppressed_by_covered(label: str, results: list, covered_threshold: float = COVERED_SUPPRESSION_THRESHOLD) -> bool:
    """Return True if a covered counterpart is detected in the frame results with enough confidence."""
    covered_labels = COVERED_COUNTERPARTS.get(label, [])
    if not covered_labels:
        return False
    for r in results:
        if r.get("class") in covered_labels and r.get("score", 0) >= covered_threshold:
            return True
    return False


def _has_nudity(results: list, threshold: float = DEFAULT_THRESHOLD) -> bool:
    """
    Core logic for single frame/image: returns True only when a genuinely explicit label is detected
    above the threshold AND is NOT suppressed by a covered-counterpart detection.
    """
    for r in results:
        label = r.get("class")
        score = r.get("score", 0)
        if label in NUDE_LABELS and score >= threshold:
            if not _is_suppressed_by_covered(label, results, COVERED_SUPPRESSION_THRESHOLD):
                return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# 🎥 VIDEO (frames)
# ─────────────────────────────────────────────────────────────────────────────
def check_nudity(frames, threshold=DEFAULT_THRESHOLD, nude_frame_threshold=NUDE_FRAME_THRESHOLD):
    """
    Scan extracted video frames for nudity with temporal windowed suppression (±4 window).

    A video is marked NSFW when at least `effective_threshold` frames
    are independently detected as nude and not suppressed by clothing/ornaments
    detected in the frame or adjacent frames.

    `effective_threshold` automatically adapts for short videos (e.g. if total
    extracted frames < nude_frame_threshold) while maintaining the 3-frame
    noise filter for standard videos.
    """
    if not frames:
        return False, None

    # Dynamically adapt threshold for short videos/clips
    effective_threshold = max(1, min(nude_frame_threshold, len(frames)))

    # Step 1: Detect labels for all frames
    detector = _get_detector()
    all_results = [detector.detect(frame) for frame in frames]

    # Step 2: Evaluate frames with temporal window (±4 frames) suppression
    nude_frames = []

    for idx, results in enumerate(all_results):
        is_nude_frame = False
        for r in results:
            label = r.get("class")
            score = r.get("score", 0)
            if label in NUDE_LABELS and score >= threshold:
                covered_labels = COVERED_COUNTERPARTS.get(label, [])
                
                # Check current frame & adjacent frames (±4 window) for covered indicators
                start_idx = max(0, idx - 4)
                end_idx = min(len(all_results), idx + 5)
                suppressed = False
                
                for adj_idx in range(start_idx, end_idx):
                    for cr in all_results[adj_idx]:
                        if cr.get("class") in covered_labels and cr.get("score", 0) >= COVERED_SUPPRESSION_THRESHOLD:
                            suppressed = True
                            break
                    if suppressed:
                        break
                
                if not suppressed:
                    is_nude_frame = True
                    break

        if is_nude_frame:
            nude_frames.append(frames[idx])
            if len(nude_frames) >= effective_threshold:
                return True, nude_frames[0]

    return False, None


# ─────────────────────────────────────────────────────────────────────────────
# 🖼 IMAGE (single file)
# ─────────────────────────────────────────────────────────────────────────────
def check_image_nudity(image_path, threshold=DEFAULT_THRESHOLD):
    """
    Check a single image for nudity.
    Returns (True, image_path) or (False, None).
    """
    results = _get_detector().detect(image_path)
    if _has_nudity(results, threshold):
        return True, image_path

    return False, None