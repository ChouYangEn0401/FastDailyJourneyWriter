// Editor for the daily devotional journal.
//
// The form builds itself from whatever the server hands back, so adding a
// question set or a page design needs no change here.

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

const FIELD_KINDS = [
  ["text", "多行文字（可換色）"],
  ["list", "條列（可增減行）"],
  ["short_text", "單行文字"],
  ["choice", "單選（例：有／沒有）"],
  ["multi_choice", "多選（可複選）"],
  ["scale", "程度（例：滿意／還可以／缺乏）"],
  ["fill", "填空句（用 {} 當空格）"],
];
const KIND_WITH_OPTIONS = new Set(["choice", "multi_choice", "scale"]);

const state = {
  templates: [],
  themes: [],
  layouts: [],
  palette: [],
  prefs: null,
  template: null,
  theme: "letterpress",
  layout: "letter",
  aiAvailable: false,
  entryId: null,
  updatedAt: null,
  answers: {},
  fieldColors: {},
  lastSvg: null,
  saving: false,
  dirty: false,
  editingTemplate: null,
};

// ---------------------------------------------------------------- helpers

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {}
    throw new Error(detail);
  }
  return res.status === 204 ? null : res.json();
}

let toastTimer;
function toast(message, isError = false) {
  const el = $("#toast");
  el.textContent = message;
  el.classList.toggle("err", isError);
  el.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("show"), 3600);
}

function download(filename, blob) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

const today = () => new Date().toISOString().slice(0, 10);
const stripHtml = (html) => {
  const d = document.createElement("div");
  d.innerHTML = html || "";
  return (d.textContent || "").trim();
};
const slug = (s) =>
  (s || "").trim().toLowerCase().replace(/[^a-z0-9-]+/g, "-").replace(/^-|-$/g, "");

// ------------------------------------------------------------ form build

function fieldColor(field, section) {
  return state.fieldColors[field.id] || field.color || section.color;
}

function richBox(fieldId, value, placeholder, color, extraClass = "") {
  const div = document.createElement("div");
  div.className = `rich ${extraClass}`.trim();
  div.contentEditable = "true";
  div.dataset.field = fieldId;
  div.style.color = color;
  if (placeholder) div.dataset.placeholder = placeholder;
  div.innerHTML = value || "";
  return div;
}

function buildChoice(field, section, multiple) {
  const wrap = document.createElement("div");
  wrap.className = "opts";
  const paint = () => {
    const current = state.answers[field.id];
    $$(".opt-pill", wrap).forEach((pill) => {
      const id = pill.dataset.opt;
      const on = multiple
        ? Array.isArray(current) && current.includes(id)
        : current === id;
      pill.setAttribute("aria-pressed", String(on));
    });
  };
  for (const opt of field.options) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "opt-pill";
    btn.dataset.opt = opt.id;
    btn.textContent = opt.label;
    btn.addEventListener("click", () => {
      if (multiple) {
        const set = new Set(
          Array.isArray(state.answers[field.id]) ? state.answers[field.id] : []
        );
        set.has(opt.id) ? set.delete(opt.id) : set.add(opt.id);
        state.answers[field.id] = [...set];
      } else {
        state.answers[field.id] =
          state.answers[field.id] === opt.id ? undefined : opt.id;
      }
      paint();
      markDirty();
    });
    wrap.append(btn);
  }
  paint();
  return wrap;
}

function buildList(field, section) {
  const color = fieldColor(field, section);
  const wrap = document.createElement("div");
  wrap.dataset.list = field.id;

  const values = Array.isArray(state.answers[field.id])
    ? [...state.answers[field.id]]
    : [];
  while (values.length < (field.min_rows || 2)) values.push("");

  const renumber = () =>
    $$(".list-row", wrap).forEach((row, i) => {
      $(".num", row).textContent = i + 1;
    });

  const addRow = (value) => {
    const row = document.createElement("div");
    row.className = "list-row";
    const num = document.createElement("span");
    num.className = "num";
    row.append(num, richBox(field.id, value, field.placeholder || "", color));
    const del = document.createElement("button");
    del.type = "button";
    del.className = "del";
    del.title = "刪除這一行";
    del.textContent = "✕";
    del.addEventListener("click", () => {
      row.remove();
      renumber();
      markDirty();
    });
    row.append(del);
    wrap.insertBefore(row, addBtn);
    renumber();
  };

  const addBtn = document.createElement("button");
  addBtn.type = "button";
  addBtn.className = "ghost small";
  addBtn.textContent = "＋ 再加一行";
  addBtn.addEventListener("click", () => {
    addRow("");
    markDirty();
  });

  wrap.append(addBtn);
  values.forEach(addRow);
  return wrap;
}

function buildFill(field, section) {
  const color = fieldColor(field, section);
  const line = document.createElement("div");
  line.className = "fill-line";
  line.dataset.fill = field.id;
  const stored = Array.isArray(state.answers[field.id])
    ? state.answers[field.id]
    : [];
  const parts = (field.pattern || "{}").split("{}");

  parts.forEach((part, i) => {
    line.append(document.createTextNode(part));
    if (i < parts.length - 1) {
      const input = document.createElement("input");
      input.type = "text";
      input.className = "blank";
      input.dataset.index = i;
      input.value = stored[i] || "";
      input.style.color = color;
      input.style.borderBottomColor = color;
      input.size = Math.max(6, (input.value.length || 5) + 2);
      input.addEventListener("input", () => {
        input.size = Math.max(6, input.value.length + 2);
        markDirty();
      });
      line.append(input);
    }
  });
  return line;
}

function buildField(field, section) {
  const box = document.createElement("div");
  box.className = "fld";

  const label = document.createElement("span");
  label.className = "lbl";
  label.textContent = field.label + (field.hint ? `　${field.hint}` : "");
  box.append(label);

  switch (field.kind) {
    case "choice":
    case "scale":
      box.append(buildChoice(field, section, false));
      break;
    case "multi_choice":
      box.append(buildChoice(field, section, true));
      break;
    case "short_text": {
      const input = document.createElement("input");
      input.type = "text";
      input.dataset.short = field.id;
      input.value = state.answers[field.id] || "";
      input.placeholder = field.placeholder || "";
      input.addEventListener("input", markDirty);
      box.append(input);
      break;
    }
    case "fill":
      box.append(buildFill(field, section));
      break;
    case "list":
      box.append(buildList(field, section));
      break;
    default:
      box.append(
        richBox(
          field.id,
          state.answers[field.id] || "",
          field.placeholder || "",
          fieldColor(field, section),
          "tall"
        )
      );
  }
  return box;
}

