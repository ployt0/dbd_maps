"""
This is where I am dumping dead code before deleting down the line.
I was unsure which versions of map are still used, and in the end
resorted to renaming them myself, as literal " i" suffixes are
commonly seen, at least in the Springwood Badham Preschool map.
"""

from pathlib import Path
import re

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

def _use_latest_map_variants(
        maps_by_realm_then_name: dict[str, dict[str, Path]]
):
    """
    This discards trailing numberals, both arabic and roman, ensuring
    only the latest version is used.
    """
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
