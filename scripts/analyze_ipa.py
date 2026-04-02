#!/usr/bin/env python3
"""Analyze an iOS IPA file and produce a categorized size breakdown."""

import subprocess
import sys
import json
import os
import re
from datetime import datetime
from collections import defaultdict


def fmt(b):
    """Format bytes to human-readable size."""
    if b >= 1_000_000_000:
        return f"{b / 1_000_000_000:.2f} GB"
    elif b >= 1_000_000:
        return f"{b / 1_000_000:.1f} MB"
    elif b >= 1000:
        return f"{b / 1000:.1f} KB"
    else:
        return f"{b} B"


def categorize(path, app_name):
    """Categorize a file path into one of the defined categories."""
    p = path
    if (
        ".assetpack/" in p
        or "OnDemandResources/" in p
        or p.endswith("OnDemandResources.plist")
        or p.endswith("AssetPackManifest.plist")
    ):
        return "On-Demand Resources"
    if "/Frameworks/" in p and (".framework/" in p or p.endswith(".dylib")):
        return "Frameworks"
    if ".dylib" in p:
        return "Frameworks"
    if "/_CodeSignature/" in p or p.endswith(".mobileprovision") or p.endswith(".cer"):
        return "Code Signing"
    if "/PlugIns/" in p and ".appex/" in p:
        return "App Extensions"
    if p.endswith(".car"):
        return "Asset Catalogs"
    if ".storyboardc/" in p or p.endswith(".storyboardc") or p.endswith(".nib"):
        return "Storyboards & NIBs"
    if ".lproj/" in p:
        return "Localization"
    ext = os.path.splitext(p)[1].lower()
    if ext in (".png", ".jpg", ".jpeg", ".gif", ".svg", ".pdf", ".webp", ".heic", ".ico", ".tiff"):
        return "Images"
    if ext in (".plist", ".json", ".xml", ".xcprivacy", ".storekit"):
        return "Plists & Config"
    if app_name and f"/{app_name}.app/{app_name}" in p and ext == "":
        return "Executable Binary"
    if ext == "":
        app_root = f"Payload/{app_name}.app/" if app_name else None
        if app_root and p.startswith(app_root) and "/" not in p[len(app_root):]:
            return "Executable Binary"
    return "Other Resources"


