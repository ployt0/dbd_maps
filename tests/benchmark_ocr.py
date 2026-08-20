import sys
import os
import difflib
from pathlib import Path
from PIL import Image

from dbd_maps.map_overlay import (
    Config, DBDOverlayApp, get_map_box, get_realm_box, calculate_confidence,
    ensure_1080p_resolution
)

## This varies with test count, it is a sum of correct confidences.
REQUIRED_SCORE = 60
## Because screens are just a snapshot, we won't expect them all to pass.
REQUIRED_PASS_RATE = 0.98

TEST_SUITE: dict[str, str] = {
    "badham_preschool_i.webp": "springwood/badham preschool i",
    "badham_preschool_i_2.webp": "springwood/badham preschool i",
    "badham_preschool_i_3.webp": "springwood/badham preschool i",
    "badham_preschool_i_4.webp": "springwood/badham preschool i",
    "badham_preschool_i_5.webp": "springwood/badham preschool i",
    "badham_preschool_i_6.webp": "springwood/badham preschool i",
    "badham_preschool_i_7.webp": "springwood/badham preschool i",
    "dead_dawg_saloon.webp": "grave of glenvale/dead dawg saloon",
    "disturbed_ward.webp": "crotus prenn asylum/disturbed ward",
    "disturbed_ward_2.webp": "crotus prenn asylum/disturbed ward",
    "eyrie_of_crows.webp": "foresaken boneyard/eyrie of crows",
    "eyrie_of_crows_2.webp": "foresaken boneyard/eyrie of crows",
    "family_residence.webp": "yamaoka estate/family residence",
    "father_campbells_chapel.webp": "crotus prenn asylum/father campbells chapel",
    "forgotten_ruins.webp": "the decimated borgo/forgotten ruins",
    "dead_sands.webp": "forsaken boneyard/dead sands",
    "dead_sands_2.webp": "forsaken boneyard/dead sands",
    "fractured_cowshed_720.webp": "coldwind farm/fractured cowshed",
    "fractured_cowshed_720_2.webp": "coldwind farm/fractured cowshed",
    "freddy_fazbear's_pizza.webp": "withered isle/freddy fazbear's pizza",
    "greenville_square.webp": "withered isle/greenville square",
    "grim_pantry.webp": "backwater swamp/grim pantry",
    "groaning_storehouse.webp": "the macmillan estate/groaning storehouse",
    "groaning_storehouse_2.webp": "the macmillan estate/groaning storehouse",
    "ironworks_of_misery.webp": "the macmillan estate/ironworks of misery",
    "ironworks_of_misery_2.webp": "the macmillan estate/ironworks of misery",
    "ironworks_of_misery_3.webp": "the macmillan estate/ironworks of misery",
    "midwich_elementary_school.webp": "silent hill/midwich elementary school",
    "midwich_elementary_school_2.webp": "silent hill/midwich elementary school",
    "mount_ormond_resort.webp": "ormond/mount ormond resort",
    "mount_ormond_resort_2.webp": "ormond/mount ormond resort",
    "mount_ormond_resort_3.webp": "ormond/mount ormond resort",
    "mount_ormond_resort_4.webp": "ormond/mount ormond resort",
    "mount_ormond_resort_5.webp": "ormond/mount ormond resort",
    "mount_ormond_resort_6.webp": "ormond/mount ormond resort",
    "nostromo_wreckage.webp": "dvarka deepwood/nostromo wreckage",
    "nostromo_wreckage_2.webp": "dvarka deepwood/nostromo wreckage",
    "ormond_lake_mine.webp": "ormond/ormond lake mine",
    "ormond_lake_mine_2.webp": "ormond/ormond lake mine",
    "ormond_lake_mine_3.webp": "ormond/ormond lake mine",
    "ormond_lake_mine_4.webp": "ormond/ormond lake mine",
    "ormond_lake_mine_5.webp": "ormond/ormond lake mine",
    "ormond_lake_mine_6.webp": "ormond/ormond lake mine",
    "ormond_lake_mine_7.webp": "ormond/ormond lake mine",
    "raccoon_city_police_station.webp": "raccoon city/raccoon city police station",
    "raccoon_city_police_station_west_wing.webp": "raccoon city/raccoon city police station west wing",
    "raccoon_city_police_station_west_wing_2.webp": "raccoon city/raccoon city police station west wing",
    "rancid_abattoir.webp": "coldwind farm/rancid abattoir",
    "rancid_abattoir_2.webp": "coldwind farm/rancid abattoir",
    "rancid_abattoir_3.webp": "coldwind farm/rancid abattoir",
    "rotten_fields.webp": "coldwind farm/rotten fields",
    "shelter_woods.webp": "the macmillan estate/shelter woods",
    "shelter_woods_2.webp": "the macmillan estate/shelter woods",
    "suffocation_pit.webp": "the macmillan estate/suffocation pit",
    "suffocation_pit_2.webp": "the macmillan estate/suffocation pit",
    "suffocation_pit_3.webp": "the macmillan estate/suffocation pit",
    "suffocation_pit_4.webp": "the macmillan estate/suffocation pit",
    "temple_of_purgation.jpg": "red forest/temple of purgation",
    "the_game.webp": "gideon meat plant/the game",
    "the_thompson_house.webp": "coldwind farm/the thompson house",
    "the_thompson_house_2.webp": "coldwind farm/the thompson house",
    "toba_landing.webp": "dvarka deepwood/toba landing",
    "toba_landing_2.webp": "dvarka deepwood/toba landing",
    "treatment_theater.webp": "léry's memorial institute/treatment theater",
    "trickster's_delusion.webp": "sleepless district/trickster's delusion",
    "trickster's_delusion_2.webp": "sleepless district/trickster's delusion",
    "trickster's_delusion_3.webp": "sleepless district/trickster's delusion",
    "wreckers'_yard_reshaded.webp": "autohaven wreckers/wreckers' yard",
    "wreckers'_yard.webp": "autohaven wreckers/wreckers' yard",
}

