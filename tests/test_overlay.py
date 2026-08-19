import difflib
from pathlib import Path
from PIL import Image
import pytest
from dbd_maps.map_overlay import DBDOverlayApp, HAS_WINOCR, get_map_box, get_realm_box, is_loading_screen, detect_divider_line
from dbd_maps.mapping_lib import _use_latest_map_variants


def test_loading_screen_detection():
    img_path = Path("examples/dbd_loading_screen.png")
    img = Image.open(img_path).convert("RGB")
    is_loading, dark_pct = is_loading_screen(img)

    assert is_loading is True, f"Expected loading screen True, got False (Dark ratio: {dark_pct:.1%})"
    assert dark_pct >= 0.80


def test_ingame_screen_detection():
    img_path = Path("examples/temple_of_purgation.jpg")
    img = Image.open(img_path).convert("RGB")
    is_loading, dark_pct = is_loading_screen(img)

    assert is_loading is False, f"Expected loading screen False for in-game screenshot (Dark ratio: {dark_pct:.1%})"
    assert dark_pct < 0.80


def test_divider_line_detection():
    img_path = Path("examples/temple_of_purgation.jpg")
    img = Image.open(img_path).convert("RGB")
    has_line, line_len = detect_divider_line(img)

    assert has_line is True, f"Expected divider line True, got False ({line_len} px)"

def test_fuzzy_matching_resolves_ocr_typos():
    app = DBDOverlayApp.__new__(DBDOverlayApp)
    # Mock the internal dictionary so we don't need actual files on disk
    app.maps_by_realm_then_name = {
        "red forest": {
            "the temple of purgation": Path("mock/purgation.webp")
        }
    }
    
    # Introduce common OCR mistakes: 0 instead of O, 1 instead of I
    map_text = "THE TEMPLE 0F PURGAT1ON"
    realm_text = "RED F0REST"
    
    matched_file = app.match_map_to_file_with_confidence(map_text, realm_text)
    assert matched_file == Path("mock/purgation.webp"), "Failed to fuzzy match OCR typos"

def test_fuzzy_matching_rejects_low_confidence_noise():
    app = DBDOverlayApp.__new__(DBDOverlayApp)
    app.maps_by_realm_then_name = {
        "red forest": {
            "the temple of purgation": Path("mock/purgation.webp")
        }
    }
    
    # Random text that might be picked up from a survivor name or UI element
    matched_file = app.match_map_to_file_with_confidence("GENERATOR", "REPAIR")
    assert matched_file is None, "Should have rejected low confidence match"

def test_use_latest_map_variants_collapses_roman_numerals():
    maps = {
        "springwood": {
            "badham preschool i": Path("badham1.webp"),
            "badham preschool ii": Path("badham2.webp"),
            "badham preschool v": Path("badham5.webp"), # Latest
            "badham preschool iii": Path("badham3.webp"),
        }
    }
    
    _use_latest_map_variants(maps)
    
    assert "badham preschool" in maps["springwood"], "Base map name should exist"
    assert maps["springwood"]["badham preschool"] == Path("badham5.webp"), "Should map to the highest numeral (V)"
    assert len(maps["springwood"]) == 1, "Should have removed all other variants"

@pytest.mark.skipif(not HAS_WINOCR, reason="WinOCR requires Windows 10/11")
def test_winocr_finds_purgation_map_name():
    img_path = Path("examples/temple_of_purgation.jpg")
    img = Image.open(img_path).convert("RGB")
    map_box = get_map_box(*img.size, 0.42)

    # Bypass `__init__``; we don't need map-display preferences.
    app = DBDOverlayApp.__new__(DBDOverlayApp)
    map_text = app.perform_ocr(img.crop(map_box))

    assert "THE TEMPLE OF PURGATION" == map_text.upper()


@pytest.mark.skipif(not HAS_WINOCR, reason="WinOCR requires Windows 10/11")
def test_winocr_finds_purgation_realm_name():
    img_path = Path("examples/temple_of_purgation.jpg")
    img = Image.open(img_path).convert("RGB")
    realm_box = get_realm_box(*img.size)

    app = DBDOverlayApp.__new__(DBDOverlayApp)
    realm_text = app.perform_realm_ocr(img.crop(realm_box))

    score_realm = difflib.SequenceMatcher(
        None, realm_text.lower(), "RED FOREST".lower()).ratio()
    assert score_realm > 0.6


@pytest.mark.skipif(not HAS_WINOCR, reason="WinOCR requires Windows 10/11")
def test_winocr_misses_ormond_realm_name_with_low_contrast():
    img_path = Path("examples/mount_ormond_resort.webp")
    img = Image.open(img_path).convert("RGB")
    realm_box = get_realm_box(*img.size)

    app = DBDOverlayApp.__new__(DBDOverlayApp)
    realm_text = app.perform_realm_ocr(img.crop(realm_box))

    assert "" == realm_text.upper()


