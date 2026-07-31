// Editor for the daily devotional journal.
//
// Everything is driven by the template the server hands back, so adding a new
// template on the server needs no change here: the form builds itself from the
// field kinds.

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

const INK = [
  ["#22252a", "墨黑"],
  ["#c8322c", "硃紅"],
  ["#1f7a4d", "松綠"],
  ["#2456b8", "靛藍"],
  ["#8a5fbf", "紫"],
  ["#c98a1e", "赭黃"],
];

const state = {
  templates: [],
  themes: [],
  layouts: [],
  template: null,
  theme: "letterpress",
  layout: "letter",
  aiAvailable: false,
  entryId: null,
  answers: {},
  fieldColors: {},
  closing: "",
  lastSvg: null,
  saving: false,
  dirty: false,
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
  toastTimer = setTimeout(() => el.classList.remove("show"), 3200);
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
  const current = state.answers[field.id];
  for (const opt of field.options) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "opt-pill";
    btn.textContent = opt.label;
    const on = multiple
      ? Array.isArray(current) && current.includes(opt.id)
      : current === opt.id;
    btn.setAttribute("aria-pressed", String(on));
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
      for (const sibling of $$(".opt-pill", wrap)) {
        const id = field.options[$$(".opt-pill", wrap).indexOf(sibling)].id;
        const active = multiple
          ? (state.answers[field.id] || []).includes(id)
          : state.answers[field.id] === id;
        sibling.setAttribute("aria-pressed", String(active));
      }
      markDirty();
    });
    wrap.append(btn);
  }
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
}

// ------------------------------------------------------------ collect

