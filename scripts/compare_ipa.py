#!/usr/bin/env python3
"""Compare two IPA size reports (JSON) and display the differences."""

import json
import sys
import os


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


def fmt_delta(b):
    """Format a delta value with +/- prefix."""
    prefix = "+" if b > 0 else ""
    return f"{prefix}{fmt(b)}"


def pct_change(old, new):
    """Calculate percentage change."""
    if old == 0:
        return 0.0 if new == 0 else 100.0
    return (new - old) / old * 100


def indicator(delta):
    """Return a visual indicator for the change direction."""
    if delta > 0:
        return "\u25b2"
    elif delta < 0:
        return "\u25bc"
    return "\u2500"


def compare(old_path, new_path):
    """Compare two JSON reports and print comparison."""
    with open(old_path) as f:
        old = json.load(f)
    with open(new_path) as f:
        new = json.load(f)

    old_name = old.get("app_name", os.path.basename(old_path))
    new_name = new.get("app_name", os.path.basename(new_path))

    print(f"\n{'=' * 80}")
    print(f"  Build Comparison: {old_name} \u2192 {new_name}")
    print(f"{'=' * 80}\n")

    # Overall size metrics
    metrics = [
        ("IPA (compressed)", "ipa_compressed_size"),
        ("IPA (uncompressed)", "ipa_uncompressed_size"),
        ("Download Size", "download_size"),
        ("Install Size", "install_size"),
    ]

    header = f"  {'':>22} {'Old':>14} {'New':>14} {'Delta':>14} {'Change':>10}"
    print(header)
    print(f"  {'-' * 22} {'-' * 14} {'-' * 14} {'-' * 14} {'-' * 10}")

    for label, key in metrics:
        o = old.get(key, 0)
        n = new.get(key, 0)
        delta = n - o
        pct = pct_change(o, n)
        sign = "+" if pct > 0 else ""
        print(f"  {label:<22} {fmt(o):>14} {fmt(n):>14} {fmt_delta(delta):>14} {sign}{pct:.1f}%")

    # ODR if present
    odr_old = old.get("odr_compressed_size", 0)
    odr_new = new.get("odr_compressed_size", 0)
    if odr_old > 0 or odr_new > 0:
        delta = odr_new - odr_old
        pct = pct_change(odr_old, odr_new)
        sign = "+" if pct > 0 else ""
        print(f"  {'ODR Assets':<22} {fmt(odr_old):>14} {fmt(odr_new):>14} {fmt_delta(delta):>14} {sign}{pct:.1f}%")
    print()

    # Category comparison
    all_cats = set()
    old_cats = old.get("categories", {})
    new_cats = new.get("categories", {})
    all_cats.update(old_cats.keys())
    all_cats.update(new_cats.keys())

    cat_deltas = []
    for cat in all_cats:
        o = old_cats.get(cat, {}).get("uncompressed", 0)
        n = new_cats.get(cat, {}).get("uncompressed", 0)
        cat_deltas.append((cat, o, n, n - o))

    cat_deltas.sort(key=lambda x: abs(x[3]), reverse=True)

    print(f"  {'Category':<22} {'Old':>14} {'New':>14} {'Delta':>14} {'Change':>10}")
    print(f"  {'-' * 22} {'-' * 14} {'-' * 14} {'-' * 14} {'-' * 10}")
    for cat, o, n, delta in cat_deltas:
        pct = pct_change(o, n)
        sign = "+" if pct > 0 else ""
        ind = indicator(delta)
        print(f"  {cat:<22} {fmt(o):>14} {fmt(n):>14} {fmt_delta(delta):>14} {sign}{pct:.1f}%  {ind}")
    print()

    # Top 10 file size changes
    old_files = old.get("all_files", {})
    new_files = new.get("all_files", {})
    all_file_paths = set(old_files.keys()) | set(new_files.keys())

    file_deltas = []
    for fp in all_file_paths:
        o = old_files.get(fp, {}).get("uncompressed", 0)
        n = new_files.get(fp, {}).get("uncompressed", 0)
        if o != n:
            file_deltas.append((fp, o, n, n - o))

    file_deltas.sort(key=lambda x: abs(x[3]), reverse=True)

    print(f"  Top 10 Size Changes:")
    print(f"  {'#':<4} {'Delta':>12}   {'File'}")
    print(f"  {'-' * 4} {'-' * 12}   {'-' * 50}")
    for i, (path, o, n, delta) in enumerate(file_deltas[:10], 1):
        print(f"  {i:<4} {fmt_delta(delta):>12}   {path}")
    print()

    # New and removed files
    new_only = {fp for fp in new_files if fp not in old_files}
    removed = {fp for fp in old_files if fp not in new_files}

    new_size = sum(new_files[fp]["uncompressed"] for fp in new_only)
    removed_size = sum(old_files[fp]["uncompressed"] for fp in removed)

    print(f"  New files:          {len(new_only)} files (+{fmt(new_size)})")
    print(f"  Removed files:      {len(removed)} files (-{fmt(removed_size)})")
    print()

    # Build comparison report for HTML generation
    comparison = {
        "old": old,
        "new": new,
        "category_deltas": [
            {"name": c, "old": o, "new": n, "delta": d} for c, o, n, d in cat_deltas
        ],
        "top_file_changes": [
            {"path": p, "old": o, "new": n, "delta": d} for p, o, n, d in file_deltas[:10]
        ],
        "new_files": sorted(new_only),
        "removed_files": sorted(removed),
        "new_files_size": new_size,
        "removed_files_size": removed_size,
    }

    # Save comparison JSON
    json_path = os.path.join(
        os.path.dirname(os.path.abspath(new_path)),
        f"{old_name}-vs-{new_name}-comparison.json",
    )
    with open(json_path, "w") as f:
        json.dump(comparison, f, indent=2)
    print(f"  Comparison JSON saved: {json_path}")
    print()

    return comparison, json_path


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: compare_ipa.py <old-report.json> <new-report.json>", file=sys.stderr)
        sys.exit(1)
    compare(sys.argv[1], sys.argv[2])