function buildForm() {
  const form = $("#form");
  form.replaceChildren();
  renderClosingLabels();
  if (!state.template) return;

  for (const section of state.template.sections) {
    const sec = document.createElement("section");
    sec.className = "sec";
    sec.style.setProperty("--sec", section.color);

    const head = document.createElement("div");
    head.className = "sec-head";
    if (section.icon) {
      const icon = document.createElement("i");
      icon.style.background = section.color;
      icon.textContent = section.icon;
      head.append(icon);
    }
    const h3 = document.createElement("h3");
    h3.textContent = section.title;
    head.append(h3);

    const body = document.createElement("div");
    body.className = "sec-body";
    section.fields.forEach((f) => body.append(buildField(f, section)));

    sec.append(head, body);
    form.append(sec);
  }

  form.addEventListener("input", markDirty);
  refreshOrphanNote();
}

// ------------------------------------------------------------ collect

function collect() {
  // Start from what is already stored so answers belonging to *other*
  // question sets ride along untouched. Switching template must never be a
  // silent delete.
  const answers = { ...state.answers };
  if (!state.template) return answers;

  for (const section of state.template.sections) {
    for (const field of section.fields) {
      switch (field.kind) {
        case "choice":
        case "scale":
        case "multi_choice":
          if (state.answers[field.id] === undefined) delete answers[field.id];
          else answers[field.id] = state.answers[field.id];
          break;
        case "short_text": {
          const el = $(`[data-short="${field.id}"]`);
          if (el) answers[field.id] = el.value;
          break;
        }
        case "fill": {
          const line = $(`[data-fill="${field.id}"]`);
          if (line) answers[field.id] = $$(".blank", line).map((i) => i.value);
          break;
        }
        case "list": {
          const wrap = $(`[data-list="${field.id}"]`);
          if (wrap)
            answers[field.id] = $$(".rich", wrap).map((r) => r.innerHTML);
          break;
        }
        default: {
          const el = $(`.rich[data-field="${field.id}"]`);
          if (el) answers[field.id] = el.innerHTML;
        }
      }
    }
  }
  return answers;
}

/** Is there anything worth storing? Guards against entry-per-restart spam. */
function hasContent(payload) {
  if (payload.title.trim()) return true;
  if (stripHtml(payload.closing)) return true;
  for (const value of Object.values(payload.answers)) {
    if (typeof value === "string" && stripHtml(value)) return true;
    if (Array.isArray(value) && value.some((v) => stripHtml(String(v))))
      return true;
  }
  return false;
}

// ------------------------------------------------------------ persistence

let saveTimer;
function markDirty() {
  state.dirty = true;
  setSaveHint("未儲存…", "dirty");
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => save(true), 1200);
}

function setSaveHint(text, cls = "") {
  const el = $("#save-hint");
  el.textContent = text;
  el.className = `save-hint ${cls}`.trim();
}

function buildPayload() {
  const payload = {
    entry_date: $("#entry-date").value || today(),
    title: $("#entry-title").value,
    template_id: state.template.id,
    theme: state.theme,
    layout: state.layout,
    answers: collect(),
    closing: $("#closing").innerHTML,
    field_colors: state.fieldColors,
  };
  // Tells the server what we last read, so it can refuse rather than
  // overwrite if another tab has since saved something newer.
  if (state.entryId && state.updatedAt) {
    payload.expected_updated_at = state.updatedAt;
  }
  return payload;
}

async function save(silent = false) {
  if (state.saving || !state.template) return;
  const payload = buildPayload();

  // Choosing a template or a colour should not, by itself, create a journal
  // entry. Only real writing does.
  if (!state.entryId && !hasContent(payload)) {
    state.dirty = false;
    setSaveHint("");
    if (!silent) toast("還沒有內容，不用存。寫點東西就會自動儲存。");
    return;
  }

  state.saving = true;
  try {
    const entry = state.entryId
      ? await api(`/api/entries/${state.entryId}`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        })
      : await api("/api/entries", {
          method: "POST",
          body: JSON.stringify(payload),
        });
    state.entryId = entry.id;
    state.answers = entry.answers;
    state.updatedAt = entry.updated_at;
    state.dirty = false;
    $("#btn-history").disabled = false;
    setSaveHint(`已儲存 ${new Date().toTimeString().slice(0, 5)}`, "ok");
    if (!silent) toast("已儲存");
    await loadEntries();
    refreshOrphanNote();
  } catch (err) {
    state.saving = false;
    if (/被改過/.test(err.message)) {
      await handleConflict();
      return;
    }
    setSaveHint("儲存失敗", "err");
    toast(`儲存失敗：${err.message}`, true);
  } finally {
    state.saving = false;
  }
}

/** Another tab saved first. Never resolve this silently. */
async function handleConflict() {
  setSaveHint("有衝突", "err");
  const keepMine = confirm(
    "這篇日記在別的地方被改過了（可能是另一個分頁開著）。\n\n" +
      "按「確定」用你這邊的版本覆蓋過去（舊版本仍會留在歷史裡，可以還原）。\n" +
      "按「取消」放棄這邊的修改，載入比較新的版本。"
  );
  if (keepMine) {
    const latest = await api(`/api/entries/${state.entryId}`);
    state.updatedAt = latest.updated_at;
    await save(true);
    toast("已用你的版本覆蓋，舊版本留在「歷史」裡");
  } else {
    applyEntry(await api(`/api/entries/${state.entryId}`));
    toast("已載入比較新的版本");
  }
}

async function ensureSaved() {
  if (!state.entryId || state.dirty) await save(true);
  if (!state.entryId) throw new Error("要先寫一點內容才能輸出。");
  return state.entryId;
}

/** Show what this entry holds that the current question set does not display. */
async function refreshOrphanNote() {
  const note = $("#orphan-note");
  if (!state.entryId || !state.template) {
    note.hidden = true;
    return;
  }
  try {
    const orphans = await api(
      `/api/entries/${state.entryId}/orphans?template_id=${state.template.id}`
    );
    if (!orphans.length) {
      note.hidden = true;
      return;
    }
    note.replaceChildren();
    const head = document.createElement("b");
    head.textContent = `這篇還留著 ${orphans.length} 段別的題組寫的內容`;
    const sub = document.createElement("span");
    sub.textContent = "沒有不見，換回原本的題組就會出現。";
    note.append(head, sub);
    const ul = document.createElement("ul");
    for (const o of orphans) {
      const li = document.createElement("li");
      li.textContent = o.preview;
      ul.append(li);
    }
    note.append(ul);
    note.hidden = false;
  } catch {
    note.hidden = true;
  }
}

// ------------------------------------------------------------ entries

