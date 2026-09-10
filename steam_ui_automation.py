#!/usr/bin/env python3
"""
EXPERIMENTAL: drives the real Steam client window with simulated clicks/
keystrokes to recreate your categories.json as real Steam Library
Collections, since Collections are cloud-synced server-side and there's no
reliable file we can just write to instead (see localconfig.vdf/leveldb
investigation -- both turned out to be dead ends Steam doesn't read back).

This is fragile by nature: it depends on exact screen coordinates that will
break if your Steam window moves, resizes, changes theme, or Valve tweaks
the UI. Its model: every category is created once (you type its name
yourself, since that's stayed the one unreliable-to-automate step), and the
exact spot it was created at gets reused directly for every later game
added to that same category -- fully automated, no re-marking needed.
The only thing that ever needs a fresh mark is starting a genuinely NEW
category, since "New Collection" shifts down one row every time a
previous category gets created above it.

SAFETY:
  - pyautogui's failsafe is enabled: slam your mouse into any screen
    corner at any time to immediately abort.
  - Always run --dry-run first to sanity check the game/category list.
  - Always test with --only-category on a category with 2+ games before
    running the full set, so you see both the creation step and a fully
    automated repeat-add while it's easy to watch closely.
  - Nothing here touches any file -- it only simulates mouse/keyboard
    input into whatever window has focus, which should be Steam.
  - Every click the script makes is preceded by a brief red ring flashed
    on screen at the exact target coordinates, so you can watch in real
    time where it's about to click and abort (failsafe corner) if it
    looks wrong. Marks made while you're actively confirming something
    (calibration, or re-marking "New Collection" for a new category) stay
    on screen persistently instead of just flashing.
  - "Add to" opens as a hover-triggered flyout submenu, so the script
    hovers there rather than clicking it -- clicking it can close the
    whole context menu instead of expanding the submenu.

Setup:
  pip install pyautogui pygetwindow

Calibration:
  No pre-editing required anymore. Each real run starts with a short
  interactive wizard: it tells you where to hover your mouse, you hover
  there (without clicking Steam), then press Enter (no need to focus this terminal window) --
  the script reads your live mouse position at that moment. This also
  means it recalibrates fresh every run, so a moved/resized Steam window
  doesn't leave you running on stale numbers.

Usage:
  python steam_ui_automation.py --dry-run
  python steam_ui_automation.py --only-category "GTA"
  python steam_ui_automation.py
"""

import argparse
import json
import os
import sys
import time
import tkinter as tk

try:
    import pyautogui
except ImportError:
    print("Missing dependency. Run: pip install pyautogui pygetwindow")
    sys.exit(1)

try:
    import pygetwindow as gw
except Exception:
    gw = None  # not available/supported on this platform -- we'll just ask the user to focus Steam manually

# ---------- CONFIG ----------

ACTION_DELAY = 1.0          # seconds paused between steps -- raise this if things move too fast
SEARCH_LOAD_DELAY = 1.2     # seconds to wait after typing for the filtered list to settle

LIBRARY_FILE = "steam_library.json"
CATEGORIES_FILE = "categories.json"

pyautogui.FAILSAFE = True   # move mouse to a screen corner any time to abort immediately
pyautogui.PAUSE = 0.15      # small built-in pause after every pyautogui call


def load_json(filename):
    for path in (filename, os.path.join(os.path.expanduser("~"), filename)):
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    return None


def load_appid_to_name():
    data = load_json(LIBRARY_FILE)
    if data is None:
        print(f"Couldn't find {LIBRARY_FILE}. Fetch your library first.")
        sys.exit(1)
    games = (data.get("own_games", []) + data.get("shared_games", [])
             if isinstance(data, dict) else data)
    return {g["appid"]: g.get("name", "Unknown") for g in games}


def load_categories():
    data = load_json(CATEGORIES_FILE)
    if data is None:
        print(f"Couldn't find {CATEGORIES_FILE}. Build categories in the GUI first.")
        sys.exit(1)
    return data


