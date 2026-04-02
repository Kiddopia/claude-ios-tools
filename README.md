# claude-ios-tools

A Claude Code plugin with iOS development utilities.

## Skills

### ipa-size-report

Analyze iOS IPA file sizes with categorized breakdown, build comparison, and optional HTML report.

**Features:**
- Categorized size breakdown (Frameworks, Assets, ODR, Code Signing, etc.)
- On-Demand Resources (ODR) detection — separates download vs install size
- Build-to-build comparison with delta analysis
- Interactive HTML report generation
- JSON export for tracking size trends over time

## Installation

Add the marketplace and install:

```
/plugin marketplace add Kiddopia/claude-ios-tools
/plugin install claude-ios-tools@Kiddopia/claude-ios-tools
```

## Usage

### Analyze a single IPA

```
/ipa-size-report /path/to/MyApp.ipa
```

Prints a terminal report with download size, install size, category breakdown, and top 20 largest files. Also saves a JSON report (`MyApp-size-report.json`) for future comparisons.

### Compare two builds

```
/ipa-size-report --compare /path/to/old.ipa /path/to/new.ipa
```

Shows size deltas for overall metrics, per-category changes, top 10 file changes, and new/removed files. You can also compare using previously saved JSON reports:

```
/ipa-size-report --compare old-size-report.json new-size-report.json
```

### Generate an HTML report

Add `--html` to any command to get a self-contained HTML report:

```
/ipa-size-report /path/to/MyApp.ipa --html
/ipa-size-report --compare old.ipa new.ipa --html
```

The HTML file opens automatically in your default browser.

## Author

**ashishswain-20** @ [Kiddopia](https://github.com/Kiddopia)
