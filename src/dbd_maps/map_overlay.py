import ctypes
import configparser
import datetime
import difflib
import keyboard
from enum import Enum, auto
from pathlib import Path
import sys
import threading
import time
import tkinter as tk
import re

from mss import MSS
from PIL import Image, ImageEnhance, ImageTk

# Windows Native OCR Check
HAS_WINOCR = False
try:
    import winocr
    HAS_WINOCR = True
except ImportError:
    pass


STATUS_PANEL_WIDTH = 110
STATUS_FONT_SIZE = 8
TOP_BORDER_PC = 209.0 / 1080
BOTTOM_BORDER_PC = 980.0 / 1080
LEFT_BORDER_PC = 510.0 / 1920
RIGT_BORDER_PC = 1458.0 / 1920
MAP_FONT_THRESHOLD = 230
REALM_FONT_THRESHOLD = 150

_ROMAN_SUFFIX = re.compile(
    r"^(.*?)\s+(i|ii|iii|iv|v|vi|vii|viii|ix|x)$"
)
_NUMERIC_SUFFIX = re.compile(r"^(.*?)(\d+)$")

_ROMAN_VALUES = {
    "i": 1,
    "ii": 2,
    "iii": 3,
    "iv": 4,
    "v": 5,
    "vi": 6,
    "vii": 7,
    "viii": 8,
    "ix": 9,
    "x": 10,
}


def timestamp() -> str:
    return datetime.datetime.now().strftime("%H:%M:%S")


def log(msg: str) -> None:
    print(f"[{timestamp()}] {msg}", flush=True)


def get_map_box(w: int, h: int):
    return (int(w * 0.04), int(h * 0.81), int(w * 0.45), int(h * 0.86))

def get_realm_box(w: int, h: int):
    return (int(w * 0.04), int(h * 0.86), int(w * 0.35), int(h * 0.90))

def _correct_realm_and_map_names(maps_by_realm_then_name: dict[str, dict[str, Path]], aliases: dict[str, str], realm_aliases: dict[str, str]):
    for realm in list(maps_by_realm_then_name.keys()):
        if realm in realm_aliases:
            maps_by_realm_then_name[realm_aliases[realm]] = maps_by_realm_then_name[realm]
            del maps_by_realm_then_name[realm]

    for realm in maps_by_realm_then_name.keys():
        for map_name in list(maps_by_realm_then_name[realm].keys()):
            if map_name in aliases:
                maps_by_realm_then_name[realm][aliases[map_name]] = maps_by_realm_then_name[realm][map_name]
                del maps_by_realm_then_name[realm][map_name]

def _use_latest_map_variants(
        maps_by_realm_then_name: dict[str, dict[str, Path]]
):
    for maps in maps_by_realm_then_name.values():
        variants: dict[str, list[tuple[int, str]]] = {}

        for map_name in maps:
            if match := _ROMAN_SUFFIX.match(map_name):
                base, numeral = match.groups()
                variants.setdefault(base, []).append(
                    (_ROMAN_VALUES[numeral], map_name)
                )

            elif match := _NUMERIC_SUFFIX.match(map_name):
                base, number = match.groups()
                variants.setdefault(base, []).append(
                    (int(number), map_name)
                )

        for base, suffixed_variants in variants.items():
            _, latest_name = max(suffixed_variants)
            latest_path = maps[latest_name]

            # Remove every version, including an unsuffixed original.
            for _, variant_name in suffixed_variants:
                del maps[variant_name]
            maps.pop(base, None)

            # Reintroduce the latest version under its canonical name.
            maps[base] = latest_path


