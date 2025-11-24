# Requirements Dashboard

> [!NOTE] Master View
> This dashboard aggregates all requirements from the exported markdown files using Dataview queries. Place this file in your Obsidian vault alongside the requirement markdown files.

## 📊 All Requirements - Excel-Like Table

```dataview
TABLE WITHOUT ID
  file.link as "Requirement",
  Req_ID as "ID",
  Doc_Type as "Document",
  Level as "Level",
  Section as "Section #",
  Section_Title as "Section Title",
  Object_Number as "Object #",
  choice(Is_Section_Header, "📑 Header", "📄 Req") as "Type",
  Parents as "Parent IDs",
  Children as "Child IDs"
FROM "02-CACTCS/Requirements"
SORT Section ASC, Object_Number ASC
```

---

## 🔍 Filtered Views

### By Document Type

#### FCSS Requirements
```dataview
TABLE WITHOUT ID
  Req_ID as "ID",
  Section_Title as "Section",
  Object_Number as "Object #",
  file.link as "Requirement"
FROM "02-CACTCS/Requirements"
WHERE Doc_Type = "FCSS"
SORT Section ASC, Object_Number ASC
```

#### SRS Requirements  
```dataview
TABLE WITHOUT ID
  Req_ID as "ID",
  Section_Title as "Section",
  SRS_Local_Req_No as "Local Req #",
  file.link as "Requirement"
FROM "02-CACTCS/Requirements"
WHERE Doc_Type = "SRS"
SORT Section ASC
```

#### FCSRD Requirements
```dataview
TABLE WITHOUT ID
  Req_ID as "ID",
  Section_Title as "Section",
  Object_Number as "Object #",
  file.link as "Requirement"
FROM "02-CACTCS/Requirements"
WHERE Doc_Type = "FCSRD" OR Doc_Type = "CCSRD"
SORT Section ASC, Object_Number ASC
```

---

### By System Level

#### System Level (High)
```dataview
TABLE WITHOUT ID
  Req_ID as "ID",
  Doc_Type as "Doc",
  Section_Title as "Section",
  file.link as "Requirement"
FROM "02-CACTCS/Requirements"
WHERE contains(Level, "System") OR contains(Level, "High")
SORT Doc_Type ASC, Section ASC
```

#### Software Level (Low)
```dataview
TABLE WITHOUT ID
  Req_ID as "ID",
  Doc_Type as "Doc",
  Section_Title as "Section",
  file.link as "Requirement"
FROM "02-CACTCS/Requirements"
WHERE contains(Level, "Software") OR contains(Level, "Low")
SORT Doc_Type ASC, Section ASC
```

---

### Section Headers Only

```dataview
TABLE WITHOUT ID
  Req_ID as "Section ID",
  Doc_Type as "Document",
  Section_Title as "Title",
  Object_Number as "Section #",
  file.link as "Details"
FROM "02-CACTCS/Requirements"
WHERE Section_Inferred = false AND Is_Section_Header = true
SORT Doc_Type ASC, Object_Number ASC
```

---

## 🌳 Hierarchical Section View

### FCSS Sections with Requirements

```dataview
TABLE WITHOUT ID
  Section_Title as "Section",
  Object_Number as "Number",
  count(rows) as "Count",
  rows.file.link as "Requirements"
FROM "02-CACTCS/Requirements"
WHERE Doc_Type = "FCSS" AND Section_Title != ""
GROUP BY Section_Title, Object_Number
SORT Object_Number ASC
```

---

## 🔗 Traceability Views

### Requirements with Parents
```dataview
TABLE WITHOUT ID
  Req_ID as "ID",
  Section_Title as "Section",
  Parents as "Parent Requirements",
  file.link as "Requirement"
FROM "02-CACTCS/Requirements"
WHERE Parents != "" AND Parents != null
SORT Req_ID ASC
```

### Requirements with Children
```dataview
TABLE WITHOUT ID
  Req_ID as "ID",
  Section_Title as "Section",
  Children as "Child Requirements",
  file.link as "Requirement"
FROM "02-CACTCS/Requirements"
WHERE Children != "" AND Children != null
SORT Req_ID ASC
```

### Orphan Requirements (No Trace Links)
```dataview
TABLE WITHOUT ID
  Req_ID as "ID",
  Doc_Type as "Document",
  Section_Title as "Section",
  file.link as "Requirement"
FROM "02-CACTCS/Requirements"
WHERE (Parents = "" OR Parents = null) AND (Children = "" OR Children = null)
SORT Doc_Type ASC, Req_ID ASC
```

---

## 🔎 Search & Filter Examples

### Search by Section Title (Example: "Flight Control")
```dataview
TABLE WITHOUT ID
  Req_ID as "ID",
  Section_Title as "Section",
  Object_Number as "Object #",
  file.link as "Requirement"
FROM "02-CACTCS/Requirements"
WHERE contains(Section_Title, "Flight Control")
SORT Object_Number ASC
```

### Filter by Multiple Documents
```dataview
TABLE WITHOUT ID
  Req_ID as "ID",
  Doc_Type as "Document",
  Section_Title as "Section",
  file.link as "Requirement"
FROM "02-CACTCS/Requirements"
WHERE Doc_Type = "FCSS" OR Doc_Type = "FCSRD"
SORT Doc_Type ASC, Section ASC
```

---

## 📈 Statistics

### Document Type Summary
```dataview
TABLE WITHOUT ID
  Doc_Type as "Document Type",
  count(rows) as "Total Requirements",
  count(rows.Section_Title) as "With Section Context"
FROM "02-CACTCS/Requirements"
GROUP BY Doc_Type
SORT Doc_Type ASC
```

### Section Coverage
```dataview
TABLE WITHOUT ID
  Section_Title as "Section",
  count(rows) as "Requirements",
  Doc_Type as "Document"
FROM "02-CACTCS/Requirements"
WHERE Section_Title != "" AND Section_Title != null
GROUP BY Section_Title, Doc_Type
SORT count(rows) DESC
LIMIT 20
```

---

## 💡 Usage Tips

1. **Interactive Tables**: Click column headers to sort
2. **Filter in Place**: Modify `WHERE` clauses to filter results
3. **Customizable**: Copy any query and adjust fields/conditions
4. **Performance**: For large vaults, consider adding more specific folder paths

## 📝 Custom Query Template

```dataview
TABLE WITHOUT ID
  Req_ID as "Requirement ID",
  Section_Title as "Section",
  file.link as "Link"
FROM "02-CACTCS/Requirements"
WHERE Doc_Type = "YOUR_DOC_TYPE"
  AND Section_Title contains "YOUR_SECTION"
SORT Req_ID ASC
```

---

## 🎯 Quick Filters

**Add these as separate notes for instant views:**

- `#filter/fcss-only` → Only FCSS requirements
- `#filter/has-parents` → Only requirements with parent links  
- `#filter/section-headers` → Only section header rows
- `#filter/orphans` → Requirements without trace links
