// Tests for the hand-written tokenizer's own edges.
//
// parity.test.js already pins the behaviour that has to match Python. What is
// left is what only a hand-written parser can get wrong: spinning forever,
// mis-reading a quoted attribute, or letting something through that the
// whitelist should have stopped.

import assert from "node:assert/strict";
import test from "node:test";

import { normalizeColor, sanitize, toPlain, toRuns, unescapeHtml } from "../richtext.js";

test("empty and missing input give an empty string, never a throw", () => {
  for (const bad of ["", null, undefined, 0, false, NaN]) {
    assert.equal(sanitize(bad), "");
    assert.deepEqual(toRuns(bad), []);
    assert.equal(toPlain(bad), "");
  }
});

test("a '>' inside a quoted attribute does not end the tag", () => {
  assert.equal(
    sanitize('<span style="color:#c00" title="a > b">紅</span>'),
    '<span style="color:#cc0000">紅</span>'
  );
  // The same, with the quote style swapped.
  assert.equal(
    sanitize("<span style='color:#c00' title='a > b'>紅</span>"),
    '<span style="color:#cc0000">紅</span>'
  );
});

test("an attribute with no value does not swallow the next one", () => {
  assert.equal(
    sanitize('<span hidden style="color:#0a0">綠</span>'),
    '<span style="color:#00aa00">綠</span>'
  );
});

test("entity references in a style attribute are decoded", () => {
  assert.equal(
    sanitize('<span style="color:&#35;c00">紅</span>'),
    '<span style="color:#cc0000">紅</span>'
  );
});

test("unescapeHtml handles numeric, hex and named references", () => {
  assert.equal(unescapeHtml("&#20013;&#x6587;"), "中文");
  assert.equal(unescapeHtml("&amp;&lt;&gt;&quot;&apos;"), "&<>\"'");
  assert.equal(unescapeHtml("&hellip;&mdash;"), "…—");
  assert.equal(unescapeHtml("&notareference;"), "&notareference;");
  assert.equal(unescapeHtml("no entities here"), "no entities here");
});

test("out-of-range character references become U+FFFD, not a crash", () => {
  assert.equal(unescapeHtml("&#0;"), "�");
  assert.equal(unescapeHtml("&#xD800;"), "�"); // lone surrogate
  assert.equal(unescapeHtml("&#99999999;"), "�");
});

test("script and style bodies are dropped, contents and all", () => {
  assert.equal(sanitize("<script>if (a<b) { c(); }</script>留下"), "留下");
  assert.equal(sanitize("<style>p{content:'<'}</style>留下"), "留下");
});

test("an unterminated tag is text, not a truncation", () => {
  // The tail must survive — silently dropping the rest of a sentence is the
  // worst possible failure mode for a journal.
  assert.equal(sanitize("a<b"), "a&lt;b");
  assert.equal(sanitize("2 < 3 and 4 > 3"), "2 &lt; 3 and 4 &gt; 3");
  assert.equal(sanitize("結尾<"), "結尾&lt;");
  assert.equal(sanitize("a<!-- 沒關的註解"), "a&lt;!-- 沒關的註解");
});

test("pathological input terminates", () => {
  const cases = [
    "<".repeat(5000),
    "<b ".repeat(2000),
    '<span style="'.repeat(1000),
    "<".repeat(1000) + ">".repeat(1000),
    "<span " + "a".repeat(20000) + ">x</span>",
    "&".repeat(5000),
    "&#".repeat(5000),
  ];
  for (const raw of cases) {
    const started = Date.now();
    sanitize(raw);
    assert.ok(Date.now() - started < 2000, `slow on ${raw.slice(0, 20)}…`);
  }
});

test("deeply nested markup does not blow the stack", () => {
  const depth = 5000;
  const raw = "<b>".repeat(depth) + "深" + "</b>".repeat(depth);
  const runs = toRuns(raw);
  assert.equal(runs.length, 1);
  assert.equal(runs[0].text, "深");
  assert.equal(runs[0].bold, true);
});

test("colour normalisation is case- and space-insensitive", () => {
  assert.equal(normalizeColor("  #ABC  "), "#aabbcc");
  assert.equal(normalizeColor("RGB(1, 2, 3)"), null); // Python's regex is lowercase-only
  assert.equal(normalizeColor("rgb(1, 2, 3)"), "#010203");
  assert.equal(normalizeColor("rgb(999,0,0)"), "#ff0000");
});

test("runs merge only when colour and weight both match", () => {
  const runs = toRuns('<span style="color:#c00">紅</span><span style="color:#c00">還是紅</span>');
  assert.equal(runs.length, 1);
  assert.equal(runs[0].text, "紅還是紅");

  const split = toRuns('<span style="color:#c00">紅</span><b>粗</b>');
  assert.equal(split.length, 2);
});

test("a newline never merges into a neighbouring run", () => {
  // The card renderer draws one line at a time; a merged newline would put two
  // visual lines into one SVG text element.
  const runs = toRuns("一<br>二");
  assert.deepEqual(runs.map((r) => r.text), ["一", "\n", "二"]);
});
