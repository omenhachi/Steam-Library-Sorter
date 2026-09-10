#!/usr/bin/env python3
"""
Steam Library GUI -- paste your access token, click a button, browse your
whole Steam library (own + family-shared, installed or not), grouped by
series and genre.

Setup (same token as before):
  1. Log into https://store.steampowered.com in a browser
  2. Visit https://store.steampowered.com/pointssummary/ajaxgetasyncconfig
  3. Copy the "webapi_token" value
  4. Paste it into the app and click "Fetch Library"

Requires: pip install requests
Run:      python steam_library_gui.py
"""

import base64
import hashlib
import json
import os
import platform
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

import requests

try:
    from fetch_franchises import fetch_franchises_for_app
except ImportError:
    fetch_franchises_for_app = None

try:
    import vdf
except ImportError:
    vdf = None

BASE = "https://api.steampowered.com"
STORE_API = "https://store.steampowered.com/api/appdetails"
STORE_APP_PAGE = "https://store.steampowered.com/app/{appid}/"
REQUEST_DELAY = 0.4
FRANCHISE_CACHE_FILE = "franchise_cache.json"
COMMUNITY_TAGS_CACHE_FILE = "community_tags_cache.json"
CURATED_TAGS_FILE = "curated_tags.json"
CATEGORIES_FILE = "categories.json"
LIBRARY_FILE = "steam_library.json"
GENRE_CACHE_FILE = "genre_cache.json"

DATA_FILES = {
    "Library (games list)": LIBRARY_FILE,
    "Genres cache": GENRE_CACHE_FILE,
    "Franchise cache": FRANCHISE_CACHE_FILE,
    "Community tags cache": COMMUNITY_TAGS_CACHE_FILE,
    "Curated per-game tags": CURATED_TAGS_FILE,
    "Categories": CATEGORIES_FILE,
}

# ---------- Themes ----------

THEMES = {
    "Steam Dark": {
        "bg": "#171a21",          # near-black Steam header colour
        "panel": "#1b2838",       # Steam's main dark blue panel
        "input_bg": "#2a3f5a",    # entries, listboxes, tree rows
        "fg": "#c7d5e0",          # Steam's light blue-grey body text
        "fg_dim": "#8f98a0",      # inactive tab text
        "fg_heading": "#ffffff",
        "fg_disabled": "#57697a",
        "accent": "#1a9fff",      # Steam blue -- used for buttons & selection
        "accent_hover": "#3fb1ff",
        "accent_press": "#0f7ed1",
        "warn": "#ffb347",
    },
    "Classic Light": {
        "bg": "#f0f0f0",
        "panel": "#ffffff",
        "input_bg": "#ffffff",
        "fg": "#000000",
        "fg_dim": "#555555",
        "fg_heading": "#000000",
        "fg_disabled": "#a0a0a0",
        "accent": "#3a7ebf",
        "accent_hover": "#5a9bd8",
        "accent_press": "#2c5f8f",
        "warn": "#a05a00",
    },
}

STORE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Cookie": "birthtime=283993201; mature_content=1; wants_mature_content=1; lastagecheckage=1-January-1990",
    "Accept-Language": "en-US,en;q=0.9",
}


def create_steam_session():
    """Create a persistent requests.Session with connection pooling and keep-alive."""
    session = requests.Session()
    session.headers.update(STORE_HEADERS)
    adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=1)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

GENERIC_FIRST_WORDS = {
    "dead", "total", "grand", "call", "age", "world", "dragon", "star",
    "shadow", "night", "dark", "super", "king", "tomb", "house", "home",
    "project", "warhammer", "command", "the", "a", "final", "street",
}

EDITION_SUFFIXES = [
    "game of the year edition", "goty edition", "goty", "definitive edition",
    "enhanced edition", "special edition", "complete edition", "deluxe edition",
    "ultimate edition", "director's cut", "remastered", "remaster", "trilogy",
    "collection", " hd", "playtest", "open beta",
]

FRANCHISES = [
    "Metal Gear Solid", "Metal Gear", "Grand Theft Auto", "Call of Duty",
    "Dark Souls", "Resident Evil", "Fallout", "Elder Scrolls",
    "Assassin's Creed", "Yakuza", "Like a Dragon", "Final Fantasy",
    "Kingdom Hearts", "Batman: Arkham", "Batman™: Arkham", "Borderlands",
    "BioShock", "Tomb Raider", "Mafia", "Hitman", "Sonic", "Danganronpa",
    "Etrian Odyssey", "Total War", "Warhammer 40,000", "Warhammer",
    "Civilization", "Command & Conquer", "Mortal Kombat", "Deus Ex",
    "Dead Rising", "Overlord", "Saints Row", "Left 4 Dead", "Half-Life",
    "Portal", "Counter-Strike", "Team Fortress", "Battlefield", "TEKKEN",
    "Street Fighter", "KING OF FIGHTERS", "Guilty Gear", "Persona",
    "Shin Megami Tensei", "Descent", "Age of Mythology", "Dying Light",
    "Dead Space", "Splinter Cell", "Rainbow Six", "The Division", "Far Cry",
    "Just Cause", "Watch Dogs", "God of War", "Horizon", "Death Stranding",
    "Ace Attorney", "Darksiders", "Divinity", "Dishonored",
    "Dragon Age", "Dragon's Dogma", "Mass Effect", "XCOM",
    "Sid Meier's Civilization", "Age of Empires", "Company of Heroes",
    "Crysis", "Titanfall", "Apex Legends", "Overwatch",
    "Diablo", "World of Warcraft", "StarCraft", "Sekiro", "Nioh",
    "Monster Hunter", "Dragon Quest", "NieR", "Devil May Cry",
    "Ninja Gaiden", "Dynasty Warriors", "Cyberpunk", "Witcher",
    "Gears of War", "Halo", "Forza", "DOOM", "Quake", "Wolfenstein", "Prey",
    "Uncharted", "The Last of Us", "Days Gone", "Ghost of Tsushima",
    "Spider-Man", "Marvel", "Lego", "Plants vs. Zombies", "Rayman",
    "Rocket League", "Red Dead", "L.A. Noire", "Max Payne", "Duke Nukem",
    "Serious Sam", "Painkiller", "Alan Wake", "Control", "Quantum Break",
    "Trine", "Ori and the", "Cuphead", "Hollow Knight", "Hades",
    "Slay the Spire", "Vampire Survivors", "Risk of Rain",
    "Streets of Rage", "Golden Axe", "Shadow Warrior",
]


# ---------- Steam API helpers ----------

def steamid_from_token(token):
    try:
        payload_b64 = token.split(".")[1]
        payload_b64 += "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        return payload.get("sub")
    except Exception:
        return None


def api_get(interface, method, version, token, **params):
    url = f"{BASE}/{interface}/{method}/{version}/"
    params["access_token"] = token
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def get_own_games(token, steamid):
    data = api_get("IPlayerService", "GetOwnedGames", "v0001", token,
                    steamid=steamid, include_appinfo=1,
                    include_played_free_games=1, include_extended_appinfo=1)
    return data.get("response", {}).get("games", [])


def get_family_groupid(token):
    data = api_get("IFamilyGroupsService", "GetFamilyGroupForUser", "v1", token)
    return data.get("response", {}).get("family_groupid")


def get_shared_library(token, family_groupid):
    data = api_get("IFamilyGroupsService", "GetSharedLibraryApps", "v1", token,
                    family_groupid=family_groupid, include_own=1,
                    include_excluded=1, include_free=1, include_non_games=0)
    return data.get("response", {}).get("apps", [])


def fetch_genres(appid, session=None):
    client = session or requests
    try:
        resp = client.get(STORE_API, params={"appids": appid, "l": "english"}, timeout=12)
        if resp.status_code == 429:
            return None  # Rate-limited by Steam
        resp.raise_for_status()
        entry = resp.json().get(str(appid), {})
        if not entry.get("success"):
            return []
        return [g["description"] for g in entry.get("data", {}).get("genres", [])]
    except Exception:
        return []


def guess_series(name):
    for franchise in FRANCHISES:
        if franchise.lower() in name.lower():
            return franchise
    return None


def normalize_name(name):
    n = name.lower()
    n = re.sub(r"[™®©]", "", n)
    n = re.sub(r"\([^)]*\)", "", n)
    for suf in EDITION_SUFFIXES:
        n = n.replace(suf, "")
    n = re.sub(r"[:\-–].*", "", n)
    n = re.sub(r"\s+(i|ii|iii|iv|v|vi|vii|viii|ix|x|[0-9]+)$", "", n.strip())
    return n.strip()


def cluster_key(name):
    words = normalize_name(name).split()
    if not words:
        return None
    first = words[0]
    if first in GENERIC_FIRST_WORDS and len(words) > 1:
        return f"{first} {words[1]}"
    return first


def auto_cluster(names):
    groups = {}
    for n in names:
        key = cluster_key(n)
        if key:
            groups.setdefault(key, []).append(n)
    return {k: v for k, v in groups.items() if len(v) >= 2}


def load_franchise_cache():
    for path in (FRANCHISE_CACHE_FILE, os.path.join(os.path.expanduser("~"), FRANCHISE_CACHE_FILE)):
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except OSError:
                continue
    return {}


def fetch_community_tags(appid, session=None):
    """Scrape the user-voted community tags off a game's public store page
    (the little pill-shaped tags near the top of every store listing, e.g.
    'Souls-like', 'Roguelike', 'Co-op'). No login needed -- same public page
    anyone sees in a browser. Returns None on rate-limit (429), [] on
    failure/no tags found, otherwise a list of tag strings."""
    client = session or requests
    try:
        url = STORE_APP_PAGE.format(appid=appid)
        resp = client.get(url, params={"l": "english"}, timeout=12)
        if resp.status_code == 429:
            return None
        resp.raise_for_status()
        html = resp.text
        tags = re.findall(r'class="app_tag"[^>]*>\s*([^<]+?)\s*</a>', html)
        seen = []
        for t in tags:
            t = t.strip()
            if t and t not in seen:
                seen.append(t)
        return seen[:15]
    except Exception:
        return []


