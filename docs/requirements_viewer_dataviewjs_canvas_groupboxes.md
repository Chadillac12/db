```dataviewjs
try {
  // =========================
  // CONFIGURATION
  // =========================
  const CONFIG = {
    PAGE_SIZE: 20,
    DEBOUNCE_MS: 300,
    FOLDER_PATH: "02-CACTCS/Requirements",
    CACHE_DURATION: 60000,
    CANVAS_EXPORT_PATH: "Canvas Exports",

    HEADING_REQ_TEXT: "Requirement Text",
    HEADING_SIMULINK: "Simulink Model Views",

    DEFAULT_INCLUDE_SIMULINK: true,

    DISPLAY_FIELDS: [
      { label: "Document", field: "Doc_Name" },
      { label: "Document Type", field: "Doc_Type" },
      { label: "Section_Type", field: "Requirement_Type", fallback: "Section_Type" },
      { label: "Level", field: "Level" },
      { label: "Section Title", field: "Section_Title" },
      { label: "Object #", field: "Object_Number" },
      { label: "SRS Local", field: "SRS_Local_Req_No" }
    ]
  };

  // bumped key because reqType is now multi-select
  const FILTER_STATE_KEY = "requirements_filter_state_grouped_sectiontitle_v4_multireqtype";

  // =========================
  // STATE
  // =========================
  let displayedCount = 0;
  let currentQueue = [];
  let currentFilteredPages = [];
  let contentCache = new Map();
  let lastCacheClean = Date.now();

  // =========================
  // STYLES
  // =========================
  const STYLES = {
    container: { padding: "20px", backgroundColor: "var(--background-primary)" },

    filtersContainer: {
      padding: "20px",
      backgroundColor: "var(--background-primary-alt)",
      borderRadius: "8px",
      marginBottom: "15px",
      border: "1px solid var(--background-modifier-border)",
      display: "grid",
      gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))",
      gap: "15px"
    },
    filterGroup: { display: "flex", flexDirection: "column", gap: "5px" },
    filterLabel: { color: "var(--text-normal)", fontWeight: "700", fontSize: "0.9em" },
    select: {
      padding: "8px",
      borderRadius: "6px",
      border: "1px solid var(--background-modifier-border)",
      backgroundColor: "var(--background-primary)",
      color: "var(--text-normal)"
    },
    multiSelect: {
      padding: "8px",
      borderRadius: "6px",
      border: "1px solid var(--background-modifier-border)",
      backgroundColor: "var(--background-primary)",
      color: "var(--text-normal)",
      width: "100%",
      minHeight: "115px"
    },
    input: {
      padding: "8px",
      borderRadius: "6px",
      border: "1px solid var(--background-modifier-border)",
      backgroundColor: "var(--background-primary)",
      color: "var(--text-normal)"
    },

    stats: {
      display: "flex",
      justifyContent: "space-between",
      alignItems: "center",
      padding: "10px",
      backgroundColor: "var(--background-secondary)",
      borderRadius: "8px",
      marginBottom: "12px",
      fontSize: "0.9em"
    },

    bulkActions: {
      display: "flex",
      flexWrap: "wrap",
      gap: "10px",
      marginBottom: "15px"
    },
    button: {
      padding: "9px 14px",
      borderRadius: "8px",
      border: "1px solid var(--background-modifier-border)",
      cursor: "pointer",
      fontSize: "0.9em",
      fontWeight: "800",
      backgroundColor: "var(--background-secondary)",
      color: "var(--text-normal)"
    },
    primaryButton: {
      backgroundColor: "var(--interactive-accent)",
      color: "var(--text-on-accent)",
      border: "none"
    },
    // IMPORTANT: prevent TypeError from Object.assign(..., STYLES.secondaryButton)
    secondaryButton: {},

    groupHeader: {
      marginTop: "18px",
      marginBottom: "10px",
      padding: "12px",
      backgroundColor: "var(--background-secondary-alt)",
      borderRadius: "10px",
      borderLeft: "5px solid var(--interactive-accent)"
    },
    groupTitle: {
      fontSize: "1.15em",
      fontWeight: "900",
      color: "var(--interactive-accent)",
      lineHeight: "1.2"
    },
    groupMeta: { marginTop: "6px", fontSize: "0.9em", color: "var(--text-muted)" },

    requirementCard: {
      marginBottom: "14px",
      border: "1px solid var(--background-modifier-border)",
      borderRadius: "10px",
      padding: "14px",
      backgroundColor: "var(--background-primary-alt)"
    },
    reqHeader: {
      display: "flex",
      justifyContent: "space-between",
      alignItems: "center",
      marginBottom: "10px",
      padding: "10px",
      backgroundColor: "var(--background-secondary)",
      borderRadius: "8px"
    },
    reqId: {
      fontSize: "1.05em",
      fontWeight: "900",
      color: "var(--interactive-accent)",
      cursor: "pointer"
    },
    badge: {
      padding: "3px 10px",
      borderRadius: "12px",
      fontSize: "0.8em",
      fontWeight: "800",
      backgroundColor: "var(--background-modifier-border)",
      color: "var(--text-muted)"
    },

    metadataGrid: {
      display: "grid",
      gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
      gap: "8px",
      marginBottom: "10px"
    },
    metadataItem: {
      display: "flex",
      gap: "6px",
      fontSize: "0.9em",
      padding: "6px 10px",
      backgroundColor: "var(--background-secondary)",
      borderRadius: "6px"
    },

    sectionLabel: {
      fontWeight: "900",
      fontSize: "0.9em",
      color: "var(--text-muted)",
      marginTop: "10px",
      marginBottom: "6px"
    },

    markdownBox: {
      padding: "10px",
      borderLeft: "3px solid var(--background-modifier-border)",
      backgroundColor: "var(--background-primary)",
      borderRadius: "8px",
      overflowX: "auto"
    },

    loadMore: {
      width: "100%",
      padding: "12px",
      marginTop: "20px",
      backgroundColor: "var(--interactive-accent)",
      color: "var(--text-on-accent)",
      border: "none",
      borderRadius: "10px",
      cursor: "pointer",
      fontSize: "1em",
      fontWeight: "900"
    },

    fallbackPre: {
      whiteSpace: "pre-wrap",
      margin: "0"
    },
    imgGrid: {
      marginTop: "10px",
      display: "flex",
      flexWrap: "wrap",
      gap: "10px"
    },
    img: {
      maxWidth: "420px",
      maxHeight: "300px",
      borderRadius: "8px",
      border: "1px solid var(--background-modifier-border)"
    }
  };

  // =========================
  // UTILS
  // =========================
  function debounce(func, wait) {
    let t;
    return (...args) => { clearTimeout(t); t = setTimeout(() => func(...args), wait); };
  }

  function getCachedContent(path) {
    if (Date.now() - lastCacheClean > CONFIG.CACHE_DURATION) {
      contentCache.clear();
      lastCacheClean = Date.now();
    }
    return contentCache.get(path);
  }

  function setCachedContent(path, content) {
    contentCache.set(path, content);
  }

  // UPDATED: supports multi-select
  function saveFilterState(filters) {
    const state = {};
    for (const k in filters) {
      const el = filters[k];
      if (el.type === "checkbox") state[k] = Boolean(el.checked);
      else if (el.tagName === "SELECT" && el.multiple) {
        state[k] = Array.from(el.selectedOptions).map(o => o.value);
      } else state[k] = el.value;
    }
    localStorage.setItem(FILTER_STATE_KEY, JSON.stringify(state));
  }

  function loadFilterState() {
    const saved = localStorage.getItem(FILTER_STATE_KEY);
    return saved ? JSON.parse(saved) : {};
  }

  function wildcardMatch(value, pattern) {
    if (!pattern) return true;
    const regex = new RegExp(String(pattern).split("*").join(".*"), "i");
    return regex.test(String(value || ""));
  }

  function normalizeTitle(t) {
    return String(t || "")
      .replace(/\u00A0/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  }

  function extractSectionIdFromTitle(t) {
    const m = normalizeTitle(t).match(/^(\d+(?:\.\d+)*)\b/);
    return m ? m[1] : "";
  }

  function compareSectionIds(a, b) {
    const aParts = String(a || "").split(".").map(x => parseInt(x, 10) || 0);
    const bParts = String(b || "").split(".").map(x => parseInt(x, 10) || 0);
    const len = Math.max(aParts.length, bParts.length);
    for (let i = 0; i < len; i++) {
      const av = aParts[i] ?? 0;
      const bv = bParts[i] ?? 0;
      if (av < bv) return -1;
      if (av > bv) return 1;
    }
    return 0;
  }

  function getPageSortKey(page) {
    const fromSection = page.Section;
    if (fromSection && String(fromSection).trim()) return String(fromSection).trim();

    const fromObj = page.Object_Number;
    if (fromObj && String(fromObj).trim()) return String(fromObj).trim();

    const fromSrs = page.SRS_Local_Req_No;
    if (fromSrs && String(fromSrs).trim()) return String(fromSrs).trim();

    const fromTitle = extractSectionIdFromTitle(page.Section_Title);
    if (fromTitle) return fromTitle;

    return String(page.Req_ID || page.file.name || "");
  }

  function extractHeadingSection(markdown, headingText, toEnd = false) {
    if (!markdown) return "";
    const escaped = headingText.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const headingRegex = new RegExp(`^##\\s+${escaped}\\s*$`, "mi");
    const m = markdown.match(headingRegex);
    if (!m) return "";

    const idx = markdown.toLowerCase().indexOf(m[0].toLowerCase());
    if (idx < 0) return "";

    const after = idx + m[0].length;
    const rest = markdown.slice(after);

    if (toEnd) return rest.trim();

    const next = rest.search(/^\s*##\s+/m);
    if (next === -1) return rest.trim();
    return rest.slice(0, next).trim();
  }

  // =========================
  // PROMPT MODAL
  // =========================
  async function customPrompt(message, defaultText = "") {
    return new Promise((resolve) => {
      const overlay = document.createElement("div");
      Object.assign(overlay.style, {
        position: "fixed",
        top: "0",
        left: "0",
        width: "100%",
        height: "100%",
        backgroundColor: "rgba(0,0,0,0.6)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: "9999"
      });

      const modal = document.createElement("div");
      Object.assign(modal.style, {
        backgroundColor: "var(--background-primary)",
        padding: "24px",
        borderRadius: "10px",
        boxShadow: "0 4px 20px rgba(0,0,0,0.35)",
        minWidth: "360px",
        maxWidth: "520px",
        border: "1px solid var(--background-modifier-border)"
      });

      const msg = modal.createEl("div", { text: message });
      msg.style.marginBottom = "14px";
      msg.style.fontSize = "1.05em";
      msg.style.fontWeight = "800";

      const input = modal.createEl("input");
      input.type = "text";
      input.value = defaultText;
      Object.assign(input.style, STYLES.input);
      input.style.marginBottom = "14px";

      const row = modal.createEl("div");
      row.style.display = "flex";
      row.style.justifyContent = "flex-end";
      row.style.gap = "10px";

      const ok = row.createEl("button", { text: "OK" });
      Object.assign(ok.style, STYLES.button, STYLES.primaryButton);

      const cancel = row.createEl("button", { text: "Cancel" });
      Object.assign(cancel.style, STYLES.button);

      overlay.appendChild(modal);
      document.body.appendChild(overlay);
      input.focus();

      ok.onclick = () => { document.body.removeChild(overlay); resolve(input.value); };
      cancel.onclick = () => { document.body.removeChild(overlay); resolve(null); };
      input.onkeydown = (e) => {
        if (e.key === "Enter") ok.click();
        if (e.key === "Escape") cancel.click();
      };
    });
  }

  // =========================
  // MARKDOWN RENDERING (fallback + image resolution + TABLES)
  // =========================
  const MarkdownRenderer = globalThis.MarkdownRenderer || null;

  function resolveVaultLinkToFile(linkText, sourcePath) {
    const cleaned = String(linkText || "")
      .split("|")[0]
      .trim()
      .split("#")[0]
      .split("^")[0]
      .trim();

    if (!cleaned) return null;

    const file = app.metadataCache?.getFirstLinkpathDest?.(cleaned, sourcePath) || null;
    return file;
  }

  function isImageFile(file) {
    const ext = (file?.extension || "").toLowerCase();
    return ["png","jpg","jpeg","gif","webp","svg","bmp","tif","tiff"].includes(ext);
  }

  // NEW: simple fallback renderer that renders markdown TABLES (and images)
  function renderFallbackParsed(targetEl, markdown, sourcePath) {
    targetEl.innerHTML = "";

    const lines = String(markdown || "").split("\n").map(l => l.replace(/\r$/, ""));

    const isBlank = (s) => !String(s || "").trim();
    const isComment = (s) => /^\s*<!--.*-->\s*$/.test(s);

    const embedRe = /^\s*!\[\[([^\]]+)\]\]\s*$/;          // ![[...]]
    const mdImgRe = /^\s*!\[[^\]]*\]\(([^)]+)\)\s*$/;     // ![](path)

    const isTableRow = (s) => /^\s*\|.*\|\s*$/.test(s);
    const isTableSep = (s) => {
      const cells = s.trim().split("|").slice(1, -1).map(x => x.trim());
      if (!cells.length) return false;
      return cells.every(c => /^:?-{3,}:?$/.test(c));
    };

    function parseTable(rows) {
      const splitRow = (r) => r.trim().split("|").slice(1, -1).map(x => x.trim());

      const header = splitRow(rows[0]);
      let align = header.map(() => "left");

      if (rows.length >= 2 && isTableSep(rows[1])) {
        const sep = splitRow(rows[1]);
        align = sep.map(c => {
          const left = c.startsWith(":");
          const right = c.endsWith(":");
          if (left && right) return "center";
          if (right) return "right";
          return "left";
        });
      }

      const bodyStart = (rows.length >= 2 && isTableSep(rows[1])) ? 2 : 1;
      const body = rows.slice(bodyStart).map(splitRow);
      return { header, body, align };
    }

    function renderTable(parent, table) {
      const wrap = parent.createEl("div");
      wrap.style.overflowX = "auto";
      wrap.style.margin = "8px 0";

      const t = wrap.createEl("table");
      t.style.width = "100%";
      t.style.borderCollapse = "collapse";
      t.style.fontSize = "0.9em";

      const border = "1px solid var(--background-modifier-border)";

      const thead = t.createEl("thead");
      const trh = thead.createEl("tr");
      table.header.forEach((h, i) => {
        const th = trh.createEl("th");
        th.textContent = h;
        th.style.textAlign = table.align[i] || "left";
        th.style.border = border;
        th.style.padding = "6px 8px";
        th.style.background = "var(--background-secondary)";
        th.style.fontWeight = "800";
        th.style.whiteSpace = "nowrap";
      });

      const tbody = t.createEl("tbody");
      table.body.forEach(row => {
        const tr = tbody.createEl("tr");
        row.forEach((cell, i) => {
          const td = tr.createEl("td");
          td.textContent = cell;
          td.style.textAlign = table.align[i] || "left";
          td.style.border = border;
          td.style.padding = "6px 8px";
          td.style.verticalAlign = "top";
        });
      });
    }

    let i = 0;
    while (i < lines.length) {
      const line = lines[i];

      if (isBlank(line) || isComment(line)) { i++; continue; }

      // Headings
      const hx = line.match(/^\s*(#{1,6})\s+(.*)\s*$/);
      if (hx) {
        const level = hx[1].length;
        const txt = hx[2];

        const h = targetEl.createEl("div");
        h.textContent = txt;
        h.style.fontWeight = "900";
        h.style.margin = "10px 0 6px";
        h.style.fontSize = level <= 2 ? "1.05em" : "0.95em";
        i++;
        continue;
      }

      // Table block
      if (isTableRow(line)) {
        const tableRows = [];
        while (i < lines.length && isTableRow(lines[i])) {
          tableRows.push(lines[i]);
          i++;
        }

        if (tableRows.length >= 2 && isTableSep(tableRows[1])) {
          renderTable(targetEl, parseTable(tableRows));
          continue;
        }

        // Not a "real" table; render raw
        const p = targetEl.createEl("div");
        p.style.whiteSpace = "pre-wrap";
        p.textContent = tableRows.join("\n");
        continue;
      }

      // Obsidian embed image
      const em = line.match(embedRe);
      if (em) {
        const file = resolveVaultLinkToFile(em[1], sourcePath);
        if (file && isImageFile(file)) {
          const img = targetEl.createEl("img");
          img.src = app.vault.getResourcePath(file);
          Object.assign(img.style, STYLES.img);
        } else {
          const warn = targetEl.createEl("div");
          warn.style.color = "var(--text-muted)";
          warn.textContent = `⚠️ Could not resolve embed: ${line}`;
        }
        i++;
        continue;
      }

      // Markdown image ![](...)
      const mi = line.match(mdImgRe);
      if (mi) {
        const raw = (mi[1] || "").trim().replace(/^["']|["']$/g, "");
        const file = resolveVaultLinkToFile(raw, sourcePath);
        const img = targetEl.createEl("img");
        img.src = file && isImageFile(file) ? app.vault.getResourcePath(file) : raw;
        Object.assign(img.style, STYLES.img);
        i++;
        continue;
      }

      // Plain text line
      const p = targetEl.createEl("div");
      p.style.whiteSpace = "pre-wrap";
      p.style.margin = "4px 0";
      p.textContent = line;

      i++;
    }
  }

  async function renderMarkdownInto(targetEl, markdown, sourcePath) {
    targetEl.innerHTML = "";
    if (!markdown) return;

    if (MarkdownRenderer && typeof MarkdownRenderer.renderMarkdown === "function") {
      const dummyComponent = { addChild() {}, register() {}, registerEvent() {}, unload() {} };
      try {
        await MarkdownRenderer.renderMarkdown(markdown, targetEl, sourcePath, dummyComponent);
        return;
      } catch (e) {
        // fall through
      }
    }

    renderFallbackParsed(targetEl, markdown, sourcePath);
  }

  function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }

  // =========================
  // CANVAS EXPORT (editable)  (UNCHANGED from your "known good")
  // =========================
  async function exportToCanvas(filteredPages) {
    try {
      if (!filteredPages?.length) {
        new Notice("⚠️ Nothing to export.");
        return;
      }

      // ---------------------------
      // Local md cache (fast-ish)
      // ---------------------------
      const mdCache = new Map();
      async function loadMd(path) {
        if (mdCache.has(path)) return mdCache.get(path);
        const md = await dv.io.load(path);
        mdCache.set(path, md);
        return md;
      }

      // ---------------------------
      // Safe IDs (short + stable)
      // ---------------------------
      function fnv1a(str) {
        let h = 0x811c9dc5;
        for (let i = 0; i < str.length; i++) {
          h ^= str.charCodeAt(i);
          h = (h + ((h << 1) + (h << 4) + (h << 7) + (h << 8) + (h << 24))) >>> 0;
        }
        return ("0000000" + h.toString(16)).slice(-8);
      }
      function safeId(path, suffix = "") {
        return "n_" + fnv1a(String(path) + "|" + suffix);
      }

      // ---------------------------
      // Folder + write
      // ---------------------------
      async function ensureFolderExists(folderPath) {
        const parts = folderPath.split("/").filter(Boolean);
        let cur = "";
        for (const p of parts) {
          cur = cur ? `${cur}/${p}` : p;
          if (!(await app.vault.adapter.exists(cur))) {
            try { await app.vault.createFolder(cur); } catch (_) {}
          }
        }
      }
      async function writeFile(path, text) {
        const existing = app.vault.getAbstractFileByPath(path);
        if (existing) await app.vault.modify(existing, text);
        else await app.vault.create(path, text);
      }

      // ---------------------------
      // Sorting: 1.2.3.4 numeric
      // ---------------------------
      function compareSection(a, b) {
        const aKey = String(a.Section ?? a.Object_Number ?? "").trim();
        const bKey = String(b.Section ?? b.Object_Number ?? "").trim();

        const toParts = (s) => s.split(".").map(x => (parseInt(x, 10) || 0));
        const ap = aKey ? toParts(aKey) : [];
        const bp = bKey ? toParts(bKey) : [];

        const len = Math.max(ap.length, bp.length);
        for (let i = 0; i < len; i++) {
          const av = ap[i] ?? 0, bv = bp[i] ?? 0;
          if (av !== bv) return av - bv;
        }

        const at = String(a.Section_Title ?? "").toLowerCase();
        const bt = String(b.Section_Title ?? "").toLowerCase();
        if (at !== bt) return at.localeCompare(bt);

        return String(a.Req_ID ?? a.file?.path ?? "").localeCompare(String(b.Req_ID ?? b.file?.path ?? ""));
      }

      // ---------------------------
      // Markdown heading extraction
      // ---------------------------
      function extractHeadingBlock(markdown, headingText) {
        if (!markdown) return "";
        const esc = headingText.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
        const startRe = new RegExp(`^##\\s+${esc}\\s*$`, "mi");
        const m = markdown.match(startRe);
        if (!m || m.index == null) return "";
        const startIdx = m.index + m[0].length;
        const rest = markdown.slice(startIdx);
        const n = rest.search(/^\s*#{1,2}\s+/m); // next H1/H2
        const endIdx = n === -1 ? markdown.length : startIdx + n;
        return markdown.slice(startIdx, endIdx).trim();
      }

      function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }

      async function estimateNodeSize(page, opts) {
        let w = opts.kind === "sim" ? 640 : 540;
        let h = opts.kind === "sim" ? 520 : 360;

        if (!opts.autoSize) return { w: clamp(w, 420, 1000), h: clamp(h, 260, 1400) };

        const reqText = String(page.Requirement_Text ?? "");
        if (opts.kind === "core" && reqText) h += Math.floor(reqText.length / 900) * 120;

        if (opts.layout === "whole" || opts.kind === "sim") {
          const md = await loadMd(page.file.path);
          const src = (opts.kind === "sim")
            ? (extractHeadingBlock(md, opts.simHeading) || "")
            : md;

          h += Math.floor(src.length / 1200) * 140;

          const imgCount =
            (src.match(/!\[\[[^\]]+\]\]/g) || []).length +
            (src.match(/!\[[^\]]*\]\([^)]+\)/g) || []).length;

          h += imgCount * 180;
        }

        return { w: clamp(w, 420, 1000), h: clamp(h, 260, 1400) };
      }

      // ---------------------------
      // Prompts / options
      // ---------------------------
      const mode = (await customPrompt("Canvas node mode? (file/text)", "file") || "file").trim().toLowerCase();
      const layout = (await customPrompt("Core layout? (whole/req)", "req") || "req").trim().toLowerCase();

      const simScope = (await customPrompt("Simulink source scope? (none/self/parents/children/both)", "self") || "self")
        .trim().toLowerCase();
      const simHeading = (await customPrompt("Simulink heading text (exact H2)", "Simulink Model Views") || "Simulink Model Views").trim();

      const depth = clamp(parseInt((await customPrompt("Expand hierarchy depth? (0/1/2)", "1") || "1"), 10) || 1, 0, 2);

      const includeParents = depth >= 1
        ? ((await customPrompt("Include Parent nodes? (yes/no)", "yes")) || "yes").toLowerCase().startsWith("y")
        : false;

      const includeChildren = depth >= 1
        ? ((await customPrompt("Include Child nodes? (yes/no)", "yes")) || "yes").toLowerCase().startsWith("y")
        : false;

      const maxParents = parseInt((await customPrompt("Max parents per core", "4") || "4"), 10) || 4;
      const maxChildren = parseInt((await customPrompt("Max children per core", "4") || "4"), 10) || 4;

      const maxGrandParents = parseInt((await customPrompt("Max grandparents per parent (depth=2)", "2") || "2"), 10) || 2;
      const maxGrandChildren = parseInt((await customPrompt("Max grandchildren per child (depth=2)", "2") || "2"), 10) || 2;

      const maxSimNodes = parseInt((await customPrompt("Max simulink nodes per core", "6") || "6"), 10) || 6;

      let autoSize = ((await customPrompt("Auto-size cards (best effort)? (yes/no)", "yes")) || "yes")
        .toLowerCase().startsWith("y");

      if (filteredPages.length > 150 && autoSize && (layout === "whole" || simScope !== "none")) {
        const ok = ((await customPrompt(
          `Auto-size may read many notes (${filteredPages.length}). Keep auto-size? (yes/no)`,
          "no"
        )) || "no").toLowerCase().startsWith("y");
        autoSize = ok;
      }

      const folderPath = CONFIG?.CANVAS_EXPORT_PATH || "Canvas Exports";

      // ---------------------------
      // Build lookups
      // ---------------------------
      const reqIdMap = new Map();
      const allPages = dv.pages(`"${CONFIG.FOLDER_PATH}"`).array();
      allPages.forEach(p => { if (p.Req_ID) reqIdMap.set(p.Req_ID, p); });

      function getParentsOf(p) {
        return String(p?.Parents || "").split(",").map(s => s.trim()).filter(Boolean)
          .map(id => reqIdMap.get(id)).filter(Boolean);
      }
      function getChildrenOf(p) {
        return String(p?.Children || "").split(",").map(s => s.trim()).filter(Boolean)
          .map(id => reqIdMap.get(id)).filter(Boolean);
      }

      // ---------------------------
      // Canvas collections
    // ---------------------------

    // Build "Section Title" groups to match the viewer's grouping,
    // and create Canvas "group" boxes (large outlined boxes with labels).
    const groupNodes = [];
    const { queue } = buildQueue(filteredPages);
    const groups = [];
    let _cur = null;

    for (const item of queue) {
      if (item.type === "group") {
        _cur = { title: item.group.title, sortId: item.group.sortId, pages: [] };
        groups.push(_cur);
      } else if (item.type === "page") {
        if (!_cur) {
          _cur = { title: "Unsectioned", sortId: "", pages: [] };
          groups.push(_cur);
        }
        _cur.pages.push(item.page);
      }
    }

    const nodes = [];
      const edges = [];
      const added = new Set();

      const GAP_X = 280;
      const GAP_Y = 130;

      function addEdge(fromId, toId, color = null) {
        edges.push({
          id: `e_${fromId}_${toId}`,
          fromNode: fromId,
          fromSide: "right",
          toNode: toId,
          toSide: "left",
          color
        });
      }

      async function addFileNode(page, id, x, y, w, h, color, subpath) {
        if (added.has(id)) return id;
        added.add(id);
        const node = { id, type: "file", file: page.file.path, x, y, width: w, height: h, color };
        if (subpath) node.subpath = subpath;
        nodes.push(node);
        return id;
      }

      async function addTextNode(id, x, y, w, h, color, text) {
        if (added.has(id)) return id;
        added.add(id);
        nodes.push({ id, type: "text", text: text ?? "", x, y, width: w, height: h, color });
        return id;
      }

      async function addCoreNode(page, x, y, color) {
        const id = safeId(page.file.path, "core");
        const { w, h } = await estimateNodeSize(page, { layout, kind: "core", autoSize, simHeading });

        if (mode === "file") {
          const subpath = (layout === "req") ? "#Requirement Text" : null;
          await addFileNode(page, id, x, y, w, h, color, subpath);
        } else {
          const title = page.Section_Title || page.Section || page.Req_ID || page.file.name;
          const body = [
            `### [[${page.file.path}|${title}]]`,
            page.Req_ID ? `**Req_ID:** ${page.Req_ID}` : "",
            page.Section ? `**Section:** ${page.Section}` : "",
            page.Section_Title ? `**Section Title:** ${page.Section_Title}` : "",
            "",
            `[[${page.file.path}#Requirement Text]]`,
            `[[${page.file.path}#${simHeading}]]`,
          ].filter(Boolean).join("\n");
          await addTextNode(id, x, y, w, h, color, body);
        }

        return { id, w, h };
      }

      async function addRelatedReqNode(page, idSuffix, x, y, color) {
        const id = safeId(page.file.path, idSuffix);
        const { w, h } = await estimateNodeSize(page, { layout: "req", kind: "core", autoSize: false, simHeading });

        if (mode === "file") {
          await addFileNode(page, id, x, y, w, h, color, "#Requirement Text");
        } else {
          const title = page.Section_Title || page.Section || page.Req_ID || page.file.name;
          const body = `### [[${page.file.path}|${title}]]\n\n[[${page.file.path}#Requirement Text]]`;
          await addTextNode(id, x, y, w, h, color, body);
        }
        return { id, w, h };
      }

      async function hasSimulinkSection(page) {
        const md = await loadMd(page.file.path);
        const block = extractHeadingBlock(md, simHeading);
        return Boolean(block && block.trim().length > 0);
      }

      async function addSimulinkNodesFor(corePage, coreNode, baseX, baseY) {
        if (simScope === "none") return { rightEdge: coreNode.w + baseX, usedHeight: 0 };

        const candidates = [];
        const seen = new Set();

        function push(p) {
          if (!p?.file?.path) return;
          if (seen.has(p.file.path)) return;
          seen.add(p.file.path);
          candidates.push(p);
        }

        if (simScope === "self" || simScope === "both") push(corePage);

        const parents = getParentsOf(corePage);
        const children = getChildrenOf(corePage);

        if (simScope === "parents" || simScope === "both") parents.forEach(push);
        if (simScope === "children" || simScope === "both") children.forEach(push);

        const withModels = [];
        for (const c of candidates) {
          try { if (await hasSimulinkSection(c)) withModels.push(c); } catch (_) {}
        }

        if (withModels.length === 0) return { rightEdge: coreNode.w + baseX, usedHeight: 0 };

        let y = baseY;
        let rightEdge = baseX;
        let usedHeight = 0;

        const shown = withModels.slice(0, maxSimNodes);
        const overflow = withModels.slice(maxSimNodes);

        for (const c of shown) {
          const simId = safeId(c.file.path, `sim_for_${corePage.file.path}`);
          const { w, h } = await estimateNodeSize(c, { layout, kind: "sim", autoSize, simHeading });

          if (mode === "file") {
            await addFileNode(c, simId, baseX, y, w, h, "2", `#${simHeading}`);
          } else {
            const body = [
              `### [[${c.file.path}#${simHeading}|${c.Req_ID || c.file.name} — ${simHeading}]]`,
              "",
              `[[${c.file.path}#${simHeading}]]`
            ].join("\n");
            await addTextNode(simId, baseX, y, w, h, "2", body);
          }

          addEdge(coreNode.id, simId, "2");
          rightEdge = Math.max(rightEdge, baseX + w);
          y += h + GAP_Y * 0.5;
          usedHeight = y - baseY;
        }

        if (overflow.length > 0) {
          const moreId = safeId(corePage.file.path, "sim_overflow");
          const text = [
            `### More ${simHeading} links (${overflow.length})`,
            ...overflow.map(p => `- [[${p.file.path}#${simHeading}|${p.Req_ID || p.file.name}]]`)
          ].join("\n");
          const w = 520, h = clamp(180 + overflow.length * 22, 220, 800);
          await addTextNode(moreId, baseX, y, w, h, "2", text);
          addEdge(coreNode.id, moreId, "2");
          rightEdge = Math.max(rightEdge, baseX + w);
          y += h + GAP_Y * 0.5;
          usedHeight = y - baseY;
        }

        return { rightEdge, usedHeight };
      }

      // ---------------------------
      // Render loop
      // ---------------------------
      const totalReqs = filteredPages.length;
    new Notice(`🧱 Exporting ${totalReqs} requirements…`);
    let yCursor = 0;

    // Section group box padding (Canvas "group" node)
    const GROUP_PAD_X = 80;
    const GROUP_PAD_Y_TOP = 70;
    const GROUP_PAD_Y_BOT = 50;

    for (const g of groups) {
      if (!g?.pages?.length) continue;

      const groupStartY = yCursor;
      let groupMaxX = 0;
      let groupBottom = groupStartY;

      for (const corePage of g.pages) {
        const coreX = 0;
        const coreY = yCursor;

        const core = await addCoreNode(corePage, coreX, coreY, "1");

        const simBaseX = coreX + core.w + GAP_X;
        const sim = await addSimulinkNodesFor(corePage, core, simBaseX, coreY);

        let rowHeight = core.h;
        if (sim.usedHeight > 0) rowHeight = Math.max(rowHeight, sim.usedHeight);

        if (includeParents && depth >= 1) {
          const parents = getParentsOf(corePage).slice(0, maxParents);

          let parentY = coreY;
          const parentX = coreX - (560 + GAP_X);

          for (const p of parents) {
            const pn = await addRelatedReqNode(p, `p_for_${corePage.file.path}`, parentX, parentY, "4");
            addEdge(pn.id, core.id, "4");

            if (depth >= 2) {
              const gps = getParentsOf(p).slice(0, maxGrandParents);
              let gpY = parentY;
              const gpX = parentX - (560 + GAP_X) * 0.85;

              for (const gp of gps) {
                const gpn = await addRelatedReqNode(gp, `gp_for_${p.file.path}`, gpX, gpY, "4");
                addEdge(gpn.id, pn.id, "4");
                gpY += gpn.h + GAP_Y * 0.4;
                rowHeight = Math.max(rowHeight, (gpY - coreY));
              }
            }

            parentY += pn.h + GAP_Y * 0.5;
            rowHeight = Math.max(rowHeight, (parentY - coreY));
          }
        }

        if (includeChildren && depth >= 1) {
          const childrenBaseX = (sim.usedHeight > 0) ? (sim.rightEdge + GAP_X) : (coreX + core.w + GAP_X);
          const kids = getChildrenOf(corePage).slice(0, maxChildren);

          let childY = coreY;

          for (const c of kids) {
            const cn = await addRelatedReqNode(c, `c_for_${corePage.file.path}`, childrenBaseX, childY, "5");
            addEdge(core.id, cn.id, "5");

            if (depth >= 2) {
              const gcs = getChildrenOf(c).slice(0, maxGrandChildren);
              let gcY = childY;
              const gcX = childrenBaseX + (560 + GAP_X) * 0.85;

              for (const gc of gcs) {
                const gcn = await addRelatedReqNode(gc, `gc_for_${c.file.path}`, gcX, gcY, "5");
                addEdge(cn.id, gcn.id, "5");
                gcY += gcn.h + GAP_Y * 0.4;
                rowHeight = Math.max(rowHeight, (gcY - coreY));
              }
            }

            childY += cn.h + GAP_Y * 0.5;
            rowHeight = Math.max(rowHeight, (childY - coreY));
          }
        }

                yCursor += rowHeight + GAP_Y;

        // Group bounds: core + simulink column (keeps parents/children outside the box)
        groupMaxX = Math.max(groupMaxX, coreX + core.w, (sim?.rightEdge ?? 0));
        groupBottom = Math.max(groupBottom, yCursor - GAP_Y);
      }

      const label = g.sortId ? `${g.sortId} — ${g.title}` : g.title;
      const grpId = safeId(label, "section_group");

      groupNodes.push({
        id: grpId,
        type: "group",
        x: 0 - GROUP_PAD_X,
        y: groupStartY - GROUP_PAD_Y_TOP,
        width: Math.max(480, groupMaxX + GROUP_PAD_X * 2),
        height: Math.max(200, (groupBottom - groupStartY) + GROUP_PAD_Y_TOP + GROUP_PAD_Y_BOT),
        label,
        color: "6"
      });

      // A little extra whitespace between section groups
      yCursor += Math.floor(GAP_Y * 0.4);
    }
await ensureFolderExists(folderPath);
      const stamp = new Date().toISOString().replace(/[:.]/g, "-");
      const fullPath = `${folderPath}/Requirements_Trace_${stamp}.canvas`;

      const jsonStr = JSON.stringify({ nodes: [...groupNodes, ...nodes], edges }, null, 2);
      await writeFile(fullPath, jsonStr);

      new Notice(`✅ Canvas created: ${fullPath} (${nodes.length} nodes, ${edges.length} edges)`);
      app.workspace.openLinkText(fullPath, "", true);

    } catch (e) {
      console.error("Canvas export failed:", e);
      new Notice(`❌ Canvas export failed: ${e?.message || e}`);
    }
  }

  // =========================
  // MAIN UI SETUP
  // =========================
  const container = dv.container;
  container.innerHTML = "";
  Object.assign(container.style, STYLES.container);

  const pages = dv.pages(`"${CONFIG.FOLDER_PATH}"`).array();
  if (!pages.length) {
    dv.paragraph(`⚠️ No pages found in "${CONFIG.FOLDER_PATH}". Check folder path.`);
    return;
  }

  // For Canvas export lookups
  const reqIdMap = new Map();
  pages.forEach(p => { if (p.Req_ID) reqIdMap.set(p.Req_ID, p); });

  const docTypes = [...new Set(pages.map(p => p.Doc_Type).filter(Boolean))].sort();
  const levels = [...new Set(pages.map(p => p.Level).filter(Boolean))].sort();
  const docNames = [...new Set(pages.map(p => p.Doc_Name).filter(Boolean))].sort();
  const reqTypes = [...new Set(pages.map(p => p.Requirement_Type ?? p.Section_Type).filter(Boolean))].sort();

  const filtersDiv = container.createEl("div");
  Object.assign(filtersDiv.style, STYLES.filtersContainer);

  const createFilter = (label, type, options = []) => {
    const group = filtersDiv.createEl("div");
    Object.assign(group.style, STYLES.filterGroup);

    const labelEl = group.createEl("label");
    Object.assign(labelEl.style, STYLES.filterLabel);
    labelEl.textContent = label;

    if (type === "select") {
      const sel = group.createEl("select");
      Object.assign(sel.style, STYLES.select);

      const def = sel.createEl("option");
      def.text = `All ${label}`;
      def.value = "";

      options.forEach(opt => {
        const o = sel.createEl("option");
        o.text = opt;
        o.value = opt;
      });
      return sel;
    }

    const input = group.createEl("input");
    input.type = "text";
    input.placeholder = `Filter ${label}...`;
    Object.assign(input.style, STYLES.input);
    return input;
  };

  const createCheckbox = (label, defaultValue = false) => {
    const group = filtersDiv.createEl("div");
    Object.assign(group.style, STYLES.filterGroup);

    const labelEl = group.createEl("label");
    Object.assign(labelEl.style, STYLES.filterLabel);
    labelEl.textContent = label;

    const cb = group.createEl("input");
    cb.type = "checkbox";
    cb.checked = defaultValue;
    return cb;
  };

  // NEW: Requirement Type multi-select
  const createReqTypeMultiSelect = (label, options = []) => {
    const group = filtersDiv.createEl("div");
    Object.assign(group.style, STYLES.filterGroup);

    const labelEl = group.createEl("label");
    Object.assign(labelEl.style, STYLES.filterLabel);
    labelEl.textContent = label;

    const hint = group.createEl("div");
    hint.style.fontSize = "0.8em";
    hint.style.color = "var(--text-muted)";
    hint.textContent = "Tip: Ctrl/Cmd-click for multi-select. Shift-click for range.";

    const sel = group.createEl("select");
    sel.multiple = true;
    Object.assign(sel.style, STYLES.multiSelect);

    options.forEach(opt => {
      const o = sel.createEl("option");
      o.text = opt;
      o.value = opt;
    });

    return sel;
  };

  const filters = {
    docType: createFilter("Document Type", "select", docTypes),
    docName: createFilter("Document Name", "select", docNames),
    reqType: createReqTypeMultiSelect("Requirement Type (multi)", reqTypes),
    level: createFilter("Level", "select", levels),
    sectionTitle: createFilter("Section Title", "text"),
    reqId: createFilter("Req ID", "text"),
    showHeadersOnly: createCheckbox("Show Headers Only", false),
    includeSimulink: createCheckbox("Include Simulink Model Views", CONFIG.DEFAULT_INCLUDE_SIMULINK),
    global: createFilter("Global Search", "text")
  };

  // Restore saved state (UPDATED for multi-select)
  const saved = loadFilterState();
  for (const k in filters) {
    if (saved[k] === undefined) continue;

    const el = filters[k];
    const val = saved[k];

    if (el.type === "checkbox") el.checked = Boolean(val);
    else if (el.tagName === "SELECT" && el.multiple && Array.isArray(val)) {
      const set = new Set(val);
      Array.from(el.options).forEach(o => { o.selected = set.has(o.value); });
    } else el.value = val;
  }

  const statsDiv = container.createEl("div");
  Object.assign(statsDiv.style, STYLES.stats);

  const bulkDiv = container.createEl("div");
  Object.assign(bulkDiv.style, STYLES.bulkActions);

  const bulkTagBtn = bulkDiv.createEl("button", { text: "📌 Add Tag to All (Filtered)" });
  Object.assign(bulkTagBtn.style, STYLES.button, STYLES.primaryButton);

  const bulkNoteBtn = bulkDiv.createEl("button", { text: "📝 Update Notes for All (Filtered)" });
  Object.assign(bulkNoteBtn.style, STYLES.button);

  const exportCsvBtn = bulkDiv.createEl("button", { text: "📊 Export to CSV (Clipboard)" });
  Object.assign(exportCsvBtn.style, STYLES.button);

  const renderAllPdfBtn = bulkDiv.createEl("button", { text: "🖨 Render ALL (PDF mode)" });
  Object.assign(renderAllPdfBtn.style, STYLES.button, STYLES.secondaryButton);

  const exportPrintableBtn = bulkDiv.createEl("button", { text: "🧾 Export Printable Markdown" });
  Object.assign(exportPrintableBtn.style, STYLES.button, STYLES.secondaryButton);

  const exportCanvasBtn = bulkDiv.createEl("button", { text: "🎨 Export to Canvas (Editable)" });
  Object.assign(exportCanvasBtn.style, STYLES.button);

  const resultsDiv = container.createEl("div");

  const loadMoreBtn = container.createEl("button", { text: "Load More" });
  Object.assign(loadMoreBtn.style, STYLES.loadMore);
  loadMoreBtn.style.display = "none";

  // =========================
  // FILTER + GROUP BUILD
  // =========================
  async function filterResults() {
    let filtered = pages;

    if (filters.docType.value) filtered = filtered.filter(p => p.Doc_Type === filters.docType.value);
    if (filters.docName.value) filtered = filtered.filter(p => p.Doc_Name === filters.docName.value);

    // UPDATED: multi-select requirement type
    const selectedReqTypes = Array.from(filters.reqType.selectedOptions).map(o => o.value);
    if (selectedReqTypes.length) {
      const set = new Set(selectedReqTypes.map(x => String(x)));
      filtered = filtered.filter(p => set.has(String(p.Requirement_Type ?? p.Section_Type ?? "")));
    }

    if (filters.level.value) filtered = filtered.filter(p => p.Level === filters.level.value);

    if (filters.sectionTitle.value) {
      filtered = filtered.filter(p => wildcardMatch(p.Section_Title, filters.sectionTitle.value));
    }

    if (filters.reqId.value) filtered = filtered.filter(p => wildcardMatch(p.Req_ID, filters.reqId.value));
    if (filters.showHeadersOnly.checked) filtered = filtered.filter(p => p.Is_Section_Header === true);

    if (filters.global.value) {
      const pat = filters.global.value;
      const out = [];
      for (const p of filtered) {
        let content = getCachedContent(p.file.path);
        if (!content) {
          content = await dv.io.load(p.file.path);
          setCachedContent(p.file.path, content);
        }
        if (wildcardMatch(content, pat)) out.push(p);
      }
      filtered = out;
    }

    return filtered;
  }

  function buildQueue(filteredPages) {
    const map = new Map();

    for (const p of filteredPages) {
      const titleNorm = normalizeTitle(p.Section_Title);
      const key = titleNorm || "Unsectioned";

      if (!map.has(key)) {
        map.set(key, { title: key, sortId: extractSectionIdFromTitle(key), pages: [] });
      }
      map.get(key).pages.push(p);
    }

    const groups = Array.from(map.values()).sort((a, b) => {
      const c = compareSectionIds(a.sortId, b.sortId);
      if (c !== 0) return c;
      return String(a.title).localeCompare(String(b.title));
    });

    for (const g of groups) {
      g.pages.sort((pa, pb) => {
        const ka = getPageSortKey(pa);
        const kb = getPageSortKey(pb);
        const c = compareSectionIds(extractSectionIdFromTitle(ka) || ka, extractSectionIdFromTitle(kb) || kb);
        if (c !== 0) return c;
        return String(pa.Req_ID || pa.file.name).localeCompare(String(pb.Req_ID || pb.file.name));
      });
    }

    const queue = [];
    for (const g of groups) {
      queue.push({ type: "group", group: g });
      for (const p of g.pages) queue.push({ type: "page", page: p });
    }

    return { queue, groupsCount: groups.length };
  }

  // =========================
  // RENDERERS
  // =========================
  function renderGroupHeader(group) {
    const box = resultsDiv.createEl("div");
    Object.assign(box.style, STYLES.groupHeader);

    const title = box.createEl("div");
    Object.assign(title.style, STYLES.groupTitle);
    title.textContent = group.title;

    const meta = box.createEl("div");
    Object.assign(meta.style, STYLES.groupMeta);
    const numeric = group.sortId ? `Section ${group.sortId}` : "Section (no numeric id found)";
    meta.textContent = `${numeric} • ${group.pages.length} items`;
  }

  async function renderPageCard(page) {
    const card = resultsDiv.createEl("div");
    Object.assign(card.style, STYLES.requirementCard);

    const header = card.createEl("div");
    Object.assign(header.style, STYLES.reqHeader);

    const reqIdEl = header.createEl("div");
    Object.assign(reqIdEl.style, STYLES.reqId);
    reqIdEl.textContent = page.Req_ID || page.file.name || "No ID";
    reqIdEl.onclick = (e) => {
      if (e.ctrlKey || e.metaKey) app.workspace.openLinkText(page.file.path, "", true);
    };

    const badge = header.createEl("span");
    Object.assign(badge.style, STYLES.badge);
    badge.textContent = page.Doc_Type || (page.Is_Section_Header ? "Header" : "Unknown");

    const metaGrid = card.createEl("div");
    Object.assign(metaGrid.style, STYLES.metadataGrid);

    CONFIG.DISPLAY_FIELDS.forEach(fc => {
      const v = page[fc.field] || (fc.fallback ? page[fc.fallback] : null);
      if (!v) return;
      const item = metaGrid.createEl("div");
      Object.assign(item.style, STYLES.metadataItem);
      item.innerHTML = `<strong>${fc.label}:</strong> <span>${String(v)}</span>`;
    });

    let content = getCachedContent(page.file.path);
    if (!content) {
      content = await dv.io.load(page.file.path);
      setCachedContent(page.file.path, content);
    }

    const reqText = extractHeadingSection(content, CONFIG.HEADING_REQ_TEXT, false);
    if (reqText) {
      const label = card.createEl("div");
      Object.assign(label.style, STYLES.sectionLabel);
      label.textContent = CONFIG.HEADING_REQ_TEXT;

      const box = card.createEl("div");
      Object.assign(box.style, STYLES.markdownBox);
      await renderMarkdownInto(box, reqText, page.file.path);
    }

    if (filters.includeSimulink.checked) {
      const sim = extractHeadingSection(content, CONFIG.HEADING_SIMULINK, true);
      if (sim) {
        const label = card.createEl("div");
        Object.assign(label.style, STYLES.sectionLabel);
        label.textContent = `${CONFIG.HEADING_SIMULINK} (to end of file)`;

        const box = card.createEl("div");
        Object.assign(box.style, STYLES.markdownBox);
        await renderMarkdownInto(box, sim, page.file.path);
      }
    }
  }

  // =========================
  // RENDER LOOP
  // =========================
  async function rebuildAndRender() {
    const filtered = await filterResults();
    currentFilteredPages = filtered;

    const { queue, groupsCount } = buildQueue(filtered);
    currentQueue = queue;
    displayedCount = 0;
    resultsDiv.innerHTML = "";

    statsDiv.innerHTML = `
      <div><strong>Total:</strong> ${filtered.length}</div>
      <div><strong>Groups:</strong> ${groupsCount}</div>
      <div><strong>Displayed:</strong> <span id="displayed-count">0</span></div>
    `;

    await loadMore();
  }

  async function loadMore() {
    const start = displayedCount;
    const end = Math.min(start + CONFIG.PAGE_SIZE, currentQueue.length);

    for (let i = start; i < end; i++) {
      const item = currentQueue[i];
      if (item.type === "group") renderGroupHeader(item.group);
      else await renderPageCard(item.page);
    }

    displayedCount = end;
    const displayedSpan = document.getElementById("displayed-count");
    if (displayedSpan) displayedSpan.textContent = displayedCount;

    if (displayedCount < currentQueue.length) {
      loadMoreBtn.style.display = "block";
      loadMoreBtn.textContent = `Load More (${currentQueue.length - displayedCount} remaining)`;
    } else {
      loadMoreBtn.style.display = "none";
    }
  }

  // A tiny "yield" so Obsidian doesn't feel frozen during big renders
  async function uiYield() { await new Promise(r => setTimeout(r, 0)); }

  // =========================
  // BUTTON ACTIONS
  // =========================

  // FIXED: uses rebuildAndRender/currentQueue instead of missing renderResults/currentResults
  renderAllPdfBtn.onclick = async () => {
    try {
      new Notice("🖨 Rendering all results for PDF…");

      await rebuildAndRender(); // renders first page

      let safety = 0;
      while (displayedCount < currentQueue.length) {
        await loadMore();
        safety++;
        if (safety % 3 === 0) await uiYield();
        if (safety > 20000) break;
      }

      new Notice("✅ All results rendered. Now use Obsidian → Export to PDF (or Print → Save as PDF).");
    } catch (e) {
      console.error(e);
      new Notice(`❌ Render-all failed: ${e.message}`);
    }
  };

  bulkTagBtn.onclick = async () => {
    const tag = await customPrompt("Enter tag to add to all filtered requirements:", "");
    if (!tag) return;

    let updated = 0;
    for (const page of currentFilteredPages) {
      try {
        const file = app.vault.getAbstractFileByPath(page.file.path);
        if (!file) continue;

        await app.fileManager.processFrontMatter(file, (fm) => {
          let tags = fm["tags"];
          if (!tags) tags = [];
          if (typeof tags === "string") tags = [tags];
          if (!Array.isArray(tags)) tags = [];

          if (!tags.includes(tag)) {
            tags.push(tag);
            fm["tags"] = tags;
            updated++;
          }
        });
      } catch (e) {
        console.error("Tag update failed:", page.file.path, e);
      }
    }

    new Notice(`✅ Added tag "${tag}" to ${updated} notes`);
    setTimeout(rebuildAndRender, 250);
  };

  // Printable export (as you had it)
  exportPrintableBtn.onclick = async () => {
    try {
      const simHeading = (await customPrompt("Simulink heading text (exact H2)", "Simulink Model Views")) || "Simulink Model Views";
      const outFolder = (await customPrompt("Output folder for printable note", CONFIG.CANVAS_EXPORT_PATH || "Canvas Exports"))
        || (CONFIG.CANVAS_EXPORT_PATH || "Canvas Exports");

      const results = await filterResults();
      if (!results.length) {
        new Notice("⚠️ No results to export.");
        return;
      }

      // Basic numeric comparator used elsewhere in your script
      function compareSectionStrings(a, b) {
        const aRaw = String(a.Section ?? a.Object_Number ?? a.Section_Title ?? "").trim();
        const bRaw = String(b.Section ?? b.Object_Number ?? b.Section_Title ?? "").trim();

        const aMatch = aRaw.match(/^(\d+(?:\.\d+)*)/);
        const bMatch = bRaw.match(/^(\d+(?:\.\d+)*)/);

        const aKey = aMatch ? aMatch[1] : "";
        const bKey = bMatch ? bMatch[1] : "";

        const aParts = aKey ? aKey.split(".").map(x => parseInt(x, 10) || 0) : [];
        const bParts = bKey ? bKey.split(".").map(x => parseInt(x, 10) || 0) : [];

        const len = Math.max(aParts.length, bParts.length);
        for (let i = 0; i < len; i++) {
          const av = aParts[i] ?? 0;
          const bv = bParts[i] ?? 0;
          if (av !== bv) return av - bv;
        }

        const at = String(a.Section_Title ?? "").toLowerCase();
        const bt = String(b.Section_Title ?? "").toLowerCase();
        if (at !== bt) return at.localeCompare(bt);

        return String(a.Req_ID ?? a.file?.path ?? "").localeCompare(String(b.Req_ID ?? b.file?.path ?? ""));
      }

      async function ensureFolderExists(folderPath) {
        const parts = folderPath.split("/").filter(Boolean);
        let cur = "";
        for (const p of parts) {
          cur = cur ? `${cur}/${p}` : p;
          if (!(await app.vault.adapter.exists(cur))) {
            try { await app.vault.createFolder(cur); } catch (_) {}
          }
        }
      }
      async function writeOrModify(path, text) {
        const existing = app.vault.getAbstractFileByPath(path);
        if (existing) await app.vault.modify(existing, text);
        else await app.vault.create(path, text);
      }
      function extractHeadingBlock(markdown, headingText) {
        if (!markdown) return "";
        const esc = headingText.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
        const startRe = new RegExp(`^##\\s+${esc}\\s*$`, "mi");
        const m = markdown.match(startRe);
        if (!m || m.index == null) return "";
        const startIdx = m.index + m[0].length;
        const rest = markdown.slice(startIdx);
        const n = rest.search(/^\s*#{1,2}\s+/m);
        const endIdx = n === -1 ? markdown.length : startIdx + n;
        return markdown.slice(startIdx, endIdx).trim();
      }
      async function loadMarkdownCached(filePath) {
        let md = getCachedContent(filePath);
        if (!md) {
          md = await dv.io.load(filePath);
          setCachedContent(filePath, md);
        }
        return md;
      }

      results.sort(compareSectionStrings);

      const groupKey = (p) => String(p.Section_Title || p.Section || p.Object_Number || "Ungrouped").trim();

      const groups = new Map();
      for (const p of results) {
        const k = groupKey(p);
        if (!groups.has(k)) groups.set(k, []);
        groups.get(k).push(p);
      }

      const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
      const outPath = `${outFolder}/Requirements_Printable_${timestamp}.md`;

      await ensureFolderExists(outFolder);

      const lines = [];
      lines.push(`# Requirements Export (Printable)`);
      lines.push(``);
      lines.push(`- Generated: ${new Date().toLocaleString()}`);
      lines.push(`- Source folder: \`${CONFIG.FOLDER_PATH}\``);
      lines.push(`- Total: **${results.length}**`);
      lines.push(``);

      for (const [title, pagesInGroup] of groups.entries()) {
        const first = pagesInGroup[0];
        const sectionNum = String(first.Section || first.Object_Number || "").trim();
        const groupHeader = sectionNum ? `${sectionNum} — ${title}` : title;

        lines.push(`## ${groupHeader}`);
        lines.push(``);

        for (const p of pagesInGroup) {
          const reqId = p.Req_ID || p.file?.name || "No ID";
          const link = p.file?.path ? `[[${p.file.path}|${reqId}]]` : reqId;

          lines.push(`### ${link}`);
          lines.push(``);

          let reqText = p.Requirement_Text;
          if (!reqText && p.file?.path) {
            const md = await loadMarkdownCached(p.file.path);
            const block = extractHeadingBlock(md, "Requirement Text");
            if (block) reqText = block;
          }

          if (reqText) {
            lines.push(`#### Requirement Text`);
            lines.push(reqText);
            lines.push(``);
          }

          if (p.file?.path) {
            const md = await loadMarkdownCached(p.file.path);
            const simBlock = extractHeadingBlock(md, simHeading);
            if (simBlock && simBlock.trim().length > 0) {
              lines.push(`#### ${simHeading}`);
              lines.push(simBlock);
              lines.push(``);
            }
          }

          if (p.Parents) lines.push(`**Parents:** ${String(p.Parents)}`);
          if (p.Children) lines.push(`**Children:** ${String(p.Children)}`);
          if (p.Parents || p.Children) lines.push(``);

          lines.push(`---`);
          lines.push(``);
        }
      }

      await writeOrModify(outPath, lines.join("\n"));

      new Notice(`✅ Printable note created: ${outPath}`);
      app.workspace.openLinkText(outPath, "", true);

      new Notice(`➡️ Now export THAT note to PDF (it will include everything).`);
    } catch (e) {
      console.error(e);
      new Notice(`❌ Printable export failed: ${e.message}`);
    }
  };

  bulkNoteBtn.onclick = async () => {
    const note = await customPrompt("Enter the notes value to set for ALL filtered requirements:", "");
    if (note === null) return;

    let updated = 0;
    for (const page of currentFilteredPages) {
      try {
        const file = app.vault.getAbstractFileByPath(page.file.path);
        if (!file) continue;

        await app.fileManager.processFrontMatter(file, (fm) => {
          fm["notes"] = note;
          updated++;
        });
      } catch (e) {
        console.error("Notes update failed:", page.file.path, e);
      }
    }

    new Notice(`✅ Updated notes for ${updated} notes`);
    setTimeout(rebuildAndRender, 250);
  };

  exportCsvBtn.onclick = () => {
    const headers = [
      "Req_ID", "Doc_Name", "Doc_Type", "Requirement_Type", "Section_Type",
      "Level", "Section_Title", "Section", "Object_Number", "SRS_Local_Req_No",
      "Parents", "Children"
    ];

    const rows = [headers.join(",")];

    currentFilteredPages.forEach(p => {
      const row = headers.map(h => {
        const v = p[h] ?? "";
        return `"${String(v).replace(/"/g, '""')}"`;
      });
      rows.push(row.join(","));
    });

    const csv = rows.join("\n");
    navigator.clipboard.writeText(csv);
    new Notice("✅ CSV copied to clipboard");
  };

  exportCanvasBtn.onclick = async () => {
    if (!currentFilteredPages.length) return;

    if (currentFilteredPages.length > 200) {
      const confirmText = await customPrompt(
        `You are exporting ${currentFilteredPages.length} nodes. Type 'yes' to proceed:`,
        ""
      );
      if (confirmText !== "yes") return;
    }

    await exportToCanvas(currentFilteredPages, reqIdMap);
  };

  // =========================
  // FILTER HOOKS
  // =========================
  const debounced = debounce(() => {
    saveFilterState(filters);
    rebuildAndRender();
  }, CONFIG.DEBOUNCE_MS);

  Object.values(filters).forEach(el => {
    el.addEventListener("change", debounced);
    if (el.type !== "checkbox") el.addEventListener("keyup", debounced);
  });

  loadMoreBtn.onclick = loadMore;

  await rebuildAndRender();

} catch (e) {
  dv.container.innerHTML = `
    <div style="color: var(--text-error); padding: 20px; border: 2px solid var(--text-error); border-radius: 8px;">
      <h3>❌ Error</h3>
      <p><strong>Message:</strong> ${e.message}</p>
      <p><strong>Stack:</strong></p>
      <pre style="font-size: 0.9em; overflow-x: auto;">${e.stack}</pre>
    </div>
  `;
  console.error(e);
}
```