async function loadEntries() {
  const entries = await api("/api/entries?limit=40");
  const list = $("#entry-list");
  list.replaceChildren();

  const emptyCount = entries.filter((e) => e.is_empty).length;
  const tidy = $("#btn-tidy");
  tidy.hidden = emptyCount === 0;
  tidy.textContent = `清理 ${emptyCount} 筆空白`;
  tidy.dataset.ids = entries.filter((e) => e.is_empty).map((e) => e.id).join(",");

  const byDate = {};
  for (const e of entries) byDate[e.entry_date] = (byDate[e.entry_date] || 0) + 1;

  for (const entry of entries) {
    const row = document.createElement("div");
    row.className = "ent-row";

    const btn = document.createElement("button");
    btn.className = "ent";
    btn.setAttribute("aria-pressed", String(entry.id === state.entryId));
    const dup = byDate[entry.entry_date] > 1 ? " ·同日多筆" : "";
    btn.innerHTML =
      `<span class="ent-date">${entry.entry_date}${dup}</span>` +
      `<span class="ent-title">${entry.title || "（未命名）"}</span>` +
      `<span class="ent-meta">${
        entry.is_empty ? "空白" : entry.word_count + " 字"
      }</span>`;
    btn.addEventListener("click", () => openEntry(entry.id));

    const del = document.createElement("button");
    del.className = "ent-del";
    del.title = "刪除這一筆";
    del.textContent = "✕";
    del.addEventListener("click", (ev) => {
      ev.stopPropagation();
      deleteEntry(entry);
    });

    row.append(btn, del);
    list.append(row);
  }
}

async function deleteEntry(entry) {
  const label = entry.is_empty
    ? `刪掉 ${entry.entry_date} 這筆空白日記？`
    : `刪掉 ${entry.entry_date}「${entry.title || "未命名"}」？` +
      `\n這篇有 ${entry.word_count} 個字，刪掉就沒有了。`;
  if (!confirm(label)) return;
  await api(`/api/entries/${entry.id}`, { method: "DELETE" });
  if (state.entryId === entry.id) newEntry();
  await loadEntries();
  await refreshSafety();
  toast("已刪除（可以從「備份與垃圾桶」救回來）");
}

async function tidyEmpty() {
  const ids = ($("#btn-tidy").dataset.ids || "").split(",").filter(Boolean);
  if (!ids.length) return;
  if (!confirm(`刪掉 ${ids.length} 筆完全空白的日記？有寫字的不會被動到。`)) return;
  for (const id of ids) await api(`/api/entries/${id}`, { method: "DELETE" });
  if (ids.includes(String(state.entryId))) newEntry();
  await loadEntries();
  toast(`清掉了 ${ids.length} 筆空白`);
}

function applyEntry(entry) {
  state.entryId = entry.id;
  state.updatedAt = entry.updated_at;
  state.answers = entry.answers || {};
  state.fieldColors = entry.field_colors || {};
  $("#btn-history").disabled = false;
  state.theme = entry.theme;
  state.layout = entry.layout || "letter";
  state.template =
    state.templates.find((t) => t.id === entry.template_id) || state.template;
  $("#entry-date").value = entry.entry_date;
  $("#entry-title").value = entry.title;
  $("#closing").innerHTML = entry.closing || "";
  renderTemplatePicker();
  renderLayoutPicker();
  renderThemePicker();
  buildForm();
  state.dirty = false;
  setSaveHint("已儲存", "ok");
}

async function openEntry(id) {
  if (state.dirty) await save(true);
  applyEntry(await api(`/api/entries/${id}`));
  await loadEntries();
}

function newEntry() {
  state.entryId = null;
  state.updatedAt = null;
  state.answers = {};
  state.fieldColors = {};
  $("#btn-history").disabled = true;
  $("#entry-date").value = today();
  $("#entry-title").value = "";
  $("#closing").innerHTML = "";
  buildForm();
  loadEntries();
  setSaveHint("");
  state.dirty = false;
}

// ------------------------------------------------------------ pickers

/** Question sets in list order, bucketed under their group heading. */
function groupedTemplates() {
  const groups = new Map();
  for (const tpl of state.templates) {
    const name = (tpl.group || "").trim() || "其他";
    if (!groups.has(name)) groups.set(name, []);
    groups.get(name).push(tpl);
  }
  // "其他" collects the ungrouped, so it belongs at the bottom.
  const other = groups.get("其他");
  if (other && groups.size > 1) {
    groups.delete("其他");
    groups.set("其他", other);
  }
  return groups;
}

function renderTemplatePicker() {
  const list = $("#template-list");
  list.replaceChildren();
  const groups = groupedTemplates();
  const showHeadings = groups.size > 1;

  for (const [name, templates] of groups) {
    if (showHeadings) {
      const head = document.createElement("div");
      head.className = "tpl-group";
      head.textContent = name;
      list.append(head);
    }
    for (const tpl of templates) {
      const row = document.createElement("div");
      row.className = "tpl-row";

      const btn = document.createElement("button");
      btn.className = "tpl";
      btn.setAttribute("aria-pressed", String(tpl.id === state.template?.id));
      btn.innerHTML = `<b>${tpl.name}</b><span>${tpl.description || ""}</span>`;
      btn.addEventListener("click", () => switchTemplate(tpl));

      const edit = document.createElement("button");
      edit.className = "tpl-edit";
      edit.title = "編輯這個題組";
      edit.textContent = "✎";
      edit.addEventListener("click", (ev) => {
        ev.stopPropagation();
        openTemplateEditor(tpl);
      });

      row.append(btn, edit);
      list.append(row);
    }
  }
}

/** The closing block is named by the question set — not every set is a prayer. */
function renderClosingLabels() {
  const tpl = state.template;
  $("#closing-label").textContent = tpl?.closing_label || "給主的話";
  $("#closing-hint").textContent =
    tpl?.closing_hint || "今天想對主說的一段話。也可以換色。";
  $("#closing").dataset.placeholder =
    tpl?.closing_placeholder || "親愛的主耶穌，今天…";
}

async function switchTemplate(tpl) {
  if (tpl.id === state.template?.id) return;

  // Warn only when there is something to lose sight of.
  if (state.entryId) {
    if (state.dirty) await save(true);
    try {
      const orphans = await api(
        `/api/entries/${state.entryId}/orphans?template_id=${tpl.id}`
      );
      if (orphans.length) {
        const ok = confirm(
          `換成「${tpl.name}」後，這篇有 ${orphans.length} 段內容不會顯示。\n\n` +
            `內容不會被刪除——換回原本的題組就會回來。要換嗎？`
        );
        if (!ok) return;
      }
    } catch {}
  }

  state.template = tpl;
  if (tpl.default_theme) state.theme = tpl.default_theme;
  if (tpl.default_layout) state.layout = tpl.default_layout;
  renderTemplatePicker();
  renderLayoutPicker();
  renderThemePicker();
  buildForm();
  markDirty();
}

