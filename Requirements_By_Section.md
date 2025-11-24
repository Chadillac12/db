# Requirements by Section - Interactive View

> [!TIP] Section-Focused Dashboard
> This view organizes requirements by their section hierarchy, making it easy to navigate through the document structure.

## 📂 Browse by Section

### All Sections with Their Requirements

```dataviewjs
const pages = dv.pages('"02-CACTCS/Requirements"')
  .where(p => p.Section_Title && p.Section_Title != "");

const grouped = pages
  .groupBy(p => p.Section_Title);

for (let group of grouped.sort(g => g.key)) {
  dv.header(3, `📑 ${group.key}`);
  
  const reqs = group.rows.sort(r => r.Object_Number);
  
  dv.table(
    ["ID", "Object #", "Type", "Requirement"],
    reqs.map(r => [
      r.Req_ID,
      r.Object_Number || "—",
      r.Is_Section_Header ? "📑 Header" : "📄 Req",
      r.file.link
    ])
  );
}
```

---

## 🎯 Section Navigator

### Quick Jump to Section

```dataview
TABLE WITHOUT ID
  ("[[#" + Section_Title + "|→ Jump]]") as "Jump",
  Section_Title as "Section Name",
  count(rows) as "Requirements",
  Doc_Type as "Document"
FROM "02-CACTCS/Requirements"
WHERE Section_Title != "" AND Section_Title != null
GROUP BY Section_Title, Doc_Type
SORT Section_Title ASC
```

---

## 📊 Section Statistics

### Requirements Count per Section

```dataviewjs
const pages = dv.pages('"02-CACTCS/Requirements"')
  .where(p => p.Section_Title && p.Section_Title != "");

const stats = pages
  .groupBy(p => `${p.Doc_Type} - ${p.Section_Title}`)
  .map(g => {
    const headers = g.rows.filter(r => r.Is_Section_Header).length;
    const reqs = g.rows.filter(r => !r.Is_Section_Header).length;
    return {
      section: g.key,
      headers: headers,
      requirements: reqs,
      total: g.rows.length
    };
  })
  .sort(s => s.total, 'desc');

dv.table(
  ["Section", "Headers", "Requirements", "Total"],
  stats.map(s => [s.section, s.headers, s.requirements, s.total])
);
```

---

## 🌲 Section Tree Structure

### FCSS Hierarchy

```dataviewjs
const fcss = dv.pages('"02-CACTCS/Requirements"')
  .where(p => p.Doc_Type == "FCSS" && p.Object_Number);

// Group by top-level section (e.g., "4" from "4.1.1")
const topLevel = fcss
  .groupBy(p => {
    const obj = String(p.Object_Number);
    return obj.split('.')[0] || obj.split('-')[0];
  });

for (let section of topLevel.sort(g => Number(g.key))) {
  dv.header(3, `Section ${section.key}`);
  
  const items = section.rows.sort(r => String(r.Object_Number));
  
  for (let item of items) {
    const indent = (String(item.Object_Number).split('.').length - 1) * 2;
    const spaces = " ".repeat(indent);
    const icon = item.Is_Section_Header ? "📑" : "📄";
    
    dv.paragraph(
      `${spaces}- ${icon} \`${item.Object_Number}\` ${item.file.link} - ${item.Section_Title || ''}`
    );
  }
}
```

---

## 🔍 Section Search

### Find Requirements in Specific Sections

**Modify the section name in the query below:**

```dataview
TABLE WITHOUT ID
  Req_ID as "ID",
  Object_Number as "Object #",
  choice(Is_Section_Header, "📑", "📄") as "",
  file.link as "Requirement",
  Parents as "Parents"
FROM "anythingllm_md_export"
WHERE contains(Section_Title, "YOUR_SECTION_NAME_HERE")
SORT Object_Number ASC
```

**Example searches:**
- Replace `YOUR_SECTION_NAME_HERE` with `"Flight Control"` 
- Replace with `"System"` for all system-related sections
- Replace with `"Safety"` for safety requirements

---

## 📑 Section Headers Reference

```dataview
TABLE WITHOUT ID
  Object_Number as "Section #",
  Section_Title as "Title",
  Doc_Type as "Doc",
  file.link as "Details"
FROM "anythingllm_md_export"
WHERE Is_Section_Header = true
SORT Doc_Type ASC, Object_Number ASC
```
