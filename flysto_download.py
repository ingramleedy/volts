#!/usr/bin/env python3
"""
FlySto.net G1000 CSV Log Downloader

Downloads source G1000 CSV log files from FlySto.net for aircraft N238PS.
Credentials are read from environment variables or prompted interactively.

Usage:
    python flysto_download.py                  # download all missing G3000 CSVs
    python flysto_download.py --list           # list available logs without downloading
    python flysto_download.py --force          # re-download even if file exists
    python flysto_download.py --last 10        # download only the 10 most recent logs

Environment variables (optional, will prompt if not set):
    FLYSTO_EMAIL    - FlySto account email
    FLYSTO_PASSWORD - FlySto account password
"""

import argparse
import getpass
import json
import os
import sys
import time

import requests


def decode_flysto(s: str) -> str:
    """Decode FlySto's obfuscated response encoding."""
    return ''.join(
        chr((127 - ord(c)) + 32) if 32 <= ord(c) <= 127 else c
        for c in s
    )


def api_request(session: requests.Session, path: str, params: dict = None):
    """Make an authenticated GET request to FlySto API, decode the response."""
    url = f'https://www.flysto.net{path}'
    resp = session.get(url, params=params)
    resp.raise_for_status()

    raw = resp.text
    if raw.startswith('wait'):
        raw = raw[4:].strip()
    if not raw:
        return None

    outer = json.loads(raw)
    if isinstance(outer, dict) and 'RESPONSE' in outer:
        decoded = decode_flysto(outer['RESPONSE'])
        return json.loads(decoded)
    return outer


def login(session: requests.Session, email: str, password: str):
    """Authenticate to FlySto. Returns True on success."""
    resp = session.post('https://www.flysto.net/api/login', json={
        'email': email,
        'password': password,
    })
    if resp.status_code == 204:
        return True
    print(f"Login failed: HTTP {resp.status_code}", file=sys.stderr)
    return False


def get_log_ids(session: requests.Session) -> list[str]:
    """Get all log IDs from FlySto. Returns list of ID strings."""
    data = api_request(session, '/api/log-list')
    return [x for x in data if isinstance(x, str)]


def get_file_info(session: requests.Session, log_ids: list[str]) -> dict:
    """Get file metadata for each log. Returns {log_id: [{format, file}, ...]}."""
    all_files = {}
    batch_size = 20
    for i in range(0, len(log_ids), batch_size):
        batch = log_ids[i:i + batch_size]
        data = api_request(session, '/api/log-summary', params={
            'logs': ','.join(batch)
        })
        for item in data.get('items', []):
            log_id = item['id']
            t3 = item.get('summary', {}).get('data', {}).get('t3', [])
            all_files[log_id] = t3
    return all_files


def download_file(session: requests.Session, log_id: str, format_id: str,
                  file_name: str, dest_path: str) -> bool:
    """Download a single source log file. Returns True on success."""
    url = f'https://www.flysto.net/log-files/{log_id}/{format_id}/{file_name}'
    resp = session.get(url, stream=True)
    if resp.status_code != 200:
        print(f"  FAILED: HTTP {resp.status_code} for {file_name}", file=sys.stderr)
        return False

    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    with open(dest_path, 'wb') as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
    return True


def main():
    parser = argparse.ArgumentParser(description='Download G1000 CSV logs from FlySto.net')
    parser.add_argument('--list', action='store_true', help='List available logs without downloading')
    parser.add_argument('--force', action='store_true', help='Re-download even if file already exists')
    parser.add_argument('--last', type=int, default=0, help='Only process the N most recent logs')
    parser.add_argument('--output', default='data/source', help='Output directory (default: data/source)')
    parser.add_argument('--format', default='G3000', help='Log format to download (default: G3000)')
    args = parser.parse_args()

    # Get credentials
    email = os.environ.get('FLYSTO_EMAIL')
    password = os.environ.get('FLYSTO_PASSWORD')
    if not email:
        email = input('FlySto email: ')
    if not password:
        password = getpass.getpass('FlySto password: ')

    # Login
    session = requests.Session()
    print("Logging in to FlySto...")
    if not login(session, email, password):
        sys.exit(1)
    print("Authenticated successfully.")

    # Get log list
    print("Fetching log list...")
    log_ids = get_log_ids(session)
    print(f"Found {len(log_ids)} total logs.")

    # Get file info for all logs
    print("Fetching file metadata...")
    file_info = get_file_info(session, log_ids)

    # Filter to requested format and build download list
    # log_ids are in order from FlySto (most recent first based on the data we've seen)
    downloads = []
    for log_id in log_ids:
        files = file_info.get(log_id, [])
        for f in files:
            if f.get('format') == args.format:
                downloads.append((log_id, f['format'], f['file']))

    print(f"Found {len(downloads)} {args.format} logs out of {len(log_ids)} total.")

    if args.last > 0:
        downloads = downloads[:args.last]
        print(f"Limited to {len(downloads)} most recent.")

    if args.list:
        print(f"\n{'Log ID':<12} {'Filename'}")
        print('-' * 60)
        for log_id, fmt, fname in downloads:
            exists = os.path.exists(os.path.join(args.output, fname))
            marker = ' [local]' if exists else ''
            print(f"{log_id:<12} {fname}{marker}")
        return

    # Download
    os.makedirs(args.output, exist_ok=True)
    downloaded = 0
    skipped = 0
    failed = 0

    for i, (log_id, fmt, fname) in enumerate(downloads, 1):
        dest = os.path.join(args.output, fname)
        if os.path.exists(dest) and not args.force:
            skipped += 1
            continue

        print(f"[{i}/{len(downloads)}] Downloading {fname}...", end=' ', flush=True)
        if download_file(session, log_id, fmt, fname, dest):
            size = os.path.getsize(dest)
            print(f"{size:,} bytes")
            downloaded += 1
        else:
            failed += 1

        # Small delay to be polite to the server
        time.sleep(0.25)

    print(f"\nDone: {downloaded} downloaded, {skipped} skipped (already exist), {failed} failed.")


if __name__ == '__main__':
    main()
