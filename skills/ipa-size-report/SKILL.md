---
name: ipa-size-report
description: "Analyze iOS IPA file sizes with categorized breakdown, comparison between builds, and optional HTML report"
---

# IPA Size Report

You are an iOS IPA file size analyzer. Your job is to analyze IPA files and present clear, categorized size breakdowns.

## Argument Parsing

Parse `$ARGUMENTS` to determine the mode:

- **`--compare <path1> <path2>`**: Comparison mode (two IPAs, two JSON reports, or one of each)
- **`--html`**: Generate an HTML report in addition to terminal output
- **Any other path**: Single IPA analysis mode
- **Empty**: Ask the user for the IPA file path

A `.json` file is a saved report. A `.ipa` file needs fresh analysis.

## Step 1: Validate Input

For each IPA or JSON path provided:
1. Check the file exists using `test -f "<path>"`
2. For IPAs, show the compressed size using `stat -f "%z" "<path>"` (macOS syntax)
3. If the file doesn't exist, report the error and stop

**IMPORTANT**: Always double-quote all file paths — they may contain spaces.

## Step 2: Analyze IPA

For each IPA that needs analysis, run a single `python3` script via Bash that does everything:

```bash
python3 << 'PYEOF'
import subprocess, sys, json, os, re
from datetime import datetime
from collections import defaultdict

ipa_path = "<IPA_PATH>"  # Replace with actual quoted path

# Get compressed IPA size
ipa_size = os.path.getsize(ipa_path)

# Run zipinfo
result = subprocess.run(["zipinfo", "-l", ipa_path], capture_output=True, text=True)
if result.returncode != 0:
    print(f"Error running zipinfo: {result.stderr}", file=sys.stderr)
    sys.exit(1)

lines = result.stdout.strip().split("\n")

# Detect app name from Payload/*.app/ pattern
app_name = None
for line in lines:
    m = re.search(r'Payload/([^/]+)\.app/', line)
    if m:
        app_name = m.group(1)
        break

# Parse zipinfo -l output
# Format: perms version os uncompressed flags compressed method date time path
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
def categorize(path):
    # Relative path inside the app bundle
    p = path
    # On-Demand Resources (highest priority - excluded from download/install size)
    if ".assetpack/" in p or "OnDemandResources/" in p or p.endswith("OnDemandResources.plist") or p.endswith("AssetPackManifest.plist"):
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
    # Executable binary: file in app root with no extension matching app name
    if app_name and f"/{app_name}.app/{app_name}" in p and ext == "":
        return "Executable Binary"
    if ext == "":
        # Other binaries (in Frameworks, appex, etc. already caught above)
        # Check if it looks like a binary in the app root
        app_root = f"Payload/{app_name}.app/" if app_name else None
        if app_root and p.startswith(app_root) and "/" not in p[len(app_root):]:
            return "Executable Binary"
    return "Other Resources"

categories = defaultdict(lambda: {"uncompressed": 0, "compressed": 0, "file_count": 0})
all_files = {}

for filepath, sizes in files.items():
    cat = categorize(filepath)
    categories[cat]["uncompressed"] += sizes["uncompressed"]
    categories[cat]["compressed"] += sizes["compressed"]
    categories[cat]["file_count"] += 1
    all_files[filepath] = {**sizes, "category": cat}

# Sort categories by uncompressed size descending
sorted_cats = sorted(categories.items(), key=lambda x: x[1]["uncompressed"], reverse=True)

# Top 20 files by uncompressed size
top_files = sorted(files.items(), key=lambda x: x[1]["uncompressed"], reverse=True)[:20]

# Human-readable size
def fmt(b):
    if b >= 1_000_000_000:
        return f"{b / 1_000_000_000:.2f} GB"
    elif b >= 1_000_000:
        return f"{b / 1_000_000:.1f} MB"
    elif b >= 1000:
        return f"{b / 1000:.1f} KB"
    else:
        return f"{b} B"

# Calculate ODR (On-Demand Resources) sizes to exclude from download/install
odr_compressed = 0
odr_uncompressed = 0
for filepath, sizes in files.items():
    if ".assetpack/" in filepath or "OnDemandResources/" in filepath or filepath.endswith("OnDemandResources.plist") or filepath.endswith("AssetPackManifest.plist"):
        odr_compressed += sizes["compressed"]
        odr_uncompressed += sizes["uncompressed"]

# Print report
ipa_name = os.path.basename(ipa_path)
ratio = ((total_uncompressed - ipa_size) / total_uncompressed * 100) if total_uncompressed > 0 else 0

download_size = ipa_size - odr_compressed
install_size = total_uncompressed - odr_uncompressed

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
print(f"  {'-'*22} {'-'*14} {'-'*14} {'-'*10} {'-'*6}")
for cat, data in sorted_cats:
    pct = (data["uncompressed"] / total_uncompressed * 100) if total_uncompressed > 0 else 0
    print(f"  {cat:<22} {fmt(data['uncompressed']):>14} {fmt(data['compressed']):>14} {pct:>9.1f}% {data['file_count']:>6}")
print()

# Top 20 files
print(f"  Top 20 Largest Files:")
print(f"  {'#':<4} {'Size':>12}   {'File'}")
print(f"  {'-'*4} {'-'*12}   {'-'*50}")
for i, (path, sizes) in enumerate(top_files, 1):
    print(f"  {i:<4} {fmt(sizes['uncompressed']):>12}   {path}")
print()

# Save JSON report
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
    "top_files": [{"path": p, "uncompressed": s["uncompressed"], "compressed": s["compressed"]} for p, s in top_files],
    "all_files": all_files
}

json_path = os.path.splitext(ipa_path)[0] + "-size-report.json"
with open(json_path, "w") as f:
    json.dump(report, f, indent=2)
print(f"  JSON report saved: {json_path}")
print()

PYEOF
```

