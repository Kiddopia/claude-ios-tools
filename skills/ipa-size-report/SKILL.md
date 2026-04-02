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

## Step 0: Locate Scripts

Use Glob to find the plugin's scripts directory:

```
pattern: **/claude-ios-tools/scripts/analyze_ipa.py
```

Extract the directory path from the result — this is `SCRIPTS_DIR`. All scripts are in this directory:
- `analyze_ipa.py` — single IPA analysis
- `compare_ipa.py` — comparison of two JSON reports
- `generate_html_report.py` — HTML report generation

## Step 1: Validate Input

For each IPA or JSON path provided:
1. Check the file exists using `test -f "<path>"`
2. For IPAs, show the compressed size using `stat -f "%z" "<path>"` (macOS syntax)
3. If the file doesn't exist, report the error and stop

**IMPORTANT**: Always double-quote all file paths — they may contain spaces.

## Step 2: Analyze IPA

For each IPA that needs analysis, run:

```bash
python3 "SCRIPTS_DIR/analyze_ipa.py" "<IPA_PATH>"
```

This will:
- Parse the IPA using `zipinfo -l` (no extraction needed)
- Categorize all files into 10 categories
- Print a formatted terminal report with size metrics, category breakdown, and top 20 files
- Save a JSON report as `<ipa-name>-size-report.json` for future comparisons

## Step 3: Comparison Mode

When `--compare` is detected with two paths:

1. For each path:
   - If `.json`: use it directly
   - If `.ipa`: run `analyze_ipa.py` on it first to generate the JSON report
2. Run the comparison:

```bash
python3 "SCRIPTS_DIR/compare_ipa.py" "<OLD_JSON_PATH>" "<NEW_JSON_PATH>"
```

This displays: overall size deltas, per-category comparison, top 10 file changes, and new/removed file counts.

## Step 4: HTML Report (when --html is passed or user requests it)

After analysis or comparison, generate an HTML report:

**Single IPA:**
```bash
python3 "SCRIPTS_DIR/generate_html_report.py" "<JSON_REPORT_PATH>"
```

**Comparison:**
```bash
python3 "SCRIPTS_DIR/generate_html_report.py" --compare "<OLD_JSON_PATH>" "<NEW_JSON_PATH>"
```

The HTML report is self-contained (inline CSS, no external dependencies) and saved alongside the JSON report. Open it with:

```bash
open "<html_path>"
```

## Important Notes

- Always quote file paths (spaces are common in IPA paths)
- Use macOS `stat -f "%z"` (not Linux `stat -c`)
- The JSON report is saved automatically on every analysis for future comparisons
