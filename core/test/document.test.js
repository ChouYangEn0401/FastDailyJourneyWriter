// Tests for the things the parity fixture cannot reach.
//
// parity.test.js proves core/ agrees with backend/ on the same inputs. It runs
// in one process, in one timezone, on well-formed data. This file covers what
// is left: the timezone trap that only exists in JavaScript, and the malformed
// input a real editor will eventually hand over.

import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";
import test from "node:test";

import { buildDocument, parseISODate, weekdayIndex, WEEKDAYS_ZH } from "../document.js";

const DOCUMENT_URL = new URL("../document.js", import.meta.url).href;

const TEMPLATE = {
  id: "t",
  name: "測試",
  closing_label: "給主的話",
  sections: [
    { id: "s", title: "段落", color: "#b5623c", fields: [{ id: "a", label: "問題", kind: "text" }] },
  ],
};

const entry = (over = {}) => ({
  id: 1,
  entry_date: "2026-08-11",
  title: "",
  template_id: "t",
  theme: "letterpress",
  layout: "letter",
  answers: {},
  closing: "",
  field_colors: {},
  ...over,
});

// ------------------------------------------------------------------ dates

test("parseISODate keeps the calendar date, not a UTC instant", () => {
  assert.deepEqual(parseISODate("2026-08-11"), { year: 2026, month: 8, day: 11 });
  assert.deepEqual(parseISODate("2026-08-11T23:00:00"), { year: 2026, month: 8, day: 11 });
  assert.deepEqual(parseISODate(new Date(2026, 7, 11)), { year: 2026, month: 8, day: 11 });
});

test("parseISODate refuses anything it cannot read", () => {
  for (const bad of ["", null, undefined, "not a date", "11/08/2026", "2026-8-1"]) {
    assert.throws(() => parseISODate(bad), /日期/, `accepted ${JSON.stringify(bad)}`);
  }
});

/**
 * The bug this guards against: `new Date("2026-08-11")` is UTC midnight, so
 * reading it back with local getters returns the 10th anywhere west of
 * Greenwich. A journal that renames yesterday's entry is not a small bug.
 *
 * Runs in child processes because TZ has to be set before the process starts.
 */
test("the rendered date does not move with the timezone", () => {
  const script = `
    import { buildDocument } from ${JSON.stringify(DOCUMENT_URL)};
    const doc = buildDocument(
      { id: 1, entry_date: "2026-08-11", title: "", theme: "letterpress",
        layout: "letter", answers: {}, closing: "", field_colors: {} },
      { id: "t", name: "測試", sections: [] }
    );
    process.stdout.write(JSON.stringify({
      offset: new Date().getTimezoneOffset(),
      display: doc.date_display,
      weekday: doc.weekday,
      date: doc.entry_date,
    }));
  `;

  const run = (tz) =>
    JSON.parse(
      execFileSync(process.execPath, ["--input-type=module", "-e", script], {
        env: { ...process.env, TZ: tz },
        encoding: "utf8",
      })
    );

  const east = run("Pacific/Kiritimati"); // UTC+14
  const west = run("Pacific/Niue"); //       UTC-11

  if (east.offset === west.offset) {
    // Some platforms ignore TZ. Say so rather than passing on a test that
    // never actually exercised anything.
    test.skip("this platform does not honour TZ for child processes");
    return;
  }

  for (const result of [east, west]) {
    assert.equal(result.display, "2026．08．11");
    assert.equal(result.date, "2026-08-11");
    assert.equal(result.weekday, "二"); // 2026-08-11 is a Tuesday
  }
});

test("weekdayIndex is Monday-is-0 across a whole week", () => {
  const week = ["10", "11", "12", "13", "14", "15", "16"].map((d) =>
    WEEKDAYS_ZH[weekdayIndex(parseISODate(`2026-08-${d}`))]
  );
  assert.deepEqual(week, ["一", "二", "三", "四", "五", "六", "日"]);
});

// --------------------------------------------------------- malformed input

test("a template with no sections still renders", () => {
  const doc = buildDocument(entry(), { id: "t", name: "空的" });
  assert.deepEqual(doc.sections, []);
  assert.equal(doc.word_count, 0);
  assert.equal(doc.has_closing, false);
});

test("missing answers, colours and titles fall back instead of throwing", () => {
  const doc = buildDocument(
    { id: 2, entry_date: "2026-08-11", template_id: "t" },
    TEMPLATE
  );
  assert.equal(doc.title, "");
  assert.equal(doc.closing_label, "給主的話");
  assert.deepEqual(doc.sections, []);
});

test("a section with no colour gets the documented default", () => {
  const doc = buildDocument(
    entry({ answers: { a: "字" } }),
    { id: "t", name: "n", sections: [{ id: "s", title: "t", fields: [{ id: "a", label: "l" }] }] }
  );
  assert.equal(doc.sections[0].color, "#2f3437");
  assert.equal(doc.sections[0].fields[0].color, "#2f3437");
});

test("an answer of the wrong shape is ignored, not crashed on", () => {
  const doc = buildDocument(
    entry({ answers: { a: { unexpected: true } } }),
    TEMPLATE
  );
  // Object stringifies to "[object Object]" — the point is that it survives.
  assert.equal(doc.sections.length, 1);
});

// ------------------------------------------------------------- word count

test("word count counts CJK characters and skips every kind of space", () => {
  const doc = buildDocument(
    entry({ closing: "今天　很好  \n真的" }), // ideographic + nbsp + newline
    { id: "t", name: "n", sections: [] }
  );
  assert.equal(doc.word_count, 6); // 今天很好真的 — the three kinds of space drop out
});

test("word count treats an emoji as one character", () => {
  const doc = buildDocument(entry({ closing: "🙏" }), { id: "t", name: "n", sections: [] });
  assert.equal(doc.word_count, 1);
});
