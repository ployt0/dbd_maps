import sys
import difflib
from pathlib import Path
from PIL import Image

from dbd_maps.map_overlay import (
    Config, DBDOverlayApp, get_map_box, get_realm_box,
    MAP_FONT_THRESHOLD, REALM_FONT_THRESHOLD
)

## This varies with test count, it is a sum of correct confidences.
REQUIRED_SCORE = 7.5
REQUIRED_PASS_RATE = 1.0

# Validation Set
# Format: "path/to/test_image": ("Expected Realm", "Expected Map")
TEST_SUITE = {
    "examples/temple_of_purgation.jpg": ("Red Forest", "Temple of Purgation"),
    "examples/treatment_theater.webp": ("Léry's Memorial Institute",
                                        "Treatment Theatre"),
    "examples/ironworks_of_misery.webp": ("MacMillan Estate",
                                          "Ironworks of Misery"),
    "examples/the_thompson_house.webp": ("Coldwind Farm", "The Thompson House"),
    "examples/forgotten_ruins.webp": ("Decimated Borgo", "Forgotten Ruins"),
    "examples/mount_ormond_resort.webp": ("Ormond", "Mount Ormond Resort"),
    "examples/mount_ormond_resort_2.webp": ("Ormond", "Mount Ormond Resort"),
    "examples/mount_ormond_resort_3.webp": ("Ormond", "Mount Ormond Resort"),
    "examples/ormond_lake_mine.webp": ("Ormond", "Ormond Lake Mine"),
}


def calculate_confidence(ocr_map: str, ocr_realm: str, exp_map: str,
                         exp_realm: str) -> float:
    """Calculates confidence identically to the app's internal logic."""
    score_map = difflib.SequenceMatcher(None, ocr_map.lower(),
                                        exp_map.lower()).ratio()
    score_realm = difflib.SequenceMatcher(None, ocr_realm.lower(),
                                          exp_realm.lower()).ratio()

    len_map, len_realm = len(exp_map), len(exp_realm)
    if len_map + len_realm == 0: return 0.0

    return (score_map * len_map + score_realm * len_realm) / (
                len_map + len_realm)


def run_benchmark():
    print("=== Initializing DBD Overlay Benchmark ===\n")
    cfg = Config()
    app = DBDOverlayApp(cfg)

    # We don't want the background thread running for this
    app.running = False

    total_score = 0.0
    passes = 0
    failures = 0

    print(
        f"{'FILE':<35} | {'EXPECTED':<25} | {'OCR OUTPUT':<25} | {'CONF'} | {'RESULT'}")
    print("-" * 110)

    for file_path, (exp_realm, exp_map) in TEST_SUITE.items():
        if not Path(file_path).exists():
            print(f"[!] File not found: {file_path}")
            continue

        img = Image.open(file_path).convert("RGB")

        crop_map = img.crop(get_map_box(*img.size))
        crop_realm = img.crop(get_realm_box(*img.size))

        map_text = app.perform_ocr(crop_map, MAP_FONT_THRESHOLD)
        realm_text = app.perform_ocr(crop_realm, REALM_FONT_THRESHOLD)
        matched_path = app.match_map_to_file_with_confidence(map_text,
                                                             realm_text)

        # Calculate raw OCR confidence against truth
        conf = calculate_confidence(map_text, realm_text, exp_map, exp_realm)

        is_correct = False
        if matched_path:
            # Reverse lookup the matched path to find the App's canonical realm and map names (post-aliases)
            app_realm, app_map = None, None
            for r_key, maps in app.maps_by_realm_then_name.items():
                for m_key, path_val in maps.items():
                    if path_val == matched_path:
                        app_realm, app_map = r_key, m_key
                        break

            if app_realm and app_map:
                # Check if the test suite's expected name matches the canonical name
                map_similarity = difflib.SequenceMatcher(None, exp_map.lower(), app_map).ratio()
                # Lery's and Temple of Purgation don't match better than 0.9:
                if map_similarity > 0.9:
                    is_correct = True

        short_name = Path(file_path).name
        out_str = f"M:'{map_text}' R:'{realm_text}'"
        exp_str = f"M:'{exp_map}'"

        if is_correct:
            result = "[PASS]"
            total_score += conf
            passes += 1
        else:
            result = "[FAIL]"
            total_score -= (conf * 2)
            failures += 1

        print(
            f"{short_name:<35} | {exp_str:<25} | {out_str:<25} | {conf:.2f} | {result}")

    total_tests = passes + failures
    pass_rate = passes / total_tests

    print("-" * 110)
    print("=== BENCHMARK RESULTS ===")
    print(f"Total Tests : {total_tests}")
    print(f"Pass Rate   : {pass_rate * 100:.1f}%")
    print(f"Final Score : {total_score:.2f}")
    print("=========================\n")

    if pass_rate < REQUIRED_PASS_RATE:
        print(f"[!] CI FAILURE: Pass rate dropped below {int(REQUIRED_PASS_RATE * 100)}%.")
        sys.exit(1)

    if total_score < REQUIRED_SCORE:
        print(
            f"[!] CI FAILURE: Final score {total_score:.2f} is below the required {REQUIRED_SCORE} threshold.")
        sys.exit(1)

    print("[+] CI SUCCESS: OCR thresholds passed all validation criteria.")
    sys.exit(0)

if __name__ == "__main__":
    run_benchmark()