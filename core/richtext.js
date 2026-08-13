// Port of backend/richtext.py — sanitising and parsing the colour-annotated
// rich text the editor produces.
//
// The editor is a `contenteditable` region, so anything could arrive. We accept
// a deliberately tiny subset — enough for "write this sentence in red, that one
// in green", nothing more:
//
//     <b> <strong> <i> <em> <u> <s> <br>
//     <span style="color: #hex">
//     <div> <p>          (treated as line breaks)
//
// Everything else is dropped, attributes included. The same module also converts
// that HTML into flat *runs* — `{text, color, bold, italic}` — which is what the
// SVG card renderer needs, since SVG has no inline markup.
//
// Why a hand-written tokenizer instead of DOMParser: this module has to run
// where there is no DOM (Node, for the tests below; a worker; a future native
// bridge). Safety does not depend on the tokenizer being perfect — the
// sanitizer never re-emits input. Tag names come from a fixed whitelist, colour
// values are re-serialised from a validated hex, and every text node is escaped.
// A mis-tokenised document can therefore come out wrong, but never dangerous.

const INLINE_TAGS = new Set(["b", "strong", "i", "em", "u", "s", "strike", "span"]);
const BLOCK_TAGS = new Set(["div", "p", "li"]);
const VOID_TAGS = new Set(["br"]);

/** Tags whose *contents* must be discarded too, not just the tags themselves —
 *  otherwise pasting a page fragment leaks script bodies into the journal text. */
const DROP_CONTENT_TAGS = new Set([
  "script",
  "style",
  "title",
  "textarea",
  "noscript",
  "iframe",
  "object",
  "embed",
  "template",
  "head",
  "svg",
  "math",
]);

/** Tags whose content the HTML spec reads as raw text, so `<` inside them is
 *  not a tag start. Both are dropped wholesale, but the tokenizer still has to
 *  know where they end. */
const RAWTEXT_TAGS = new Set(["script", "style"]);

const CANONICAL_TAG = { strong: "b", em: "i", strike: "s" };

const HEX_RE = /^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/;
const RGB_RE = /^rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*(?:,[^)]*)?\)$/;
const COLOR_DECL_RE = /(?:^|;)\s*color\s*:\s*([^;]+)/i;

// --------------------------------------------------------------- entities

/** The named references that actually turn up in pasted text. Python's
 *  `html.unescape` knows the full HTML5 table; carrying all 2231 of those here
 *  would cost more than it buys. Anything unlisted is left as literal text,
 *  which is the same thing the browser shows for an unknown reference. */
const NAMED_ENTITIES = {
  amp: "&", lt: "<", gt: ">", quot: '"', apos: "'",
  nbsp: " ", ensp: " ", emsp: " ", thinsp: " ",
  copy: "©", reg: "®", trade: "™", deg: "°",
  hellip: "…", mdash: "—", ndash: "–", minus: "−",
  lsquo: "‘", rsquo: "’", ldquo: "“", rdquo: "”",
  laquo: "«", raquo: "»", bull: "•", middot: "·",
  times: "×", divide: "÷", plusmn: "±",
  sect: "§", para: "¶", dagger: "†",
  euro: "€", pound: "£", yen: "¥", cent: "¢",
  larr: "←", rarr: "→", uarr: "↑", darr: "↓",
  le: "≤", ge: "≥", ne: "≠",
};

const CHARREF_RE = /&(#[0-9]+;?|#[xX][0-9a-fA-F]+;?|[a-zA-Z][a-zA-Z0-9]*;?)/g;

function codepointToString(code) {
  // Mirrors the spec's handling of the references a real document should never
  // contain: NUL, lone surrogates and out-of-range values all become U+FFFD.
  if (code === 0 || code > 0x10ffff || (code >= 0xd800 && code <= 0xdfff)) {
    return "�";
  }
  return String.fromCodePoint(code);
}

/** Decode character references, the way an HTML parser does before handing
 *  text to the application. */
export function unescapeHtml(text) {
  if (!text || !text.includes("&")) return text || "";
  return text.replace(CHARREF_RE, (whole, body) => {
    if (body[0] === "#") {
      const hex = body[1] === "x" || body[1] === "X";
      const digits = body.slice(hex ? 2 : 1).replace(/;$/, "");
      const code = parseInt(digits, hex ? 16 : 10);
      return Number.isNaN(code) ? whole : codepointToString(code);
    }
    const name = body.replace(/;$/, "");
    const hit = NAMED_ENTITIES[name];
    return hit === undefined ? whole : hit;
  });
}

/** The counterpart of Python's `html.escape(s, quote=False)`. */
function escapeText(text) {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

// ------------------------------------------------------------------ colour

/** Return a `#rrggbb` string, or `null` if the value isn't a plain colour. */
export function normalizeColor(value) {
  if (!value) return null;
  const text = String(value).trim();
  if (HEX_RE.test(text)) {
    if (text.length === 4) {
      // #abc -> #aabbcc
      return "#" + [...text.slice(1)].map((ch) => ch + ch).join("").toLowerCase();
    }
    return text.toLowerCase();
  }
  const m = RGB_RE.exec(text);
  if (m) {
    const [r, g, b] = m.slice(1, 4).map((p) => Math.min(255, parseInt(p, 10)));
    const hex = (n) => n.toString(16).padStart(2, "0");
    return `#${hex(r)}${hex(g)}${hex(b)}`;
  }
  return null;
}

function extractColor(style) {
  if (!style) return null;
  const m = COLOR_DECL_RE.exec(style);
  return m ? normalizeColor(m[1]) : null;
}

// --------------------------------------------------------------- tokenizer

const TAG_NAME_RE = /^[a-zA-Z][^\s/>]*/;
const ATTR_RE = /([^\s/>=]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s/>]*)))?/g;

