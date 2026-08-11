// Port of backend/render/document.py — normalise an entry + its question set
// into the one structure every renderer consumes.
//
// Answer values are stored loosely (whatever kind the field is), so this module
// is the single place that knows how to read each kind. The page generator and
// the card generator both consume `RenderedDoc`, which keeps them from drifting
// apart.
//
// Property names are snake_case throughout because `content/layouts/*.j2` reads
// them (`doc.date_display`, `f.is_empty`, `doc.has_closing`) and those layout
// files are shared verbatim with the Python renderer. See core/README.md.

import { Run, toPlain, toRuns } from "./richtext.js";

export const WEEKDAYS_ZH = ["一", "二", "三", "四", "五", "六", "日"];

export const FieldKind = Object.freeze({
  CHOICE: "choice",
  MULTI_CHOICE: "multi_choice",
  SCALE: "scale",
  SHORT_TEXT: "short_text",
  FILL: "fill",
  TEXT: "text",
  LIST: "list",
});

/** The closing block's ink. Fixed rather than themed: the writer's own pen
 *  colours are chosen against pale paper, and so is this. */
const CLOSING_INK = "#22252a";

const DEFAULT_SECTION_COLOR = "#2f3437";
const DEFAULT_CLOSING_LABEL = "給主的話";

/** Python's `str.isspace()`, spelled out as codepoints. JS `\s` is close but
 *  not identical — it misses the C1 separators (U+001C–U+001F, U+0085) and
 *  counts U+FEFF, which Python does not. The word count has to agree across the
 *  two renderers, or the same entry reports two different lengths depending on
 *  which one drew it. */
const PY_SPACE = new RegExp(
  "^[\t\n\v\f\r\u001c-\u001f \u0085\u00a0\u1680\u2000-\u200a" +
    "\u2028\u2029\u202f\u205f\u3000]$",
  "u"
);

export class Chip {
  constructor(label, selected) {
    this.label = label;
    this.selected = selected;
  }
}

export class RenderedField {
  constructor({ id, label, kind, color }) {
    this.id = id;
    this.label = label;
    this.kind = kind;
    this.color = color;
    this.chips = [];
    /** Each entry is one visual line, already flattened into colour runs. */
    this.lines = [];
    /** `true` for LIST fields, so renderers can number them. */
    this.numbered = false;
    this.plain = "";
  }

  /**
   * Was this question left unanswered?
   *
   * A tick question always carries its full row of chips — that is how the
   * unpicked options get drawn next to the picked one — so "has chips" says
   * nothing about whether it was answered. Only a selection does.
   */
  get is_empty() {
    if (this.chips.length) return !this.chips.some((c) => c.selected);
    return !this.lines.some((line) => line.some((r) => r.text.trim()));
  }
}

export class RenderedSection {
  constructor({ id, title, color, icon }) {
    this.id = id;
    this.title = title;
    this.color = color;
    this.icon = icon;
    this.fields = [];
  }

  get is_empty() {
    return this.fields.every((f) => f.is_empty);
  }
}

export class RenderedDoc {
  constructor(props) {
    Object.assign(this, props);
  }

  get has_closing() {
    return this.closing_lines.some((line) => line.some((r) => r.text.trim()));
  }

  /** A compact text digest — this is what gets sent to Claude. */
  to_plain_text() {
    const parts = [`${this.date_display}（週${this.weekday}）`];
    if (this.title) parts.push(this.title);
    for (const section of this.sections) {
      if (section.is_empty) continue;
      parts.push(`\n## ${section.title}`);
      for (const f of section.fields) {
        if (f.is_empty) continue;
        if (f.chips.length) {
          const picked = f.chips.filter((c) => c.selected).map((c) => c.label).join("、");
          parts.push(`- ${f.label}：${picked}`);
        } else {
          parts.push(`- ${f.label}：`);
          for (const line of f.lines) {
            const text = line.map((r) => r.text).join("").trim();
            if (text) parts.push(`    ${text}`);
          }
        }
      }
    }
    if (this.has_closing) {
      parts.push(`\n## ${this.closing_label}`);
      for (const line of this.closing_lines) {
        const text = line.map((r) => r.text).join("").trim();
        if (text) parts.push(text);
      }
    }
    return parts.join("\n");
  }
}

/** Split a run list on newlines into per-line run lists. */
function splitLines(runs) {
  const lines = [[]];
  for (const run of runs) {
    if (!run.text.includes("\n")) {
      lines[lines.length - 1].push(run);
      continue;
    }
    const chunks = run.text.split("\n");
    chunks.forEach((chunk, i) => {
      if (i) lines.push([]);
      if (chunk) {
        lines[lines.length - 1].push(new Run(chunk, run.color, run.bold, run.italic));
      }
    });
  }
  const kept = lines.filter((ln) => ln.length);
  return kept.length ? kept : [[]];
}

/** Weave `values` into `pattern`'s `{}` holes as coloured, bold runs. */
function fillRuns(pattern, values, color) {
  const runs = [];
  const parts = pattern.split("{}");
  parts.forEach((part, i) => {
    if (part) runs.push(new Run(part));
    if (i < parts.length - 1) {
      const value = i < values.length ? values[i] : "";
      runs.push(new Run(value || "＿＿＿＿", color, Boolean(value)));
    }
  });
  return runs;
}