function renderLayoutPicker() {
  const list = $("#layout-list");
  list.replaceChildren();
  for (const layout of state.layouts) {
    const btn = document.createElement("button");
    btn.className = "tpl";
    btn.setAttribute("aria-pressed", String(layout.id === state.layout));
    const badges = (layout.tags || []).map((t) => `<em>${t}</em>`).join("");
    btn.innerHTML =
      `<b>${layout.name}</b><span>${layout.description || ""}</span>` +
      (badges ? `<span class="badges">${badges}</span>` : "");
    btn.addEventListener("click", () => {
      state.layout = layout.id;
      if (layout.default_theme) state.theme = layout.default_theme;
      renderLayoutPicker();
      renderThemePicker();
      markDirty();
    });
    list.append(btn);
  }
  const cur = state.layouts.find((l) => l.id === state.layout);
  $("#cur-layout").textContent = cur ? cur.name : state.layout;
}

function renderThemePicker() {
  const list = $("#theme-list");
  list.replaceChildren();
  for (const theme of state.themes) {
    const btn = document.createElement("button");
    btn.className = "thm";
    btn.setAttribute("aria-pressed", String(theme.id === state.theme));
    btn.innerHTML = `<i style="background:${theme.swatch[0]};border-color:${theme.swatch[2]}"></i>${theme.name}`;
    btn.addEventListener("click", () => {
      state.theme = theme.id;
      renderThemePicker();
      markDirty();
    });
    list.append(btn);
  }
}

// ------------------------------------------------------------ palette

function renderSwatches() {
  const swatches = $("#swatches");
  swatches.replaceChildren();
  for (const pen of state.palette) {
    const btn = document.createElement("button");
    btn.className = "sw";
    btn.style.background = pen.hex;
    btn.title = pen.name || pen.hex;
    btn.dataset.color = pen.hex;
    swatches.append(btn);
  }
}

function renderPaletteEditor() {
  const box = $("#palette-editor");
  box.replaceChildren();
  state.palette.forEach((pen, i) => {
    const row = document.createElement("div");
    row.className = "pal-row";

    const chip = document.createElement("span");
    chip.className = "pal-chip";
    chip.style.background = pen.hex;

    const name = document.createElement("input");
    name.type = "text";
    name.value = pen.name || "";
    name.placeholder = pen.hex;
    name.addEventListener("input", () => {
      state.palette[i].name = name.value;
    });

    const hex = document.createElement("span");
    hex.className = "pal-hex";
    hex.textContent = pen.hex;

    const del = document.createElement("button");
    del.className = "ent-del";
    del.title = "刪掉這個顏色";
    del.textContent = "✕";
    del.addEventListener("click", () => {
      state.palette.splice(i, 1);
      renderPaletteEditor();
    });

    row.append(chip, name, hex, del);
    box.append(row);
  });
}

async function savePalette() {
  const prefs = { ...(state.prefs || {}), palette: state.palette };
  state.prefs = await api("/api/preferences", {
    method: "PUT",
    body: JSON.stringify(prefs),
  });
  state.palette = state.prefs.palette;
  renderSwatches();
}

function setupPalette() {
  // Keep the text selection alive when a palette button is pressed.
  $("#palette-bar").addEventListener("mousedown", (e) => {
    if (e.target.closest("button")) e.preventDefault();
  });

  $("#palette-bar").addEventListener("click", (e) => {
    const btn = e.target.closest("button");
    if (!btn || btn.id === "btn-palette") return;
    const sel = document.getSelection();
    const inRich =
      sel && !sel.isCollapsed && sel.anchorNode?.parentElement?.closest(".rich");
    if (!inRich) {
      toast("先在文字上選取一段，再點顏色。", true);
      return;
    }
    document.execCommand("styleWithCSS", false, true);
    if (btn.dataset.color) {
      document.execCommand("foreColor", false, btn.dataset.color);
    } else if (btn.dataset.cmd === "bold") {
      document.execCommand("bold");
    } else if (btn.dataset.cmd === "clear") {
      document.execCommand("removeFormat");
    }
    markDirty();
  });

  $("#btn-palette").addEventListener("click", () => {
    renderPaletteEditor();
    $("#palette-dialog").showModal();
  });
  $("#pal-add").addEventListener("click", () => {
    const hex = $("#pal-new-hex").value;
    if (state.palette.some((p) => p.hex.toLowerCase() === hex.toLowerCase())) {
      toast("這個顏色已經在裡面了。", true);
      return;
    }
    state.palette.push({ hex, name: $("#pal-new-name").value.trim() });
    $("#pal-new-name").value = "";
    renderPaletteEditor();
  });
  $("#pal-reset").addEventListener("click", async () => {
    state.prefs = await api("/api/preferences/palette/reset", { method: "POST" });
    state.palette = state.prefs.palette;
    renderPaletteEditor();
    renderSwatches();
    toast("已還原預設顏色");
  });
  $("#pal-close").addEventListener("click", async () => {
    $("#palette-dialog").close();
    await savePalette();
    toast("顏色已存好");
  });
}

// ------------------------------------------------------- template editor

function blankField() {
  return {
    id: `f${Math.random().toString(36).slice(2, 8)}`,
    label: "",
    kind: "text",
    options: [],
    pattern: null,
    placeholder: null,
    min_rows: 2,
    color: null,
    hint: null,
  };
}

function blankSection() {
  return {
    id: `s${Math.random().toString(36).slice(2, 8)}`,
    title: "",
    color: state.palette[0]?.hex || "#2456b8",
    icon: null,
    fields: [blankField()],
  };
}

function openTemplateEditor(tpl) {
  const draft = tpl
    ? JSON.parse(JSON.stringify(tpl))
    : {
        id: "",
        name: "",
        description: "",
        group: "",
        default_theme: "letterpress",
        default_layout: "letter",
        sections: [blankSection()],
      };
  state.editingTemplate = { draft, isNew: !tpl };
  $("#tpl-dlg-title").textContent = tpl ? "編輯題組" : "新增題組";
  $("#tpl-name").value = draft.name;
  $("#tpl-desc").value = draft.description || "";
  $("#tpl-group").value = draft.group || "";
  $("#tpl-closing").value = draft.closing_label || "";

  // Offer the groups that already exist, so a new set joins one by typing
  // rather than by remembering how it was spelled.
  const options = $("#tpl-group-options");
  options.replaceChildren();
  for (const name of groupedTemplates().keys()) {
    if (name === "其他") continue;
    const opt = document.createElement("option");
    opt.value = name;
    options.append(opt);
  }

  $("#tpl-delete").hidden = !tpl;
  renderTemplateSections();
  $("#tpl-dialog").showModal();
}