def load_community_tags_cache():
    for path in (COMMUNITY_TAGS_CACHE_FILE, os.path.join(os.path.expanduser("~"), COMMUNITY_TAGS_CACHE_FILE)):
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except OSError:
                continue
    return {}


def load_curated_tags():
    for path in (CURATED_TAGS_FILE, os.path.join(os.path.expanduser("~"), CURATED_TAGS_FILE)):
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except OSError:
                continue
    return {}


def load_categories():
    for path in (CATEGORIES_FILE, os.path.join(os.path.expanduser("~"), CATEGORIES_FILE)):
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except OSError:
                continue
    return {}  # {category_name: [appid, ...]}


# ---------- Steam Collections import (writes to Steam's local config) ----------
#
# Steam's "Collections" (the tag/folder groupings you see in the Library) are
# stored client-side in a per-account file, localconfig.vdf, under a JSON
# blob at WebStorage -> user-collections. This structure is NOT officially
# documented by Valve -- it's reverse-engineered from what the Steam client
# itself writes there. Treat this code as experimental: it backs up the file
# before touching it and supports a dry-run preview for exactly that reason.

COLLECTION_ID_PREFIX = "clm-"  # namespace our generated collections so we never touch Steam's own


def find_steam_path():
    system = platform.system()
    candidates = []
    if system == "Windows":
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
            path, _ = winreg.QueryValueEx(key, "SteamPath")
            candidates.append(path.replace("/", os.sep))
        except Exception:
            pass
        candidates += [r"C:\Program Files (x86)\Steam", r"C:\Program Files\Steam"]
    elif system == "Darwin":
        candidates.append(os.path.expanduser("~/Library/Application Support/Steam"))
    else:
        candidates += [
            os.path.expanduser("~/.steam/steam"),
            os.path.expanduser("~/.local/share/Steam"),
            os.path.expanduser("~/.var/app/com.valvesoftware.Steam/.local/share/Steam"),
        ]
    for c in candidates:
        if c and os.path.isdir(c):
            return c
    return None


def list_userdata_accounts(steam_path):
    userdata = os.path.join(steam_path, "userdata")
    if not os.path.isdir(userdata):
        return []
    return sorted([d for d in os.listdir(userdata) if d.isdigit() and
                   os.path.isdir(os.path.join(userdata, d))])


def steamid_to_accountid(steamid64):
    try:
        return str(int(steamid64) - 76561197960265728)
    except (TypeError, ValueError):
        return None


def is_steam_running():
    """Best-effort check only -- not a guarantee. Always confirmed by the user too."""
    system = platform.system()
    try:
        if system == "Windows":
            out = subprocess.run(["tasklist"], capture_output=True, text=True, timeout=5).stdout.lower()
            return "steam.exe" in out
        else:
            out = subprocess.run(["ps", "-A"], capture_output=True, text=True, timeout=5).stdout.lower()
            return "steam" in out
    except Exception:
        return None  # unknown -- couldn't check


def _find_key_ci(d, key):
    """VDF keys are effectively case-insensitive in practice; find the real
    key spelling so we don't create a duplicate sibling by guessing wrong."""
    for k in d:
        if k.lower() == key.lower():
            return k
    return None


def get_localconfig_path(steam_path, accountid):
    return os.path.join(steam_path, "userdata", str(accountid), "config", "localconfig.vdf")


def load_user_collections(vdf_path):
    """Returns (full_vdf_dict, root_dict, webstorage_dict, collections_dict).
    Raises on I/O or parse failure -- caller should handle."""
    with open(vdf_path, "r", encoding="utf-8", errors="replace") as f:
        data = vdf.load(f, mapper=dict)
    root_key = _find_key_ci(data, "UserLocalConfigStore")
    if not root_key:
        raise ValueError("Couldn't find 'UserLocalConfigStore' at the top of this file -- "
                          "it may not be a normal localconfig.vdf.")
    root = data[root_key]
    ws_key = _find_key_ci(root, "WebStorage")
    if not ws_key:
        root["WebStorage"] = {}
        ws_key = "WebStorage"
    ws = root[ws_key]
    uc_key = _find_key_ci(ws, "user-collections")
    raw = ws.get(uc_key) if uc_key else None
    try:
        collections = json.loads(raw) if raw else {}
    except (TypeError, ValueError):
        collections = {}
    return data, root, ws, collections


def save_localconfig(data, vdf_path):
    """Writes atomically (temp file + replace) so a crash mid-write can't
    leave a half-written, corrupt config file behind."""
    tmp_path = vdf_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        vdf.dump(data, f, pretty=True)
    os.replace(tmp_path, vdf_path)


def make_collection_id(name):
    h = hashlib.md5((COLLECTION_ID_PREFIX + name).encode("utf-8")).hexdigest()[:16]
    return f"{COLLECTION_ID_PREFIX}{h}"


def _normalize_game(g, default_source="Own"):
    """Different script versions have saved steam_library.json with
    slightly different keys over time (e.g. the CLI export uses
    'playtime_hours' with no 'source'/'installed'). Normalize whatever we
    find into the shape the GUI expects, so an older file on disk doesn't
    crash a newer version of the app."""
    return {
        "appid": g.get("appid"),
        "name": g.get("name", "Unknown"),
        "hours": g.get("hours", g.get("playtime_hours", 0)),
        "source": g.get("source", default_source),
        "installed": g.get("installed", ""),
    }


def load_saved_library():
    for path in (LIBRARY_FILE, os.path.join(os.path.expanduser("~"), LIBRARY_FILE)):
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    own = [_normalize_game(g, "Own") for g in data.get("own_games", [])]
                    shared = [_normalize_game(g, "Shared") for g in data.get("shared_games", [])]
                    return own + shared
                elif isinstance(data, list):
                    return [_normalize_game(g) for g in data]
            except OSError:
                continue
    return []


# ---------- GUI ----------

