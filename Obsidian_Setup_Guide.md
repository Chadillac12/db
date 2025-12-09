# Obsidian Dataview Setup Guide

## 📦 Prerequisites

### 1. Install Obsidian Dataview Plugin

1. Open Obsidian Settings (⚙️)
2. Go to **Community Plugins**
3. Click **Browse** and search for "Dataview"
4. Install and **Enable** the Dataview plugin
5. Restart Obsidian

### 2. Enable JavaScript Queries (Optional)

For advanced views with DataviewJS:
1. Open **Settings** → **Dataview**
2. Enable **Enable JavaScript Queries**
3. Enable **Enable Inline JavaScript Queries**

---

## 📁 Folder Structure

Organize your Obsidian vault as follows:

```
YourVault/
├── Requirements_Dashboard.md          ← Master dashboard (place in root)
├── Requirements_By_Section.md         ← Section view (place in root)
├── 02-CACTCS/Requirements/            ← Export folder from build script
│   ├── FCSS/
│   │   ├── FCSS-00001.md
│   │   ├── FCSS-00002.md
│   │   └── ...
│   ├── SRS/
│   │   ├── SRS-1-1.md
│   │   ├── SRS-1-2.md
│   │   └── ...
│   └── FCSRD/
│       └── ...
```

---

## 🚀 Quick Start

### Step 1: Export Requirements

Run your build script to generate markdown files:

```powershell
cd c:\ws_c\dev
python build_requirements_db_v2.py `
  --run-config run_config_v3.yaml `
  --output-dir output `
  --create-markdown
```

This creates: `output/02-CACTCS/Requirements/`

### Step 2: Copy to Obsidian

Copy the export folder to your Obsidian vault:

```powershell
Copy-Item -Recurse `
  output\anythingllm_md_export\ `
  "C:\Path\To\Your\ObsidianVault\"
```

### Step 3: Copy Dashboard Files

Copy the dashboard markdown files to your vault root:

```powershell
Copy-Item c:\ws_c\dev\Requirements_Dashboard.md `
  "C:\Path\To\Your\ObsidianVault\"
  
Copy-Item c:\ws_c\dev\Requirements_By_Section.md `
  "C:\Path\To\Your\ObsidianVault\"
```

### Step 4: Open Dashboards

In Obsidian, open:
- `Requirements_Dashboard.md` for the main view
- `Requirements_By_Section.md` for hierarchical view

---

## ✨ Features & Capabilities

### Excel-Like Filtering

✅ **Sortable Columns**: Click any column header to sort  
✅ **Multiple Conditions**: Combine filters with AND/OR  
✅ **Text Search**: Search within section titles, IDs, etc.  
✅ **Grouping**: Group by document type, section, level  
✅ **Statistics**: Count, aggregate, summarize data

### Sample Queries You Can Modify

#### Filter by Multiple Criteria
```dataview
TABLE Req_ID, Section_Title, file.link
FROM "02-CACTCS/Requirements"
WHERE Doc_Type = "FCSS" 
  AND contains(Section_Title, "Control")
  AND Level contains "System"
SORT Req_ID ASC
```

#### Count Requirements by Type
```dataview
TABLE Doc_Type, count(rows) as Total
FROM "02-CACTCS/Requirements"
GROUP BY Doc_Type
```

#### Find Requirements Without Parents
```dataview
TABLE Req_ID, Section_Title, file.link
FROM "02-CACTCS/Requirements"
WHERE Parents = "" OR Parents = null
SORT Req_ID
```

---

## 🎨 Customization Tips

### Change Folder Path

If your requirements are in a different folder, update queries:

**Before:**
```dataview
FROM "02-CACTCS/Requirements"
```

**After:**
```dataview
FROM "my_requirements"
```

### Add Custom Columns

Modify the TABLE clause to show different fields:

```dataview
TABLE WITHOUT ID
  Req_ID as "ID",
  YOUR_CUSTOM_FIELD as "Custom",
  file.link as "Link"
FROM "02-CACTCS/Requirements"
```

### Create Saved Filters

Create a new note for each filter, e.g., `Filter - FCSS Only.md`:

```dataview
TABLE Req_ID, Section_Title, file.link
FROM "02-CACTCS/Requirements"
WHERE Doc_Type = "FCSS"
SORT Section, Object_Number
```

---

## 🔧 Troubleshooting

### Queries Show No Results

1. **Check folder path**: Ensure `"anythingllm_md_export"` matches your actual folder name
2. **Verify YAML**: Open a requirement file and check the frontmatter format
3. **Refresh**: Press `Ctrl+R` to reload the vault
4. **Enable Dataview**: Ensure the plugin is enabled in Settings

### Slow Performance

1. **Limit results**: Add `LIMIT 100` to queries
2. **Use specific folders**: Specify exact paths instead of searching everywhere
3. **Disable auto-refresh**: Settings → Dataview → disable auto-refresh

### Fields Not Showing

1. **Check field names**: Exact match required (case-sensitive)
2. **View raw markdown**: Open any requirement file in source mode
3. **Verify YAML syntax**: Ensure frontmatter is properly formatted

---

## 📚 Resources

- **Dataview Documentation**: https://blacksmithgu.github.io/obsidian-dataview/
- **Query Language**: https://blacksmithgu.github.io/obsidian-dataview/queries/structure/
- **Functions Reference**: https://blacksmithgu.github.io/obsidian-dataview/reference/functions/

---

## 💡 Pro Tips

1. **Pin Dashboards**: Right-click tab → Pin for quick access
2. **Use Tags**: Add tags in queries for additional filtering
3. **Combine Views**: Create multiple tabs with different dashboards
4. **Export Results**: Copy table results to Excel via clipboard
5. **Live Updates**: Dataview refreshes automatically when files change

---

## 🎯 Next Steps

1. ✅ Install Dataview plugin
2. ✅ Export requirements from build script  
3. ✅ Copy files to Obsidian vault
4. ✅ Open dashboards
5. 🎨 Customize queries for your workflow
6. 📊 Create additional filtered views as needed