"""
The map and realm names are not at the expected position on console.
Know that happens, and extend/switch to console support eventually.
"""
CONSOLE_SUITE: dict[str, str] = {
    "dead_dawg_saloon_console_1.webp": "grave of glenvale/dead dawg saloon",
    "dead_dawg_saloon_console_2.webp": "grave of glenvale/dead dawg saloon",
    "mother's_dwelling_console_1.webp": "red forest/mothers dwelling",
    "mother's_dwelling_console_2.webp": "red forest/mothers dwelling",
    "the_game_console_720_1.webp": "gideon meat plant/the game",
    "the_game_console_720_2.webp": "gideon meat plant/the game",
    "trickster's_delusion_console_1.webp": "sleepless district/trickster's delusion",
    "trickster's_delusion_console_2.webp": "sleepless district/trickster's delusion",
}

LOW_QUALITY: dict = {
    "midwich_elementary_school_720.webp": "silent hill/midwich elementary school",
}

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

    for file_path, expected_realm_map in TEST_SUITE.items():
        img = Image.open(os.path.join("examples", file_path)).convert("RGB")

        # Single call to the multi-width matching pipeline
        matched_path, map_text, realm_text = app.identify_map(img)
        conf = calculate_confidence(realm_text.lower(), map_text.lower(), *expected_realm_map.split("/"))

        is_correct = False
        if matched_path:
            # Reverse lookup the matched path to find the App's canonical realm and map names.
            app_realm, app_map = None, None
            for r_key, maps in app.maps_by_realm_then_name.items():
                for m_key, path_val in maps.items():
                    if path_val == matched_path:
                        app_realm, app_map = r_key, m_key
                        break

            if app_realm and app_map:
                # Check if the test suite's expected name matches the canonical name
                map_similarity = difflib.SequenceMatcher(None, expected_realm_map.split("/")[1].lower(), app_map).ratio()
                if map_similarity > 0.9:
                    is_correct = True

        short_name = Path(file_path).name
        out_str = f"M:'{map_text}' R:'{realm_text}'"
        exp_str = "M:'{}' R:'{}'".format(*expected_realm_map.split("/")[::-1])

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