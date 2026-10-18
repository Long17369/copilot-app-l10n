"""add_palettes.py - keep theme/palette names in English.

Palette names are product/brand names (Catppuccin Mocha, Tokyo Night, ...). They should
not be translated, and they should not show up as untranslated strings either.
"""

import io
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "i18n", "terminology.json")

PALETTES = [
    "A cup of coffee", "Aurora", "Ayu", "Base16 Flat", "Base16 Mocha",
    "Blue Dolphin", "Calm Days, Sober Nights Sky", "Catppuccin Frappé",
    "Catppuccin Macchiato", "Catppuccin Mocha", "Chai", "Chinolor", "Cyberdyne",
    "Desert", "Django Reborn Again", "Espresso", "EyeHealth", "Flexoki", "Fox",
    "Garbage Oracle", "Gruvbox Material", "Homebrew", "HydraFusion",
    "IC Orange PPL", "Kanso Ink", "Kary Pro Colors", "Light purple",
    "Maple Mono CN", "Mondrian", "Monochrome", "Monochrome Stone",
    "Monokai Pro Spectrum", "Monospace", "Noctis Azureus", "Noctis Hibernus",
    "Noir Essence", "Nord Midnight", "Notionish", "Phonebook", "Polychrome",
    "Purplepeter", "Rainglow Codecourse", "Rainglow Crisp", "Rainglow Lavender",
    "Remedy Tilted", "Rosé Pine", "Selene Selenized", "Shades of Purple",
    "Soft Color", "Tearout", "Tokyo Night", "Tomorrow Night Eighties",
    "Vaporizer Turquoise", "Xotopio", "Yuttari", "Zenbones Rosebones",
    "Zhxo'red",
]


def main() -> None:
    with io.open(PATH, encoding="utf-8") as fh:
        data = json.load(fh)

    keys = data.setdefault("keep_english_keys", [])
    for name in PALETTES:
        if name not in keys:
            keys.append(name)

    with io.open(PATH, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(data, ensure_ascii=False, indent=2))
        fh.write("\n")
    print("keep_english_keys: %d entries" % len(keys))


if __name__ == "__main__":
    main()
