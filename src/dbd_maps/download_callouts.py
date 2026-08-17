"""
Fetch DBD maps, direct from hens333, because that is straight from
the source. I'll throw them on screen each game in a separate script.
"""

from pathlib import Path
import re
import sys
import urllib.parse
import urllib.request
from bs4 import BeautifulSoup

# Configuration
PAGE_URL = "https://hens333.com/callouts"
IMAGE_BASE_URL = "https://hens333.com/img/dbd/callouts/"
OUTPUT_DIR = Path("local_maps")

# Header to avoid potential 403 Forbidden blocks
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36"
}


def sanitize_name(name: str) -> str:
    """Sanitize directory and file names to be OS-safe."""
    # Remove characters prohibited in Windows/Linux filenames
    clean = re.sub(r'[\\/*?:"<>|]', "", name)
    return clean.strip()


def get_html_content(source: str) -> str:
    """Fetch HTML content from a URL or load from a local file path."""
    source_path = Path(source)
    if source_path.is_file():
        print(f"[+] Loading local HTML file: {source_path.resolve()}")
        return source_path.read_text(encoding="utf-8")

    print(f"[+] Fetching web page from: {source}")
    req = urllib.request.Request(source, headers=HEADERS)
    with urllib.request.urlopen(req) as response:
        return response.read().decode("utf-8")


def parse_map_entries(html: str) -> list[dict[str, str]]:
    """Parse Realm headings and their associated map data-path attributes."""
    soup = BeautifulSoup(html, "html.parser")
    maps_data = []
    seen_paths = set()

    # Find all realm headers matching the user's description
    realm_headers = soup.find_all("h1")

    for h1 in realm_headers:
        realm_name = h1.get_text(strip=True)
        if not realm_name:
            continue

        # Find the div following the h1 header containing map buttons
        container = h1.find_next_sibling("div")
        if not container:
            continue

        buttons = container.find_all("button", attrs={"data-path": True})
        for btn in buttons:
            data_path = btn["data-path"]
            if data_path in seen_paths:
                continue

            seen_paths.add(data_path)
            maps_data.append({
                "realm": realm_name,
                "data_path": data_path,
                "button_text": btn.get_text(strip=True),
            })

    # Fallback: catch any orphaned buttons with data-path that might have been missed
    all_buttons = soup.find_all("button", attrs={"data-path": True})
    for btn in all_buttons:
        data_path = btn["data-path"]
        if data_path not in seen_paths:
            seen_paths.add(data_path)
            maps_data.append({
                "realm": "Uncategorized",
                "data_path": data_path,
                "button_text": btn.get_text(strip=True),
            })

    return maps_data


def download_image(url: str, dest_path: Path) -> bool:
    """Download an image from url to dest_path if not already cached."""
    if dest_path.exists() and dest_path.stat().st_size > 0:
        return False  # Already cached

    # Ensure parent folder exists
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    # Properly URL-encode spaces and special characters in path
    encoded_url = urllib.parse.quote(url, safe=":/")

    req = urllib.request.Request(encoded_url, headers=HEADERS)
    with urllib.request.urlopen(req) as response, open(dest_path, "wb") as out_file:
        out_file.write(response.read())

    return True


def sync_maps(source_location: str = PAGE_URL, target_dir: Path = OUTPUT_DIR) -> None:
    """Main execution workflow to extract and cache maps locally."""
    try:
        html = get_html_content(source_location)
    except Exception as e:
        print(f"[!] Failed to acquire HTML: {e}")
        sys.exit(1)

    maps = parse_map_entries(html)
    print(f"[+] Total map links discovered: {len(maps)}")

    if not maps:
        print("[!] No map links found. Check HTML structure or URL.")
        return

    downloaded_count = 0
    cached_count = 0
    error_count = 0

    for item in maps:
        realm_folder = sanitize_name(item["realm"])
        data_path = item["data_path"]

        # Preserve the filename from the data-path attribute
        filename = Path(data_path).name
        local_file_path = target_dir / realm_folder / filename

        # Construct full download target URL
        remote_url = f"{IMAGE_BASE_URL}{data_path}"

        try:
            was_downloaded = download_image(remote_url, local_file_path)
            if was_downloaded:
                print(f"  [DOWNLOADED] {realm_folder} -> {filename}")
                downloaded_count += 1
            else:
                print(f"  [CACHED]     {realm_folder} -> {filename}")
                cached_count += 1
        except Exception as e:
            print(f"  [ERROR]      Failed {data_path}: {e}")
            error_count += 1

    print("\n" + "=" * 40)
    print("Sync Complete Summary:")
    print(f"  - Total Maps Checked : {len(maps)}")
    print(f"  - Newly Downloaded   : {downloaded_count}")
    print(f"  - Already Cached     : {cached_count}")
    print(f"  - Download Errors    : {error_count}")
    print(f"  - Target Directory   : {target_dir.resolve()}")
    print("=" * 40)


if __name__ == "__main__":
    # Example usage:
    # Pass a local file path as argument if offline, e.g.: python download_callouts.py callouts.html
    source = sys.argv[1] if len(sys.argv) > 1 else PAGE_URL
    sync_maps(source_location=source)