# Steam Library Sorter

Browse your full Steam library — everything you own plus anything shared with you through a
Steam Family group, installed or not — group it by franchise, genre, or your own custom tags,
and build categories that can be turned into real Steam Library Collections.

\---

## What's included

|File|What it does|
|-|-|
|`steam\_library\_gui.py`|The main app. Fetch your library, browse it, tag it, and build categories. **Start here.**|
|`steam\_ui\_automation.py`|Turns your categories into real Steam Library Collections by automating the Steam client itself.|
|`list\_all\_steam\_games.py`|Command-line alternative to the GUI's fetch step.|

### Data files

Everything below is created automatically as you use the app — plain JSON, stored next to
wherever you run it (or your user folder if that's not writable). Use the **"Where are my
files?"** button in the GUI any time to see the exact path of each one.

|File|Contents|
|-|-|
|`steam\_library.json`|Your fetched library.|
|`genre\_cache.json`|Genres per game, from Steam's store.|
|`franchise\_cache.json`|Franchise tags per game, from Steam's store pages.|
|`community\_tags\_cache.json`|Community tags per game, from Steam's store pages.|
|`curated\_tags.json`|Your own hand-picked tags per game.|
|`categories.json`|Your finished categories.|

\---

## Requirements

* Python 3.9+
* `pip install requests`
* `pip install pyautogui pygetwindow` (only needed for `steam\_ui\_automation.py`)
* `tkinter` for the GUI — already included with Python on Windows/macOS; on Linux, install with
`sudo apt install python3-tk`

\---

## Getting your access token

1. Log into [https://store.steampowered.com](https://store.steampowered.com) in a browser.
2. Visit [https://store.steampowered.com/pointssummary/ajaxgetasyncconfig](https://store.steampowered.com/pointssummary/ajaxgetasyncconfig).
3. Copy the `webapi\_token` value from the page (starts with `eyJ`).
4. Paste it into the app and click **Fetch Library**.

This token expires after a while, so you'll repeat this occasionally. Treat it like a
password while it's active — the app never saves it to disk.

\---

## Using the app

```
python steam\_library\_gui.py
```

* **Fetch Library** — pulls in everything you own and everything shared with you.
* **All Games** — your full list, searchable, with playtime and install status.
* **By Franchise** / **By Genre** — automatic grouping, including official Steam data where
available.
* **Curate Tags** — pick which tags actually apply to each game, or add your own.
* **Categories** — build your own groupings by selecting tags and adding every matching game
at once, then fine-tune by hand. Shows how many games still aren't in any category yet.
* **Theme** — switch between a dark Steam-styled look and a plain light theme.

\---

## Turning categories into real Steam Collections

Steam doesn't provide a supported way to create Library Collections from outside the Steam
client itself — there's no file or API for it. `steam\_ui\_automation.py` works around that by
directly automating the real Steam window: searching for each game, right-clicking it, and
adding it to the right collection.

### Setup

```
pip install pyautogui pygetwindow
```

### Before running

```
python steam\_ui\_automation.py --dry-run
```

This prints exactly what would happen — every category and every game — without touching
anything. Check it looks right first.

Then test on one small category:

```
python steam\_ui\_automation.py --only-category "GTA"
```

Once you're happy with how it behaves, run it for real:

```
python steam\_ui\_automation.py
```

### What to expect

1. **Calibration** — a short wizard asks you to hover your mouse over a few spots in Steam
(the search box, a game row, and the "Add to" menu) and press Enter at each one. A red ring
marks each spot so you can see everything you've set. Press Enter anywhere — you don't need
to click back into the terminal window first.
2. **Creating a new category** — the script searches for the game, opens the menu, and clicks
"New Collection" for you. You then type the category's name yourself directly in Steam and
press Enter — this is the one step handed to you, since typing reliably is best done by a
person, not simulated keystrokes.
3. **Adding a second game to that category** — the first time this happens, it asks you to
hover over that category's name in the menu and press Enter, so it knows exactly where to
click from then on.
4. **Every game after that** — fully automatic, no further input needed.

### If something needs to stop

Move your mouse to any corner of your screen at any time. This immediately halts the script,
no confirmation needed.

### Notes

* This depends on Steam's current menu layout and wording. If Valve changes the Library UI,
this may need updating to match.
* If your Steam window moves, resizes, or you switch monitors mid-run, re-run calibration.
* Nothing here modifies any files — it only sends mouse and keyboard input to whatever window
is focused, which should be Steam.

\---

## Building a standalone .exe

```
pip install auto-py-to-exe
auto-py-to-exe
```

Set **Script Location** to `steam\_library\_gui.py`, choose **One File**, and choose **Window
Based** under Console Window so no terminal window appears behind it. Click Convert — the
finished `.exe` appears in an `output` folder next to the script.

Windows may show a SmartScreen warning the first time you run a new `.exe` like this, since
it isn't a recognized/signed publisher. Choose "More info" → "Run anyway."

\---

## License

MIT — see `LICENSE`.