def show_marker(x, y, duration=0.7):
    """Briefly flashes a red ring at (x, y) so you can watch exactly where
    the script is about to click, in real time, before it happens. It's a
    ring rather than a filled dot so its center stays click-through --
    purely a visual aid; if it fails for any reason, automation continues
    without it rather than crashing the run."""
    marker = _draw_marker(x, y)
    if marker is not None:
        marker.update()
        time.sleep(duration)
        try:
            marker.destroy()
        except Exception:
            pass


def _draw_marker(x, y):
    try:
        marker = tk.Tk()
        size = 28
        marker.overrideredirect(True)
        marker.attributes("-topmost", True)
        marker.geometry(f"{size}x{size}+{x - size // 2}+{y - size // 2}")
        try:
            marker.attributes("-transparentcolor", "white")  # Windows: true see-through + click-through
            bg = "white"
        except tk.TclError:
            bg = marker.cget("bg")  # non-Windows fallback: won't be click-through, just visible
        canvas = tk.Canvas(marker, width=size, height=size, highlightthickness=0, bg=bg)
        canvas.pack()
        # Ring, not a filled dot -- the center stays click-through so this
        # never blocks a real click from reaching Steam underneath it.
        canvas.create_oval(3, 3, size - 3, size - 3, outline="red", width=3)
        return marker
    except Exception:
        return None


def wait_for_enter(prompt=""):
    """Waits for an Enter keypress globally across Windows (so the terminal window
    does not need to be focused or highlighted), or falls back to standard input()."""
    if prompt:
        print(prompt, flush=True)

    if sys.platform == "win32":
        try:
            import ctypes
            VK_RETURN = 0x0D
            user32 = ctypes.windll.user32
            # 1. Wait until Enter is released from any previous keypress
            while user32.GetAsyncKeyState(VK_RETURN) & 0x8000:
                time.sleep(0.02)
            # 2. Wait until Enter is pressed globally anywhere on the system
            while not (user32.GetAsyncKeyState(VK_RETURN) & 0x8000):
                time.sleep(0.02)
            # 3. Wait until Enter is released so it doesn't bleed into the next prompt
            while user32.GetAsyncKeyState(VK_RETURN) & 0x8000:
                time.sleep(0.02)
            return
        except Exception:
            pass

    input()

def click_at(x, y, right=False):
    """Flash a marker at the target, then perform the click at that exact spot."""
    show_marker(x, y)
    if right:
        pyautogui.rightClick(x, y)
    else:
        pyautogui.click(x, y)


def hover_at(x, y, settle=0.6):
    """Flash a marker, move there (no click), and pause -- for menu items
    that open a flyout submenu on hover rather than on click."""
    show_marker(x, y)
    pyautogui.moveTo(x, y, duration=0.2)
    time.sleep(settle)


def capture_point(prompt, markers):
    """Ask the user to hover the mouse somewhere and press Enter -- reads
    the live mouse position at that moment. Pressing Enter is detected
    globally, so you don't need to focus/highlight the terminal window.
    Leaves a persistent red ring at the captured spot (appended to
    `markers` so calibrate() can clean them all up at the end) so every
    previously-marked point stays visible for the rest of calibration."""
    wait_for_enter(f"{prompt}\n  (don't click -- just hover, then press Enter) > ")
    pos = pyautogui.position()
    print(f"  Captured: {pos}\n")
    marker = _draw_marker(*pos)
    if marker is not None:
        marker.update()
        markers.append(marker)
    return pos


