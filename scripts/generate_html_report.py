#!/usr/bin/env python3
"""Generate an HTML report from IPA size analysis JSON data."""

import json
import sys
import os
from html import escape

# ---------------------------------------------------------------------------
# Shared utilities
# ---------------------------------------------------------------------------

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


def delta_color(delta):
    """Return CSS color for a delta value."""
    if delta > 0:
        return "#dc3545"  # red — size increased
    elif delta < 0:
        return "#28a745"  # green — size decreased
    return "#6c757d"      # gray — unchanged


# ---------------------------------------------------------------------------
# CSS shared by both report types
# ---------------------------------------------------------------------------

BASE_CSS = """
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto,
                     Helvetica, Arial, sans-serif;
        max-width: 960px; margin: 0 auto; padding: 24px 20px;
        color: #1d1d1f; background: #fff; line-height: 1.5;
    }
    h1 { font-size: 1.6em; border-bottom: 2px solid #007AFF; padding-bottom: 8px; margin-bottom: 4px; }
    h2 { font-size: 1.15em; margin: 28px 0 12px; color: #1d1d1f; }
    .subtitle { color: #86868b; font-size: 0.9em; margin-bottom: 24px; }
    .metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px; margin-bottom: 28px; }
    .metric {
        background: #f5f5f7; border: 1px solid #e8e8ed; border-radius: 10px;
        padding: 14px 16px;
    }
    .metric-label { font-size: 0.8em; color: #86868b; margin-bottom: 2px; }
    .metric-value { font-size: 1.35em; font-weight: 600; }
    table { width: 100%; border-collapse: collapse; margin-bottom: 24px; font-size: 0.9em; }
    thead th {
        text-align: left; padding: 8px 10px;
        background: #f5f5f7; border-bottom: 2px solid #d2d2d7;
        font-weight: 600; white-space: nowrap;
    }
    thead th.r { text-align: right; }
    tbody td { padding: 7px 10px; border-bottom: 1px solid #e8e8ed; }
    tbody td.r { text-align: right; font-variant-numeric: tabular-nums; }
    tbody td.mono {
        font-family: 'SF Mono', Monaco, 'Cascadia Code', 'Consolas', monospace;
        font-size: 0.88em; word-break: break-all;
    }
    .bar-cell { width: 28%; }
    .bar-bg { background: #e8e8ed; border-radius: 4px; height: 18px; overflow: hidden; }
    .bar { height: 100%; background: #007AFF; border-radius: 4px; min-width: 2px; }
    .footer { margin-top: 32px; padding-top: 12px; border-top: 1px solid #e8e8ed; color: #86868b; font-size: 0.78em; }

    /* File explorer tree */
    .tree { font-size: 0.88em; margin-bottom: 24px; }
    .tree details { margin-left: 20px; }
    .tree > details { margin-left: 0; }
    .tree summary {
        cursor: pointer; padding: 5px 8px; border-radius: 6px;
        display: flex; align-items: center; gap: 8px;
        list-style: none; user-select: none;
    }
    .tree summary::-webkit-details-marker { display: none; }
    .tree summary::before {
        content: '\\25B6'; font-size: 0.6em; color: #86868b;
        transition: transform 0.15s ease; flex-shrink: 0;
    }
    .tree details[open] > summary::before { transform: rotate(90deg); }
    .tree summary:hover { background: #f5f5f7; }
    .tree .node-name {
        font-weight: 500;
        font-family: 'SF Mono', Monaco, 'Cascadia Code', 'Consolas', monospace;
        overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    }
    .tree .node-size {
        margin-left: auto; flex-shrink: 0; font-variant-numeric: tabular-nums;
        color: #1d1d1f; font-weight: 600; font-size: 0.95em;
    }
    .tree .node-pct {
        flex-shrink: 0; width: 48px; text-align: right;
        color: #86868b; font-size: 0.85em;
    }
    .tree .node-bar {
        flex-shrink: 0; width: 80px; height: 8px;
        background: #e8e8ed; border-radius: 4px; overflow: hidden;
    }
    .tree .node-bar-fill {
        height: 100%; background: #007AFF; border-radius: 4px;
    }
    .tree .file-row {
        margin-left: 20px; padding: 4px 8px; display: flex;
        align-items: center; gap: 8px; border-radius: 6px;
    }
    .tree .file-row:hover { background: #f5f5f7; }
    .tree .file-icon { color: #86868b; flex-shrink: 0; font-size: 0.85em; }
    .tree .folder-icon { flex-shrink: 0; font-size: 0.85em; }
    .tree .file-name {
        font-family: 'SF Mono', Monaco, 'Cascadia Code', 'Consolas', monospace;
        overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
        color: #555;
    }
    .tree .cat-badge {
        flex-shrink: 0; font-size: 0.7em; padding: 1px 6px;
        border-radius: 4px; background: #e8e8ed; color: #555;
    }
"""