function renderTemplateSections() {
  const host = $("#tpl-sections");
  host.replaceChildren();
  const { draft } = state.editingTemplate;

  draft.sections.forEach((section, si) => {
    const box = document.createElement("div");
    box.className = "tpl-section";
    box.style.setProperty("--sec", section.color);

    // -- section header
    const head = document.createElement("div");
    head.className = "tpl-sec-head";

    const color = document.createElement("input");
    color.type = "color";
    color.value = section.color;
    color.title = "段落顏色";
    color.addEventListener("input", () => {
      section.color = color.value;
      box.style.setProperty("--sec", color.value);
    });

    const title = document.createElement("input");
    title.type = "text";
    title.value = section.title;
    title.placeholder = "段落標題，例：感恩";
    title.addEventListener("input", () => (section.title = title.value));

    const icon = document.createElement("input");
    icon.type = "text";
    icon.className = "tpl-icon";
    icon.value = section.icon || "";
    icon.placeholder = "圖示";
    icon.maxLength = 2;
    icon.addEventListener("input", () => (section.icon = icon.value || null));

    const delSec = document.createElement("button");
    delSec.className = "ent-del";
    delSec.title = "刪掉這個段落";
    delSec.textContent = "✕";
    delSec.addEventListener("click", () => {
      draft.sections.splice(si, 1);
      if (!draft.sections.length) draft.sections.push(blankSection());
      renderTemplateSections();
    });

    head.append(color, title, icon, delSec);
    box.append(head);

    // -- fields
    section.fields.forEach((field, fi) => {
      const row = document.createElement("div");
      row.className = "tpl-field";

      const label = document.createElement("input");
      label.type = "text";
      label.value = field.label;
      label.placeholder = "題目，例：今天最感謝的事";
      label.addEventListener("input", () => (field.label = label.value));

      const kind = document.createElement("select");
      for (const [value, text] of FIELD_KINDS) {
        const opt = document.createElement("option");
        opt.value = value;
        opt.textContent = text;
        if (field.kind === value) opt.selected = true;
        kind.append(opt);
      }
      kind.addEventListener("change", () => {
        field.kind = kind.value;
        if (KIND_WITH_OPTIONS.has(field.kind) && !field.options.length) {
          field.options =
            field.kind === "scale"
              ? [
                  { id: "good", label: "滿意" },
                  { id: "ok", label: "還可以" },
                  { id: "low", label: "缺乏" },
                ]
              : [
                  { id: "yes", label: "有" },
                  { id: "no", label: "沒有" },
                ];
        }
        renderTemplateSections();
      });

      const delField = document.createElement("button");
      delField.className = "ent-del";
      delField.title = "刪掉這一題";
      delField.textContent = "✕";
      delField.addEventListener("click", () => {
        section.fields.splice(fi, 1);
        if (!section.fields.length) section.fields.push(blankField());
        renderTemplateSections();
      });

      row.append(label, kind, delField);

      // options / pattern editors
      if (KIND_WITH_OPTIONS.has(field.kind)) {
        const opts = document.createElement("div");
        opts.className = "tpl-opts";
        field.options.forEach((opt, oi) => {
          const chip = document.createElement("span");
          chip.className = "tpl-opt";
          const oin = document.createElement("input");
          oin.type = "text";
          oin.value = opt.label;
          oin.size = Math.max(3, opt.label.length + 1);
          oin.addEventListener("input", () => {
            opt.label = oin.value;
            opt.id = slug(oin.value) || `o${oi}`;
            oin.size = Math.max(3, oin.value.length + 1);
          });
          const ox = document.createElement("button");
          ox.textContent = "✕";
          ox.addEventListener("click", () => {
            field.options.splice(oi, 1);
            renderTemplateSections();
          });
          chip.append(oin, ox);
          opts.append(chip);
        });
        const addOpt = document.createElement("button");
        addOpt.className = "ghost tiny";
        addOpt.textContent = "＋ 選項";
        addOpt.addEventListener("click", () => {
          field.options.push({ id: `o${field.options.length}`, label: "" });
          renderTemplateSections();
        });
        opts.append(addOpt);
        row.append(opts);
      } else if (field.kind === "fill") {
        const pat = document.createElement("input");
        pat.type = "text";
        pat.className = "tpl-pattern";
        pat.value = field.pattern || "";
        pat.placeholder = "句子，用 {} 當空格。例：今天讀了 {}，最觸動我的是 {}";
        pat.addEventListener("input", () => (field.pattern = pat.value));
        row.append(pat);
      } else {
        const ph = document.createElement("input");
        ph.type = "text";
        ph.className = "tpl-pattern";
        ph.value = field.placeholder || "";
        ph.placeholder = "提示文字（可留白）";
        ph.addEventListener("input", () => (field.placeholder = ph.value || null));
        row.append(ph);
      }

      box.append(row);
    });

    const addField = document.createElement("button");
    addField.className = "ghost tiny";
    addField.textContent = "＋ 加一題";
    addField.addEventListener("click", () => {
      section.fields.push(blankField());
      renderTemplateSections();
    });
    box.append(addField);

    host.append(box);
  });
}

async function saveTemplateDraft() {
  const { draft, isNew } = state.editingTemplate;
  draft.name = $("#tpl-name").value.trim();
  draft.description = $("#tpl-desc").value.trim();
  draft.group = $("#tpl-group").value.trim();
  const closing = $("#tpl-closing").value.trim();
  if (closing) draft.closing_label = closing;

  if (!draft.name) {
    toast("先給這個題組一個名字。", true);
    return;
  }
  draft.sections = draft.sections
    .map((s) => ({
      ...s,
      title: s.title.trim() || "未命名段落",
      fields: s.fields.filter((f) => f.label.trim()),
    }))
    .filter((s) => s.fields.length);
  if (!draft.sections.length) {
    toast("至少要有一題。", true);
    return;
  }

  const id = draft.id || slug(draft.name) || `tpl-${Date.now()}`;
  draft.id = id;
  try {
    const saved = await api(`/api/templates/${id}`, {
      method: "PUT",
      body: JSON.stringify(draft),
    });
    state.templates = await api("/api/templates");
    $("#tpl-dialog").close();
    if (isNew || state.template?.id === saved.id) {
      state.template = state.templates.find((t) => t.id === saved.id);
      buildForm();
    }
    renderTemplatePicker();
    toast(isNew ? "題組建好了" : "題組已更新");
  } catch (err) {
    toast(`存不起來：${err.message}`, true);
  }
}