def calibrate():
    """Interactive wizard run at the start of every real (non-dry-run)
    session. Walks through the real Steam UI live so the coordinates
    always match the current window position/size/theme -- nothing here
    is trusted from a previous run."""
    print("=== Calibration ===")
    print("With Steam's Library open and maximized, follow each prompt below.")
    print("A red ring stays marking each spot as you go, for reference.\n")

    markers = []
    try:
        search_pos = capture_point("1) Hover over Steam's library SEARCH BOX.", markers)

        print("Now click that search box yourself and type any game name so the list")
        print("filters down to a single result.")
        result_pos = capture_point("2) Hover over that single filtered game row.", markers)

        wait_for_enter(
            "A red ring is now marking that exact spot.\n"
            "  Right-click INSIDE the ring to open the context menu at the same point\n"
            "  the script will use later, then press Enter to continue... > "
        )

        add_pos = capture_point("3) Hover over 'Add to' in that menu.", markers)

        print("Now let the submenu open (hover 'Add to' for a moment, or click it if it doesn't auto-expand).")
        create_pos = capture_point("4) Hover over 'New Collection' at the BOTTOM of that submenu.", markers)

        print("Calibration complete. You can press Escape now to close any open menus.\n")
        return search_pos, result_pos, add_pos, create_pos
    finally:
        for marker in markers:
            try:
                marker.destroy()
            except Exception:
                pass


def focus_steam_window(quiet=False):
    """Brings Steam's window to the foreground. With quiet=True (used mid-run,
    once things are already automated), it never blocks on input() -- it just
    does its best and moves on, since pausing here would defeat the point of
    unattended automation. quiet=False (used at the very start) still asks
    you to click Steam yourself if it can't be found automatically."""
    if gw is None:
        if quiet:
            return
        wait_for_enter("Click on the Steam window yourself now, then press Enter to continue...")
        return
    matches = [w for w in gw.getAllTitles() if w.strip().lower() == "steam"]
    if not matches:
        if quiet:
            return
        wait_for_enter("Couldn't find a window titled 'Steam' -- click on it yourself, then press Enter...")
        return
    try:
        win = gw.getWindowsWithTitle(matches[0])[0]
        win.activate()
        time.sleep(0.3)
    except Exception:
        if not quiet:
            wait_for_enter("Couldn't focus Steam automatically -- click on it yourself, then press Enter...")


def search_and_open_context_menu(game_name, search_pos, result_pos, add_pos):
    click_at(*search_pos)
    pyautogui.hotkey("ctrl", "a")
    pyautogui.press("backspace")
    pyautogui.write(game_name, interval=0.02)
    time.sleep(SEARCH_LOAD_DELAY)
    click_at(*result_pos, right=True)
    time.sleep(ACTION_DELAY * 0.5)
    # "Add to" opens a flyout submenu on hover -- clicking it can close the
    # whole context menu instead of expanding it, so we hover, not click.
    hover_at(*add_pos)


def mark_new_collection_position():
    """Live re-mark of 'New Collection's current position. Needed every time
    a brand new category starts (except the very first, which reuses the
    position from initial calibration), since 'New Collection' shifts down
    one row each time a previous category gets created above it. Leaves a
    persistent red ring visible through the create+type steps, same as the
    calibration markers."""
    wait_for_enter("  This is a NEW category -- 'New Collection' has shifted down since last time.\n"
                   "  Hover over 'New Collection' at the bottom of the submenu now, then press Enter > ")
    pos = pyautogui.position()
    print(f"  Marked: {pos}")
    marker = _draw_marker(*pos)
    if marker is not None:
        marker.update()
    return pos, marker


def create_new_collection(category_name, pos):
    """Click 'New Collection' at pos, then hand typing to the human --
    this is the one step that's stayed unreliable to automate, and a human
    doing it directly in the real Steam UI just works, every time."""
    click_at(*pos)
    print(f"    -> A text box should now be open. Click into it and type: {category_name}")
    wait_for_enter("       Press Enter once you've typed it in Steam... > ")


def mark_existing_collection_position(category_name):
    """Asks the user to hover over an ALREADY-CREATED category name in the
    'Add to' submenu (e.g. for Game #2 of a new category). Captures the live
    mouse position so all remaining games in this category can be clicked
    automatically at this exact spot."""
    wait_for_enter(f"  Hover over '{category_name}' in the 'Add to' submenu now, then press Enter > ")
    pos = pyautogui.position()
    print(f"  Marked '{category_name}' at: {pos}")
    marker = _draw_marker(*pos)
    if marker is not None:
        marker.update()
        time.sleep(0.3)
        try:
            marker.destroy()
        except Exception:
            pass
    return pos