function renderField(tf, rawValue, color) {
  const rendered = new RenderedField({
    id: tf.id,
    label: tf.label,
    kind: tf.kind ?? FieldKind.TEXT,
    color,
  });
  const options = tf.options ?? [];

  if (rendered.kind === FieldKind.CHOICE || rendered.kind === FieldKind.SCALE) {
    const picked = typeof rawValue === "string" ? rawValue : "";
    rendered.chips = options.map((o) => new Chip(o.label, o.id === picked));
    rendered.plain = options.find((o) => o.id === picked)?.label ?? "";
  } else if (rendered.kind === FieldKind.MULTI_CHOICE) {
    const pickedIds = new Set(Array.isArray(rawValue) ? rawValue : []);
    rendered.chips = options.map((o) => new Chip(o.label, pickedIds.has(o.id)));
    rendered.plain = options
      .filter((o) => pickedIds.has(o.id))
      .map((o) => o.label)
      .join("、");
  } else if (rendered.kind === FieldKind.SHORT_TEXT) {
    const text = typeof rawValue === "string" ? rawValue : "";
    rendered.lines = text ? [[new Run(text, color)]] : [];
    rendered.plain = text;
  } else if (rendered.kind === FieldKind.FILL) {
    const values = Array.isArray(rawValue) ? rawValue.map((v) => String(v)) : [];
    const runs = fillRuns(tf.pattern || "{}", values, color);
    const answered = values.some(Boolean);
    rendered.lines = answered ? splitLines(runs) : [];
    rendered.plain = answered ? runs.map((r) => r.text).join("") : "";
  } else if (rendered.kind === FieldKind.LIST) {
    const items = Array.isArray(rawValue) ? rawValue : [];
    rendered.numbered = true;
    for (const item of items) {
      const runs = toRuns(String(item), color);
      if (runs.some((r) => r.text.trim())) rendered.lines.push(runs);
    }
    rendered.plain = rendered.lines
      .map((line) => line.map((r) => r.text).join(""))
      .join("\n");
  } else {
    // TEXT
    const raw = String(rawValue ?? "");
    const runs = toRuns(raw, color);
    rendered.lines = splitLines(runs).filter((ln) => ln.some((r) => r.text.trim()));
    rendered.plain = toPlain(raw);
  }

  return rendered;
}

/**
 * Read an ISO `YYYY-MM-DD` string as a calendar date.
 *
 * Deliberately not `new Date(str)`: that parses a bare date as UTC midnight, so
 * anywhere west of Greenwich the local getters hand back the previous day and
 * the entry is dated wrong. Splitting the string keeps the date the writer
 * picked, whatever timezone they are in.
 */
export function parseISODate(value) {
  if (value instanceof Date) {
    return {
      year: value.getFullYear(),
      month: value.getMonth() + 1,
      day: value.getDate(),
    };
  }
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(value ?? ""));
  if (!m) throw new Error(`不是有效的日期：${value}`);
  return { year: Number(m[1]), month: Number(m[2]), day: Number(m[3]) };
}

/** Weekday index the Python way: Monday is 0, Sunday is 6. */
export function weekdayIndex({ year, month, day }) {
  const jsDay = new Date(Date.UTC(year, month - 1, day)).getUTCDay(); // Sunday = 0
  return (jsDay + 6) % 7;
}

const pad2 = (n) => String(n).padStart(2, "0");

export function buildDocument(entry, template, { dropEmpty = true } = {}) {
  const sections = [];
  const palette = [];
  const answers = entry.answers ?? {};
  const fieldColors = entry.field_colors ?? {};

  for (const ts of template.sections ?? []) {
    const sectionColor = ts.color || DEFAULT_SECTION_COLOR;
    const rs = new RenderedSection({
      id: ts.id,
      title: ts.title,
      color: sectionColor,
      icon: ts.icon ?? null,
    });
    for (const tf of ts.fields ?? []) {
      const color = fieldColors[tf.id] || tf.color || sectionColor;
      const rf = renderField(tf, answers[tf.id], color);
      if (dropEmpty && rf.is_empty) continue;
      rs.fields.push(rf);
      if (!palette.includes(color)) palette.push(color);
    }
    if (!(dropEmpty && rs.is_empty)) sections.push(rs);
    if (!palette.includes(sectionColor)) palette.push(sectionColor);
  }

  const closingRuns = toRuns(entry.closing ?? "", CLOSING_INK);
  const closingLines = splitLines(closingRuns).filter((ln) =>
    ln.some((r) => r.text.trim())
  );

  const body =
    sections.flatMap((s) => s.fields.map((f) => f.plain)).join("\n") +
    "\n" +
    closingLines.map((ln) => ln.map((r) => r.text).join("")).join("\n");

  const d = parseISODate(entry.entry_date);

  return new RenderedDoc({
    entry_id: entry.id ?? null,
    title: (entry.title ?? "").trim(),
    entry_date: `${d.year}-${pad2(d.month)}-${pad2(d.day)}`,
    date_display: `${d.year}．${pad2(d.month)}．${pad2(d.day)}`,
    weekday: WEEKDAYS_ZH[weekdayIndex(d)],
    template_name: template.name,
    theme: entry.theme,
    layout: entry.layout,
    sections,
    closing_lines: closingLines,
    word_count: [...body].filter((ch) => !PY_SPACE.test(ch)).length,
    palette,
    closing_label: template.closing_label || DEFAULT_CLOSING_LABEL,
  });
}