COMPARISON_EXTRA_CSS = """
    .delta-pos { color: #dc3545; }
    .delta-neg { color: #28a745; }
    .delta-zero { color: #86868b; }
    .indicator { font-size: 0.85em; margin-left: 4px; }
    .section-note { color: #86868b; font-size: 0.85em; margin-bottom: 12px; }
"""


# ---------------------------------------------------------------------------
# File explorer tree
# ---------------------------------------------------------------------------

def build_file_tree(all_files):
    """Build a nested tree structure from a flat dict of file paths."""
    root = {"children": {}, "files": [], "size": 0}

    for filepath, info in all_files.items():
        parts = filepath.split("/")
        node = root
        for folder in parts[:-1]:
            if folder not in node["children"]:
                node["children"][folder] = {"children": {}, "files": [], "size": 0}
            node = node["children"][folder]
        node["files"].append({
            "name": parts[-1],
            "uncompressed": info["uncompressed"],
            "compressed": info.get("compressed", 0),
            "category": info.get("category", ""),
        })

    def calc_size(node):
        size = sum(f["uncompressed"] for f in node["files"])
        for child in node["children"].values():
            calc_size(child)
            size += child["size"]
        node["size"] = size

    calc_size(root)
    return root


def render_tree_html(node, total_size, depth=0):
    """Recursively render a tree node as HTML with <details>/<summary>."""
    html = ""
    sorted_children = sorted(
        node["children"].items(), key=lambda x: x[1]["size"], reverse=True
    )
    sorted_files = sorted(
        node["files"], key=lambda x: x["uncompressed"], reverse=True
    )

    for child_name, child in sorted_children:
        pct = (child["size"] / total_size * 100) if total_size > 0 else 0
        open_attr = " open" if depth < 2 else ""
        html += (
            f'<details{open_attr}>'
            f'<summary>'
            f'<span class="folder-icon">&#128193;</span>'
            f'<span class="node-name">{escape(child_name)}</span>'
            f'<span class="node-pct">{pct:.1f}%</span>'
            f'<span class="node-bar"><span class="node-bar-fill" style="width:{pct:.1f}%"></span></span>'
            f'<span class="node-size">{fmt(child["size"])}</span>'
            f'</summary>'
            f'{render_tree_html(child, total_size, depth + 1)}'
            f'</details>\n'
        )

    for f in sorted_files:
        pct = (f["uncompressed"] / total_size * 100) if total_size > 0 else 0
        cat = f.get("category", "")
        badge = f'<span class="cat-badge">{escape(cat)}</span>' if cat else ""
        html += (
            f'<div class="file-row">'
            f'<span class="file-icon">&#128196;</span>'
            f'<span class="file-name">{escape(f["name"])}</span>'
            f'{badge}'
            f'<span class="node-pct">{pct:.1f}%</span>'
            f'<span class="node-bar"><span class="node-bar-fill" style="width:{pct:.1f}%"></span></span>'
            f'<span class="node-size">{fmt(f["uncompressed"])}</span>'
            f'</div>\n'
        )

    return html


# ---------------------------------------------------------------------------
# Single report
# ---------------------------------------------------------------------------

