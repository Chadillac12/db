# Requirements Interactive Viewer

> [!IMPORTANT] Advanced DataviewJS Viewer
> This is an interactive, Excel-like requirements browser with filtering, editing, lazy loading, and bulk operations.
>
> **Features:**
> - ✅ Multi-field filtering with wildcards
> - ✅ Lazy loading for performance  
> - ✅ Inline editing of notes and tags
> - ✅ Bulk operations on filtered results
> - ✅ Persistent filter state
> - ✅ Quick section navigation
> - ✅ Traceability link navigation

```dataviewjs
try {
  // ========== CONFIGURATION ==========
  const CONFIG = {
    PAGE_SIZE: 50,  // Lazy load batch size
    DEBOUNCE_MS: 300,  // Filter debounce delay
    FOLDER_PATH: "02-CACTCS/Requirements",  // Requirements folder
    CACHE_DURATION: 60000,  // 1 minute cache
    CANVAS_EXPORT_PATH: "Canvas Exports",
    // Display Configuration
    SHOW_PARENT_TAGS: true,
    SHOW_REQ_TEXT_HEADER: true,
    DISPLAY_FIELDS: [
      { label: "Document", field: "Doc_Name" },
      { label: "Level", field: "Level" },
      { label: "Section", field: "Section_Title", fallback: "Section" },
      { label: "Object #", field: "Object_Number" },
      { label: "SRS Local", field: "SRS_Local_Req_No" }
    ]
  };

  const FILTER_STATE_KEY = 'requirements_filter_state_v2';
  
  // Global state
  let currentResults = [];
  let displayedCount = 0;
  let contentCache = new Map();
  let lastCacheClean = Date.now();
  
  // ========== STYLES ==========
  const STYLES = {
    container: {
      padding: "20px",
      backgroundColor: "var(--background-primary)"
    },
    filtersContainer: {
      padding: "20px",
      backgroundColor: "var(--background-primary-alt)",
      borderRadius: "8px",
      marginBottom: "20px",
      border: "1px solid var(--background-modifier-border)",
      display: "grid",
      gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))",
      gap: "15px"
    },
    filterGroup: {
      display: "flex",
      flexDirection: "column",
      gap: "5px"
    },
    filterLabel: {
      color: "var(--text-normal)",
      fontWeight: "600",
      fontSize: "0.9em"
    },
    select: {
      padding: "8px",
      borderRadius: "4px",
      border: "1px solid var(--background-modifier-border)",
      backgroundColor: "var(--background-primary)",
      color: "var(--text-normal)",
      width: "100%"
    },
    input: {
      padding: "8px",
      borderRadius: "4px",
      border: "1px solid var(--background-modifier-border)",
      backgroundColor: "var(--background-primary)",
      color: "var(--text-normal)",
      width: "100%"
    },
    requirementCard: {
      marginBottom: "20px",
      border: "1px solid var(--background-modifier-border)",
      borderRadius: "8px",
      padding: "16px",
      backgroundColor: "var(--background-primary-alt)",
      transition: "all 0.2s ease"
    },
    sectionHeader: {
      fontSize: "1.3em",
      fontWeight: "700",
      color: "var(--interactive-accent)",
      marginBottom: "15px",
      padding: "12px",
      backgroundColor: "var(--background-secondary-alt)",
      borderRadius: "6px",
      borderLeft: "4px solid var(--interactive-accent)",
      cursor: "pointer"
    },
    metadataGrid: {
      display: "grid",
      gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
      gap: "8px",
      marginBottom: "12px"
    },
    metadataItem: {
      display: "flex",
      gap: "6px",
      fontSize: "0.9em",
      padding: "6px 10px",
      backgroundColor: "var(--background-secondary)",
      borderRadius: "4px"
    },
    reqHeader: {
      display: "flex",
      justifyContent: "space-between",
      alignItems: "center",
      marginBottom: "12px",
      padding: "10px",
      backgroundColor: "var(--background-secondary)",
      borderRadius: "6px"
    },
    reqId: {
      fontSize: "1.1em",
      fontWeight: "600",
      color: "var(--interactive-accent)",
      cursor: "pointer"
    },
    badge: {
      padding: "3px 8px",
      borderRadius: "12px",
      fontSize: "0.8em",
      fontWeight: "600"
    },
    sectionBadge: {
      backgroundColor: "var(--interactive-accent)",
      color: "var(--text-on-accent)"
    },
    reqBadge: {
      backgroundColor: "var(--background-modifier-border)",
      color: "var(--text-muted)"
    },
    descriptionHeader: {
      fontWeight: "600",
      fontSize: "0.9em",
      color: "var(--text-muted)",
      marginBottom: "4px",
      marginTop: "12px"
    },
    description: {
      padding: "12px",
      borderLeft: "3px solid var(--background-modifier-border)",
      backgroundColor: "var(--background-primary)"
    },
    traceSection: {
      marginTop: "10px",
      padding: "10px",
      backgroundColor: "var(--background-primary)",
      borderRadius: "4px"
    },
    traceLabel: {
      fontWeight: "600",
      fontSize: "0.9em",
      marginBottom: "6px"
    },
    traceLinks: {
      display: "flex",
      flexWrap: "wrap",
      gap: "6px"
    },
    traceLink: {
      display: "inline-block",
      padding: "3px 8px",
      backgroundColor: "var(--background-secondary)",
      borderRadius: "4px",
      fontSize: "0.85em",
      cursor: "pointer",
      border: "1px solid var(--background-modifier-border)"
    },
    parentTags: {
      marginTop: "8px",
      display: "flex",
      gap: "6px",
      flexWrap: "wrap",
      alignItems: "center"
    },
    parentTagLabel: {
      fontSize: "0.85em",
      color: "var(--text-muted)",
      marginRight: "4px"
    },
    parentTag: {
      fontSize: "0.8em",
      padding: "2px 8px",
      borderRadius: "10px",
      backgroundColor: "var(--background-secondary-alt)",
      border: "1px solid var(--background-modifier-border)",
      color: "var(--text-muted)"
    },
    stats: {
      display: "flex",
      justifyContent: "space-between",
      alignItems: "center",
      padding: "10px",
      backgroundColor: "var(--background-secondary)",
      borderRadius: "4px",
      marginBottom: "15px",
      fontSize: "0.9em"
    },
    bulkActions: {
      display: "flex",
      gap: "10px",
      marginBottom: "15px",
      flexWrap: "wrap"
    },
    button: {
      padding: "8px 16px",
      borderRadius: "4px",
      border: "none",
      cursor: "pointer",
      fontSize: "0.9em",
      fontWeight: "600",
      transition: "all 0.2s ease"
    },
    primaryButton: {
      backgroundColor: "var(--interactive-accent)",
      color: "var(--text-on-accent)"
    },
    secondaryButton: {
      backgroundColor: "var(--background-modifier-border)",
      color: "var(--text-normal)"
    },
    loadMore: {
      width: "100%",
      padding: "12px",
      marginTop: "20px",
      backgroundColor: "var(--interactive-accent)",
      color: "var(--text-on-accent)",
      border: "none",
      borderRadius: "6px",
      cursor: "pointer",
      fontSize: "1em",
      fontWeight: "600"
    },
    editableField: {
      padding: "8px",
      borderRadius: "4px",
      border: "1px solid transparent",
      cursor: "text",
      minHeight: "24px",
      backgroundColor: "var(--background-primary)",
      transition: "all 0.2s ease"
    },
    editableFieldActive: {
      border: "1px solid var(--interactive-accent)",
      boxShadow: "0 0 0 2px var(--background-modifier-border)"
    },
    tagContainer: {
      display: "flex",
      flexWrap: "wrap",
      gap: "6px",
      marginTop: "10px"
    },
    tag: {
      backgroundColor: "var(--interactive-accent-hover)",
      color: "var(--text-normal)",
      padding: "3px 10px",
      borderRadius: "12px",
      fontSize: "0.85em",
      display: "flex",
      alignItems: "center",
      gap: "6px"
    },
    tagRemove: {
      cursor: "pointer",
      opacity: "0.7",
      fontWeight: "bold"
    }
  };

  // ========== UTILITY FUNCTIONS ==========
  
  // Debounce helper
  function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
      const later = () => {
        clearTimeout(timeout);
        func(...args);
      };
      clearTimeout(timeout);
      timeout = setTimeout(later, wait);
    };
  }
  
  // Cache management
  function getCachedContent(filePath) {
    if (Date.now() - lastCacheClean > CONFIG.CACHE_DURATION) {
      contentCache.clear();
      lastCacheClean = Date.now();
    }
    return contentCache.get(filePath);
  }
  
  function setCachedContent(filePath, content) {
    contentCache.set(filePath, content);
  }
  
  // Filter state persistence
  function saveFilterState(filters) {
    const state = {};
    for (let key in filters) {
      state[key] = filters[key].value;
    }
    localStorage.setItem(FILTER_STATE_KEY, JSON.stringify(state));
  }
  
  function loadFilterState() {
    const saved = localStorage.getItem(FILTER_STATE_KEY);
    return saved ? JSON.parse(saved) : {};
  }

  // Custom prompt with modal
  async function customPrompt(message, defaultText = '') {
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
        borderRadius: "8px",
        boxShadow: "0 4px 20px rgba(0,0,0,0.3)",
        minWidth: "350px",
        maxWidth: "500px"
      });

      const messageEl = modal.createEl("div", {text: message});
      messageEl.style.marginBottom = "15px";
      messageEl.style.fontSize = "1.1em";

      const input = modal.createEl("input");
      input.type = "text";
      input.value = defaultText;
      Object.assign(input.style, STYLES.input);
      input.style.marginBottom = "15px";

      const btnContainer = modal.createEl("div");
      btnContainer.style.display = "flex";
      btnContainer.style.gap = "10px";
      btnContainer.style.justifyContent = "flex-end";

      const okBtn = btnContainer.createEl("button", {text: "OK"});
      Object.assign(okBtn.style, STYLES.button, STYLES.primaryButton);
      
      const cancelBtn = btnContainer.createEl("button", {text: "Cancel"});
      Object.assign(cancelBtn.style, STYLES.button, STYLES.secondaryButton);

      overlay.appendChild(modal);
      document.body.appendChild(overlay);
      input.focus();

      okBtn.onclick = () => {
        document.body.removeChild(overlay);
        resolve(input.value);
      };
      
      cancelBtn.onclick = () => {
        document.body.removeChild(overlay);
        resolve(null);
      };
      
      input.onkeydown = (e) => {
        if (e.key === "Enter") okBtn.click();
        if (e.key === "Escape") cancelBtn.click();
      };
    });
  }

  // Wildcard matching
  function wildcardMatch(value, pattern) {
    if (!pattern) return true;
    const regex = new RegExp(pattern.split("*").join(".*"), "i");
    return regex.test(String(value || ""));
  }

  // Canvas Export Logic
  async function exportToCanvas(filteredPages) {
    // 1. Ask user for options
    const includeParents = await customPrompt("Include Parent Requirements? (yes/no)", "yes");
    const includeChildren = await customPrompt("Include Child Requirements? (yes/no)", "yes");
    
    const showParents = (includeParents || "").toLowerCase().startsWith("y");
    const showChildren = (includeChildren || "").toLowerCase().startsWith("y");

    const nodes = [];
    const edges = [];
    
    // Layout Constants
    const CARD_WIDTH = 400;
    const CARD_HEIGHT = 400;
    const GAP_X = 200; // Horizontal gap between columns
    const GAP_Y = 50;  // Vertical gap between cards
    
    // Column X positions (Center is 0)
    const X_CENTER = 0;
    const X_LEFT = -(CARD_WIDTH + GAP_X);
    const X_RIGHT = (CARD_WIDTH + GAP_X);

    // Track added nodes to avoid duplicates
    const nodeMap = new Map(); // file.path -> node.id
    
    // Helper to add a node
    const addNode = (page, x, y, color = null) => {
      if (nodeMap.has(page.file.path)) return nodeMap.get(page.file.path);
      
      // Generate a safe, unique ID (Obsidian Canvas prefers short hex strings)
      const id = 'n' + Math.random().toString(36).substr(2, 9);
      nodeMap.set(page.file.path, id);
      
      nodes.push({
        id: id,
        type: "file",
        file: page.file.path,
        x: x,
        y: y,
        width: CARD_WIDTH,
        height: CARD_HEIGHT,
        color: color // Optional color
      });
      return id;
    };

    // Helper to add an edge
    const addEdge = (fromId, toId, color = null) => {
      const edgeId = `edge-${fromId}-${toId}`;
      edges.push({
        id: edgeId,
        fromNode: fromId,
        fromSide: "right",
        toNode: toId,
        toSide: "left",
        color: color
      });
    };

    // 2. Process Core Nodes (Center Column)
    // We'll stack them vertically
    let currentY = 0;
    
    for (const page of filteredPages) {
      const coreId = addNode(page, X_CENTER, currentY, "1"); // Color 1 = Red/Default
      
      // 3. Process Parents (Left Column)
      if (showParents && page.Parents) {
        const parents = String(page.Parents).split(",").map(p => p.trim()).filter(Boolean);
        let parentY = currentY; // Align roughly with the core node
        
        for (const parentId of parents) {
          const parentPage = reqIdMap.get(parentId);
          if (parentPage) {
            const pId = addNode(parentPage, X_LEFT, parentY, "4"); // Color 4 = Blue
            addEdge(pId, coreId, "4");
            parentY += GAP_Y + 50; // Stagger if multiple parents
          }
        }
      }

      // 4. Process Children (Right Column)
      if (showChildren && page.Children) {
        const children = String(page.Children).split(",").map(p => p.trim()).filter(Boolean);
        let childY = currentY;
        
        for (const childId of children) {
          const childPage = reqIdMap.get(childId);
          if (childPage) {
            const cId = addNode(childPage, X_RIGHT, childY, "5"); // Color 5 = Cyan/Green
            addEdge(coreId, cId, "5");
            childY += GAP_Y + 50;
          }
        }
      }
      
      currentY += CARD_HEIGHT + GAP_Y;
    }

    const canvasData = {
      nodes: nodes,
      edges: edges
    };

    const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
    const filename = `Requirements_Trace_${timestamp}.canvas`;
    const folderPath = CONFIG.CANVAS_EXPORT_PATH;
    const fullPath = `${folderPath}/${filename}`;

    try {
      if (!await app.vault.adapter.exists(folderPath)) {
        await app.vault.createFolder(folderPath);
      }
      
      await app.vault.create(fullPath, JSON.stringify(canvasData, null, 2));
      new Notice(`✅ Exported trace view to ${fullPath}`);
    } catch (e) {
      console.error("Canvas export failed:", e);
      new Notice(`❌ Export failed: ${e.message}`);
    }
  }



  // ========== UI COMPONENTS ==========
  
  // Editable field
  function makeEditable(element, onSave) {
    let isEditing = false;
    let originalContent = "";
    
    const startEdit = () => {
      if (isEditing) return;
      isEditing = true;
      originalContent = element.textContent;
      element.contentEditable = true;
      element.focus();
      Object.assign(element.style, STYLES.editableFieldActive);
    };
    
    const stopEdit = () => {
      if (!isEditing) return;
      isEditing = false;
      element.contentEditable = false;
      Object.assign(element.style, STYLES.editableField);
      if (originalContent !== element.textContent) {
        onSave(element.textContent);
      }
    };
    
    Object.assign(element.style, STYLES.editableField);
    element.addEventListener('dblclick', startEdit);
    element.addEventListener('blur', stopEdit);
    element.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        stopEdit();
      }
      if (e.key === 'Escape') {
        element.textContent = originalContent;
        stopEdit();
      }
    });
  }

  // Tag manager
  class TagManager {
    constructor(container, initialTags = [], onUpdate) {
      this.container = container;
      this.tags = new Set(initialTags);
      this.onUpdate = onUpdate;
      this.render();
    }
    
    render() {
      this.container.innerHTML = '';
      const tagDiv = this.container.createEl("div");
      Object.assign(tagDiv.style, STYLES.tagContainer);
      
      this.tags.forEach(tag => {
        const tagEl = tagDiv.createEl("span");
        Object.assign(tagEl.style, STYLES.tag);
        tagEl.textContent = tag;
        
        const removeBtn = tagEl.createEl("span");
        Object.assign(removeBtn.style, STYLES.tagRemove);
        removeBtn.textContent = "×";
        removeBtn.onclick = (e) => {
          e.stopPropagation();
          this.removeTag(tag);
        };
      });
      
      const addBtn = tagDiv.createEl("span");
      Object.assign(addBtn.style, STYLES.tag);
      addBtn.style.cursor = "pointer";
      addBtn.style.backgroundColor = "var(--background-modifier-border)";
      addBtn.textContent = "+ Add Tag";
      addBtn.onclick = async () => {
        const newTag = await customPrompt("Enter new tag:");
        if (newTag) this.addTag(newTag);
      };
    }
    
    addTag(tag) {
      if (!this.tags.has(tag)) {
        this.tags.add(tag);
        this.render();
        this.onUpdate(Array.from(this.tags));
      }
    }
    
    removeTag(tag) {
      if (this.tags.delete(tag)) {
        this.render();
        this.onUpdate(Array.from(this.tags));
      }
    }
  }

  // ========== MAIN IMPLEMENTATION ==========
  
  const container = dv.container;
  container.innerHTML = "";
  Object.assign(container.style, STYLES.container);

  // Load all requirements pages
  console.log("Loading pages from:", CONFIG.FOLDER_PATH);
  const pages = dv.pages(`"${CONFIG.FOLDER_PATH}"`).array();
  console.log("Pages found:", pages.length);
  if (pages.length === 0) {
    console.warn("No pages found! Check folder path.");
    dv.paragraph(`⚠️ No pages found in "${CONFIG.FOLDER_PATH}". Please check the folder path.`);
  }
  
  // Create lookup map for parent tags
  const reqIdMap = new Map();
  pages.forEach(p => {
    if (p.Req_ID) reqIdMap.set(p.Req_ID, p);
  });
  
  // Extract unique values for dropdowns
  const docTypes = [...new Set(pages.map(p => p.Doc_Type).filter(Boolean))].sort();
  const levels = [...new Set(pages.map(p => p.Level).filter(Boolean))].sort();
  const docNames = [...new Set(pages.map(p => p.Doc_Name).filter(Boolean))].sort();

  // Create filters container
  const filtersDiv = container.createEl("div");
  Object.assign(filtersDiv.style, STYLES.filtersContainer);

  // Filter creation helper
  const createFilter = (label, type, options = []) => {
    const group = filtersDiv.createEl("div");
    Object.assign(group.style, STYLES.filterGroup);
    
    const labelEl = group.createEl("label");
    Object.assign(labelEl.style, STYLES.filterLabel);
    labelEl.textContent = label;
    
    if (type === 'select') {
      const select = group.createEl("select");
      Object.assign(select.style, STYLES.select);
      const defaultOpt = select.createEl("option");
      defaultOpt.text = `All ${label}`;
      defaultOpt.value = "";
      options.forEach(opt => {
        const option = select.createEl("option");
        option.text = opt;
        option.value = opt;
      });
      return select;
    } else {
      const input = group.createEl("input");
      input.type = "text";
      input.placeholder = `Filter ${label}...`;
      Object.assign(input.style, STYLES.input);
      return input;
    }
  };

  // Create filters
  const filters = {
    docType: createFilter("Document Type", "select", docTypes),
    docName: createFilter("Document Name", "select", docNames),
    level: createFilter("Level", "select", levels),
    section: createFilter("Section", "text"),
    reqId: createFilter("Req ID", "text"),
    showHeadersOnly: (() => {
      const group = filtersDiv.createEl("div");
      Object.assign(group.style, STYLES.filterGroup);
      const labelEl = group.createEl("label");
      Object.assign(labelEl.style, STYLES.filterLabel);
      labelEl.textContent = "Show Headers Only";
      const checkbox = group.createEl("input");
      checkbox.type = "checkbox";
      return checkbox;
    })(),
    global: createFilter("Global Search", "text")
  };

  // Load saved filter state
  const savedState = loadFilterState();
  for (let key in filters) {
    if (savedState[key] !== undefined) {
      if (filters[key].type === 'checkbox') {
        filters[key].checked = savedState[key];
      } else {
        filters[key].value = savedState[key];
      }
    }
  }

  // Stats and bulk actions
  const statsDiv = container.createEl("div");
  Object.assign(statsDiv.style, STYLES.stats);

  const bulkDiv = container.createEl("div");
  Object.assign(bulkDiv.style, STYLES.bulkActions);

  const bulkTagBtn = bulkDiv.createEl("button", {text: "📌 Add Tag to All"});
  Object.assign(bulkTagBtn.style, STYLES.button, STYLES.primaryButton);
  
  const bulkNoteBtn = bulkDiv.createEl("button", {text: "📝 Update Notes for All"});
  Object.assign(bulkNoteBtn.style, STYLES.button, STYLES.secondaryButton);

  const exportCsvBtn = bulkDiv.createEl("button", {text: "📊 Export to CSV"});
  Object.assign(exportCsvBtn.style, STYLES.button, STYLES.secondaryButton);

  const exportCanvasBtn = bulkDiv.createEl("button", {text: "🎨 Export to Canvas"});
  Object.assign(exportCanvasBtn.style, STYLES.button, STYLES.secondaryButton);
  exportCanvasBtn.onclick = async () => {
    const results = await filterResults();
    if (results.length > 200) {
      const confirm = await customPrompt(`Warning: You are about to export ${results.length} cards to a canvas. This might be slow. Type 'yes' to proceed:`);
      if (confirm !== 'yes') return;
    }
    await exportToCanvas(results);
  };

  // Results container
  const resultsDiv = container.createEl("div");
  const loadMoreBtn = container.createEl("button", {text: "Load More Results"});
  Object.assign(loadMoreBtn.style, STYLES.loadMore);
  loadMoreBtn.style.display = "none";

  // ========== RENDERING ==========
  
  async function filterResults() {
    let filtered = pages;
    
    if (filters.docType.value) {
      filtered = filtered.filter(p => p.Doc_Type === filters.docType.value);
    }
    if (filters.docName.value) {
      filtered = filtered.filter(p => p.Doc_Name === filters.docName.value);
    }
    if (filters.level.value) {
      filtered = filtered.filter(p => p.Level === filters.level.value);
    }
    if (filters.section.value) {
      filtered = filtered.filter(p => 
        wildcardMatch(p.Section, filters.section.value) ||
        wildcardMatch(p.Section_Title, filters.section.value)
      );
    }
    if (filters.reqId.value) {
      filtered = filtered.filter(p => wildcardMatch(p.Req_ID, filters.reqId.value));
    }
    if (filters.showHeadersOnly.checked) {
      filtered = filtered.filter(p => p.Is_Section_Header === true);
    }
    
    // Global search in requirement text
    if (filters.global.value) {
      const globalPattern = filters.global.value;
      const globalFiltered = [];
      for (const page of filtered) {
        let cached = getCachedContent(page.file.path);
        if (!cached) {
          cached = await dv.io.load(page.file.path);
          setCachedContent(page.file.path, cached);
        }
        if (wildcardMatch(cached, globalPattern)) {
          globalFiltered.push(page);
        }
      }
      filtered = globalFiltered;
    }
    
    // Sort by section and object number
    filtered.sort((a, b) => {
      const sectionA = String(a.Section || a.Object_Number || "");
      const sectionB = String(b.Section || b.Object_Number || "");
      return sectionA.localeCompare(sectionB, undefined, {numeric: true});
    });
    
    return filtered;
  }

  async function renderRequirement(page) {
    const card = resultsDiv.createEl("div");
    Object.assign(card.style, STYLES.requirementCard);
    
    // Section header style
    if (page.Is_Section_Header) {
      const headerDiv = card.createEl("div");
      Object.assign(headerDiv.style, STYLES.sectionHeader);
      headerDiv.textContent = `${page.Object_Number || page.Section || ""} - ${page.Section_Title || page.Requirement_Text || ""}`;
      headerDiv.onclick = (e) => {
        if (e.ctrlKey || e.metaKey) {
          app.workspace.openLinkText(page.file.path, "", true);
        }
      };
      return;
    }
    
    // Regular requirement
    const reqHeader = card.createEl("div");
    Object.assign(reqHeader.style, STYLES.reqHeader);
    
    const reqIdEl = reqHeader.createEl("div");
    Object.assign(reqIdEl.style, STYLES.reqId);
    reqIdEl.textContent = page.Req_ID || "No ID";
    reqIdEl.onclick = (e) => {
      if (e.ctrlKey || e.metaKey) {
        app.workspace.openLinkText(page.file.path, "", true);
      }
    };
    
    const badge = reqHeader.createEl("span");
    Object.assign(badge.style, STYLES.badge, STYLES.reqBadge);
    badge.textContent = page.Doc_Type || "Unknown";
    
    // Metadata grid (Configurable)
    const metaGrid = card.createEl("div");
    Object.assign(metaGrid.style, STYLES.metadataGrid);
    
    CONFIG.DISPLAY_FIELDS.forEach(fieldConfig => {
      const value = page[fieldConfig.field] || (fieldConfig.fallback ? page[fieldConfig.fallback] : null);
      if (value) {
        const item = metaGrid.createEl("div");
        Object.assign(item.style, STYLES.metadataItem);
        item.innerHTML = `<strong>${fieldConfig.label}:</strong> <span>${value}</span>`;
      }
    });
    
    // Requirement text
    let reqText = page.Requirement_Text;
    
    // Fallback: If no YAML text, try to read from file content
    if (!reqText) {
      let content = getCachedContent(page.file.path);
      if (!content) {
        // This is async, but we can't await inside the render loop easily without slowing things down.
        // For now, we'll trigger a load and re-render if needed, or just show a placeholder.
        // Better approach: Load content on demand if missing.
        try {
           const rawContent = await dv.io.load(page.file.path);
           setCachedContent(page.file.path, rawContent);
           content = rawContent;
        } catch (e) {
           console.error("Failed to load content for", page.file.path, e);
        }
      }
      
      if (content) {
        // Extract text between "## Requirement Text" and the next header or end of file
        const match = content.match(/## Requirement Text\s*\n([\s\S]*?)(?=\n## |$)/);
        if (match) {
          reqText = match[1].trim();
        }
      }
    }

    if (reqText) {
      if (CONFIG.SHOW_REQ_TEXT_HEADER) {
        const textHeader = card.createEl("div");
        Object.assign(textHeader.style, STYLES.descriptionHeader);
        textHeader.textContent = "Requirement Text";
      }
      
      const textDiv = card.createEl("div");
      Object.assign(textDiv.style, STYLES.description);
      textDiv.textContent = reqText;
    }
    
    // Traceability
    if (page.Parents || page.Children) {
      const traceDiv = card.createEl("div");
      Object.assign(traceDiv.style, STYLES.traceSection);
      
      if (page.Parents) {
        const parentLabel = traceDiv.createEl("div");
        Object.assign(parentLabel.style, STYLES.traceLabel);
        parentLabel.textContent = "⬆️ Parents:";
        
        const parentLinks = traceDiv.createEl("div");
        Object.assign(parentLinks.style, STYLES.traceLinks);
        
        const parents = String(page.Parents).split(",").map(p => p.trim()).filter(Boolean);
        
        parents.forEach(parent => {
          const link = parentLinks.createEl("span");
          Object.assign(link.style, STYLES.traceLink);
          link.textContent = parent;
        });

        // Parent Tags Display
        if (CONFIG.SHOW_PARENT_TAGS) {
          const parentTags = new Set();
          parents.forEach(parentId => {
            const parentPage = reqIdMap.get(parentId);
            if (parentPage && parentPage.tags) {
              parentPage.tags.forEach(tag => parentTags.add(tag));
            }
          });

          if (parentTags.size > 0) {
            const tagsDiv = traceDiv.createEl("div");
            Object.assign(tagsDiv.style, STYLES.parentTags);
            
            const label = tagsDiv.createEl("span");
            Object.assign(label.style, STYLES.parentTagLabel);
            label.textContent = "Parent Tags:";
            
            parentTags.forEach(tag => {
              const tagEl = tagsDiv.createEl("span");
              Object.assign(tagEl.style, STYLES.parentTag);
              tagEl.textContent = tag;
            });
          }
        }
      }
      
      if (page.Children) {
        const childLabel = traceDiv.createEl("div");
        Object.assign(childLabel.style, STYLES.traceLabel);
        childLabel.textContent = "⬇️ Children:";
        
        const childLinks = traceDiv.createEl("div");
        Object.assign(childLinks.style, STYLES.traceLinks);
        
        String(page.Children).split(",").forEach(child => {
          const link = childLinks.createEl("span");
          Object.assign(link.style, STYLES.traceLink);
          link.textContent = child.trim();
        });
      }
    }
    
    // Notes (editable)
    const notesLabel = card.createEl("div");
    notesLabel.textContent = "📝 Notes";
    notesLabel.style.fontWeight = "600";
    notesLabel.style.marginTop = "10px";
    
    const notesEl = card.createEl("div");
    notesEl.textContent = page.notes || "Double-click to add notes...";
    makeEditable(notesEl, async (newContent) => {
      try {
        const file = app.vault.getAbstractFileByPath(page.file.path);
        if (file) {
          await app.fileManager.processFrontMatter(file, (frontmatter) => {
            frontmatter["notes"] = newContent;
          });
        }
      } catch (e) {
        console.error("Error saving notes:", e);
      }
    });
    
    // Tags
    const tagsDiv = card.createEl("div");
    tagsDiv.style.marginTop = "10px";
    new TagManager(tagsDiv, page.tags || [], async (newTags) => {
      try {
        const file = app.vault.getAbstractFileByPath(page.file.path);
        if (file) {
          await app.fileManager.processFrontMatter(file, (frontmatter) => {
            frontmatter["tags"] = newTags;
          });
        }
      } catch (e) {
        console.error("Error saving tags:", e);
      }
    });
  }

  async function renderResults() {
    currentResults = await filterResults();
    resultsDiv.innerHTML = "";
    displayedCount = 0;
    
    // Update stats
    statsDiv.innerHTML = `
      <div><strong>Total:</strong> ${currentResults.length} requirements</div>
      <div><strong>Displayed:</strong> <span id="displayed-count">0</span></div>
    `;
    
    await loadMore();
  }

  async function loadMore() {
    const startIdx = displayedCount;
    const endIdx = Math.min(startIdx + CONFIG.PAGE_SIZE, currentResults.length);
    
    for (let i = startIdx; i < endIdx; i++) {
      await renderRequirement(currentResults[i]);
    }
    
    displayedCount = endIdx;
    document.getElementById("displayed-count").textContent = displayedCount;
    
    if (displayedCount < currentResults.length) {
      loadMoreBtn.style.display = "block";
      loadMoreBtn.textContent = `Load More (${currentResults.length - displayedCount} remaining)`;
    } else {
      loadMoreBtn.style.display = "none";
    }
  }

  // Bulk actions
  bulkTagBtn.onclick = async () => {
    const tag = await customPrompt("Enter tag to add to all filtered requirements:");
    if (!tag || !currentResults.length) return;
    
    let updatedCount = 0;
    for (const page of currentResults) {
      try {
        const file = app.vault.getAbstractFileByPath(page.file.path);
        if (file) {
          await app.fileManager.processFrontMatter(file, (frontmatter) => {
            if (!frontmatter["tags"]) {
              frontmatter["tags"] = [];
            }
            // Handle case where tags might be a string (single tag)
            if (typeof frontmatter["tags"] === "string") {
              frontmatter["tags"] = [frontmatter["tags"]];
            }
            if (Array.isArray(frontmatter["tags"]) && !frontmatter["tags"].includes(tag)) {
              frontmatter["tags"].push(tag);
              updatedCount++;
            }
          });
        }
      } catch (e) {
        console.error("Error adding tag:", e);
      }
    }
    new Notice(`Tag "${tag}" added to ${updatedCount} requirements!`);
    // Wait a bit for Obsidian to index changes before re-rendering
    setTimeout(() => renderResults(), 1000);
  };

  bulkNoteBtn.onclick = async () => {
    const note = await customPrompt("Enter note to add to all filtered requirements:");
    if (note === null || !currentResults.length) return;
    
    let updatedCount = 0;
    for (const page of currentResults) {
      try {
        const file = app.vault.getAbstractFileByPath(page.file.path);
        if (file) {
          await app.fileManager.processFrontMatter(file, (frontmatter) => {
            frontmatter["notes"] = note;
            updatedCount++;
          });
        }
      } catch (e) {
        console.error("Error adding note:", e);
      }
    }
    new Notice(`Note added to ${updatedCount} requirements!`);
    setTimeout(() => renderResults(), 1000);
  };

  exportCsvBtn.onclick = () => {
    const headers = ["Req_ID", "Doc_Type", "Level", "Section_Title", "Object_Number", "Requirement_Text"];
    const rows = [headers.join(",")];
    currentResults.forEach(p => {
      const row = headers.map(h => `"${String(p[h] || "").replace(/"/g, '""')}"`);
      rows.push(row.join(","));
    });
    const csv = rows.join("\n");
    navigator.clipboard.writeText(csv);
    alert("CSV copied to clipboard!");
  };

  // Event listeners with debouncing
  const debouncedRender = debounce(() => {
    saveFilterState(filters);
    renderResults();
  }, CONFIG.DEBOUNCE_MS);

  Object.values(filters).forEach(filter => {
    filter.addEventListener("change", debouncedRender);
    if (filter.type !== 'checkbox') {
      filter.addEventListener("keyup", debouncedRender);
    }
  });

  loadMoreBtn.onclick = loadMore;

  // Initial render
  renderResults();

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

## Key Enhancements

### ✅ Lazy Loading
- Renders 50 requirements at a time
- "Load More" button for pagination
- Dramatically improves performance with large datasets

### ✅ Content Caching
- Caches file content for 1 minute
- Reduces redundant file reads
- Auto-clears expired cache

### ✅ Debounced Filtering
- 300ms debounce on text inputs
- Prevents excessive re-renders while typing
- Smoother user experience

### ✅ Optimized for Requirements
- Filters: Doc Type, Doc Name, Level, Section, Req ID
- Section header detection and special styling
- Traceability links display (Parents/Children)
- Global text search across requirement content

### ✅ Modern Grid Layout
- Responsive filter grid
- Metadata grid for clean display
- Card-based design