def is_loading_screen(img: Image.Image) -> tuple[bool, float]:
    """
    Check for loading screen dark margins.
    """
    w, h = img.size
    crops = [
        img.crop((0, 0, int(w * LEFT_BORDER_PC), h)),
        img.crop((int(w * RIGT_BORDER_PC), 0, w, h)),
        img.crop((0, 0, w, int(h * TOP_BORDER_PC))),
        img.crop((0, int(h * BOTTOM_BORDER_PC), w, h))
    ]

    total_pixels = 0
    dark_pixels = 0

    for crop in crops:
        raw_bytes = crop.convert("L").tobytes()
        total_pixels += len(raw_bytes)
        dark_pixels += sum(1 for b in raw_bytes if b <= 5)

    dark_ratio = (dark_pixels / total_pixels) if total_pixels > 0 else 0.0
    return (dark_ratio >= 0.90), dark_ratio

def detect_divider_line(img: Image.Image) -> tuple[bool, int]:
    """
    Scans horizontal rows for a continuous span of pixels with Delta RGB <= 13.
    We could make the threshold smaller, but tests would fail because I am lossy
    compression, that blurs the noise into the line.
    """
    RGB_THRESHOLD = 13
    w, h = img.size
    line_box = (int(w * 0.065), int(h * 929 / 1080.0), int(w * 0.35), int(h * 932 / 1080.0))
    crop = img.crop(line_box).convert("RGB")
    crop_w, crop_h = crop.size
    raw_bytes = crop.tobytes()

    max_line_length = 0

    for y in range(crop_h):
        row_start = y * crop_w * 3
        current_length = 1

        for x in range(1, crop_w):
            idx1 = row_start + (x - 1) * 3
            idx2 = row_start + x * 3

            r1, g1, b1 = raw_bytes[idx1], raw_bytes[idx1 + 1], raw_bytes[idx1 + 2]
            r2, g2, b2 = raw_bytes[idx2], raw_bytes[idx2 + 1], raw_bytes[idx2 + 2]

            if (r2 + g2 + b2 > 90) and abs(r1 - r2) <= RGB_THRESHOLD and abs(g1 - g2) <= RGB_THRESHOLD and abs(b1 - b2) <= RGB_THRESHOLD:
                current_length += 1
            else:
                if current_length > max_line_length:
                    max_line_length = current_length
                current_length = 1

        if current_length > max_line_length:
            max_line_length = current_length

    return (max_line_length >= 180), max_line_length



class Config:
    def __init__(self):
        if getattr(sys, "frozen", False): # A frozen exe, not a py script.
            config_file = Path(sys.executable).parent / "config.ini"
        else:
            config_file = Path("config.ini")

        if not config_file.is_file():
            raise FileNotFoundError(
                f"Configuration file not found: {config_file}"
            )

        self.parser = configparser.ConfigParser()
        self.parser.read(config_file)

        self.overlay_x = self.parser.getint("Overlay", "x", fallback=0)
        self.overlay_y = self.parser.getint("Overlay", "y", fallback=0)
        self.overlay_w = self.parser.getint("Overlay", "width", fallback=240)
        self.overlay_h = self.parser.getint("Overlay", "height", fallback=240)
        self.opacity = self.parser.getfloat("Overlay", "opacity", fallback=0.5)

        self.exit_hotkey = self.parser.get("Overlay", "exit_hotkey", fallback="ctrl+alt+shift+f7")
        self.maps_dir = config_file.parent / Path("local_maps")
        self.aliases = dict(self.parser.items("Map aliases")) if self.parser.has_section("Map aliases") else {}
        self.realm_aliases = dict(self.parser.items("Realm aliases")) if self.parser.has_section("Realm aliases") else {}


class GameState(Enum):
    IDLE = auto()
    LOADING = auto()
    MAP_INTRO = auto()
    OVERLAY_SHOWING = auto()
    IN_GAME_NO_MAP = auto()