**IMPORTANT**: Replace `<IPA_PATH>` with the actual path, properly escaped for Python strings. If the path contains single quotes, use proper escaping.

## Step 3: Comparison Mode

When `--compare` is detected with two paths, do the following:

1. For each path:
   - If `.json`: load the saved report with `json.load()`
   - If `.ipa`: analyze it fresh (same logic as Step 2) and load the resulting JSON
2. Run a comparison Python script that:
   - Computes delta for overall sizes
   - Computes delta per category
   - Identifies top 10 individual file size changes (by absolute delta)
   - Lists new files (in new but not old) and removed files (in old but not new)
3. Display formatted output:

```
=== Build Comparison: <old_name> -> <new_name> ===

                     Old              New              Delta           Change
IPA (compressed):    120.5 MB         126.3 MB         +5.8 MB        +4.8%
IPA (uncompressed):  145.2 MB         152.2 MB         +7.0 MB        +4.8%
Download Size:       118.0 MB         123.5 MB         +5.5 MB        +4.7%
Install Size:        142.0 MB         148.8 MB         +6.8 MB        +4.8%

Category             Old              New              Delta           Change
-------------------  ---------------  ---------------  ----------      ------
Asset Catalogs       68.2 MB          71.5 MB          +3.3 MB        +4.8%  ▲
Frameworks           25.6 MB          25.6 MB           0.0 MB         0.0%  ─
...

Top 10 Size Changes:
#   Delta         File
--  -----------   ----------------------------------------
1   +3.2 MB       Payload/MyApp.app/Assets.car
...

New files:          3 files (+1.2 MB)
Removed files:      1 file  (-0.1 MB)
```

Use `▲` for increase, `▼` for decrease, `─` for unchanged. Format delta with `+` or `-` prefix.

## Step 4: HTML Report (when --html is passed or user requests it)

Generate a self-contained HTML file using the Write tool. The HTML should include:

- **Inline CSS only** (no external dependencies)
- **Clean, professional styling**: white background, system font stack, subtle borders
- **Summary header** with app name, date, download size, install size
- **Category table** with horizontal CSS bar charts (colored div widths proportional to size)
- **Top 20 files table**
- **If comparison mode**: side-by-side category comparison with color-coded deltas (green for decrease, red for increase), and new/removed files section

Save as `<ipa-name>-size-report.html` (or `<old>-vs-<new>-size-report.html` for comparison) in the same directory as the IPA.

Open with: `open "<html_path>"`

## Category Definitions

Use these patterns to classify files (checked in this priority order):

| Priority | Category | Match Rule |
|----------|----------|-----------|
| 0 | On-Demand Resources | Path contains `.assetpack/` or `OnDemandResources/` or ends with `OnDemandResources.plist`/`AssetPackManifest.plist` |
| 1 | Frameworks | Path contains `/Frameworks/` and (`.framework/` or `.dylib`) |
| 2 | Code Signing | Path contains `/_CodeSignature/` or ends with `.mobileprovision`/`.cer` |
| 3 | App Extensions | Path contains `/PlugIns/` and `.appex/` |
| 4 | Asset Catalogs | Ends with `.car` |
| 5 | Storyboards & NIBs | Contains `.storyboardc` or ends with `.nib` |
| 6 | Localization | Contains `.lproj/` |
| 7 | Images | Extension in: png, jpg, jpeg, gif, svg, pdf, webp, heic, ico, tiff |
| 8 | Plists & Config | Extension in: plist, json, xml, xcprivacy, storekit |
| 9 | Executable Binary | No extension, matches app name, in app root |
| 10 | Other Resources | Everything else |

## Important Notes

- Always quote file paths (spaces are common in IPA paths)
- Use `zipinfo -l` to avoid extracting large IPAs
- Use macOS `stat -f "%z"` (not Linux `stat -c`)
- The JSON report is saved automatically on every analysis for future comparisons
- Human-readable sizes: B < 1 KB, KB < 1 MB, MB < 1 GB, GB >= 1 GB (1 decimal place)
