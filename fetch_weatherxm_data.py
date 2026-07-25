"""
fetch_weatherxm_data.py

Logs into your WeatherXM account, downloads recent readings for your
station, and saves them to a CSV file on your computer.

HOW TO USE (Mac):
1. Open Terminal.
2. Navigate to the folder where you saved this file, e.g.:
     cd ~/Downloads
3. Install the one library this script needs (only needed once):
     pip3 install requests
4. Run it:
     python3 fetch_weatherxm_data.py
5. It will ask for your WeatherXM email and password (the same ones you
   use in the phone app). Typing your password won't show any characters
   on screen — that's normal, just type it and press Enter.

Each time you run it, it fetches the last 7 days of readings and adds
any new rows to weatherxm_data.csv in the same folder (it won't
duplicate rows you already have).
"""

import requests
import csv
import os
import getpass
from datetime import date, timedelta

BASE_URL = "https://api.weatherxm.com/api/v1"
DEVICE_ID = "39a1f050-1e04-11ed-960f-d7d4cf200cc9"  # Uneven Fawn Anemometer (Stanardsville)
CSV_FILE = "weatherxm_data.csv"
DAYS_TO_FETCH = 7  # WeatherXM only keeps ~7 days of history available


def login():
    # When run automatically (e.g. by GitHub Actions), credentials come
    # from environment variables instead of being typed in.
    email = os.environ.get("WEATHERXM_EMAIL")
    password = os.environ.get("WEATHERXM_PASSWORD")

    if not email or not password:
        print("Log in to WeatherXM (same email/password as the phone app).")
        email = input("Email: ").strip()
        password = getpass.getpass("Password: ")

    response = requests.post(
        f"{BASE_URL}/auth/login",
        json={"username": email, "password": password},
        timeout=30,
    )
    if response.status_code != 200:
        print(f"\nLogin failed ({response.status_code}): {response.text}")
        raise SystemExit(1)
    return response.json()["token"]


def fetch_day(token: str, day: date):
    """Fetch one day of readings for the station."""
    url = f"{BASE_URL}/me/devices/{DEVICE_ID}/history"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"fromDate": day.isoformat(), "toDate": day.isoformat()}

    response = requests.get(url, headers=headers, params=params, timeout=30)

    if response.status_code != 200:
        print(f"  -> Request failed for {day}: {response.status_code} {response.text[:200]}")
        return []

    data = response.json()
    # The API returns a day-level record with a nested "hourly" list of
    # actual readings inside it — unpack that so each hour becomes a row.
    day_records = data if isinstance(data, list) else [data]
    readings = []
    for day_record in day_records:
        if isinstance(day_record, dict) and "hourly" in day_record:
            readings.extend(day_record["hourly"])
        elif isinstance(day_record, dict):
            readings.append(day_record)
    return readings


def load_existing_rows():
    if not os.path.exists(CSV_FILE):
        return [], set(), []
    with open(CSV_FILE, newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames or []
    timestamps = {row.get("timestamp") for row in rows if row.get("timestamp")}
    return rows, timestamps, fieldnames


def main():
    token = login()
    print("\nLogged in successfully. Fetching data...\n")

    existing_rows, existing_timestamps, existing_fields = load_existing_rows()
    new_rows = []
    all_keys = set(existing_fields)

    for i in range(DAYS_TO_FETCH):
        day = date.today() - timedelta(days=i)
        print(f"Fetching {day} ...")
        readings = fetch_day(token, day)

        for r in readings:
            if not isinstance(r, dict):
                continue
            ts = r.get("timestamp") or r.get("date") or r.get("time")
            if ts and ts not in existing_timestamps:
                if not r.get("timestamp") and ts:
                    r["timestamp"] = ts
                new_rows.append(r)
                existing_timestamps.add(ts)
                all_keys.update(r.keys())

    if not new_rows and not existing_rows:
        print("\nNo data returned. Double check the device ID and that your")
        print("account has access to this station's history.")
        return

    fieldnames = sorted(all_keys, key=lambda k: (k != "timestamp", k))

    with open(CSV_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(existing_rows)
        writer.writerows(new_rows)

    print(f"\nDone. Added {len(new_rows)} new rows. Total rows in {CSV_FILE}: {len(existing_rows) + len(new_rows)}.")


if __name__ == "__main__":
    main()