class DBDOverlayApp:
    def __init__(self, config: Config):
        self.cfg = config
        self.state = GameState.IDLE
        self.running = True

        self.maps_by_realm_then_name = self._get_maps_by_realm_then_name()
        _use_latest_map_variants(self.maps_by_realm_then_name)
        _correct_realm_and_map_names(self.maps_by_realm_then_name, self.cfg.aliases, self.cfg.realm_aliases)

        self.captures_dir = Path("debug_captures")
        self.captures_dir.mkdir(exist_ok=True)

        # Tkinter overlay window setup (Borderless, Topmost, Top-Left +0+0)
        self.root = tk.Tk()
        self.root.title("DBD Overlay")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.7)
        # Fix geometry of dbg overlay, to be ignored by loading screen detection.
        self.root.geometry(f"{STATUS_PANEL_WIDTH}x60+0+0")
        self.root.resizable(False, False)

        self._make_clickthrough()

        # Container Frame for Status HUD
        self.main_frame = tk.Frame(self.root, bg="#000000", highlightbackground="#222222", highlightthickness=1)
        self.main_frame.pack(fill="both", expand=True)
        self.main_frame.pack_propagate(False)

        self.lbl_line1 = tk.Label(
            self.main_frame, text=f"{timestamp()} IDLE",
            fg="#00FFCC", bg="#000000", font=("Consolas", STATUS_FONT_SIZE, "bold"), anchor="w"
        )
        self.lbl_line1.pack(fill="x", expand=False)

        self.lbl_line2 = tk.Label(
            self.main_frame, text="DARK: 0.0%",
            fg="#888888", bg="#000000", font=("Consolas", STATUS_FONT_SIZE), anchor="w"
        )
        self.lbl_line2.pack(fill="x", expand=False)

        self.lbl_line3 = tk.Label(
            self.main_frame, text="LINE: 0px",
            fg="#888888", bg="#000000", font=("Consolas", STATUS_FONT_SIZE), anchor="w"
        )
        self.lbl_line3.pack(fill="x", expand=False)

        # Label for Map Graphic
        self.map_label = tk.Label(self.root, bg="#000000")

        # Thread for game loop
        self.thread = threading.Thread(target=self._monitor_game_loop, daemon=True)
        self.thread.start()

        keyboard.add_hotkey(self.cfg.exit_hotkey, self._shutdown_app)

    def _keep_on_top(self):
        """Forces the Tkinter window to stay topmost if any other app/game reasserts its own Z-order."""
        self.root.lift()
        self.root.attributes("-topmost", True)

    def _make_clickthrough(self):
        """Makes the Tkinter window completely transparent to mouse events (Windows only)."""
        try:
            # Force Tkinter to draw the window so the handle (HWND) exists
            self.root.update_idletasks()

            # Get the top-level window handle as an integer
            hwnd = int(self.root.wm_frame(), 16)

            user32 = ctypes.windll.user32
            GWL_EXSTYLE = -20
            WS_EX_LAYERED = 0x00080000
            WS_EX_TRANSPARENT = 0x00000020

            # Fetch the API functions dynamically to safely support both 32-bit and 64-bit Python
            GetWindowLong = getattr(user32, "GetWindowLongPtrW", user32.GetWindowLongW)
            SetWindowLong = getattr(user32, "SetWindowLongPtrW", user32.SetWindowLongW)

            # Combine current styles with the layered and transparent styles
            style = GetWindowLong(hwnd, GWL_EXSTYLE)
            SetWindowLong(hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED | WS_EX_TRANSPARENT)

        except Exception as e:
            log(f"[!] Could not set click-through: {e}")

    def _get_maps_by_realm_then_name(self) -> dict[str, dict[str, Path]]:
        maps_by_realm_then_name = {}
        if not self.cfg.maps_dir.exists():
            log(f"[!] Warning: Path '{self.cfg.maps_dir}' does not exist.")
            return maps_by_realm_then_name

        files = list(self.cfg.maps_dir.rglob("*.webp"))
        for path in files:
            realm_name = path.parent.name.lower()
            maps_by_realm_then_name.setdefault(realm_name, {})
            maps_by_realm_then_name[realm_name][path.stem.lower()] = path

        log(f"[+] Indexed {len(maps_by_realm_then_name)} local map templates ({len(files)} files).")
        return maps_by_realm_then_name

    # --- UI View Switchers ---
    def update_status_hud(self, state_str: str, dark_pct: float, line_len: int, state_color: str = "#00FFCC"):
        """Show compact {STATUS_PANEL_WIDTH}x60 status HUD."""
        def _update():
            if self.map_label.winfo_manager():
                self.map_label.pack_forget()

            if not self.main_frame.winfo_manager():
                self.main_frame.pack(fill="both", expand=True)

            self.root.geometry(f"{STATUS_PANEL_WIDTH}x60+0+0")
            self.lbl_line1.config(text=f"{timestamp()} {state_str}", fg=state_color)
            self.lbl_line2.config(text=f"DARK: {dark_pct:.1%}")
            self.lbl_line3.config(text=f"LINE: {line_len}px")
        self.root.after(0, _update)

    def show_map_graphic(self, image_path: Path):
        """Expand window to configured size and show scaled map graphic."""
        def _update():
            if self.main_frame.winfo_manager():
                self.main_frame.pack_forget()

            img = Image.open(image_path).convert("RGBA")
            img = img.resize((self.cfg.overlay_w, self.cfg.overlay_h), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img)

            self.map_label.config(image=photo, bg="#000000")
            self.map_label.image = photo  # Prevent garbage collection
            self.map_label.pack(fill="both", expand=True)

            # Expand window to configured dimensions at 0,0
            self.root.geometry(f"{self.cfg.overlay_w}x{self.cfg.overlay_h}+{self.cfg.overlay_x}+{self.cfg.overlay_y}")
            self.root.attributes("-alpha", min(0.95, self.cfg.opacity))

        self.root.after(0, _update)

    def _shutdown_app(self):
        log(f"[+] Global hotkey ({self.cfg.exit_hotkey}) pressed. Shutting down...")
        self.running = False
        self.root.after(0, self.root.destroy)

    def perform_realm_ocr(self, crop_img: Image.Image) -> str:
        """
        Uses explicit RGB bounds to isolate the dark grayish realm sub-text
        from any background (including bright white snow).
        """
        if not HAS_WINOCR:
            return ""

        crop_rgb = crop_img.convert("RGB")
        width, height = crop_rgb.size
        pixels = crop_rgb.load()

        # Create a pure black canvas to draw our extracted text onto
        out_img = Image.new("L", (width, height), 0)
        out_pixels = out_img.load()

        for y in range(height):
            for x in range(width):
                r, g, b = pixels[x, y]

                # Actual observed bounds:
                # if 0x59 <= r <= 0x70 and 0x5b <= g <= 0x6c and 0x57 <= b <= 0x67:
                if 0x4a <= r <= 0x70 and 0x5b <= g <= 0x6c and 0x57 <= b <= 0x80:
                    # Ensure it's a desaturated tone (R,G,B are very close to each other)
                    if max(r, g, b) - min(r, g, b) <= 25:
                        out_pixels[
                            x, y] = 255  # Turn matching pixels pure white

        # Optional: Uncomment this to see exactly how beautifully this extracts the realm!
        # out_img.save(self.captures_dir / f"realm_debug_{int(time.time())}.png")

        try:
            result = winocr.recognize_pil_sync(out_img)
            return result.get("text", "").strip()
        except Exception as e:
            log(f"[!] WinOCR Error (Realm): {e}")
            return ""

    def perform_ocr(self, crop_img: Image.Image, threshold: int) -> str:
        """
        threshold is the text/font brightness. The map is brighter than the realm.
        The realm is sub-text.
        150 is usually ok. Very bright backgrounds need a bit more, but this loses
        the realm, so we pass 180 for the map, and 150 for the realm.
        """
        if not HAS_WINOCR:
            return ""

        crop_gray = crop_img.convert("L")
        enhancer = ImageEnhance.Contrast(crop_gray)
        crop_gray = enhancer.enhance(2.5)
        threshold_crop = crop_gray.point(lambda p: 255 if p > threshold else 0)

        try:
            result = winocr.recognize_pil_sync(threshold_crop)
            return result.get("text", "").strip()
        except Exception as e:
            log(f"[!] WinOCR Error: {e}")
            return ""

    def match_map_to_file_with_confidence(self, map_text: str, realm_text: str) -> Path | None:
        """
        Matches OCR text to local map files with a 60% confidence threshold.
        """
        map_clean = map_text.strip().lower()
        realm_clean = realm_text.strip().lower()

        if len(map_clean) < 3 and len(realm_clean) < 3:
            log(f"[!] Ignored short OCR noise: Map='{map_text}', Realm='{realm_text}'")
            return None

        # Calculate similarity score for all indexed candidates
        best_candidate = None
        best_score = 0.0

        for realm_name, maps in self.maps_by_realm_then_name.items():
            for map_name, path in maps.items():
                score_map = difflib.SequenceMatcher(
                    None,
                    map_clean,
                    map_name.lower(),
                ).ratio()

                score_realm = difflib.SequenceMatcher(
                    None,
                    realm_clean,
                    realm_name.lower(),
                ).ratio()

                # Whether to rate the realm name as important as the longer map name.
                # I say no as it means having to match two different fonts, at once.
                # this_score = (score_map + score_realm) / 2
                this_score = (score_map * len(map_name) + score_realm * len(realm_name)) / (len(map_name) + len(realm_name))

                if this_score > best_score:
                    best_score = this_score
                    best_candidate = (map_name, path)

        # 60% Confidence Threshold
        CONFIDENCE_THRESHOLD = 0.60

        if best_candidate and best_score >= CONFIDENCE_THRESHOLD:
            matched_key, matched_path = best_candidate
            log(f"[+] Matched '{map_text}' / '{realm_text}' -> {matched_path} (Confidence: {best_score:.0%})")
            return matched_path

        # Reject low confidence match
        top_name = best_candidate[0] if best_candidate else "None"
        log(f"[!] Rejected low-confidence OCR '{map_text}' / '{realm_text}' -> Best match '{top_name}' was only {best_score:.0%} (Target >= 60%)")
        return None

    def _monitor_game_loop(self):
        EZ_SLEEP = 3.0
        QK_SLEEP = 0.4
        log("[+] Game monitor thread started.")

        with MSS() as sct:
            monitor = sct.monitors[1]

            while self.running:
                self.root.after(0, self._keep_on_top)
                screenshot = sct.grab(monitor)
                img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

                is_loading, dark_pct = is_loading_screen(img)
                has_line, line_len = detect_divider_line(img)

                if self.state == GameState.IDLE:
                    self.update_status_hud("IDLE", dark_pct, line_len, "#00FFCC")
                    if is_loading:
                        log(f"[+] Loading screen detected (Dark ratio: {dark_pct:.1%}).")
                        self.state = GameState.LOADING
                    time.sleep(EZ_SLEEP)

                elif self.state == GameState.LOADING:
                    # Collapse map image back to status HUD on loading screen (end of game or new match)
                    self.update_status_hud("LOADING", dark_pct, line_len, "#FFFF00")
                    if not is_loading:
                        log(f"[+] Loading ended (Dark ratio: {dark_pct:.1%}). Scanning for Map Intro...")
                        self.state = GameState.MAP_INTRO
                        self.intro_scan_start = time.time()
                    time.sleep(QK_SLEEP)

                elif self.state == GameState.MAP_INTRO:
                    self.update_status_hud("SCANNING", dark_pct, line_len, "#00FFFF")
                    elapsed = time.time() - self.intro_scan_start

                    if has_line:
                        log(f"[+] HUD divider line detected ({line_len}px)! Reading text...")
                        map_box = get_map_box(*img.size)
                        realm_box = get_realm_box(*img.size)

                        crop_map = img.crop(map_box)
                        crop_map.save(self.captures_dir / f"capture_map_{int(time.time())}.png")

                        map_text = self.perform_ocr(crop_map, MAP_FONT_THRESHOLD)
                        realm_text = self.perform_realm_ocr(img.crop(realm_box))
                        # realm_text = self.perform_ocr(img.crop(realm_box), REALM_FONT_THRESHOLD)

                        log(f"[+] OCR Result -> Map: '{map_text}' | Realm: '{realm_text}'")

                        matched_file = self.match_map_to_file_with_confidence(map_text, realm_text)
                        if matched_file:
                            log(f"[+] ACTIVE MATCH: Realm='{matched_file.parent.name}', Map='{matched_file.stem}'")
                            self.show_map_graphic(matched_file)
                            self.state = GameState.OVERLAY_SHOWING
                        else:
                            # Don't just give up; the background was likely noisy.
                            log(f"[+] NO MATCH, retrying...")
                            time.sleep(QK_SLEEP)

                    elif elapsed > 4.0:
                        log("[!] Intro HUD scan timed out.")
                        self.state = GameState.IN_GAME_NO_MAP
                    else:
                        time.sleep(QK_SLEEP)

                elif self.state == GameState.OVERLAY_SHOWING:
                    # Map graphic is visible. Monitor for game over loading screen.
                    if is_loading:
                        log(f"[+] Game Over / Next Loading screen detected (Dark ratio: {dark_pct:.1%}). Resetting overlay...")
                        self.state = GameState.LOADING
                    time.sleep(EZ_SLEEP)

                elif self.state == GameState.IN_GAME_NO_MAP:
                    self.update_status_hud("NO MATCH", dark_pct, line_len, "#FF9900")
                    if is_loading:
                        log(f"[+] Game Over / Next Loading screen detected (Dark ratio: {dark_pct:.1%}). Resetting overlay...")
                        self.state = GameState.LOADING
                    time.sleep(EZ_SLEEP)

    def run(self):
        self.root.mainloop()


