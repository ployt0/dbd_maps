[![Tests](https://github.com/ployt0/dbd_maps/actions/workflows/tests.yml/badge.svg)](https://github.com/ployt0/dbd_maps/actions/workflows/tests.yml) [![Release](https://img.shields.io/github/v/release/ployt0/dbd_maps)](https://github.com/ployt0/dbd_maps/releases/latest) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE) ![Downloads](https://img.shields.io/github/downloads/ployt0/dbd_maps/total)

## DBD Maps

This automatically and efficiently overlays the current map in an area of the user's choosing. Configured with the config.ini file in the release archive. Default key combo to end the app is <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>Alt</kbd>+<kbd>F7</kbd>.

Maps drawn by Lethia from hens333's discord server.

This is a short script that is easy to inspect and maintain. I am also trying to keep it lightweight and low rent. No heavy .NET dependencies. You can [use a relatively recent python interpreter](#for-the-curious), and the modest packages identified in ~~`requirements.txt`~~ `pyproject.toml`.

Alternatively, just download the Windows release, run it (preferably from a shell for more feedback), and stop reading this, now.


https://github.com/user-attachments/assets/77b72df5-decd-408c-be0c-d59ee33195bf



## For the curious

I wrote this to run from the Bash shell, on Windows.

```bash
pip install -r requirements.txt
python src/dbd_maps/map_overlay.py
```

The commands to run on PowerShell are:

```powershell
pip install .
python -m dbd_maps.map_overlay
```

Edit the `config.ini` file to suit your needs.

## Get the maps

I include the maps, because they are everywhere and I want us to be on the same page. I am also including the downloader script, so I don't *have* to include the maps. I have had to rename quite a few maps, so I won't be maintaining the downloader. That script, is `download_callouts.py`, and puts them where they should go.

Maps need aliases because hens' naming doesn't match precisely to what is shown on screen. The `config.ini` file has the aliases.

To use the downloader_script (from Bash):

```bash
pip install beautifulsoup4
python src/download_callouts.py
```

If I had to make my own maps, I'd start from https://deadbydaylight.wiki.gg/wiki/Realms, which is very basic, but they are all there.

## Tests

I recorded some screenshots when there were teething issues. I use these for tests, mostly of OCR performance.

```bash
python src/map_overlay.py --test examples/dbd_loading_screen.png
python src/map_overlay.py --test examples/temple_of_purgation.jpg
python src/map_overlay.py --test examples/treatment_theater.webp
python src/map_overlay.py --test examples/ironworks_of_misery.webp
python src/map_overlay.py --test examples/the_thompson_house.webp
python src/map_overlay.py --test examples/forgotten_ruins.webp
python src/map_overlay.py --test examples/mount_ormond_resort.webp
python src/map_overlay.py --test examples/mount_ormond_resort_2.webp
python src/map_overlay.py --test examples/father_campbells_chapel.webp
```

These form part of the test suite.

To run pytest tests:

```bash
PYTHONPATH=src pytest
```