def generate_single_report(report, output_path):
    """Generate a single-IPA HTML report."""
    app_name = escape(report["app_name"])
    date = escape(report["date"][:10])
    total_uncompressed = report["ipa_uncompressed_size"]

    # Build file explorer tree
    all_files = report.get("all_files", {})
    tree = build_file_tree(all_files)
    tree_html = render_tree_html(tree, total_uncompressed)

    odr_line = ""
    if report.get("odr_compressed_size", 0) > 0:
        odr_line = f"""
        <div class="metric">
            <div class="metric-label">ODR Assets</div>
            <div class="metric-value">{fmt(report['odr_compressed_size'])}</div>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>IPA Size Report — {app_name}</title>
    <style>{BASE_CSS}</style>
</head>
<body>
    <h1>IPA Size Report</h1>
    <p class="subtitle">{app_name} &mdash; {date}</p>

    <div class="metrics">
        <div class="metric">
            <div class="metric-label">Download Size</div>
            <div class="metric-value">{fmt(report['download_size'])}</div>
        </div>
        <div class="metric">
            <div class="metric-label">Install Size</div>
            <div class="metric-value">{fmt(report['install_size'])}</div>
        </div>
        <div class="metric">
            <div class="metric-label">IPA (compressed)</div>
            <div class="metric-value">{fmt(report['ipa_compressed_size'])}</div>
        </div>
        <div class="metric">
            <div class="metric-label">Total Files</div>
            <div class="metric-value">{report['total_files']}</div>
        </div>{odr_line}
    </div>

    <h2>File Explorer</h2>
    <div class="tree">
{tree_html}    </div>

    <div class="footer">Generated by ipa-size-report &bull; claude-ios-tools</div>
</body>
</html>"""

    with open(output_path, "w") as f:
        f.write(html)
    print(f"HTML report saved: {output_path}")


# ---------------------------------------------------------------------------
# Comparison report
# ---------------------------------------------------------------------------

def generate_comparison_report(old_report, new_report, output_path):
    """Generate a comparison HTML report from two JSON reports."""
    old_name = escape(old_report["app_name"])
    new_name = escape(new_report["app_name"])
    old_date = escape(old_report["date"][:10])
    new_date = escape(new_report["date"][:10])

    # Overall metrics comparison
    metrics = [
        ("IPA (compressed)", "ipa_compressed_size"),
        ("IPA (uncompressed)", "ipa_uncompressed_size"),
        ("Download Size", "download_size"),
        ("Install Size", "install_size"),
    ]

    metrics_rows = ""
    for label, key in metrics:
        o = old_report.get(key, 0)
        n = new_report.get(key, 0)
        delta = n - o
        pct = pct_change(o, n)
        sign = "+" if pct > 0 else ""
        css = "delta-pos" if delta > 0 else ("delta-neg" if delta < 0 else "delta-zero")
        metrics_rows += f"""        <tr>
            <td>{escape(label)}</td>
            <td class="r">{fmt(o)}</td>
            <td class="r">{fmt(n)}</td>
            <td class="r {css}">{fmt_delta(delta)}</td>
            <td class="r {css}">{sign}{pct:.1f}%</td>
        </tr>\n"""

    # Category comparison
    all_cats = set()
    old_cats = old_report.get("categories", {})
    new_cats = new_report.get("categories", {})
    all_cats.update(old_cats.keys())
    all_cats.update(new_cats.keys())

    cat_deltas = []
    for cat in all_cats:
        o = old_cats.get(cat, {}).get("uncompressed", 0)
        n = new_cats.get(cat, {}).get("uncompressed", 0)
        cat_deltas.append((cat, o, n, n - o))
    cat_deltas.sort(key=lambda x: abs(x[3]), reverse=True)

    cat_rows = ""
    for cat, o, n, delta in cat_deltas:
        pct = pct_change(o, n)
        sign = "+" if pct > 0 else ""
        css = "delta-pos" if delta > 0 else ("delta-neg" if delta < 0 else "delta-zero")
        ind = "\u25b2" if delta > 0 else ("\u25bc" if delta < 0 else "\u2500")
        cat_rows += f"""        <tr>
            <td>{escape(cat)}</td>
            <td class="r">{fmt(o)}</td>
            <td class="r">{fmt(n)}</td>
            <td class="r {css}">{fmt_delta(delta)}</td>
            <td class="r {css}">{sign}{pct:.1f}%</td>
            <td class="{css}"><span class="indicator">{ind}</span></td>
        </tr>\n"""

    # Top file changes
    old_files = old_report.get("all_files", {})
    new_files = new_report.get("all_files", {})
    all_paths = set(old_files.keys()) | set(new_files.keys())

    file_changes = []
    for fp in all_paths:
        o = old_files.get(fp, {}).get("uncompressed", 0)
        n = new_files.get(fp, {}).get("uncompressed", 0)
        if o != n:
            file_changes.append((fp, o, n, n - o))
    file_changes.sort(key=lambda x: abs(x[3]), reverse=True)

    file_rows = ""
    for i, (path, o, n, delta) in enumerate(file_changes[:10], 1):
        css = "delta-pos" if delta > 0 else ("delta-neg" if delta < 0 else "delta-zero")
        file_rows += f"""        <tr>
            <td class="r">{i}</td>
            <td class="r {css}">{fmt_delta(delta)}</td>
            <td class="mono">{escape(path)}</td>
        </tr>\n"""

    # New / removed files
    new_only = sorted(fp for fp in new_files if fp not in old_files)
    removed = sorted(fp for fp in old_files if fp not in new_files)
    new_size = sum(new_files[fp]["uncompressed"] for fp in new_only)
    removed_size = sum(old_files[fp]["uncompressed"] for fp in removed)

    new_files_rows = ""
    for fp in new_only[:20]:
        new_files_rows += f"""        <tr>
            <td class="r delta-pos">+{fmt(new_files[fp]['uncompressed'])}</td>
            <td class="mono">{escape(fp)}</td>
        </tr>\n"""
    if len(new_only) > 20:
        new_files_rows += f'        <tr><td colspan="2" class="delta-zero">...and {len(new_only) - 20} more</td></tr>\n'

    removed_files_rows = ""
    for fp in removed[:20]:
        removed_files_rows += f"""        <tr>
            <td class="r delta-neg">-{fmt(old_files[fp]['uncompressed'])}</td>
            <td class="mono">{escape(fp)}</td>
        </tr>\n"""
    if len(removed) > 20:
        removed_files_rows += f'        <tr><td colspan="2" class="delta-zero">...and {len(removed) - 20} more</td></tr>\n'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>IPA Comparison — {old_name} vs {new_name}</title>
    <style>{BASE_CSS}{COMPARISON_EXTRA_CSS}</style>
