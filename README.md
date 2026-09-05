# Steam Library Sorter

Quick-and-dirty tools to list your full Steam library — your own games plus
anything shared with you through a Steam Family group — whether or not it's
currently installed, then optionally sort it by series/franchise and genre.

## Why this exists

The public Steam Web API only returns games *you* own, and only if your
profile privacy allows it. It has no concept of Steam Families sharing.
These scripts instead use a session **access token** (the same kind your
browser uses when you're logged into the Steam store) to call:

- `IPlayerService/GetOwnedGames` — your full owned library, private profile or not
- `IFamilyGroupsService/GetSharedLibraryApps` — everything shared with you via
  your Steam Family group, installed or not

> **Note:** `IFamilyGroupsService` is an undocumented Steam endpoint. It's
> the same one the Steam client itself uses, but Valve could change or break
> it without notice.

## Contents

| File | What it does |
|---|---|
| `steam_library_gui.py` | Desktop GUI — paste your token, browse your library, view it grouped by series and genre |
| `list_all_steam_games.py` | Command-line version of the fetch step; saves `steam_library.json` |
| `categorize_library.py` | Command-line categorizer; reads `steam_library.json`, adds genre/series grouping |

The GUI does everything the two command-line scripts do combined, in one
window — start there unless you specifically want the terminal versions.

## Requirements

- Python 3.9+
- `pip install requests`
- `tkinter` for the GUI (bundled with the standard Windows/macOS Python installer; on Linux you may need `sudo apt install python3-tk` or equivalent)

## Getting your access token

You'll need this every time the token expires (it's a session token, so it
lasts a while but not forever).

1. Log into <https://store.steampowered.com> in a browser.
2. Visit <https://store.steampowered.com/pointssummary/ajaxgetasyncconfig> directly.
3. You'll see raw JSON like `{"success": true, "data": {"webapi_token": "eyJ..."}}`.
4. Copy the `webapi_token` value (starts with `eyJ`).

Treat this token like a password — anyone who has it can read your account's
library and Family data until it expires. Don't commit it to a repo, paste it
into public chat logs, or leave it sitting in a plain-text file.

## Using the GUI

```
python steam_library_gui.py
```

1. Paste the token into the field at the top.
2. Click **Fetch Library**.
3. Browse:
   - **All Games** — full list with playtime, source (own/shared), install status; filter box above narrows it live.
   - **By Series** — expandable groups by franchise (name-matching, not perfect — see below).
   - **By Genre** — click **Fetch Genres** to pull tags from Steam's store API. This is slow (~1–1.5s per unique game, rate-limited) and runs in the background with a progress bar. It checkpoints to `genre_cache.json`, so closing and re-running only fetches what's missing.

The token is only kept in memory for that run — it's never written to disk
by the GUI.

## Using the command-line scripts instead

```
python list_all_steam_games.py YOUR_TOKEN
python categorize_library.py
```

`list_all_steam_games.py` prints your library and saves `steam_library.json`
(with appids) alongside it. `categorize_library.py` reads that file, fetches
genres (cached to `genre_cache.json`), and prints/saves a series + genre
breakdown to `library_categorized.json`. Pass `--skip-genres` to
`categorize_library.py` for instant series-only grouping with no API calls.

## Building a standalone .exe

Using [auto-py-to-exe](https://pypi.org/project/auto-py-to-exe/):

```
pip install auto-py-to-exe
auto-py-to-exe
```

In the window that opens:
- **Script Location** → the actual `.py` file (e.g. `steam_library_gui.py`), not its folder
- **Onefile** → One File
- **Console Window** → Window Based (hide the console)

Click Convert; the `.exe` lands in an `output` folder next to the script.
First run will likely trigger a Windows SmartScreen / antivirus warning since
it's an unsigned, unrecognized binary — this is normal for PyInstaller
output, not a sign of a problem. Click "More info" → "Run anyway".

## Known limitations

- **Series grouping is a heuristic**, matching game names against a curated
  list of franchise keywords in the script (`FRANCHISES`). It'll miss
  franchises not in that list — add more strings to it as needed. Anything
  unmatched lands in "(Unclassified / standalone)".
- **Genre data** comes straight from Steam's store page per appid, so it
  should match what you see in the store, but delisted or region-restricted
  games may return nothing.
- If saving `steam_library.json` or `genre_cache.json` fails (e.g. file open
  elsewhere, folder permissions), the GUI falls back to your user home
  folder and keeps working rather than crashing.
- Because `IFamilyGroupsService` is undocumented, Valve changing it could
  break the shared-library fetch without warning.