async function deleteTemplateDraft() {
  const { draft } = state.editingTemplate;
  if (!confirm(`刪掉「${draft.name}」這個題組？\n已經寫好的日記不會被刪。`)) return;

  const remove = async (force) =>
    api(`/api/templates/${draft.id}${force ? "?force=true" : ""}`, {
      method: "DELETE",
    });

  try {
    try {
      await remove(false);
    } catch (err) {
      // The server refuses when entries still use it, and says how many.
      if (!confirm(`${err.message}\n\n還是要刪除嗎？`)) return;
      await remove(true);
    }
    state.templates = await api("/api/templates");
    $("#tpl-dialog").close();
    if (state.template?.id === draft.id) {
      state.template = state.templates[0] || null;
      buildForm();
    }
    renderTemplatePicker();
    await loadEntries();
    toast("已刪除");
  } catch (err) {
    toast(err.message, true);
  }
}

function setupTemplateEditor() {
  $("#btn-new-tpl").addEventListener("click", () => openTemplateEditor(null));
  $("#tpl-add-section").addEventListener("click", () => {
    state.editingTemplate.draft.sections.push(blankSection());
    renderTemplateSections();
  });
  $("#tpl-save").addEventListener("click", saveTemplateDraft);
  $("#tpl-delete").addEventListener("click", deleteTemplateDraft);
  $("#tpl-cancel").addEventListener("click", () => $("#tpl-dialog").close());
  $("#tpl-close").addEventListener("click", () => $("#tpl-dialog").close());
}

// ------------------------------------------------------------ export

async function exportHtml(preview) {
  const id = await ensureSaved();
  const result = await api("/api/export/html", {
    method: "POST",
    body: JSON.stringify({
      entry_id: id,
      theme: state.theme,
      layout: state.layout,
      gift_cover: $("#opt-gift").checked,
      gift_message: $("#opt-gift-msg").value,
    }),
  });

  const blob = new Blob([result.html], { type: "text/html;charset=utf-8" });
  if (preview) {
    const box = $("#html-preview");
    box.replaceChildren();
    const frame = document.createElement("iframe");
    frame.srcdoc = result.html;
    frame.title = "頁面預覽";
    box.append(frame);
    const open = document.createElement("button");
    open.className = "ghost tiny wide";
    open.textContent = "在新分頁開啟（比較好讀）";
    open.addEventListener("click", () => {
      const url = URL.createObjectURL(blob);
      window.open(url, "_blank", "noopener");
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    });
    box.append(open);
    box.hidden = false;
    toast("這就是「頁面」的樣子");
  } else {
    download(`${$("#entry-date").value || "journal"}.html`, blob);
    toast("已下載 .html");
  }
}

async function makeCard() {
  const id = await ensureSaved();
  const result = await api("/api/export/card", {
    method: "POST",
    body: JSON.stringify({
      entry_id: id,
      theme: state.theme,
      layout: state.layout,
      width: Number($("#opt-shape").value),
      paper: $("#opt-paper").value || null,
    }),
  });
  state.lastSvg = result.svg;
  $("#card-preview").innerHTML = result.svg;
  $("#btn-svg").disabled = false;
  $$("#png-row button").forEach((b) => (b.disabled = false));
  toast(`卡片 ${result.width}×${result.height}`);
}

function svgDataUrl(svg) {
  const utf8 = new TextEncoder().encode(svg);
  let binary = "";
  utf8.forEach((b) => (binary += String.fromCharCode(b)));
  return `data:image/svg+xml;base64,${btoa(binary)}`;
}

async function downloadPng(scale) {
  if (!state.lastSvg) return;
  const svg = state.lastSvg;
  const width = Number(svg.match(/width="(\d+)"/)[1]);
  const height = Number(svg.match(/height="(\d+)"/)[1]);

  const img = new Image();
  await new Promise((resolve, reject) => {
    img.onload = resolve;
    img.onerror = () => reject(new Error("SVG 無法轉成圖片"));
    img.src = svgDataUrl(svg);
  });

  const canvas = document.createElement("canvas");
  canvas.width = width * scale;
  canvas.height = height * scale;
  canvas.getContext("2d").drawImage(img, 0, 0, canvas.width, canvas.height);
  canvas.toBlob((blob) => {
    download(`${$("#entry-date").value || "journal"}@${scale}x.png`, blob);
    toast(`已下載 ${canvas.width}×${canvas.height} PNG`);
  }, "image/png");
}

async function makeImagePrompt() {
  const id = await ensureSaved();
  toast("產生中…");
  const result = await api("/api/ai/image-prompt", {
    method: "POST",
    body: JSON.stringify({ entry_id: id, style: $("#opt-style").value }),
  });
  const out = $("#prompt-out");
  out.replaceChildren();

  const block = (title, text) => {
    const div = document.createElement("div");
    div.className = "blk";
    const b = document.createElement("b");
    b.textContent = title;
    const p = document.createElement("div");
    p.textContent = text;
    const copy = document.createElement("button");
    copy.className = "ghost small copy";
    copy.textContent = "複製";
    copy.addEventListener("click", async () => {
      await navigator.clipboard.writeText(text);
      toast("已複製");
    });
    div.append(b, p, copy);
    return div;
  };

  out.append(block("English prompt", result.prompt_en));
  out.append(block("中文 prompt", result.prompt_zh));
  if (result.negative_prompt)
    out.append(block("Negative prompt", result.negative_prompt));

  const tags = document.createElement("div");
  tags.className = "tags";
  tags.append(
    ...[result.mood, ...result.keywords].map((k) => {
      const s = document.createElement("span");
      s.textContent = k;
      return s;
    })
  );
  out.append(tags);
  toast(
    result.source === "claude" ? "Claude 產生完成" : "已用內建規則產生"
  );
}

// --------------------------------------------------- history / trash / backup

const REASON_LABEL = {
  edit: "存檔前",
  delete: "刪除前",
  restore: "還原前",
  import: "匯入前",
};

function timeLabel(iso) {
  return String(iso).replace("T", " ").slice(0, 16);
}

function safetyRow(title, sub, actions) {
  const row = document.createElement("div");
  row.className = "hist-row";
  const text = document.createElement("div");
  text.className = "hist-text";
  const b = document.createElement("b");
  b.textContent = title;
  const s = document.createElement("span");
  s.textContent = sub;
  text.append(b, s);
  row.append(text);
  const box = document.createElement("div");
  box.className = "hist-actions";
  for (const [label, cls, fn] of actions) {
    const btn = document.createElement("button");
    btn.className = cls;
    btn.textContent = label;
    btn.addEventListener("click", fn);
    box.append(btn);
  }
  row.append(box);
  return row;
}

