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

```
/ipa-size-report <path-to-ipa>
/ipa-size-report --html <path-to-ipa>
/ipa-size-report --compare <old-ipa-or-json> <new-ipa-or-json>
```

## Author

**ashishswain-20** @ [Kiddopia](https://github.com/Kiddopia)
