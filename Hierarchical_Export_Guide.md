# Hierarchical Markdown Export Guide

## Overview

The `reorganize_hierarchical.py` script creates a hierarchical copy of your flat markdown exports, organizing files into folders based on their section numbers.

## Folder Structure Examples

### Before (Flat):
```
02-CACTCS/Requirements/
├── FCSS/
│   ├── FCSS-00001.md  (Section 1.2.3)
│   ├── FCSS-00002.md  (Section 1.2.3-1)
│   ├── FCSS-00050.md  (Section 4.1)
│   └── FCSS-00100.md  (Section 4.1.2-5)
```

### After (Hierarchical):
```
anythingllm_md_export_hierarchical/
├── FCSS/
│   ├── 1/
│   │   └── 1.2/
│   │       └── 1.2.3/
│   │           ├── FCSS-00001.md  (Section 1.2.3)
│   │           └── FCSS-00002.md  (Section 1.2.3-1)
│   ├── 4/
│   │   └── 4.1/
│   │       ├── FCSS-00050.md  (Section 4.1)
│   │       └── 4.1.2/
│   │           └── FCSS-00100.md  (Section 4.1.2-5)
│   └── _unsectioned/
│       └── FCSS-XXXX.md  (No section number)
```

## Usage

### Basic Usage

```powershell
# After running build_requirements_db_v2.py with --create-markdown
python reorganize_hierarchical.py `
  output/anythingllm_md_export `
  output/anythingllm_md_export_hierarchical
```

### Dry Run (Preview)

```powershell
# See what would happen without actually creating files
python reorganize_hierarchical.py `
  output/anythingllm_md_export `
  output/hierarchical `
  --dry-run -v
```

### With Verbose Output

```powershell
# Show detailed file-by-file progress
python reorganize_hierarchical.py `
  anythingllm_md_export `
  hierarchical_export `
  -v
```

## How It Works

### Section Number Parsing

The script extracts section numbers from YAML frontmatter in this priority order:

1. `Section_Number`
2. `Section`
3. `Object_Number` (only if no dash - section headers)
4. `SRS_Section` (for SRS documents)

### Hierarchy Rules

- **"1.2.3"** → Creates folders: `1/` → `1.2/` → `1.2.3/`
- **"4.1.2-5"** → Creates folders: `4/` → `4.1/` → `4.1.2/` (ignores `-5` suffix)
- **"2"** → Creates folder: `2/`
- **No section** → Goes to `_unsectioned/` folder

### Example Transformations

| Section Number | Folder Path |
|----------------|-------------|
| `1.2.3` | `FCSS/1/1.2/1.2.3/` |
| `4.1.2-5` | `FCSS/4/4.1/4.1.2/` |
| `2` | `FCSS/2/` |
| `10.5.2` | `FCSS/10/10.5/10.5.2/` |
| (none) | `FCSS/_unsectioned/` |

## Integration with Build Script

### Option 1: Run Manually After Export

```powershell
# Step 1: Generate flat export
python build_requirements_db_v2.py `
  --run-config schema.yaml `
  --output-dir output `
  --create-markdown

# Step 2: Create hierarchical version
python reorganize_hierarchical.py `
  output/anythingllm_md_export `
  output/anythingllm_md_export_hierarchical
```

### Option 2: Create Batch Script

Create `export_both.ps1`:
```powershell
# Generate requirements and both markdown formats

# Run main build
python build_requirements_db_v2.py `
  --run-config schema.yaml `
  --output-dir output `
  --create-markdown

# Create hierarchical copy
if ($LASTEXITCODE -eq 0) {
  Write-Host "`nCreating hierarchical export..." -ForegroundColor Cyan
  python reorganize_hierarchical.py `
    output/anythingllm_md_export `
    output/anythingllm_md_export_hierarchical
}

Write-Host "`n✅ Export complete!" -ForegroundColor Green
Write-Host "  Flat:         output/02-CACTCS/Requirements/" -ForegroundColor Gray
Write-Host "  Hierarchical: output/anythingllm_md_export_hierarchical/" -ForegroundColor Gray
```

Then run:
```powershell
./export_both.ps1
```

## Features

### ✅ Preserves Original Files
- Copies files (doesn't move them)
- Original flat structure remains unchanged
- Safe to run multiple times

### ✅ Smart Section Parsing
- Handles multi-level sections (1.2.3.4.5...)
- Ignores requirement suffixes (1.2.3-5 → 1.2.3/)
- Works with various section formats

### ✅ Handles Edge Cases
- Files without sections → `_unsectioned/` folder
- Invalid section numbers → `_unsectioned/` folder
- Missing YAML → `_unsectioned/` folder

### ✅ Safe Operations
- Prompts before overwriting existing output
- Dry-run mode for testing
- Detailed error messages

## Use Cases

### 1. Obsidian File Browser Navigation
Navigate requirements by section hierarchy in Obsidian's file explorer:
```
FCSS/
  └── 4/
      └── 4.1/
          ├── 4.1.1/
          │   ├── FCSS-00045.md
          │   └── FCSS-00046.md
          └── 4.1.2/
              └── FCSS-00050.md
```

### 2. Section-Based Reviews
Review all requirements in a specific section:
```powershell
# All section 4.1.2 requirements
ls output/hierarchical/FCSS/4/4.1/4.1.2/
```

### 3. Team Collaboration
Different team members work on different sections:
- Team A: `FCSS/4/` folder
- Team B: `FCSS/5/` folder

### 4. Export Subsets
Copy just one section's requirements:
```powershell
# Copy all section 4 requirements
Copy-Item -Recurse `
  output/hierarchical/FCSS/4/ `
  section_4_review/
```

## Compatibility

### Works With:
- ✅ All document types (FCSS, SRS, FCSRD, etc.)
- ✅ Section headers (Is_Section_Header: true)
- ✅ Regular requirements
- ✅ Arbitrary section depth (1.2.3.4.5...)
- ✅ SRS-specific sections

### Obsidian Integration:
- ✅ Use with existing Dataview dashboards
- ✅ Update folder path in queries: `FROM "anythingllm_md_export_hierarchical"`
- ✅ File links still work (same filenames)
- ✅ Visual folder navigation in file browser

## Troubleshooting

### Q: Files going to _unsectioned?
**A:** Check YAML frontmatter has `Section:` or `Section_Number:` field

### Q: Want to change folder names?
**A:** Edit the `parse_section_number()` function in the script

### Q: Need to reorganize existing hierarchical export?
**A:** Delete output directory and run again, or use `--dry-run` first

### Q: Performance with thousands of files?
**A:** Script is fast (copies ~1000 files/second), uses efficient pathlib operations

## Output Summary

After running, you'll see:
```
Reorganizing markdown files...
  Source: output/anythingllm_md_export
  Output: output/anythingllm_md_export_hierarchical
  Mode: LIVE

Found 1245 markdown files in output/anythingllm_md_export

Processed 1245 files:
  ✓ Organized into hierarchical folders: 1189
  ⚠ No section number (in _unsectioned): 56

✅ Hierarchical export created at: output/anythingllm_md_export_hierarchical
```

## Benefits

1. **Better Navigation**: Browse by section in Obsidian file explorer
2. **Logical Organization**: Mirrors document structure
3. **Team Workflows**: Assign folders to team members
4. **Selective Review**: Easily review one section at a time
5. **Flexibility**: Keep both flat and hierarchical versions
6. **No Data Loss**: Original files unchanged
