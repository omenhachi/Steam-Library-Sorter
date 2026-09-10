#!/usr/bin/env python3
"""
List ALL your Steam games -- your own full library AND everything
shared with you through a Steam Family group -- regardless of
whether they're installed. Includes games you haven't touched yet.

Why this needs a token instead of just an API key:
  Family Sharing data isn't public, so the normal Web API key
  won't see it. We need a short-lived access token tied to your
  logged-in browser session instead.

Setup (one-time, ~30 seconds):
  1. Open a browser, log into https://store.steampowered.com
  2. Visit this URL directly:
     https://store.steampowered.com/pointssummary/ajaxgetasyncconfig
  3. You'll see raw JSON like:
     {"success": true, "data": {"webapi_token": "eyJ...", ...}}
  4. Copy the long "webapi_token" value (starts with "eyJ")
  5. Paste it below as ACCESS_TOKEN, or pass it as argv[1]

Note: this token expires after a while (it's a session token) --
if the script suddenly gets 401/403 errors, just grab a fresh one.

Usage:
  python list_all_steam_games.py
  python list_all_steam_games.py YOUR_TOKEN
"""

import sys
import os
import json
import base64
import requests

ACCESS_TOKEN = os.environ.get("STEAM_ACCESS_TOKEN", "PASTE_YOUR_TOKEN_HERE")
BASE = "https://api.steampowered.com"


def steamid_from_token(token):
    """Pull the SteamID64 out of the token's JWT payload (no signature check needed,
    we're just reading a field out of our own token)."""
    try:
        payload_b64 = token.split(".")[1]
        payload_b64 += "=" * (-len(payload_b64) % 4)  # fix base64 padding
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
    data = api_get(
        "IPlayerService", "GetOwnedGames", "v0001", token,
        steamid=steamid,
        include_appinfo=1, include_played_free_games=1,
        include_extended_appinfo=1,
    )
    return data.get("response", {}).get("games", [])


def get_family_groupid(token):
    data = api_get("IFamilyGroupsService", "GetFamilyGroupForUser", "v1", token)
    resp = data.get("response", {})
    return resp.get("family_groupid")


def get_shared_library(token, family_groupid):
    data = api_get(
        "IFamilyGroupsService", "GetSharedLibraryApps", "v1", token,
        family_groupid=family_groupid,
        include_own=1, include_excluded=1, include_free=1,
        include_non_games=0,
    )
    return data.get("response", {}).get("apps", [])


def main():
    token = sys.argv[1] if len(sys.argv) > 1 else ACCESS_TOKEN
    if token == "PASTE_YOUR_TOKEN_HERE":
        print("No token set. See the setup steps in this script's docstring,")
        print("then edit ACCESS_TOKEN or pass it as an argument.")
        sys.exit(1)

    steamid = steamid_from_token(token)
    if not steamid:
        print("Couldn't read a SteamID out of that token -- is it a full webapi_token?")
        sys.exit(1)
    print(f"Detected SteamID: {steamid}\n")

    print("Fetching your own owned games...")
    try:
        own_games = get_own_games(token, steamid)
    except requests.HTTPError as e:
        print(f"Failed to fetch owned games ({e}). Token may be invalid/expired.")
        sys.exit(1)

    print(f"  -> {len(own_games)} games you own\n")

    print("Looking up your Steam Family group...")
    family_groupid = get_family_groupid(token)

    shared_games = []
    if family_groupid:
        print(f"  -> Family group found (id {family_groupid}), fetching shared library...")
        shared_games = get_shared_library(token, family_groupid)
        print(f"  -> {len(shared_games)} apps visible in the family library\n")
    else:
        print("  -> You're not in a Steam Family group.\n")

    own_appids = {g["appid"] for g in own_games}

    print(f"=== Your own games ({len(own_games)}) ===")
    for g in sorted(own_games, key=lambda g: g.get("name", "").lower()):
        hrs = g.get("playtime_forever", 0) / 60
        print(f"  {g.get('name', 'Unknown'):<50} {hrs:>7.1f} hrs")

    shared_only = [g for g in shared_games if g["appid"] not in own_appids]
    print(f"\n=== Shared with you via Family (not owned by you) ({len(shared_only)}) ===")
    for g in sorted(shared_only, key=lambda g: g.get("name", "").lower()):
        hrs = g.get("rt_playtime", 0) / 60
        installed = "installed" if hrs > 0 or g.get("rt_last_played") else ""
        print(f"  {g.get('name', 'Unknown'):<50} {hrs:>7.1f} hrs  {installed}")

    # Save everything to JSON so other scripts (e.g. genre/series categorizer)
    # can reuse it without re-hitting the API.
    export = {
        "own_games": [
            {"appid": g["appid"], "name": g.get("name", "Unknown"),
             "playtime_hours": round(g.get("playtime_forever", 0) / 60, 1)}
            for g in own_games
        ],
        "shared_games": [
            {"appid": g["appid"], "name": g.get("name", "Unknown"),
             "playtime_hours": round(g.get("rt_playtime", 0) / 60, 1)}
            for g in shared_only
        ],
    }
    out_path = "steam_library.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(export, f, indent=2)
    print(f"\nSaved full library data (with appids) to {out_path}")


if __name__ == "__main__":
    main()
