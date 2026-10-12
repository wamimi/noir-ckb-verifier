#!/usr/bin/env python3
"""Fetch pinned official CKB, ckb-cli and Nargo executables for this host.

Shows every URL before downloading and asks for consent (or --yes). Verifies the
archive and the extracted executable against toolchains/platforms.json, writes
only that executable (mode 0755) and never runs installers, edits shell profiles,
escalates privileges, touches wallets or contacts a CKB network.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import urllib.request

import counter_platform as cp


def plan(tools_dir, key, entry, names):
    rows = []
    for name in names:
        existing = cp.find_tool(tools_dir, key, entry, name)
        rows.append(dict(tool=name, url=entry["tools"][name]["url"],
                         destination=str(existing or Path(tools_dir) / key / name),
                         action="already-present-and-verified" if existing else "download"))
    return rows


def download(url):
    request = urllib.request.Request(url, headers={"User-Agent": "noir-ckb/counter-tools"})
    with urllib.request.urlopen(request, timeout=120) as response:  # default TLS verification
        return response.read()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=cp.ROOT / "target/counter-tools", help="tools directory")
    parser.add_argument("--tools", default=",".join(cp.TOOL_NAMES), help="comma-separated subset of ckb,ckb-cli,nargo")
    parser.add_argument("--list", action="store_true", help="print the plan and exit without downloading")
    parser.add_argument("--yes", action="store_true", help="consent to the listed downloads without a prompt")
    args = parser.parse_args(argv)
    names = [n.strip() for n in args.tools.split(",") if n.strip()]
    unknown = sorted(set(names) - set(cp.TOOL_NAMES))
    if unknown:
        parser.error(f"unknown tool(s): {', '.join(unknown)}")
    key, entry = cp.detect()
    tools_dir = args.out.resolve()
    rows = plan(tools_dir, key, entry, names)
    print(f"Host platform: {key} ({entry['status']})")
    for row in rows:
        print(f"  {row['tool']:8} {row['action']:30} {row['url']}\n           -> {row['destination']}")
    pending = [row for row in rows if row["action"] == "download"]
    if args.list or not pending:
        print("Nothing to download." if not pending else "Plan only; nothing downloaded.")
        return 0
    if not args.yes:
        if not sys.stdin.isatty():
            parser.error("downloads need --yes in a non-interactive terminal")
        if input(f"Download {len(pending)} official archive(s) from GitHub? [y/N] ").strip().lower() not in ("y", "yes"):
            print("Cancelled; nothing downloaded.")
            return 0
    records = []
    for row in pending:
        pin = entry["tools"][row["tool"]]
        print(f"Downloading {row['tool']} ...", flush=True)
        installed = cp.install_tool(download(pin["url"]), pin, row["destination"])
        records.append(dict(tool=row["tool"], platform=key, url=pin["url"], archive_sha256=pin["archive_sha256"],
                            binary_sha256=pin["binary_sha256"], binary=str(installed)))
        print(f"  verified and installed {installed}", flush=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    record = tools_dir / f"fetch-{key}-{stamp}.json"
    record.write_text(json.dumps(records, indent=2) + "\n")
    print(f"Record: {record}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (cp.PlatformError, OSError) as error:
        sys.exit(f"error: {error}")