def analyze(ipa_path):
    """Analyze an IPA file and return the report dict and JSON path."""
    ipa_size = os.path.getsize(ipa_path)

    result = subprocess.run(["zipinfo", "-l", ipa_path], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error running zipinfo: {result.stderr}", file=sys.stderr)
        sys.exit(1)

    lines = result.stdout.strip().split("\n")

    # Detect app name from Payload/*.app/ pattern
    app_name = None
    for line in lines:
        m = re.search(r"Payload/([^/]+)\.app/", line)
        if m:
            app_name = m.group(1)
            break

    # Parse zipinfo -l output
    files = {}
    total_uncompressed = 0
    total_compressed = 0
    file_count = 0

    for line in lines[2:-1]:  # Skip header and footer
        parts = line.split()
        if len(parts) < 9:
            continue
        try:
            uncompressed = int(parts[3])
            compressed = int(parts[5])
        except (ValueError, IndexError):
            continue
        filepath = " ".join(parts[8:])
        if filepath.endswith("/"):  # Skip directories
            continue
        files[filepath] = {"uncompressed": uncompressed, "compressed": compressed}
        total_uncompressed += uncompressed
        total_compressed += compressed
        file_count += 1

    # Categorize files
    categories = defaultdict(lambda: {"uncompressed": 0, "compressed": 0, "file_count": 0})
    all_files = {}

    for filepath, sizes in files.items():
        cat = categorize(filepath, app_name)
        categories[cat]["uncompressed"] += sizes["uncompressed"]
        categories[cat]["compressed"] += sizes["compressed"]
        categories[cat]["file_count"] += 1
        all_files[filepath] = {**sizes, "category": cat}

    # Sort categories by uncompressed size descending
    sorted_cats = sorted(categories.items(), key=lambda x: x[1]["uncompressed"], reverse=True)

    # Top 20 files by uncompressed size
    top_files = sorted(files.items(), key=lambda x: x[1]["uncompressed"], reverse=True)[:20]

    # Calculate ODR sizes to exclude from download/install
    odr_compressed = 0
    odr_uncompressed = 0
    for filepath, sizes in files.items():
        if (
            ".assetpack/" in filepath
            or "OnDemandResources/" in filepath
            or filepath.endswith("OnDemandResources.plist")
            or filepath.endswith("AssetPackManifest.plist")
        ):
            odr_compressed += sizes["compressed"]
            odr_uncompressed += sizes["uncompressed"]

    download_size = ipa_size - odr_compressed
    install_size = total_uncompressed - odr_uncompressed

    # Print report
    ipa_name = os.path.basename(ipa_path)
    ratio = ((total_uncompressed - ipa_size) / total_uncompressed * 100) if total_uncompressed > 0 else 0

    print(f"\n{'=' * 70}")
    print(f"  IPA Size Analysis: {ipa_name}")
    print(f"{'=' * 70}\n")
    print(f"  IPA (compressed):    {fmt(ipa_size):>12}    (total IPA file size)")
    print(f"  IPA (uncompressed):  {fmt(total_uncompressed):>12}    (total uncompressed size)")
    print(f"  Download Size:       {fmt(download_size):>12}    (compressed, excluding ODR assets)")
    print(f"  Install Size:        {fmt(install_size):>12}    (uncompressed, excluding ODR assets)")
    if odr_compressed > 0:
        print(f"  ODR Assets:          {fmt(odr_compressed):>12}    (on-demand resources, downloaded later)")
    print(f"  Compression ratio:   {abs(ratio):.1f}%")
    print(f"  Total files:         {file_count}")
    print()

    # Category table
    header = f"  {'Category':<22} {'Uncompressed':>14} {'Compressed':>14} {'% of Total':>10} {'Files':>6}"
    print(header)
    print(f"  {'-' * 22} {'-' * 14} {'-' * 14} {'-' * 10} {'-' * 6}")
    for cat, data in sorted_cats:
        pct = (data["uncompressed"] / total_uncompressed * 100) if total_uncompressed > 0 else 0
        print(f"  {cat:<22} {fmt(data['uncompressed']):>14} {fmt(data['compressed']):>14} {pct:>9.1f}% {data['file_count']:>6}")
    print()

    # Top 20 files
    print(f"  Top 20 Largest Files:")
    print(f"  {'#':<4} {'Size':>12}   {'File'}")
    print(f"  {'-' * 4} {'-' * 12}   {'-' * 50}")
    for i, (path, sizes) in enumerate(top_files, 1):
        print(f"  {i:<4} {fmt(sizes['uncompressed']):>12}   {path}")
    print()

    # Build report dict
    report = {
        "app_name": app_name or ipa_name.replace(".ipa", ""),
        "ipa_path": os.path.abspath(ipa_path),
        "date": datetime.now().isoformat(),
        "ipa_compressed_size": ipa_size,
        "ipa_uncompressed_size": total_uncompressed,
        "download_size": download_size,
        "install_size": install_size,
        "odr_compressed_size": odr_compressed,
        "odr_uncompressed_size": odr_uncompressed,
        "total_files": file_count,
        "categories": dict(categories),
        "sorted_categories": [{"name": name, **data} for name, data in sorted_cats],
        "top_files": [
            {"path": p, "uncompressed": s["uncompressed"], "compressed": s["compressed"]}
            for p, s in top_files
        ],
        "all_files": all_files,
    }

    # Save JSON report
    json_path = os.path.splitext(ipa_path)[0] + "-size-report.json"
    with open(json_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"  JSON report saved: {json_path}")
    print()

    return report, json_path


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: analyze_ipa.py <path-to-ipa>", file=sys.stderr)
        sys.exit(1)
    analyze(sys.argv[1])