class SteamLibraryApp:
    def __init__(self, root):
        self.root = root
        root.title("Steam Library Explorer")
        root.geometry("1000x650")

        self.games = []  # list of dicts: name, hours, source, installed, appid
        self.genre_cache = {}
        self.community_tags_cache = load_community_tags_cache()
        self.curated_tags = load_curated_tags()  # {appid_str: [selected tag strings]}
        self.categories = load_categories()  # {category_name: [appid, ...]}
        self.category_tag_selection = set()  # tags checked in the Categories tab, persists across searches
        self._add_list_mode = None  # tracks whether the "add game" list is showing "search" or "uncategorized"
        self.steamid = None  # filled in once a token fetch succeeds; used to locate the right userdata folder
        self.curate_selected_appid = None
        self.curate_tag_vars = {}  # tag_text -> tk.BooleanVar, for the currently shown game
        self.msg_queue = queue.Queue()
        self.style = ttk.Style(root)
        self._tk_listboxes = []  # raw tk.Listbox widgets that need manual theme colours
        self._tk_canvases = []   # raw tk.Canvas widgets that need manual theme colours
        self._tk_texts = []      # raw tk.Text widgets that need manual theme colours

        # --- top bar: token entry ---
        top = ttk.Frame(root, padding=10)
        top.pack(fill="x")
        ttk.Label(top, text="Access token:").pack(side="left")
        self.token_var = tk.StringVar()
        self.token_entry = ttk.Entry(top, textvariable=self.token_var, show="*", width=60)
        self.token_entry.pack(side="left", padx=5, fill="x", expand=True)
        self.show_btn = ttk.Button(top, text="Show", width=6, command=self.toggle_show)
        self.show_btn.pack(side="left", padx=2)
        self.fetch_btn = ttk.Button(top, text="Fetch Library", command=self.start_fetch)
        self.fetch_btn.pack(side="left", padx=5)

        # --- second row: utility buttons, so they never get squeezed by the expanding token field above ---
        util_row = ttk.Frame(root, padding=(10, 0))
        util_row.pack(fill="x")
        ttk.Button(util_row, text="Where are my files?", command=self.show_all_file_locations).pack(side="left")
        ttk.Label(util_row, text="Theme:").pack(side="left", padx=(10, 2))
        self.theme_var = tk.StringVar(value="Steam Dark")
        theme_cb = ttk.Combobox(util_row, textvariable=self.theme_var, state="readonly", width=13,
                                 values=list(THEMES.keys()))
        theme_cb.pack(side="left")
        theme_cb.bind("<<ComboboxSelected>>", lambda e: self.apply_theme(self.theme_var.get()))

        # --- status/progress ---
        status_frame = ttk.Frame(root, padding=(10, 0))
        status_frame.pack(fill="x")
        self.status_var = tk.StringVar(value="Paste your token and click Fetch Library.")
        ttk.Label(status_frame, textvariable=self.status_var).pack(side="left")
        self.progress = ttk.Progressbar(status_frame, mode="determinate", length=200)
        self.progress.pack(side="right")

        # --- search bar ---
        search_frame = ttk.Frame(root, padding=(10, 5))
        search_frame.pack(fill="x")
        ttk.Label(search_frame, text="Filter:").pack(side="left")
        self.filter_var = tk.StringVar()
        self.filter_var.trace_add("write", lambda *a: self.refresh_all_tab())
        ttk.Entry(search_frame, textvariable=self.filter_var, width=30).pack(side="left", padx=5)

        # --- tabs ---
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=5)

        # Tab 1: All Games (with Franchise column)
        self.tree_all, all_frame = self._create_tree_panel(self.notebook, ["Name", "Franchise", "Hours", "Source", "Installed"], show_tree=False)
        self.notebook.add(all_frame, text="All Games")

        # Tab 2: By Franchise
        self.series_tab = ttk.Frame(self.notebook)

        # Control Row 1: Action buttons & Speed selector
        series_controls = ttk.Frame(self.series_tab, padding=(5, 5))
        series_controls.pack(fill="x")
        self.franchise_btn = ttk.Button(series_controls, text="Fetch Franchises (Store, no login)",
                                         command=self.start_franchise_fetch, state="disabled")
        self.franchise_btn.pack(side="left", padx=(0, 4))

        ttk.Label(series_controls, text="Speed:").pack(side="left", padx=(6, 2))
        self.speed_var = tk.StringVar(value="Fast (0.4s)")
        speed_cb = ttk.Combobox(series_controls, textvariable=self.speed_var, state="readonly", width=13)
        speed_cb["values"] = ("Fast (0.4s)", "Turbo (0.2s)", "Balanced (0.7s)", "Safe (1.2s)")
        speed_cb.pack(side="left", padx=(0, 6))

        ttk.Button(series_controls, text="Expand All", command=self.expand_series).pack(side="left", padx=2)
        ttk.Button(series_controls, text="Collapse All", command=self.collapse_series).pack(side="left", padx=2)
        ttk.Button(series_controls, text="Open Cache File", command=self.open_cache_file).pack(side="left", padx=2)
        ttk.Button(series_controls, text="Where is my file?", command=self.show_cache_location).pack(side="left", padx=2)

        # Control Row 2: Search and View Mode filters
        series_filter_bar = ttk.Frame(self.series_tab, padding=(5, 2))
        series_filter_bar.pack(fill="x")
        ttk.Label(series_filter_bar, text="Filter Franchises:").pack(side="left", padx=(0, 4))
        self.series_filter_var = tk.StringVar()
        self.series_filter_var.trace_add("write", lambda *a: self.refresh_series_tab())
        ttk.Entry(series_filter_bar, textvariable=self.series_filter_var, width=22).pack(side="left", padx=(0, 8))

        ttk.Label(series_filter_bar, text="View:").pack(side="left", padx=(0, 4))
        self.series_mode_var = tk.StringVar(value="All Franchises & Series")
        mode_cb = ttk.Combobox(series_filter_bar, textvariable=self.series_mode_var, state="readonly", width=24)
        mode_cb["values"] = ("All Franchises & Series", "Official Store Franchises Only (★)", "Multi-Game Only (2+)")
        mode_cb.current(0)
        mode_cb.bind("<<ComboboxSelected>>", lambda e: self.refresh_series_tab())
        mode_cb.pack(side="left", padx=(0, 8))

        self.franchise_lbl = ttk.Label(series_filter_bar, text="", font=("TkDefaultFont", 9, "bold"))
        self.franchise_lbl.pack(side="left", padx=4)

        self.tree_series, series_frame = self._create_tree_panel(self.series_tab, ["Games", "Source"], show_tree=True, tree_heading="Franchise / Game Title")
        series_frame.pack(fill="both", expand=True)
        self.notebook.add(self.series_tab, text="By Franchise")

        # Tab 3: By Genre
        genre_tab = ttk.Frame(self.notebook)
        genre_controls = ttk.Frame(genre_tab, padding=5)
        genre_controls.pack(fill="x")
        self.genre_btn = ttk.Button(genre_controls, text="Fetch Genres (one-time)",
                                     command=self.start_genre_fetch, state="disabled")
        self.genre_btn.pack(side="left", padx=(0, 6))
        ttk.Label(genre_controls, text="Speed:").pack(side="left", padx=(4, 2))
        genre_speed_cb = ttk.Combobox(genre_controls, textvariable=self.speed_var, state="readonly", width=13)
        genre_speed_cb["values"] = ("Fast (0.4s)", "Turbo (0.2s)", "Balanced (0.7s)", "Safe (1.2s)")
        genre_speed_cb.pack(side="left", padx=(0, 4))
        self.tree_genre, genre_frame = self._create_tree_panel(genre_tab, ["Games"], show_tree=True, tree_heading="Genre / Game Title")
        genre_frame.pack(fill="both", expand=True)
        self.notebook.add(genre_tab, text="By Genre")

        # Tab 4: Curate Tags
        self._build_curate_tab()

        # Tab 5: Categories (build categories from tag combinations)
        self._build_categories_tab()

        # Tab 6: Import to Steam
        self._build_import_tab()

        # Automatically load saved library if present
        saved = load_saved_library()
        if saved:
            self.games = saved
            self.refresh_all_tab()
            self.refresh_series_tab()
            self.genre_btn.config(state="normal")
            self.franchise_btn.config(state="normal")
            self.community_tags_btn.config(state="normal")
            self.refresh_curate_game_list()
            self.refresh_tag_listbox()
            self.status_var.set(f"Loaded {len(saved)} games from saved steam_library.json.")
            self.refresh_uncategorized_count()

        self.root.after(100, self.poll_queue)
        self.apply_theme(self.theme_var.get())

    def apply_theme(self, name):
        theme = THEMES.get(name, THEMES["Steam Dark"])
        self.current_theme = name
        style = self.style
        style.theme_use("clam")

        self.root.configure(bg=theme["bg"])

        style.configure(".", background=theme["bg"], foreground=theme["fg"],
                         fieldbackground=theme["input_bg"])
        style.configure("TFrame", background=theme["bg"])
        style.configure("TLabel", background=theme["bg"], foreground=theme["fg"])
        style.configure("TCheckbutton", background=theme["bg"], foreground=theme["fg"])
        style.map("TCheckbutton", background=[("active", theme["bg"])])
        style.configure("TRadiobutton", background=theme["bg"], foreground=theme["fg"])
        style.map("TRadiobutton", background=[("active", theme["bg"])])

        style.configure("TButton", background=theme["accent"], foreground="#ffffff",
                         borderwidth=0, focusthickness=0, padding=6)
        style.map("TButton",
                  background=[("disabled", theme["input_bg"]), ("pressed", theme["accent_press"]),
                              ("active", theme["accent_hover"])],
                  foreground=[("disabled", theme["fg_disabled"])])

        style.configure("TEntry", fieldbackground=theme["input_bg"], foreground=theme["fg"],
                         insertcolor=theme["fg"], borderwidth=1)
        style.configure("TCombobox", fieldbackground=theme["input_bg"], background=theme["input_bg"],
                         foreground=theme["fg"], arrowcolor=theme["fg"])
        style.map("TCombobox",
                  fieldbackground=[("readonly", theme["input_bg"])],
                  selectbackground=[("readonly", theme["input_bg"])],
                  selectforeground=[("readonly", theme["fg"])])

        style.configure("TNotebook", background=theme["bg"], borderwidth=0)
        style.configure("TNotebook.Tab", background=theme["panel"], foreground=theme["fg_dim"], padding=(10, 5))
        style.map("TNotebook.Tab",
                  background=[("selected", theme["accent"])],
                  foreground=[("selected", "#ffffff")])

        style.configure("Treeview", background=theme["panel"], fieldbackground=theme["panel"],
                         foreground=theme["fg"], borderwidth=0, rowheight=22)
        style.configure("Treeview.Heading", background=theme["input_bg"], foreground=theme["fg_heading"],
                         relief="flat")
        style.map("Treeview.Heading", background=[("active", theme["accent_hover"])])
        style.map("Treeview", background=[("selected", theme["accent"])], foreground=[("selected", "#ffffff")])

        style.configure("Vertical.TScrollbar", background=theme["panel"], troughcolor=theme["bg"],
                         bordercolor=theme["bg"], arrowcolor=theme["fg"])
        style.configure("Horizontal.TScrollbar", background=theme["panel"], troughcolor=theme["bg"],
                         bordercolor=theme["bg"], arrowcolor=theme["fg"])
        style.configure("Horizontal.TProgressbar", background=theme["accent"], troughcolor=theme["panel"])

        # Raw tk widgets (not covered by ttk styles) need manual colours
        for lb in self._tk_listboxes:
            lb.configure(bg=theme["input_bg"], fg=theme["fg"], selectbackground=theme["accent"],
                         selectforeground="#ffffff", highlightthickness=0, borderwidth=0)
        for cv in self._tk_canvases:
            cv.configure(bg=theme["bg"])
        for txt in self._tk_texts:
            txt.configure(bg=theme["input_bg"], fg=theme["fg"], insertbackground=theme["fg"],
                         selectbackground=theme["accent"], selectforeground="#ffffff",
                         highlightthickness=0, borderwidth=0)

        if hasattr(self, "uncategorized_lbl"):
            self.uncategorized_lbl.configure(foreground=theme["warn"])

    def _create_tree_panel(self, parent, columns, show_tree=False, tree_heading=""):
        container = ttk.Frame(parent)

        # Standard Tkinter tuple syntax for show option
        show_opt = ("tree", "headings") if show_tree else ("headings",)
        tree = ttk.Treeview(container, columns=columns, show=show_opt)

        if show_tree:
            tree.heading("#0", text=tree_heading, anchor="w")
            tree.column("#0", width=420, minwidth=220, stretch=True, anchor="w")

        for c in columns:
            tree.heading(c, text=c)
            if c in ("Games", "Count"):
                tree.column(c, width=75, minwidth=60, stretch=False, anchor="center")
            elif c in ("Hours", "Installed"):
                tree.column(c, width=80, minwidth=60, stretch=False, anchor="center")
            elif c == "Source":
                tree.column(c, width=190, minwidth=140, stretch=False, anchor="w")
            elif c == "Franchise":
                tree.column(c, width=200, minwidth=120, stretch=True, anchor="w")
            else:
                tree.column(c, width=320, minwidth=180, stretch=True, anchor="w")

        vscroll = ttk.Scrollbar(container, orient="vertical", command=tree.yview)
        vscroll.pack(side="right", fill="y")
        tree.configure(yscrollcommand=vscroll.set)

        tree.pack(side="left", fill="both", expand=True)
        return tree, container

    def _build_curate_tab(self):
        tab = ttk.Frame(self.notebook)

        # Top controls: bulk-fetch community tags + speed (reuses the same
        # speed setting as genre/franchise fetches)
        controls = ttk.Frame(tab, padding=(5, 5))
        controls.pack(fill="x")
        self.community_tags_btn = ttk.Button(
            controls, text="Fetch Community Tags (Store, no login)",
            command=self.start_community_tag_fetch, state="disabled")
        self.community_tags_btn.pack(side="left", padx=(0, 6))
        self.curate_status_lbl = ttk.Label(controls, text="", font=("TkDefaultFont", 9))
        self.curate_status_lbl.pack(side="left", padx=6)

        # Two-pane layout: game list on the left, tag checkboxes on the right
        body = ttk.Frame(tab)
        body.pack(fill="both", expand=True, padx=5, pady=5)

        left = ttk.Frame(body)
        left.pack(side="left", fill="y", padx=(0, 8))
        ttk.Label(left, text="Filter games:").pack(anchor="w")
        self.curate_filter_var = tk.StringVar()
        self.curate_filter_var.trace_add("write", lambda *a: self.refresh_curate_game_list())
        ttk.Entry(left, textvariable=self.curate_filter_var, width=32).pack(fill="x", pady=(0, 4))

        list_frame = ttk.Frame(left)
        list_frame.pack(fill="both", expand=True)
        self.curate_listbox = tk.Listbox(list_frame, width=40, height=25, exportselection=False)
        self._tk_listboxes.append(self.curate_listbox)
        self.curate_listbox.pack(side="left", fill="both", expand=True)
        curate_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.curate_listbox.yview)
        curate_scroll.pack(side="right", fill="y")
        self.curate_listbox.configure(yscrollcommand=curate_scroll.set)
        self.curate_listbox.bind("<<ListboxSelect>>", self.on_curate_game_select)
        self._curate_list_appids = []  # parallel list: row index -> appid

        # Right pane: tag checkboxes for whichever game is selected
        right = ttk.Frame(body)
        right.pack(side="left", fill="both", expand=True)
        self.curate_game_lbl = ttk.Label(right, text="Select a game on the left to curate its tags.",
                                          font=("TkDefaultFont", 10, "bold"))
        self.curate_game_lbl.pack(anchor="w", pady=(0, 6))

        tag_canvas_frame = ttk.Frame(right)
        tag_canvas_frame.pack(fill="both", expand=True)
        self.curate_tag_canvas = tk.Canvas(tag_canvas_frame, highlightthickness=0)
        self._tk_canvases.append(self.curate_tag_canvas)
        tag_scroll = ttk.Scrollbar(tag_canvas_frame, orient="vertical", command=self.curate_tag_canvas.yview)
        self.curate_tag_frame = ttk.Frame(self.curate_tag_canvas)
        self.curate_tag_frame.bind(
            "<Configure>",
            lambda e: self.curate_tag_canvas.configure(scrollregion=self.curate_tag_canvas.bbox("all")))
        self.curate_tag_canvas.create_window((0, 0), window=self.curate_tag_frame, anchor="nw")
        self.curate_tag_canvas.configure(yscrollcommand=tag_scroll.set)
        self.curate_tag_canvas.pack(side="left", fill="both", expand=True)
        tag_scroll.pack(side="right", fill="y")

        add_row = ttk.Frame(right)
        add_row.pack(fill="x", pady=(6, 0))
        ttk.Label(add_row, text="Add custom tag:").pack(side="left")
        self.curate_new_tag_var = tk.StringVar()
        new_tag_entry = ttk.Entry(add_row, textvariable=self.curate_new_tag_var, width=25)
        new_tag_entry.pack(side="left", padx=5)
        new_tag_entry.bind("<Return>", lambda e: self.add_custom_tag())
        ttk.Button(add_row, text="Add", command=self.add_custom_tag).pack(side="left")

        self.notebook.add(tab, text="Curate Tags")

    def get_available_tags_for_game(self, appid, name):
        """Union of every tag source we know about for one game, plus
        anything already curated, so nothing gets silently lost."""
        appid_s = str(appid)
        tags = set()
        tags.update(self.community_tags_cache.get(appid_s, []) or [])
        tags.update(self.genre_cache.get(appid_s, []) or [])
        fc = load_franchise_cache()
        tags.update(fc.get(appid_s, []) or [])
        curated_series = guess_series(name)
        if curated_series:
            tags.add(curated_series)
        tags.update(self.curated_tags.get(appid_s, []) or [])
        return sorted(tags, key=str.lower)

    def refresh_curate_game_list(self):
        filt = self.curate_filter_var.get().strip().lower() if hasattr(self, "curate_filter_var") else ""
        self.curate_listbox.delete(0, "end")
        self._curate_list_appids = []
        for g in sorted(self.games, key=lambda g: g["name"].lower()):
            if filt and filt not in g["name"].lower():
                continue
            n_curated = len(self.curated_tags.get(str(g["appid"]), []) or [])
            label = f"{g['name']}" + (f"  ({n_curated} tags)" if n_curated else "")
            self.curate_listbox.insert("end", label)
            self._curate_list_appids.append(g["appid"])

    def on_curate_game_select(self, event=None):
        sel = self.curate_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx >= len(self._curate_list_appids):
            return
        appid = self._curate_list_appids[idx]
        game = next((g for g in self.games if g["appid"] == appid), None)
        if not game:
            return
        self.curate_selected_appid = appid
        self.curate_game_lbl.config(text=game["name"])
        self.rebuild_tag_checkboxes(appid, game["name"])

    def rebuild_tag_checkboxes(self, appid, name):
        for child in self.curate_tag_frame.winfo_children():
            child.destroy()
        self.curate_tag_vars = {}

        appid_s = str(appid)
        selected = set(self.curated_tags.get(appid_s, []) or [])
        available = self.get_available_tags_for_game(appid, name)

        if not available:
            ttk.Label(self.curate_tag_frame,
                      text="No tags found yet for this game. Try 'Fetch Community Tags' above,\n"
                           "or just add a custom tag below.",
                      justify="left").pack(anchor="w", pady=10)
            return

        for tag in available:
            var = tk.BooleanVar(value=tag in selected)
            cb = ttk.Checkbutton(
                self.curate_tag_frame, text=tag, variable=var,
                command=lambda t=tag, v=var: self.toggle_tag(appid_s, t, v))
            cb.pack(anchor="w", pady=1)
            self.curate_tag_vars[tag] = var

    def toggle_tag(self, appid_s, tag, var):
        current = set(self.curated_tags.get(appid_s, []) or [])
        if var.get():
            current.add(tag)
        else:
            current.discard(tag)
        self.curated_tags[appid_s] = sorted(current, key=str.lower)
        self._safe_save_json(CURATED_TAGS_FILE, self.curated_tags)
        self.refresh_curate_game_list()  # updates the "(N tags)" count in the list

    def add_custom_tag(self):
        if self.curate_selected_appid is None:
            messagebox.showinfo("No game selected", "Select a game on the left first.")
            return
        new_tag = self.curate_new_tag_var.get().strip()
        if not new_tag:
            return
        appid_s = str(self.curate_selected_appid)
        current = set(self.curated_tags.get(appid_s, []) or [])
        if new_tag in current:
            self.curate_new_tag_var.set("")
            return
        current.add(new_tag)
        self.curated_tags[appid_s] = sorted(current, key=str.lower)
        self._safe_save_json(CURATED_TAGS_FILE, self.curated_tags)
        self.curate_new_tag_var.set("")
        game = next((g for g in self.games if g["appid"] == self.curate_selected_appid), None)
        if game:
            self.rebuild_tag_checkboxes(self.curate_selected_appid, game["name"])
        self.refresh_curate_game_list()

    # ---------- Community tag bulk fetch ----------

    def start_community_tag_fetch(self):
        if not self.games:
            return
        self.community_tags_btn.config(state="disabled")
        self.curate_status_lbl.config(text="Starting community tag fetch...")
        threading.Thread(target=self._community_tag_worker, daemon=True).start()

    def _community_tag_worker(self):
        cache = self.community_tags_cache
        to_fetch = [g for g in self.games if str(g["appid"]) not in cache]
        total = len(to_fetch)
        if total == 0:
            self.msg_queue.put(("curate_status", f"All {len(cache)} games already cached."))
            self.msg_queue.put(("community_tags_done", cache))
            return

        session = create_steam_session()
        delay = self._get_delay()
        self.msg_queue.put(("progress_max", total or 1))
        warned = False

        for i, g in enumerate(to_fetch, 1):
            tags = fetch_community_tags(g["appid"], session=session)
            if tags is None:
                self.msg_queue.put(("curate_status", f"Steam rate limit (429) on {g['name']}. Pausing 15s..."))
                time.sleep(15.0)
                tags = fetch_community_tags(g["appid"], session=session)
                if tags is None:
                    self.msg_queue.put(("curate_status", "Still cooling down. Pausing 20s..."))
                    time.sleep(20.0)
                    tags = fetch_community_tags(g["appid"], session=session) or []
            cache[str(g["appid"])] = tags
            if i % 5 == 0 or i == total:
                saved = self._safe_save_json(COMMUNITY_TAGS_CACHE_FILE, cache) if not warned else True
                if not saved:
                    warned = True
                self.msg_queue.put(("curate_status", f"Fetching community tags... {i}/{total}"))
                self.msg_queue.put(("progress", i))
            time.sleep(delay)
        self._safe_save_json(COMMUNITY_TAGS_CACHE_FILE, cache)
        self.community_tags_cache = cache
        self.msg_queue.put(("community_tags_done", cache))

    # ---------- Categories tab (build categories from tag combinations) ----------

    def _build_categories_tab(self):
        tab = ttk.Frame(self.notebook)

        # Top row: which category we're currently editing
        top_row = ttk.Frame(tab, padding=(5, 5))
        top_row.pack(fill="x")
        ttk.Label(top_row, text="Category:").pack(side="left")
        self.category_var = tk.StringVar()
        self.category_cb = ttk.Combobox(top_row, textvariable=self.category_var, state="readonly", width=28)
        self.category_cb["values"] = sorted(self.categories.keys())
        self.category_cb.bind("<<ComboboxSelected>>", lambda e: self.refresh_category_members_list())
        self.category_cb.pack(side="left", padx=5)
        ttk.Button(top_row, text="New", command=self.new_category).pack(side="left", padx=2)
        ttk.Button(top_row, text="Rename", command=self.rename_category).pack(side="left", padx=2)
        ttk.Button(top_row, text="Delete", command=self.delete_category).pack(side="left", padx=2)
        self.category_count_lbl = ttk.Label(top_row, text="", font=("TkDefaultFont", 9, "bold"))
        self.category_count_lbl.pack(side="left", padx=10)
        self.uncategorized_lbl = ttk.Label(top_row, text="", font=("TkDefaultFont", 9, "bold"))
        self.uncategorized_lbl.pack(side="left", padx=10)

        body = ttk.Frame(tab)
        body.pack(fill="both", expand=True, padx=5, pady=5)

        # --- Left: tag pool ---
        left = ttk.Frame(body)
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))
        ttk.Label(left, text="Tags (check as many as you like, across as many searches as you like):",
                  font=("TkDefaultFont", 9, "bold"), wraplength=280, justify="left").pack(anchor="w")
        filter_row = ttk.Frame(left)
        filter_row.pack(fill="x", pady=(4, 0))
        ttk.Label(filter_row, text="Filter tags:").pack(side="left")
        self.tag_type_var = tk.StringVar(value="All")
        tag_type_cb = ttk.Combobox(filter_row, textvariable=self.tag_type_var, state="readonly", width=11,
                                    values=["All", "Franchise", "Genre", "Community"])
        tag_type_cb.pack(side="right")
        tag_type_cb.bind("<<ComboboxSelected>>", lambda e: self.refresh_tag_listbox())
        self.tag_filter_var = tk.StringVar()
        self.tag_filter_var.trace_add("write", lambda *a: self.refresh_tag_listbox())
        ttk.Entry(left, textvariable=self.tag_filter_var, width=28).pack(fill="x", pady=(2, 4))

        tag_canvas_frame = ttk.Frame(left)
        tag_canvas_frame.pack(fill="both", expand=True)
        self.category_tag_canvas = tk.Canvas(tag_canvas_frame, highlightthickness=0)
        self._tk_canvases.append(self.category_tag_canvas)
        tag_scroll = ttk.Scrollbar(tag_canvas_frame, orient="vertical", command=self.category_tag_canvas.yview)
        self.category_tag_inner = ttk.Frame(self.category_tag_canvas)
        self.category_tag_inner.bind(
            "<Configure>",
            lambda e: self.category_tag_canvas.configure(scrollregion=self.category_tag_canvas.bbox("all")))
        self.category_tag_canvas.create_window((0, 0), window=self.category_tag_inner, anchor="nw")
        self.category_tag_canvas.configure(yscrollcommand=tag_scroll.set)
        self.category_tag_canvas.pack(side="left", fill="both", expand=True)
        tag_scroll.pack(side="right", fill="y")

        self.tag_match_mode = tk.StringVar(value="any")
        mode_row = ttk.Frame(left)
        mode_row.pack(fill="x", pady=4)
        ttk.Radiobutton(mode_row, text="Match ANY checked tag (OR)", variable=self.tag_match_mode,
                        value="any").pack(anchor="w")
        ttk.Radiobutton(mode_row, text="Match ALL checked tags (AND)", variable=self.tag_match_mode,
                        value="all").pack(anchor="w")

        self.selected_tags_lbl = ttk.Label(left, text="Checked tags: (none)", wraplength=280, justify="left")
        self.selected_tags_lbl.pack(fill="x", pady=(2, 4))

        btn_row = ttk.Frame(left)
        btn_row.pack(fill="x")
        ttk.Button(btn_row, text="Add Matching Games to Category \u2192",
                   command=self.add_matching_games_to_category).pack(side="left", fill="x", expand=True)
        ttk.Button(btn_row, text="Clear Checks", command=self.clear_selected_tags).pack(side="left", padx=(4, 0))
        ttk.Button(left, text="Refresh Tag List", command=self.refresh_tag_listbox).pack(fill="x", pady=(2, 0))

        # --- Right: category members + manual add ---
        right = ttk.Frame(body)
        right.pack(side="left", fill="both", expand=True)
        ttk.Label(right, text="Games in this category:", font=("TkDefaultFont", 9, "bold")).pack(anchor="w")
        members_frame = ttk.Frame(right)
        members_frame.pack(fill="both", expand=True)
        self.category_members_listbox = tk.Listbox(members_frame, selectmode="extended", exportselection=False)
        self._tk_listboxes.append(self.category_members_listbox)
        self.category_members_listbox.pack(side="left", fill="both", expand=True)
        members_scroll = ttk.Scrollbar(members_frame, orient="vertical", command=self.category_members_listbox.yview)
        members_scroll.pack(side="right", fill="y")
        self.category_members_listbox.configure(yscrollcommand=members_scroll.set)
        ttk.Button(right, text="Remove Selected", command=self.remove_selected_from_category).pack(fill="x", pady=(2, 8))

        ttk.Label(right, text="Add a game manually:", font=("TkDefaultFont", 9, "bold")).pack(anchor="w")
        add_search_row = ttk.Frame(right)
        add_search_row.pack(fill="x")
        self.add_game_search_var = tk.StringVar()
        self.add_game_search_var.trace_add("write", lambda *a: self.refresh_add_game_search_list())
        ttk.Entry(add_search_row, textvariable=self.add_game_search_var, width=22).pack(side="left", fill="x", expand=True, pady=(0, 4))
        ttk.Button(add_search_row, text="Show Uncategorized", command=self.show_uncategorized_in_add_list).pack(side="left", padx=(4, 0))
        add_frame = ttk.Frame(right)
        add_frame.pack(fill="both", expand=True)
        self.add_game_listbox = tk.Listbox(add_frame, selectmode="extended", exportselection=False, height=8)
        self._tk_listboxes.append(self.add_game_listbox)
        self.add_game_listbox.pack(side="left", fill="both", expand=True)
        add_scroll = ttk.Scrollbar(add_frame, orient="vertical", command=self.add_game_listbox.yview)
        add_scroll.pack(side="right", fill="y")
        self.add_game_listbox.configure(yscrollcommand=add_scroll.set)
        self._add_game_search_appids = []
        ttk.Button(right, text="Add Selected", command=self.add_selected_games_to_category).pack(fill="x", pady=(2, 0))

        self.notebook.add(tab, text="Categories")

    def build_tag_pool(self):
        """Merge community tags, genres, and franchise/curated-series matches
        into one {tag: set(appid)} pool covering the whole library. Also
        tracks which source(s) each tag came from, so the Categories tab can
        filter to e.g. 'Franchises only'."""
        pool = {}
        sources = {}  # tag -> set of source labels ("Franchise", "Genre", "Community")
        franchise_cache = load_franchise_cache()
        for g in self.games:
            appid_s = str(g["appid"])
            appid = g["appid"]

            def add(tag, source):
                pool.setdefault(tag, set()).add(appid)
                sources.setdefault(tag, set()).add(source)

            for t in (self.community_tags_cache.get(appid_s, []) or []):
                add(t, "Community")
            for t in (self.genre_cache.get(appid_s, []) or []):
                add(t, "Genre")
            for t in (franchise_cache.get(appid_s, []) or []):
                add(t, "Franchise")
            series = guess_series(g["name"])
            if series:
                add(series, "Franchise")  # curated series list is franchise data too, just heuristic-sourced

        self._tag_sources = sources
        return pool

    def refresh_tag_listbox(self):
        pool = self.build_tag_pool()
        self._tag_pool = pool  # cache for add_matching_games_to_category
        sources = getattr(self, "_tag_sources", {})
        filt = self.tag_filter_var.get().strip().lower() if hasattr(self, "tag_filter_var") else ""
        type_filter = self.tag_type_var.get() if hasattr(self, "tag_type_var") else "All"

        items = []
        for tag, appids in pool.items():
            if filt and filt not in tag.lower():
                continue
            tag_sources = sources.get(tag, set())
            if type_filter != "All" and type_filter not in tag_sources:
                continue
            items.append((tag, len(appids), tag_sources))
        items.sort(key=lambda kv: (-kv[1], kv[0].lower()))

        for child in self.category_tag_inner.winfo_children():
            child.destroy()

        if not hasattr(self, "category_tag_selection"):
            self.category_tag_selection = set()

        icon_for = {"Franchise": "\u2605 ", "Genre": "\u25c6 ", "Community": ""}  # ★ Franchise, ◆ Genre
        for tag, count, tag_sources in items:
            icon = icon_for.get("Franchise", "") if "Franchise" in tag_sources else (
                icon_for.get("Genre", "") if "Genre" in tag_sources else "")
            var = tk.BooleanVar(value=tag in self.category_tag_selection)
            cb = ttk.Checkbutton(
                self.category_tag_inner, text=f"{icon}{tag}  ({count})", variable=var,
                command=lambda t=tag, v=var: self.toggle_category_tag(t, v))
            cb.pack(anchor="w", pady=1)

        self.update_selected_tags_label()

    def toggle_category_tag(self, tag, var):
        if var.get():
            self.category_tag_selection.add(tag)
        else:
            self.category_tag_selection.discard(tag)
        self.update_selected_tags_label()

    def update_selected_tags_label(self):
        if self.category_tag_selection:
            self.selected_tags_lbl.config(text="Checked tags: " + ", ".join(sorted(self.category_tag_selection)))
        else:
            self.selected_tags_lbl.config(text="Checked tags: (none)")

    def clear_selected_tags(self):
        self.category_tag_selection = set()
        self.refresh_tag_listbox()

    def new_category(self):
        name = simpledialog.askstring("New Category", "Category name (e.g. 'Stealth', 'FPS'):", parent=self.root)
        if not name:
            return
        name = name.strip()
        if not name:
            return
        if name not in self.categories:
            self.categories[name] = []
            self._safe_save_json(CATEGORIES_FILE, self.categories)
        self.category_cb["values"] = sorted(self.categories.keys())
        self.category_var.set(name)
        self.refresh_category_members_list()

    def rename_category(self):
        old = self.category_var.get()
        if not old:
            messagebox.showinfo("No category", "Select a category first.")
            return
        new = simpledialog.askstring("Rename Category", "New name:", initialvalue=old, parent=self.root)
        if not new or new.strip() == old:
            return
        new = new.strip()
        self.categories[new] = self.categories.pop(old)
        self._safe_save_json(CATEGORIES_FILE, self.categories)
        self.category_cb["values"] = sorted(self.categories.keys())
        self.category_var.set(new)
        self.refresh_category_members_list()

    def delete_category(self):
        name = self.category_var.get()
        if not name:
            return
        if not messagebox.askyesno("Delete Category", f"Delete '{name}'? This can't be undone."):
            return
        self.categories.pop(name, None)
        self._safe_save_json(CATEGORIES_FILE, self.categories)
        self.category_cb["values"] = sorted(self.categories.keys())
        self.category_var.set("")
        self.category_members_listbox.delete(0, "end")
        self.category_count_lbl.config(text="")
        self.refresh_uncategorized_count()

    def _ensure_active_category(self):
        name = self.category_var.get()
        if not name:
            messagebox.showinfo("No category selected", "Create or select a category first (top-left).")
            return None
        return name

    def refresh_category_members_list(self):
        name = self.category_var.get()
        self.category_members_listbox.delete(0, "end")
        if not name:
            self.category_count_lbl.config(text="")
        else:
            appids = self.categories.get(name, [])
            by_appid = {g["appid"]: g["name"] for g in self.games}
            for appid in sorted(appids, key=lambda a: by_appid.get(a, "").lower()):
                self.category_members_listbox.insert("end", by_appid.get(appid, f"(unknown appid {appid})"))
            self.category_count_lbl.config(text=f"{len(appids)} games")
        self.refresh_uncategorized_count()

    def get_uncategorized_games(self):
        categorized = set()
        for appids in self.categories.values():
            categorized.update(appids)
        return [g for g in self.games if g["appid"] not in categorized]

    def refresh_uncategorized_count(self):
        if not self.games:
            self.uncategorized_lbl.config(text="")
            return
        n = len(self.get_uncategorized_games())
        self.uncategorized_lbl.config(text=f"{n} of {len(self.games)} games not in any category yet")

    def show_uncategorized_in_add_list(self, _silent=False):
        self.add_game_search_var.set("")  # clear any text filter so it doesn't fight this view
        uncategorized = sorted(self.get_uncategorized_games(), key=lambda g: g["name"].lower())
        self.add_game_listbox.delete(0, "end")
        self._add_game_search_appids = []
        for g in uncategorized:
            self.add_game_listbox.insert("end", g["name"])
            self._add_game_search_appids.append(g["appid"])
        self._add_list_mode = "uncategorized"
        if not uncategorized and not _silent:
            messagebox.showinfo("All categorized!", "Every game in your library is in at least one category.")

    def add_matching_games_to_category(self):
        name = self._ensure_active_category()
        if not name:
            return
        selected_tags = list(getattr(self, "category_tag_selection", set()))
        if not selected_tags:
            messagebox.showinfo("No tags checked", "Check one or more tags on the left first "
                                                     "(you can search multiple times before adding).")
            return
        pool = getattr(self, "_tag_pool", None) or self.build_tag_pool()

        sets = [pool.get(t, set()) for t in selected_tags]
        if self.tag_match_mode.get() == "all":
            matched = set.intersection(*sets) if sets else set()
        else:
            matched = set.union(*sets) if sets else set()

        current = set(self.categories.get(name, []))
        added = len(matched - current)
        current.update(matched)
        self.categories[name] = sorted(current)
        self._safe_save_json(CATEGORIES_FILE, self.categories)
        self.refresh_category_members_list()
        if getattr(self, "_add_list_mode", None) == "uncategorized":
            self.show_uncategorized_in_add_list(_silent=True)
        messagebox.showinfo("Added", f"Added {added} new game(s) to '{name}' "
                                       f"({len(matched)} total matched that tag combination).")

    def remove_selected_from_category(self):
        name = self.category_var.get()
        if not name:
            return
        sel = self.category_members_listbox.curselection()
        if not sel:
            return
        selected_names = {self.category_members_listbox.get(i) for i in sel}
        by_name = {g["name"]: g["appid"] for g in self.games}
        to_remove = {by_name[n] for n in selected_names if n in by_name}
        current = [a for a in self.categories.get(name, []) if a not in to_remove]
        self.categories[name] = current
        self._safe_save_json(CATEGORIES_FILE, self.categories)
        self.refresh_category_members_list()

    def refresh_add_game_search_list(self):
        filt = self.add_game_search_var.get().strip().lower()
        self.add_game_listbox.delete(0, "end")
        self._add_game_search_appids = []
        if not filt:
            return  # don't dump the whole library until they start typing
        self._add_list_mode = "search"
        for g in sorted(self.games, key=lambda g: g["name"].lower()):
            if filt in g["name"].lower():
                self.add_game_listbox.insert("end", g["name"])
                self._add_game_search_appids.append(g["appid"])

    def add_selected_games_to_category(self):
        name = self._ensure_active_category()
        if not name:
            return
        sel = self.add_game_listbox.curselection()
        if not sel:
            return
        appids_to_add = {self._add_game_search_appids[i] for i in sel}
        current = set(self.categories.get(name, []))
        current.update(appids_to_add)
        self.categories[name] = sorted(current)
        self._safe_save_json(CATEGORIES_FILE, self.categories)
        self.refresh_category_members_list()
        if getattr(self, "_add_list_mode", None) == "uncategorized":
            self.show_uncategorized_in_add_list(_silent=True)

    # ---------- Import to Steam tab ----------

    def _build_import_tab(self):
        tab = ttk.Frame(self.notebook)

        warn_text = (
            "This writes directly to a Steam configuration file (localconfig.vdf) to turn your "
            "Categories above into real Steam Library Collections. It's based on reverse-engineered, "
            "undocumented Steam internals -- not an official feature -- so treat it as experimental.\n\n"
            "Before importing: fully close Steam (including background/tray processes), and use "
            "Preview (Dry Run) first to see exactly what would change. A timestamped backup of the "
            "file is made automatically before anything is written."
        )
        if vdf is None:
            warn_text += "\n\n⚠ The 'vdf' package isn't installed. Run: pip install vdf"
        warn_lbl = ttk.Label(tab, text=warn_text, wraplength=800, justify="left", padding=10)
        warn_lbl.pack(fill="x")

        loc_frame = ttk.Frame(tab, padding=(10, 0))
        loc_frame.pack(fill="x")
        ttk.Label(loc_frame, text="Steam install path:").grid(row=0, column=0, sticky="w", pady=2)
        self.import_steam_path_var = tk.StringVar(value=find_steam_path() or "")
        ttk.Entry(loc_frame, textvariable=self.import_steam_path_var, width=55).grid(row=0, column=1, sticky="we", padx=5)

        ttk.Label(loc_frame, text="Account ID (numeric userdata folder):").grid(row=1, column=0, sticky="w", pady=2)
        self.import_accountid_var = tk.StringVar(
            value=steamid_to_accountid(self.steamid) if self.steamid else "")
        ttk.Entry(loc_frame, textvariable=self.import_accountid_var, width=20).grid(row=1, column=1, sticky="w", padx=5)
        ttk.Button(loc_frame, text="Auto-Detect", command=self.auto_detect_steam_location).grid(row=1, column=2, padx=5)
        loc_frame.columnconfigure(1, weight=1)

        status_row = ttk.Frame(tab, padding=(10, 4))
        status_row.pack(fill="x")
        self.steam_running_lbl = ttk.Label(status_row, text="Steam running status: unknown")
        self.steam_running_lbl.pack(side="left")
        ttk.Button(status_row, text="Re-check", command=self.check_steam_running_status).pack(side="left", padx=8)

        confirm_row = ttk.Frame(tab, padding=(10, 4))
        confirm_row.pack(fill="x")
        self.import_confirm_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(confirm_row, text="I've fully closed Steam and understand this modifies a Steam config file directly",
                        variable=self.import_confirm_var).pack(anchor="w")

        btn_row = ttk.Frame(tab, padding=(10, 4))
        btn_row.pack(fill="x")
        ttk.Button(btn_row, text="Preview Changes (Dry Run)", command=lambda: self.run_steam_import(dry_run=True)).pack(side="left")
        ttk.Button(btn_row, text="Backup & Import Now", command=lambda: self.run_steam_import(dry_run=False)).pack(side="left", padx=8)

        log_frame = ttk.Frame(tab, padding=(10, 4))
        log_frame.pack(fill="both", expand=True)
        self.import_log = tk.Text(log_frame, height=16, wrap="word", state="disabled")
        self.import_log.pack(side="left", fill="both", expand=True)
        log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.import_log.yview)
        log_scroll.pack(side="right", fill="y")
        self.import_log.configure(yscrollcommand=log_scroll.set)
        self._tk_texts.append(self.import_log)

        self.notebook.add(tab, text="Import to Steam")
        self.check_steam_running_status()

    def import_log_write(self, msg):
        self.import_log.configure(state="normal")
        self.import_log.insert("end", msg + "\n")
        self.import_log.see("end")
        self.import_log.configure(state="disabled")

    def auto_detect_steam_location(self):
        path = find_steam_path()
        if path:
            self.import_steam_path_var.set(path)
        else:
            messagebox.showwarning("Not found", "Couldn't auto-detect your Steam install folder. "
                                                  "Enter it manually.")
            return

        if self.steamid:
            acc = steamid_to_accountid(self.steamid)
            if acc:
                self.import_accountid_var.set(acc)
                self.import_log_write(f"Using account ID {acc} (derived from your fetched SteamID).")
                return

        accounts = list_userdata_accounts(path)
        if len(accounts) == 1:
            self.import_accountid_var.set(accounts[0])
            self.import_log_write(f"Found one userdata account folder, using {accounts[0]}.")
        elif len(accounts) > 1:
            self.import_log_write(f"Found multiple userdata accounts: {', '.join(accounts)}. "
                                   f"Fetch your library with your token first so the right one is picked "
                                   f"automatically, or type the correct ID in manually.")
        else:
            self.import_log_write("No userdata account folders found under this Steam path.")

    def check_steam_running_status(self):
        running = is_steam_running()
        if running is True:
            self.steam_running_lbl.config(text="Steam running status: \u26a0 Steam appears to be RUNNING -- close it first")
        elif running is False:
            self.steam_running_lbl.config(text="Steam running status: \u2713 Steam doesn't appear to be running")
        else:
            self.steam_running_lbl.config(text="Steam running status: couldn't determine -- check manually")

    def run_steam_import(self, dry_run):
        if vdf is None:
            messagebox.showerror("Missing dependency", "Install the 'vdf' package first:\n\npip install vdf")
            return
        if not self.categories:
            messagebox.showinfo("No categories", "Build at least one category in the Categories tab first.")
            return
        if not dry_run and not self.import_confirm_var.get():
            messagebox.showwarning("Confirmation required",
                                    "Please tick the confirmation checkbox first -- this step writes "
                                    "directly to a Steam config file.")
            return

        steam_path = self.import_steam_path_var.get().strip()
        accountid = self.import_accountid_var.get().strip()
        if not steam_path or not os.path.isdir(steam_path):
            messagebox.showerror("Invalid Steam path", "Set a valid Steam install path first (Auto-Detect above).")
            return
        if not accountid or not accountid.isdigit():
            messagebox.showerror("Invalid Account ID", "Set a valid numeric account ID first (Auto-Detect above).")
            return

        vdf_path = get_localconfig_path(steam_path, accountid)
        if not os.path.isfile(vdf_path):
            messagebox.showerror("Not found", f"Couldn't find:\n{vdf_path}\n\n"
                                               f"Check the Steam path and Account ID.")
            return

        self.import_log_write(f"\n{'PREVIEW (dry run)' if dry_run else 'IMPORTING'} -- {vdf_path}")
        try:
            data, root, ws, collections = load_user_collections(vdf_path)
        except Exception as e:
            self.import_log_write(f"Failed to read/parse localconfig.vdf: {e}")
            messagebox.showerror("Read failed", f"Couldn't read or parse this file:\n{e}")
            return

        changed = False
        for name, appids in self.categories.items():
            if not appids:
                continue
            cid = make_collection_id(name)
            existing = collections.get(cid, {})
            existing_added = set(existing.get("added", []))
            new_added = set(appids)
            if existing_added != new_added:
                changed = True
            self.import_log_write(
                f"  '{name}' -> {len(new_added)} game(s) "
                f"({'new collection' if not existing else ('no change' if existing_added == new_added else 'will update')})")
            collections[cid] = {
                "id": cid,
                "name": name,
                "added": sorted(new_added),
                "removed": [],
            }

        if dry_run:
            self.import_log_write("Dry run only -- nothing was written. Untick nothing needed; "
                                   "click 'Backup & Import Now' when ready.")
            return

        if not changed:
            self.import_log_write("Nothing to change -- Steam already matches these categories.")
            return

        try:
            backup_path = f"{vdf_path}.bak-{time.strftime('%Y%m%d-%H%M%S')}"
            shutil.copy2(vdf_path, backup_path)
            self.import_log_write(f"Backed up original file to:\n  {backup_path}")

            ws[_find_key_ci(ws, "user-collections") or "user-collections"] = json.dumps(collections, separators=(",", ":"))
            save_localconfig(data, vdf_path)
            self.import_log_write("Wrote changes successfully. Start Steam and check Library > Collections.")
            messagebox.showinfo("Import complete", "Categories written to Steam's config.\n\n"
                                                     "Start Steam and check Library > Collections.")
        except Exception as e:
            self.import_log_write(f"Import failed: {e}")
            messagebox.showerror("Import failed", f"Something went wrong writing the file:\n{e}\n\n"
                                                    f"Your original file was backed up before any write "
                                                    f"was attempted, if the backup step completed.")

    def toggle_show(self):
        if self.token_entry.cget("show") == "*":
            self.token_entry.config(show="")
            self.show_btn.config(text="Hide")
        else:
            self.token_entry.config(show="*")
            self.show_btn.config(text="Show")

    # ---------- Fetch library ----------

    def start_fetch(self):
        token = self.token_var.get().strip()
        if not token:
            messagebox.showwarning("Missing token", "Paste your access token first.")
            return
        self.fetch_btn.config(state="disabled")
        self.status_var.set("Fetching...")
        threading.Thread(target=self._fetch_worker, args=(token,), daemon=True).start()

    def _safe_save_json(self, filename, data):
        """Try saving next to the script; on PermissionError, fall back to
        the user's home folder instead of crashing the whole fetch."""
        candidates = [filename, os.path.join(os.path.expanduser("~"), filename)]
        for path in candidates:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                return path
            except PermissionError:
                continue
            except OSError:
                continue
        self.msg_queue.put((
            "error",
            f"Couldn't write {filename} anywhere (tried current folder and your home "
            f"folder). It's probably open in another program, or the folder is "
            f"read-only. The app will still work in this session, just won't "
            f"remember results between runs."
        ))
        return None

    def _locate_file(self, filename):
        """Return (absolute_path, exists) for a data file -- checks the
        current folder first, then the home-folder fallback used by
        _safe_save_json. If neither exists yet, reports where it WOULD be
        created (the current folder)."""
        cwd_path = os.path.abspath(filename)
        home_path = os.path.abspath(os.path.join(os.path.expanduser("~"), filename))
        if os.path.isfile(cwd_path):
            return cwd_path, True
        if os.path.isfile(home_path):
            return home_path, True
        return cwd_path, False

    def show_all_file_locations(self):
        lines = []
        for label, filename in DATA_FILES.items():
            path, exists = self._locate_file(filename)
            status = "" if exists else "  (not created yet)"
            lines.append(f"{label}:\n  {path}{status}")
        messagebox.showinfo(
            "Where are my files?",
            "Everything is saved as plain JSON next to wherever you run the script "
            "from (or your user home folder if that location isn't writable):\n\n"
            + "\n\n".join(lines)
        )

    def _fetch_worker(self, token):
        try:
            steamid = steamid_from_token(token)
            if not steamid:
                self.msg_queue.put(("error", "Couldn't read a SteamID from that token."))
                return
            self.msg_queue.put(("steamid", steamid))

            self.msg_queue.put(("status", "Fetching your own games..."))
            own_games = get_own_games(token, steamid)

            self.msg_queue.put(("status", "Looking up Family group..."))
            family_groupid = get_family_groupid(token)
            shared_games = []
            if family_groupid:
                self.msg_queue.put(("status", "Fetching shared library..."))
                shared_games = get_shared_library(token, family_groupid)

            own_appids = {g["appid"] for g in own_games}
            games = []
            for g in own_games:
                games.append({
                    "appid": g["appid"], "name": g.get("name", "Unknown"),
                    "hours": round(g.get("playtime_forever", 0) / 60, 1),
                    "source": "Own", "installed": "",
                })
            for g in shared_games:
                if g["appid"] in own_appids:
                    continue
                hrs = round(g.get("rt_playtime", 0) / 60, 1)
                games.append({
                    "appid": g["appid"], "name": g.get("name", "Unknown"),
                    "hours": hrs, "source": "Shared",
                    "installed": "Yes" if hrs > 0 or g.get("rt_last_played") else "",
                })

            save_path = self._safe_save_json(LIBRARY_FILE, games)

            self.msg_queue.put(("games", games))
            status = f"Loaded {len(games)} games."
            if save_path:
                status += f" Saved to {save_path}."
            else:
                status += " (Could not save to disk -- see popup.)"
            self.msg_queue.put(("status", status))
        except requests.HTTPError as e:
            self.msg_queue.put(("error", f"Request failed: {e}\nToken may be invalid/expired."))
        except Exception as e:
            self.msg_queue.put(("error", str(e)))
        finally:
            self.msg_queue.put(("done_fetch", None))

    def _get_delay(self):
        val = self.speed_var.get()
        if "Turbo" in val:
            return 0.2
        elif "Fast" in val:
            return 0.4
        elif "Balanced" in val:
            return 0.7
        return 1.2

    # ---------- Genre fetch ----------

    def start_genre_fetch(self):
        if not self.games:
            return
        self.genre_btn.config(state="disabled")
        threading.Thread(target=self._genre_worker, daemon=True).start()

    def _genre_worker(self):
        cache = {}
        for path in (GENRE_CACHE_FILE, os.path.join(os.path.expanduser("~"), GENRE_CACHE_FILE)):
            if os.path.isfile(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        cache = json.load(f)
                    break
                except OSError:
                    continue
        to_fetch = [g for g in self.games if str(g["appid"]) not in cache]
        total = len(to_fetch)
        self.msg_queue.put(("progress_max", total or 1))

        session = create_steam_session()
        delay = self._get_delay()
        warned = False

        for i, g in enumerate(to_fetch, 1):
            genres = fetch_genres(g["appid"], session=session)
            if genres is None:
                self.msg_queue.put(("status", f"Steam rate limit (429) on {g['name']}. Pausing 15s to cool down..."))
                time.sleep(15.0)
                genres = fetch_genres(g["appid"], session=session)
                if genres is None:
                    self.msg_queue.put(("status", f"Still cooling down. Pausing 20s..."))
                    time.sleep(20.0)
                    genres = fetch_genres(g["appid"], session=session) or []

            cache[str(g["appid"])] = genres
            if i % 5 == 0 or i == total:
                saved = self._safe_save_json(GENRE_CACHE_FILE, cache) if not warned else True
                if not saved:
                    warned = True  # don't spam the same error popup every checkpoint
                self.msg_queue.put(("status", f"Fetching genres ({self.speed_var.get()})... {i}/{total}"))
                self.msg_queue.put(("progress", i))
            time.sleep(delay)
        self.genre_cache = cache
        self.msg_queue.put(("genres_done", cache))

    # ---------- Franchise fetch ----------

    def start_franchise_fetch(self):
        if not self.games:
            return
        self.franchise_btn.config(state="disabled")
        self.franchise_lbl.config(text="Starting franchise fetch...")
        threading.Thread(target=self._franchise_worker, daemon=True).start()

    def _franchise_worker(self):
        cache = load_franchise_cache()
        to_fetch = [g for g in self.games if str(g["appid"]) not in cache]
        total = len(to_fetch)
        if total == 0:
            self.msg_queue.put(("status", f"All {len(cache)} games are already cached in {FRANCHISE_CACHE_FILE}."))
            self.msg_queue.put(("franchises_done", cache))
            return

        session = create_steam_session()
        delay = self._get_delay()
        self.msg_queue.put(("progress_max", total or 1))
        warned = False

        for i, g in enumerate(to_fetch, 1):
            if fetch_franchises_for_app:
                f_names = fetch_franchises_for_app(g["appid"], session=session)
                if f_names is None:
                    self.msg_queue.put(("status", f"Steam rate limit (429) on {g['name']}. Pausing 15s to cool down..."))
                    time.sleep(15.0)
                    f_names = fetch_franchises_for_app(g["appid"], session=session)
                    if f_names is None:
                        self.msg_queue.put(("status", f"Still cooling down. Pausing 20s..."))
                        time.sleep(20.0)
                        f_names = fetch_franchises_for_app(g["appid"], session=session) or []
            else:
                f_names = []
            cache[str(g["appid"])] = f_names
            if i % 5 == 0 or i == total:
                saved = self._safe_save_json(FRANCHISE_CACHE_FILE, cache) if not warned else True
                if not saved:
                    warned = True
                self.msg_queue.put(("status", f"Fetching franchises ({self.speed_var.get()})... {i}/{total}"))
                self.msg_queue.put(("progress", i))
            time.sleep(delay)
        self._safe_save_json(FRANCHISE_CACHE_FILE, cache)
        self.msg_queue.put(("franchises_done", cache))

    # ---------- Queue polling / UI updates ----------

    def poll_queue(self):
        try:
            while True:
                kind, payload = self.msg_queue.get_nowait()
                if kind == "status":
                    self.status_var.set(payload)
                elif kind == "steamid":
                    self.steamid = payload
                    if hasattr(self, "import_accountid_var") and not self.import_accountid_var.get():
                        acc = steamid_to_accountid(payload)
                        if acc:
                            self.import_accountid_var.set(acc)
                elif kind == "error":
                    messagebox.showerror("Error", payload)
                    self.status_var.set("Error -- see popup.")
                elif kind == "games":
                    self.games = payload
                    self.refresh_all_tab()
                    self.refresh_series_tab()
                    self.refresh_curate_game_list()
                    self.refresh_tag_listbox()
                    self.genre_btn.config(state="normal")
                    self.franchise_btn.config(state="normal")
                    self.community_tags_btn.config(state="normal")
                    self.refresh_uncategorized_count()
                elif kind == "done_fetch":
                    self.fetch_btn.config(state="normal")
                    self.franchise_btn.config(state="normal")
                    self.community_tags_btn.config(state="normal")
                elif kind == "progress_max":
                    self.progress.config(maximum=payload, value=0)
                elif kind == "progress":
                    self.progress.config(value=payload)
                elif kind == "genres_done":
                    self.genre_cache = payload
                    self.refresh_genre_tab()
                    self.genre_btn.config(state="normal")
                    self.status_var.set("Genres loaded.")
                    self.refresh_tag_listbox()
                elif kind == "franchises_done":
                    self.refresh_all_tab()
                    self.refresh_series_tab()
                    self.franchise_btn.config(state="normal")
                    self.status_var.set(f"Franchises updated & saved to {os.path.abspath(FRANCHISE_CACHE_FILE)}")
                    self.notebook.select(self.series_tab)
                    self.refresh_tag_listbox()
                elif kind == "curate_status":
                    self.curate_status_lbl.config(text=payload)
                elif kind == "community_tags_done":
                    self.community_tags_cache = payload
                    self.community_tags_btn.config(state="normal")
                    self.curate_status_lbl.config(
                        text=f"Community tags updated & saved to {os.path.abspath(COMMUNITY_TAGS_CACHE_FILE)}")
                    self.refresh_curate_game_list()
                    self.refresh_tag_listbox()
                    if self.curate_selected_appid is not None:
                        game = next((g for g in self.games if g["appid"] == self.curate_selected_appid), None)
                        if game:
                            self.rebuild_tag_checkboxes(self.curate_selected_appid, game["name"])
        except queue.Empty:
            pass
        self.root.after(100, self.poll_queue)

    def refresh_all_tab(self):
        for row in self.tree_all.get_children():
            self.tree_all.delete(row)
        filt = self.filter_var.get().lower()
        franchise_cache = load_franchise_cache()

        for g in sorted(self.games, key=lambda g: g["name"].lower()):
            real = franchise_cache.get(str(g["appid"])) or []
            if real:
                f_display = "★ " + ", ".join(real)
            else:
                c = guess_series(g["name"])
                f_display = f"◆ {c}" if c else "-"

            if filt and filt not in g["name"].lower() and filt not in f_display.lower():
                continue
            self.tree_all.insert("", "end", values=(g["name"], f_display, g["hours"], g["source"], g["installed"]))

    def expand_series(self):
        for item in self.tree_series.get_children():
            self.tree_series.item(item, open=True)

    def collapse_series(self):
        for item in self.tree_series.get_children():
            self.tree_series.item(item, open=False)

    def open_cache_file(self):
        abs_path = os.path.abspath(FRANCHISE_CACHE_FILE)
        if not os.path.isfile(abs_path):
            messagebox.showinfo("File Not Found", f"Franchise cache file does not exist yet:\n{abs_path}\n\nClick 'Fetch Franchises' to generate it.")
            return
        try:
            if sys.platform == "win32":
                os.startfile(abs_path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", abs_path])
            else:
                subprocess.Popen(["xdg-open", abs_path])
        except Exception as e:
            messagebox.showinfo("Franchise File", f"File location:\n{abs_path}\n\nCould not auto-open: {e}")

    def show_cache_location(self):
        abs_path = os.path.abspath(FRANCHISE_CACHE_FILE)
        cache = load_franchise_cache()
        matched = sum(1 for v in cache.values() if v)
        msg = (
            f"Franchise Cache File:\n{abs_path}\n\n"
            f"Status:\n"
            f"• Total games in cache: {len(cache)}\n"
            f"• Official franchises matched: {matched}\n\n"
            f"File format:\n"
            f'{{"<appid>": ["Franchise Name", ...]}}\n\n'
            f"This file is saved automatically whenever franchises are fetched."
        )
        messagebox.showinfo("Franchise File Location", msg)

    def refresh_series_tab(self):
        for row in self.tree_series.get_children():
            self.tree_series.delete(row)

        franchise_cache = load_franchise_cache()
        filt = getattr(self, "series_filter_var", None)
        search_query = filt.get().strip().lower() if filt else ""
        mode = getattr(self, "series_mode_var", None)
        view_mode = mode.get() if mode else "All Franchises & Series"

        # group by category: (series_name, source_type) -> [game_names]
        groups = {}
        unmatched = []
        official_series_set = set()

        for g in self.games:
            real = franchise_cache.get(str(g["appid"])) or []
            if real:
                for series in real:
                    groups.setdefault((series, "Official Steam Store Tag"), []).append(g["name"])
                    official_series_set.add(series)
                continue
            curated = guess_series(g["name"])
            if curated:
                groups.setdefault((curated, "Curated Series"), []).append(g["name"])
                continue
            unmatched.append(g["name"])

        auto_groups = auto_cluster(unmatched)
        clustered_names = {n for names in auto_groups.values() for n in names}
        for key, names in auto_groups.items():
            groups[(f"{key.title()}", "Auto-clustered")] = names
        groups[("(Unclassified / standalone)", "Standalone")] = [n for n in unmatched if n not in clustered_names]

        sorted_groups = sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0][0].lower()))

        visible_count = 0
        total_games_in_visible = 0

        for (series, source), names in sorted_groups:
            # Mode filter
            if "Official" in view_mode and source != "Official Steam Store Tag":
                continue
            if "Multi-Game" in view_mode and len(names) < 2:
                continue

            # Search query filter (matches series name OR any game title within the series)
            if search_query:
                series_match = search_query in series.lower()
                matching_games = [n for n in names if search_query in n.lower()]
                if not series_match and not matching_games:
                    continue
                display_names = names if series_match else matching_games
            else:
                display_names = names

            icon = "★ " if source == "Official Steam Store Tag" else ("◆ " if source == "Curated Series" else "◇ ")
            # Expand by default so the user sees games right away
            is_open = bool(search_query) or (visible_count < 30 and len(display_names) <= 25)

            parent = self.tree_series.insert("", "end", text=f"{icon}{series}", values=(len(display_names), source), open=is_open)
            for n in sorted(display_names):
                self.tree_series.insert(parent, "end", text=f"    •  {n}", values=("", ""))

            visible_count += 1
            total_games_in_visible += len(display_names)

        abs_path = os.path.abspath(FRANCHISE_CACHE_FILE)
        cache_status = f"{len(official_series_set)} official store franchises" if official_series_set else "0 official tags cached"
        self.franchise_lbl.config(text=f"{cache_status}  •  Showing: {visible_count} franchises ({total_games_in_visible} games)")

    def refresh_genre_tab(self):
        for row in self.tree_genre.get_children():
            self.tree_genre.delete(row)
        groups = {}
        for g in self.games:
            genres = self.genre_cache.get(str(g["appid"])) or ["(Unknown)"]
            for genre in genres:
                groups.setdefault(genre, []).append(g["name"])
        for genre, names in sorted(groups.items(), key=lambda kv: -len(kv[1])):
            parent = self.tree_genre.insert("", "end", text=f"◆  {genre}", values=(len(names),), open=False)
            for n in sorted(names):
                self.tree_genre.insert(parent, "end", text=f"    •  {n}", values=("",))


def main():
    root = tk.Tk()
    SteamLibraryApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