</head>
<body>
    <h1>Build Comparison</h1>
    <p class="subtitle">{old_name} ({old_date}) &rarr; {new_name} ({new_date})</p>

    <h2>Overall Size</h2>
    <table>
        <thead>
            <tr>
                <th>Metric</th>
                <th class="r">Old</th>
                <th class="r">New</th>
                <th class="r">Delta</th>
                <th class="r">Change</th>
            </tr>
        </thead>
        <tbody>
{metrics_rows}        </tbody>
    </table>

    <h2>Category Comparison</h2>
    <table>
        <thead>
            <tr>
                <th>Category</th>
                <th class="r">Old</th>
                <th class="r">New</th>
                <th class="r">Delta</th>
                <th class="r">Change</th>
                <th></th>
            </tr>
        </thead>
        <tbody>
{cat_rows}        </tbody>
    </table>

    <h2>Top 10 File Size Changes</h2>
    <table>
        <thead>
            <tr>
                <th class="r">#</th>
                <th class="r">Delta</th>
                <th>File</th>
            </tr>
        </thead>
        <tbody>
{file_rows}        </tbody>
    </table>

    <h2>New Files <span class="section-note">({len(new_only)} files, +{fmt(new_size)})</span></h2>
    <table>
        <thead><tr><th class="r">Size</th><th>File</th></tr></thead>
        <tbody>
{new_files_rows}        </tbody>
    </table>

    <h2>Removed Files <span class="section-note">({len(removed)} files, -{fmt(removed_size)})</span></h2>
    <table>
        <thead><tr><th class="r">Size</th><th>File</th></tr></thead>
        <tbody>
{removed_files_rows}        </tbody>
    </table>

    <div class="footer">Generated by ipa-size-report &bull; claude-ios-tools</div>
</body>
</html>"""

    with open(output_path, "w") as f:
        f.write(html)
    print(f"HTML comparison report saved: {output_path}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(
            "Usage:\n"
            "  generate_html_report.py <report.json>\n"
            "  generate_html_report.py --compare <old.json> <new.json>",
            file=sys.stderr,
        )
        sys.exit(1)

    if sys.argv[1] == "--compare":
        if len(sys.argv) != 4:
            print("Usage: generate_html_report.py --compare <old.json> <new.json>", file=sys.stderr)
            sys.exit(1)
        with open(sys.argv[2]) as f:
            old_data = json.load(f)
        with open(sys.argv[3]) as f:
            new_data = json.load(f)
        old_name = old_data["app_name"]
        new_name = new_data["app_name"]
        out = os.path.join(
            os.path.dirname(os.path.abspath(sys.argv[3])),
            f"{old_name}-vs-{new_name}-size-report.html",
        )
        generate_comparison_report(old_data, new_data, out)
    else:
        with open(sys.argv[1]) as f:
            data = json.load(f)
        out = os.path.join(
            os.path.dirname(os.path.abspath(sys.argv[1])),
            f"{data['app_name']}-size-report.html",
        )
        generate_single_report(data, out)
