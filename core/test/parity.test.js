// Does the JavaScript core still agree with the Python renderer?
//
// The expected values in fixtures/parity.json were recorded from `backend/` by
// core/test/tools/dump_parity.py. Nothing here is hand-written, so a passing
// run means the two implementations genuinely produce the same journal — not
// that someone wrote down what they hoped it produced.
//
// When this fails after a change to backend/, that is the point: regenerate the
// fixture, read the diff, and decide whether core/ has to follow or whether the
// change was a bug.

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";
import test from "node:test";

import { normalizeColor, sanitize, toPlain, toRuns } from "../richtext.js";
import { runsToHtml } from "../artifact_html.js";
import { buildDocument, WEEKDAYS_ZH, weekdayIndex, parseISODate } from "../document.js";
import { THEMES } from "../themes.js";

const fixture = JSON.parse(
  readFileSync(fileURLToPath(new URL("./fixtures/parity.json", import.meta.url)), "utf8")
);

/** Runs carry class identity in JS and dataclass identity in Python; compare
 *  the values, not the wrappers. */
const runJson = (r) => ({ text: r.text, color: r.color, bold: r.bold, italic: r.italic });
const linesJson = (lines) => lines.map((line) => line.map(runJson));

/** Mirror of `doc_json` in dump_parity.py. */
function docJson(doc) {
  return {
    entry_id: doc.entry_id,
    title: doc.title,
    entry_date: doc.entry_date,
    date_display: doc.date_display,
    weekday: doc.weekday,
    template_name: doc.template_name,
    theme: doc.theme,
    layout: doc.layout,
    word_count: doc.word_count,
    palette: doc.palette,
    closing_label: doc.closing_label,
    has_closing: doc.has_closing,
    closing_lines: linesJson(doc.closing_lines),
    plain_text: doc.to_plain_text(),
    sections: doc.sections.map((s) => ({
      id: s.id,
      title: s.title,
      color: s.color,
      icon: s.icon,
      is_empty: s.is_empty,
      fields: s.fields.map((f) => ({
        id: f.id,
        label: f.label,
        kind: f.kind,
        color: f.color,
        numbered: f.numbered,
        plain: f.plain,
        is_empty: f.is_empty,
        chips: f.chips.map((c) => ({ label: c.label, selected: c.selected })),
        lines: linesJson(f.lines),
      })),
    })),
  };
}

/** One `test()` per case, so a failure names the exact input rather than
 *  reporting "40 cases, one of them broke". */
function eachCase(group, run) {
  for (const [i, c] of fixture[group].entries()) {
    test(`${group} #${i}: ${JSON.stringify(c.raw)}`, () => run(c));
  }
}

test("the fixture was generated, not hand-written", () => {
  assert.match(fixture._note, /dump_parity\.py/);
});

// ------------------------------------------------------------------ richtext

eachCase("sanitize", (c) => assert.equal(sanitize(c.raw), c.out));

eachCase("to_runs", (c) =>
  assert.deepEqual(toRuns(c.raw, fixture.default_color).map(runJson), c.runs)
);

eachCase("to_runs_no_default", (c) =>
  assert.deepEqual(toRuns(c.raw).map(runJson), c.runs)
);

eachCase("to_plain", (c) => assert.equal(toPlain(c.raw), c.out));

eachCase("runs_to_html", (c) =>
  assert.equal(runsToHtml(toRuns(c.raw, fixture.default_color)), c.out)
);

eachCase("normalize_color", (c) => assert.equal(normalizeColor(c.raw), c.out));

test("sanitize is idempotent", () => {
  for (const c of fixture.sanitize) {
    assert.equal(sanitize(c.out), c.out, `re-sanitizing changed ${JSON.stringify(c.out)}`);
  }
});

test("sanitize never lets a raw angle bracket through", () => {
  const dangerous = [
    "<img src=x onerror=alert(1)>",
    "<a href='javascript:alert(1)'>x</a>",
    "<span style=\"color:#c00\" onclick=\"steal()\">x</span>",
    "<script>document.cookie</script>",
    "<iframe src='//evil'></iframe>",
    "<svg/onload=alert(1)>",
    "<b onmouseover=alert(1)>hi</b>",
  ];
  for (const raw of dangerous) {
    const out = sanitize(raw);
    // Whatever survives may only be our own whitelist markup.
    const stripped = out.replace(/<\/?(?:b|i|u|s|br)>|<span style="color:#[0-9a-f]{6}">|<\/span>/g, "");
    assert.ok(
      !stripped.includes("<") && !stripped.includes(">"),
      `${raw} -> ${out}`
    );
    assert.ok(!/on[a-z]+=/i.test(out), `event handler survived: ${out}`);
    assert.ok(!/javascript:/i.test(out), `javascript: URL survived: ${out}`);
  }
});

// -------------------------------------------------------------------- themes

test("themes match the Python token sets exactly", () => {
  assert.deepEqual(Object.keys(THEMES), Object.keys(fixture.themes));
  for (const [id, expected] of Object.entries(fixture.themes)) {
    assert.deepEqual({ ...THEMES[id] }, expected, `theme ${id}`);
  }
});

// ------------------------------------------------------------------ document

for (const c of fixture.documents) {
  test(`buildDocument: ${c.label}`, () => {
    const doc = buildDocument(c.entry, fixture.template);
    assert.deepEqual(docJson(doc), c.doc);
  });

  test(`buildDocument (dropEmpty off): ${c.label}`, () => {
    const doc = buildDocument(c.entry, fixture.template, { dropEmpty: false });
    assert.deepEqual(docJson(doc), c.doc_keep_empty);
  });
}

test("weekday mapping matches Python's Monday-is-0", () => {
  for (const c of fixture.weekdays) {
    assert.equal(
      WEEKDAYS_ZH[weekdayIndex(parseISODate(c.date))],
      c.weekday,
      c.date
    );
  }
});