# CLI Static Test Runner
def run_static_test(image_path: str):
    print(f"=== Testing Static Image: {image_path} ===")
    img = Image.open(image_path).convert("RGB")

    is_loading, dark_pct = is_loading_screen(img)
    print(f"[*] Loading Screen Test : {is_loading} (Dark Pixel Ratio: {dark_pct:.1%})")

    has_line, line_len = detect_divider_line(img)
    print(f"[*] Solid Line Test    : {has_line} (Max solid run: {line_len} px)")

    if has_line:
        if HAS_WINOCR:
            cfg = Config()
            app = DBDOverlayApp(cfg)
            app.maps_by_realm_then_name = app._get_maps_by_realm_then_name()
            _use_latest_map_variants(app.maps_by_realm_then_name)
            _correct_realm_and_map_names(app.maps_by_realm_then_name, cfg.aliases, cfg.realm_aliases)

            map_box = get_map_box(*img.size)
            realm_box = get_realm_box(*img.size)

            map_text = app.perform_ocr(img.crop(map_box), MAP_FONT_THRESHOLD)
            realm_text = app.perform_realm_ocr(img.crop(realm_box))
            # realm_text = app.perform_ocr(img.crop(realm_box), REALM_FONT_THRESHOLD)

            print(f"[*] OCR Extracted       : Map='{map_text}' | Realm='{realm_text}'")
            matched = app.match_map_to_file_with_confidence(map_text, realm_text)
            print(f"[*] File Match Result   : {matched}")
        else:
            print("[*] WinOCR not installed.")
    else:
        print("[*] Map Matching Skipped (No Intro HUD / Line detected).")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        run_static_test(sys.argv[2])
    else:
        config = Config()
        app = DBDOverlayApp(config)
        log(f"[+] DBD Mapping running. {config.exit_hotkey} to stop it.")
        app.run()