function parseAttrs(source) {
  const attrs = {};
  ATTR_RE.lastIndex = 0;
  let m;
  while ((m = ATTR_RE.exec(source)) !== null) {
    if (m[0] === "") {
      ATTR_RE.lastIndex += 1; // never spin on a zero-width match
      continue;
    }
    const name = m[1].toLowerCase();
    const raw = m[2] ?? m[3] ?? m[4] ?? "";
    // Attribute values are entity-decoded regardless of text handling, so
    // `style="color:&#35;c00"` resolves the same way a browser resolves it.
    if (!(name in attrs)) attrs[name] = unescapeHtml(raw);
  }
  return attrs;
}

/**
 * Walk `html`, handing tokens to `handler`.
 *
 * Deliberately lenient in the same places Python's `html.parser` is: a `<` that
 * does not begin a tag is text, an unterminated tag at the end of input is
 * dropped, and comments/declarations are skipped.
 */
function tokenize(html, handler) {
  let i = 0;
  let text = "";
  const flush = () => {
    if (text) {
      handler.data(unescapeHtml(text));
      text = "";
    }
  };

  while (i < html.length) {
    const lt = html.indexOf("<", i);
    if (lt === -1) {
      text += html.slice(i);
      break;
    }
    text += html.slice(i, lt);
    const rest = html.slice(lt);

    // A "<" that never finds its ">" is not markup — it is someone writing
    // "a < b". Emit the bracket as text and keep scanning from the next
    // character, which is what html.parser does at end of input.
    const asText = () => {
      text += "<";
      i = lt + 1;
    };

    if (rest.startsWith("<!--")) {
      const end = html.indexOf("-->", lt + 4);
      if (end === -1) asText();
      else i = end + 3;
      continue;
    }
    if (rest.startsWith("<!") || rest.startsWith("<?")) {
      const end = html.indexOf(">", lt + 2);
      if (end === -1) asText();
      else i = end + 1;
      continue;
    }
    if (rest.startsWith("</")) {
      const end = html.indexOf(">", lt + 2);
      if (end === -1) {
        asText();
        continue;
      }
      const name = TAG_NAME_RE.exec(html.slice(lt + 2, end));
      if (name) {
        flush();
        handler.end(name[0].toLowerCase());
      }
      i = end + 1;
      continue;
    }

    const name = TAG_NAME_RE.exec(rest.slice(1));
    if (!name) {
      // A bare "<" — text, not markup.
      asText();
      continue;
    }
    const end = findTagEnd(html, lt + 1 + name[0].length);
    if (end === -1) {
      asText();
      continue;
    }
    const tag = name[0].toLowerCase();
    const inner = html.slice(lt + 1 + name[0].length, end);
    const selfClosing = inner.trimEnd().endsWith("/");
    const attrs = parseAttrs(selfClosing ? inner.slice(0, inner.lastIndexOf("/")) : inner);

    flush();
    if (selfClosing) handler.startend(tag, attrs);
    else handler.start(tag, attrs);
    i = end + 1;

    if (!selfClosing && RAWTEXT_TAGS.has(tag)) {
      // Inside <script>/<style> the spec reads raw text, so a "<" in there is
      // not a tag start. Skip straight to the matching close.
      const close = new RegExp(`</${tag}\\s*>`, "i");
      const tail = html.slice(i);
      const hit = close.exec(tail);
      if (hit) {
        handler.data(tail.slice(0, hit.index));
        handler.end(tag);
        i += hit.index + hit[0].length;
      } else {
        handler.data(tail);
        i = html.length;
      }
    }
  }
  flush();
}

/** Index of the `>` that closes a tag, skipping any inside quoted values. */
function findTagEnd(html, from) {
  let quote = null;
  for (let i = from; i < html.length; i += 1) {
    const ch = html[i];
    if (quote) {
      if (ch === quote) quote = null;
    } else if (ch === '"' || ch === "'") {
      quote = ch;
    } else if (ch === ">") {
      return i;
    }
  }
  return -1;
}