async function openHistory() {
  if (!state.entryId) return;
  if (state.dirty) await save(true);
  const list = $("#history-list");
  list.replaceChildren();
  const revs = await api(`/api/entries/${state.entryId}/revisions`);
  if (!revs.length) {
    const p = document.createElement("p");
    p.className = "muted";
    p.textContent = "還沒有歷史版本。內容變短或過一段時間再存檔時就會留一份。";
    list.append(p);
  }
  for (const rev of revs) {
    list.append(
      safetyRow(
        `${timeLabel(rev.created_at)}　${rev.char_count} 字`,
        `${REASON_LABEL[rev.reason] || rev.reason}的版本` +
          (rev.title ? `　「${rev.title}」` : ""),
        [
          ["還原", "ghost tiny", async () => {
            if (!confirm(`把這篇還原成 ${timeLabel(rev.created_at)} 的版本？\n` +
                         `目前的內容會先存成一個新的歷史版本，可以再換回來。`)) return;
            const entry = await api(
              `/api/entries/revisions/${rev.id}/restore`, { method: "POST" }
            );
            applyEntry(entry);
            $("#history-dialog").close();
            await loadEntries();
            toast("已還原");
          }],
        ]
      )
    );
  }
  $("#history-dialog").showModal();
}

async function refreshSafety() {
  const status = await api("/api/backup/status");
  const line = $("#safety-line");
  line.textContent =
    `${status.entries} 篇日記　${status.backups} 份備份` +
    (status.trash ? `　垃圾桶 ${status.trash}` : "");
  return status;
}

async function openSafety() {
  await Promise.all([renderTrash(), renderBackups()]);
  $("#safety-dialog").showModal();
}

async function renderTrash() {
  const list = $("#trash-list");
  list.replaceChildren();
  const trash = await api("/api/backup/trash");
  if (!trash.length) {
    const p = document.createElement("p");
    p.className = "muted";
    p.textContent = "垃圾桶是空的。";
    list.append(p);
    return;
  }
  for (const item of trash) {
    list.append(
      safetyRow(
        `${item.entry_date}　${item.title || "（未命名）"}`,
        `${item.char_count} 字　${timeLabel(item.deleted_at)} 刪除`,
        [
          ["救回來", "primary tiny", async () => {
            const entry = await api(
              `/api/backup/trash/${item.entry_id}/restore`, { method: "POST" }
            );
            applyEntry(entry);
            await Promise.all([loadEntries(), renderTrash(), refreshSafety()]);
            toast("已救回");
          }],
          ["永久刪除", "ghost tiny", async () => {
            if (!confirm(
              `永久刪除 ${item.entry_date}「${item.title || "未命名"}」？\n` +
              `這 ${item.char_count} 個字之後就真的救不回來了。`
            )) return;
            await api(`/api/backup/trash/${item.entry_id}?confirm=true`, {
              method: "DELETE",
            });
            await Promise.all([renderTrash(), refreshSafety()]);
            toast("已永久刪除");
          }],
        ]
      )
    );
  }
}

async function renderBackups() {
  const list = $("#backup-list");
  list.replaceChildren();
  const backups = await api("/api/backup/list");
  for (const b of backups.slice(0, 15)) {
    const kb = Math.round(b.size_bytes / 1024);
    list.append(
      safetyRow(
        timeLabel(b.created_at),
        `${kb} KB　${b.automatic ? "自動" : "手動（不會被清掉）"}`,
        [
          ["還原", "ghost tiny", async () => {
            if (!confirm(
              `把整個資料庫還原成 ${timeLabel(b.created_at)} 的狀態？\n\n` +
              `目前的資料會先自動備份一份，所以這個動作也可以再還原回來。`
            )) return;
            const r = await api(`/api/backup/restore/${b.name}`, { method: "POST" });
            await Promise.all([loadEntries(), renderBackups(), renderTrash(), refreshSafety()]);
            newEntry();
            toast(`已還原，現在有 ${r.entries_now} 篇日記`);
          }],
        ]
      )
    );
  }
}

async function exportAll() {
  const res = await fetch("/api/backup/export");
  const blob = await res.blob();
  download(`journal-export-${today()}.json`, blob);
  toast("已匯出。建議存到雲端或隨身碟。");
}

async function importFile(file) {
  let document_;
  try {
    document_ = JSON.parse(await file.text());
  } catch {
    toast("這個檔案不是有效的 JSON。", true);
    return;
  }
  const replace = confirm(
    "要怎麼匯入？\n\n" +
      "「確定」＝取代：先清掉現在的日記，再匯入（會先自動備份）。\n" +
      "「取消」＝合併：保留現在的，把新的加進來（比較安全，建議這個）。"
  );
  const r = await api("/api/backup/import", {
    method: "POST",
    body: JSON.stringify({ document: document_, replace }),
  });
  await Promise.all([loadEntries(), refreshSafety()]);
  state.templates = await api("/api/templates");
  state.layouts = await api("/api/layouts");
  renderTemplatePicker();
  renderLayoutPicker();
  toast(
    `匯入完成：日記 ${r.entries} 篇` +
      (r.skipped_entries ? `（略過重複 ${r.skipped_entries}）` : "") +
      `，題組 ${r.templates}，版型 ${r.layouts}`
  );
}

// ------------------------------------------------- optional layout designer

function openDesignDialog() {
  const base = $("#design-base");
  base.replaceChildren();
  for (const layout of state.layouts) {
    const option = document.createElement("option");
    option.value = layout.id;
    option.textContent = layout.name;
    if (layout.id === state.layout) option.selected = true;
    base.append(option);
  }
  const dialog = $("#design-dialog");
  dialog.returnValue = "";
  dialog.showModal();
}

async function runDesign() {
  const name = $("#design-name").value.trim();
  if (!name) {
    toast("先給新版型一個名字。", true);
    return;
  }
  toast("Claude 設計中，可能要一兩分鐘…");
  try {
    const { layout } = await api("/api/layouts/design", {
      method: "POST",
      body: JSON.stringify({
        name,
        brief: $("#design-brief").value,
        base_layout: $("#design-base").value,
      }),
    });
    state.layouts = await api("/api/layouts");
    state.layout = layout.id;
    renderLayoutPicker();
    markDirty();
    $("#design-name").value = "";
    $("#design-brief").value = "";
    toast(`「${layout.name}」已存好，以後不用再呼叫 API`);
  } catch (err) {
    toast(err.message, true);
  }
}