function collect() {
  const answers = {};
  if (!state.template) return answers;

  for (const section of state.template.sections) {
    for (const field of section.fields) {
      switch (field.kind) {
        case "choice":
        case "scale":
        case "multi_choice":
          if (state.answers[field.id] !== undefined)
            answers[field.id] = state.answers[field.id];
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

// ------------------------------------------------------------ persistence

let saveTimer;
function markDirty() {
  state.dirty = true;
  $("#save-hint").textContent = "未儲存…";
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => save(true), 1200);
}

async function save(silent = false) {
  if (state.saving || !state.template) return;
  state.saving = true;
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
    state.dirty = false;
    $("#save-hint").textContent = "已儲存";
    if (!silent) toast("已儲存");
    await loadEntries();
  } catch (err) {
    $("#save-hint").textContent = "";
    toast(`儲存失敗：${err.message}`, true);
  } finally {
    state.saving = false;
  }
}

async function ensureSaved() {
  if (!state.entryId || state.dirty) await save(true);
  if (!state.entryId) throw new Error("請先寫一點內容並儲存。");
  return state.entryId;
}

// ------------------------------------------------------------ entries

async function loadEntries() {
  const entries = await api("/api/entries?limit=40");
  const list = $("#entry-list");
  list.replaceChildren();
  for (const entry of entries) {
    const btn = document.createElement("button");
    btn.className = "ent";
    btn.setAttribute("aria-pressed", String(entry.id === state.entryId));
    btn.innerHTML = `${entry.entry_date}<span>${
      entry.title || "（未命名）"
    }</span>`;
    btn.addEventListener("click", () => openEntry(entry.id));
    list.append(btn);
  }
}

async function openEntry(id) {
  const entry = await api(`/api/entries/${id}`);
  state.entryId = entry.id;
  state.answers = entry.answers || {};
  state.fieldColors = entry.field_colors || {};
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
  await loadEntries();
  state.dirty = false;
  $("#save-hint").textContent = "";
}

function newEntry() {
  state.entryId = null;
  state.answers = {};
  state.fieldColors = {};
  $("#entry-date").value = today();
  $("#entry-title").value = "";
  $("#closing").innerHTML = "";
  buildForm();
  loadEntries();
  $("#save-hint").textContent = "";
  toast("開始新的一天");
}

// ------------------------------------------------------------ pickers

function renderTemplatePicker() {
  const list = $("#template-list");
  list.replaceChildren();
  for (const tpl of state.templates) {
    const btn = document.createElement("button");
    btn.className = "tpl";
    btn.setAttribute("aria-pressed", String(tpl.id === state.template?.id));
    btn.innerHTML = `<b>${tpl.name}</b><span>${tpl.description}</span>`;
    btn.addEventListener("click", () => {
      state.template = tpl;
      state.theme = tpl.default_theme || state.theme;
      state.layout = tpl.default_layout || state.layout;
      renderTemplatePicker();
      renderLayoutPicker();
      renderThemePicker();
      buildForm();
      markDirty();
    });
    list.append(btn);
  }
}

function renderLayoutPicker() {
  const list = $("#layout-list");
  list.replaceChildren();
  for (const layout of state.layouts) {
    const btn = document.createElement("button");
    btn.className = "tpl";
    btn.setAttribute("aria-pressed", String(layout.id === state.layout));
    const badges = layout.tags
      .map((t) => `<em>${t}</em>`)
      .join("");
    btn.innerHTML =
      `<b>${layout.name}</b><span>${layout.description}</span>` +
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

// ------------------------------------------------------------ colour bar

function setupPalette() {
  const swatches = $("#swatches");
  for (const [hex, name] of INK) {
    const btn = document.createElement("button");
    btn.className = "sw";
    btn.style.background = hex;
    btn.title = name;
    btn.dataset.color = hex;
    swatches.append(btn);
  }

  // Keep the text selection alive when a palette button is pressed.
  $("#palette-bar").addEventListener("mousedown", (e) => {
    if (e.target.closest("button")) e.preventDefault();
  });

  $("#palette-bar").addEventListener("click", (e) => {
    const btn = e.target.closest("button");
    if (!btn) return;
    const sel = document.getSelection();
    if (!sel || sel.isCollapsed || !sel.anchorNode?.parentElement?.closest(".rich")) {
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

  $("#custom-color").addEventListener("input", (e) => {
    document.execCommand("styleWithCSS", false, true);
    document.execCommand("foreColor", false, e.target.value);
    markDirty();
  });
}

// ------------------------------------------------------------ export

async function exportHtml(openInTab) {
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
  if (openInTab) {
    const url = URL.createObjectURL(blob);
    window.open(url, "_blank", "noopener");
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  } else {
    download(`${$("#entry-date").value || "journal"}.html`, blob);
  }
  toast("完成");
}

async function makeCard() {
  const id = await ensureSaved();
  const result = await api("/api/export/card", {
    method: "POST",
    body: JSON.stringify({
      entry_id: id,
      theme: state.theme,
      layout: state.layout,
      width: Number($("#opt-width").value),
      paper: $("#opt-paper").value || null,
    }),
  });
  state.lastSvg = result.svg;
  $("#card-preview").innerHTML = result.svg;
  $("#btn-svg").disabled = false;
  $$("#png-row button").forEach((b) => (b.disabled = false));
  toast(`卡片完成 ${result.width}×${result.height}`);
}

function svgDataUrl(svg) {
  // btoa can't take multi-byte characters directly.
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
  img.decoding = "sync";
  await new Promise((resolve, reject) => {
    img.onload = resolve;
    img.onerror = () => reject(new Error("SVG 無法轉成圖片"));
    img.src = svgDataUrl(svg);
  });

  const canvas = document.createElement("canvas");
  canvas.width = width * scale;
  canvas.height = height * scale;
  const ctx = canvas.getContext("2d");
  ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
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
    div.append(b, p);
    const copy = document.createElement("button");
    copy.className = "ghost small copy";
    copy.textContent = "複製";
    copy.addEventListener("click", async () => {
      await navigator.clipboard.writeText(text);
      toast("已複製");
    });
    div.append(copy);
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

  toast(result.source === "claude" ? "Claude 產生完成" : "已用內建規則產生（未設定 API key）");
}

// ------------------------------------------------- optional layout designer

function openDesignDialog() {
  const dialog = $("#design-dialog");
  const base = $("#design-base");
  base.replaceChildren();
  for (const layout of state.layouts) {
    const option = document.createElement("option");
    option.value = layout.id;
    option.textContent = layout.name;
    if (layout.id === state.layout) option.selected = true;
    base.append(option);
  }
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

// ------------------------------------------------------------ wiring

function wire() {
  $("#btn-new").addEventListener("click", newEntry);
  $("#btn-save").addEventListener("click", () => save(false));
  $("#entry-date").addEventListener("change", markDirty);
  $("#entry-title").addEventListener("input", markDirty);
  $("#closing").addEventListener("input", markDirty);

  $("#opt-gift").addEventListener("change", (e) => {
    $("#opt-gift-msg").disabled = !e.target.checked;
  });
  $("#btn-design").addEventListener("click", openDesignDialog);

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

  const [health, templates, themes, layouts, styles] = await Promise.all([
    api("/api/health"),
    api("/api/templates"),
    api("/api/themes"),
    api("/api/layouts"),
    api("/api/ai/styles"),
  ]);

  state.templates = templates;
  state.themes = themes;
  state.layouts = layouts;
  state.template = templates[0] ?? null;
  state.theme = state.template?.default_theme ?? "letterpress";
  state.layout = state.template?.default_layout ?? layouts[0]?.id ?? "letter";
  state.aiAvailable = Boolean(health.ai_available);

  // The three things people actually export never touch the API. Only the
  // two optional helpers do, so only those get disabled.
  $("#ai-status").textContent = health.ai_available
    ? `AI 選配功能已啟用（${health.model}）`
    : "未設定 API key — 輸出功能全部照常";

  const styleSelect = $("#opt-style");
  for (const s of styles) {
    const option = document.createElement("option");
    option.value = s.id;
    option.textContent = s.label;
    styleSelect.append(option);
  }
  $("#btn-title").disabled = !state.aiAvailable;
  $("#btn-design").disabled = !state.aiAvailable;
  if (!state.aiAvailable) {
    $("#btn-design").title = "設計新版型需要 ANTHROPIC_API_KEY。內建版型不需要。";
    $("#btn-title").title = "標題建議需要 ANTHROPIC_API_KEY。";
  }

  $("#entry-date").value = today();
  renderTemplatePicker();
  renderLayoutPicker();
  renderThemePicker();
  buildForm();
  await loadEntries();
}

init().catch((err) => toast(`啟動失敗：${err.message}`, true));