// --------------------------------------------------------------- sanitize

class Sanitizer {
  constructor() {
    this.out = [];
    this.open = [];
    this.muted = 0;
  }

  start(tag, attrs) {
    if (DROP_CONTENT_TAGS.has(tag)) {
      this.muted += 1;
      return;
    }
    if (this.muted) return;
    if (VOID_TAGS.has(tag)) {
      this.out.push("<br>");
      return;
    }
    if (BLOCK_TAGS.has(tag)) {
      // Blocks become line breaks; the first one shouldn't add a leading
      // blank line.
      if (this.out.length && this.out[this.out.length - 1] !== "<br>") {
        this.out.push("<br>");
      }
      this.open.push(""); // placeholder, nothing to close
      return;
    }
    if (!INLINE_TAGS.has(tag)) return;
    if (tag === "span") {
      const color = extractColor(attrs.style);
      if (color === null) {
        this.open.push("");
        return;
      }
      this.out.push(`<span style="color:${color}">`);
      this.open.push("span");
      return;
    }
    const canonical = CANONICAL_TAG[tag] ?? tag;
    this.out.push(`<${canonical}>`);
    this.open.push(canonical);
  }

  end(tag) {
    if (DROP_CONTENT_TAGS.has(tag)) {
      this.muted = Math.max(0, this.muted - 1);
      return;
    }
    if (this.muted) return;
    if (VOID_TAGS.has(tag)) return;
    if (!INLINE_TAGS.has(tag) && !BLOCK_TAGS.has(tag)) return;
    if (!this.open.length) return;
    const opened = this.open.pop();
    if (opened) this.out.push(`</${opened}>`);
  }

  startend(tag) {
    if (!this.muted && VOID_TAGS.has(tag)) this.out.push("<br>");
  }

  data(text) {
    if (this.muted) return;
    this.out.push(escapeText(text));
  }

  result() {
    // Close anything the input left dangling.
    const tail = [...this.open].reverse().filter(Boolean).map((t) => `</${t}>`).join("");
    return (this.out.join("") + tail)
      .replace(/^(?:<br>)+/, "")
      .replace(/(?:<br>)+$/, "");
  }
}

/** Reduce arbitrary HTML to the whitelisted subset the journal stores. */
export function sanitize(raw) {
  if (!raw) return "";
  const parser = new Sanitizer();
  tokenize(String(raw), parser);
  return parser.result();
}

// --------------------------------------------------------------------------
// HTML -> runs
// --------------------------------------------------------------------------

/** One stretch of text sharing a colour and weight. SVG has no inline markup,
 *  so the card renderer can only draw a document once it is flattened to these. */
export class Run {
  constructor(text, color = null, bold = false, italic = false) {
    this.text = text;
    this.color = color;
    this.bold = bold;
    this.italic = italic;
  }
}

class RunParser {
  constructor(defaultColor) {
    this.runs = [];
    this.colors = [];
    this.bold = 0;
    this.italic = 0;
    this.default = defaultColor;
  }

  get color() {
    return this.colors.length ? this.colors[this.colors.length - 1] : this.default;
  }

  push(text) {
    this.runs.push(new Run(text, this.color, Boolean(this.bold), Boolean(this.italic)));
  }

  start(tag, attrs) {
    if (tag === "br") {
      this.push("\n");
    } else if (tag === "span") {
      const color = extractColor(attrs.style);
      this.colors.push(color || this.color || "");
    } else if (tag === "b" || tag === "strong") {
      this.bold += 1;
    } else if (tag === "i" || tag === "em") {
      this.italic += 1;
    }
  }

  startend(tag) {
    if (tag === "br") this.push("\n");
  }

  end(tag) {
    if (tag === "span" && this.colors.length) this.colors.pop();
    else if (tag === "b" || tag === "strong") this.bold = Math.max(0, this.bold - 1);
    else if (tag === "i" || tag === "em") this.italic = Math.max(0, this.italic - 1);
  }

  data(text) {
    if (text) this.push(text);
  }
}

/** Flatten sanitized rich text into colour/weight runs for SVG output. */
export function toRuns(raw, defaultColor = null) {
  if (!raw) return [];
  const parser = new RunParser(defaultColor);
  tokenize(sanitize(raw), parser);

  const merged = [];
  for (const run of parser.runs) {
    const last = merged[merged.length - 1];
    if (
      last &&
      last.color === run.color &&
      last.bold === run.bold &&
      last.italic === run.italic &&
      !last.text.includes("\n") &&
      !run.text.includes("\n")
    ) {
      last.text += run.text;
    } else {
      merged.push(run);
    }
  }
  return merged;
}

/** Plain text, used for AI prompts and search. */
export function toPlain(raw) {
  return toRuns(raw)
    .map((r) => r.text)
    .join("")
    .trim();
}