// ------------------------------------------------------------ preferences

async function rememberSetup() {
  const prefs = {
    ...(state.prefs || {}),
    palette: state.palette,
    template_id: state.template?.id ?? null,
    layout: state.layout,
    theme: state.theme,
    card_paper: $("#opt-paper").value || null,
    card_width: Number($("#opt-shape").value),
    image_style: $("#opt-style").value,
    use_as_default: true,
  };
  state.prefs = await api("/api/preferences", {
    method: "PUT",
    body: JSON.stringify(prefs),
  });
  toast("記住了。下次開啟會直接用這組設定。");
}

function applyPrefs(prefs) {
  if (!prefs || !prefs.use_as_default) return;
  const tpl = state.templates.find((t) => t.id === prefs.template_id);
  if (tpl) state.template = tpl;
  if (state.layouts.some((l) => l.id === prefs.layout)) state.layout = prefs.layout;
  if (state.themes.some((t) => t.id === prefs.theme)) state.theme = prefs.theme;
  if (prefs.card_paper !== null && prefs.card_paper !== undefined)
    $("#opt-paper").value = prefs.card_paper;
  if (prefs.card_width) $("#opt-shape").value = String(prefs.card_width);
}

// ------------------------------------------------------------ wiring

function wire() {
  $("#btn-new").addEventListener("click", newEntry);
  $("#btn-save").addEventListener("click", () => save(false));
  $("#btn-tidy").addEventListener("click", () => tidyEmpty().catch((e) => toast(e.message, true)));
  $("#entry-date").addEventListener("change", markDirty);
  $("#entry-title").addEventListener("input", markDirty);
  $("#closing").addEventListener("input", markDirty);

  $("#opt-gift").addEventListener("change", (e) => {
    $("#opt-gift-msg").disabled = !e.target.checked;
  });
  $("#btn-design").addEventListener("click", openDesignDialog);
  $("#btn-remember").addEventListener("click", () =>
    rememberSetup().catch((e) => toast(e.message, true))
  );

  $("#btn-preview-html").addEventListener("click", () =>
    exportHtml(true).catch((e) => toast(e.message, true))
  );
  $("#btn-download-html").addEventListener("click", () =>
    exportHtml(false).catch((e) => toast(e.message, true))
  );
  $("#btn-card").addEventListener("click", () =>
    makeCard().catch((e) => toast(e.message, true))
  );
  $("#btn-svg").addEventListener("click", () => {
    download(
      `${$("#entry-date").value || "journal"}.svg`,
      new Blob([state.lastSvg], { type: "image/svg+xml;charset=utf-8" })
    );
  });
  $("#png-row").addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-scale]");
    if (btn)
      downloadPng(Number(btn.dataset.scale)).catch((err) =>
        toast(err.message, true)
      );
  });
  $("#btn-imgprompt").addEventListener("click", () =>
    makeImagePrompt().catch((e) => toast(e.message, true))
  );
  $("#btn-title").addEventListener("click", async () => {
    try {
      const id = await ensureSaved();
      toast("Claude 想想看…");
      const { title } = await api("/api/ai/title", {
        method: "POST",
        body: JSON.stringify({ entry_id: id }),
      });
      $("#entry-title").value = title;
      markDirty();
    } catch (e) {
      toast(e.message, true);
    }
  });

  $("#design-dialog").addEventListener("close", (e) => {
    if (e.target.returnValue === "go") runDesign();
  });

  const guard = (fn) => () => fn().catch((e) => toast(e.message, true));
  $("#btn-history").addEventListener("click", guard(openHistory));
  $("#history-close").addEventListener("click", () => $("#history-dialog").close());
  $("#btn-safety").addEventListener("click", guard(openSafety));
  $("#safety-close").addEventListener("click", () => $("#safety-dialog").close());
  $("#btn-make-backup").addEventListener("click", guard(async () => {
    const b = await api("/api/backup/create", { method: "POST" });
    await Promise.all([renderBackups(), refreshSafety()]);
    toast(`已備份（${Math.round(b.size_bytes / 1024)} KB）`);
  }));
  $("#btn-export").addEventListener("click", guard(exportAll));
  $("#btn-import").addEventListener("click", () => $("#import-file").click());
  $("#import-file").addEventListener("change", (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (file) importFile(file).catch((err) => toast(err.message, true));
  });

  window.addEventListener("beforeunload", (e) => {
    if (state.dirty) {
      e.preventDefault();
      e.returnValue = "";
    }
  });
}

async function init() {
  wire();
  setupPalette();
  setupTemplateEditor();

  const [health, templates, themes, layouts, styles, prefs] = await Promise.all([
    api("/api/health"),
    api("/api/templates"),
    api("/api/themes"),
    api("/api/layouts"),
    api("/api/ai/styles"),
    api("/api/preferences"),
  ]);

  state.templates = templates;
  state.themes = themes;
  state.layouts = layouts;
  state.prefs = prefs;
  state.palette = prefs.palette;
  state.template = templates[0] ?? null;
  state.theme = state.template?.default_theme ?? "letterpress";
  state.layout = state.template?.default_layout ?? layouts[0]?.id ?? "letter";
  state.aiAvailable = Boolean(health.ai_available);

  const styleSelect = $("#opt-style");
  for (const s of styles) {
    const option = document.createElement("option");
    option.value = s.id;
    option.textContent = s.label;
    styleSelect.append(option);
  }
  if (prefs.image_style) styleSelect.value = prefs.image_style;
  applyPrefs(prefs);

  // Exports never need a key; only these two helpers do.
  $("#ai-status").textContent = health.ai_available
    ? `AI 選配功能已啟用（${health.model}）`
    : "未設定 API key — 輸出功能全部照常";
  $("#btn-title").disabled = !state.aiAvailable;
  $("#btn-design").disabled = !state.aiAvailable;
  if (!state.aiAvailable) {
    $("#btn-design").title = "設計新版型需要 ANTHROPIC_API_KEY。內建版型不需要。";
    $("#btn-title").title = "標題建議需要 ANTHROPIC_API_KEY。";
  }

  renderSwatches();

  // Continue today's entry instead of quietly starting another one.
  $("#entry-date").value = today();
  const existing = await api(`/api/entries/by-date/${today()}`);
  if (existing) {
    applyEntry(existing);
    toast("接著今天已經寫的那篇繼續");
  } else {
    renderTemplatePicker();
    renderLayoutPicker();
    renderThemePicker();
    buildForm();
  }
  await loadEntries();
  await refreshSafety();
}

init().catch((err) => toast(`啟動失敗：${err.message}`, true));