def pick_existing_collection(pos):
    """Games 2+ in an already-created category: click the exact spot that
    category was created at. No math, no re-marking -- that position IS
    where the collection now sits, since collections don't move once
    created; only 'New Collection' moves as new ones get added above it."""
    click_at(*pos)


def clear_search(search_pos):
    click_at(*search_pos)
    pyautogui.hotkey("ctrl", "a")
    pyautogui.press("backspace")


def run(categories, appid_to_name, dry_run, only_category):
    if only_category:
        categories = {k: v for k, v in categories.items() if k == only_category}
        if not categories:
            print(f"No category named '{only_category}' found.")
            return

    plan = []
    for name, appids in categories.items():
        names = [appid_to_name.get(a, f"(unknown appid {a})") for a in appids]
        plan.append((name, names))

    print(f"\nPlanned: {len(plan)} categor{'y' if len(plan)==1 else 'ies'}, "
          f"{sum(len(n) for _, n in plan)} total game placements.\n")
    for name, names in plan:
        print(f"  {name} ({len(names)} games)")
        if dry_run:
            for n in names:
                print(f"      - {n}")

    if dry_run:
        print("\nDry run only -- no clicks were made.")
        return

    print("\nAbout to start calibration, then click your real Steam window.")
    print("Adding more games to an already-created category is fully automated.")
    print("Starting a brand new category needs one quick re-mark of 'New Collection' each time,")
    print("since it shifts down every time a previous category gets added above it.")
    print("Move your mouse to any screen corner at any time to abort immediately.")
    confirm = input("Type YES to proceed: ")
    if confirm.strip().upper() != "YES":
        print("Aborted.")
        return

    focus_steam_window()
    search_pos, result_pos, add_pos, create_pos = calibrate()

    print("Starting in 3 seconds...")
    time.sleep(3)

    category_positions = {}  # category name -> exact (x, y) spot in 'Add to' submenu
    created_categories = set()

    for name, names in plan:
        print(f"\n=== Category: {name} ({len(names)} game{'s' if len(names)!=1 else ''}) ===")
        for i, game_name in enumerate(names):
            print(f"  [{i+1}/{len(names)}] {game_name}")
            try:
                search_and_open_context_menu(game_name, search_pos, result_pos, add_pos)
                
                # Check if this category needs to be created on Steam (first game of a brand new category)
                if i == 0 and name not in created_categories and name not in category_positions:
                    if not created_categories:
                        # Very first category of the run -- reuse 'New Collection' spot from calibration
                        pos, marker = create_pos, None
                    else:
                        # Subsequent category -- 'New Collection' shifts down, so mark its new spot
                        pos, marker = mark_new_collection_position()
                    
                    create_new_collection(name, pos)
                    created_categories.add(name)
                    if marker is not None:
                        try:
                            marker.destroy()
                        except Exception:
                            pass
                    print(f"    -> Created collection '{name}' and added '{game_name}'.")
                else:
                    # Adding to an existing category (Game #2+ of a new category)
                    if name not in category_positions:
                        # First time picking this existing category -- ask user to mark its row in the 'Add to' submenu
                        pos = mark_existing_collection_position(name)
                        category_positions[name] = pos
                    
                    pick_existing_collection(category_positions[name])
                    print(f"    -> Added '{game_name}' to '{name}'.")

            except pyautogui.FailSafeException:
                print("\nABORTED via failsafe corner.")
                return
            time.sleep(ACTION_DELAY)
        clear_search(search_pos)

    print("\nDone. Open Steam's Library and check your Collections.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Print the plan without clicking anything")
    parser.add_argument("--only-category", help="Only process this one category (test with a small one first)")
    args = parser.parse_args()

    appid_to_name = load_appid_to_name()
    categories = load_categories()
    run(categories, appid_to_name, args.dry_run, args.only_category)


if __name__ == "__main__":
    main()
