// Partial port of backend/render/artifact_html.py.
//
// What is here: `runsToHtml`, the one custom filter the shipped layouts depend
// on. What is *not* here: the template engine binding.
//
// The layouts under `content/layouts/` are Jinja2 templates. Nunjucks reads
// almost the same syntax, so the plan is to hand those same `.j2` files to
// Nunjucks rather than maintain a second set — see docs/roadmap.md. That step
// needs a dependency and a build step, which this repo does not have yet, so it
// is deliberately left undone rather than half-done.
//
// The filter itself is pure and testable today, and it is the piece most likely
// to drift, so it is ported now.

/** Escape for HTML text content — the counterpart of Python's `html.escape`. */
export function escapeHtml(text, quote = true) {
  let out = String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  if (quote) out = out.replace(/"/g, "&quot;").replace(/'/g, "&#x27;");
  return out;
}

/**
 * Render colour runs as inline markup.
 *
 * The writer's colour goes into an `--ink` custom property as well as `color`,
 * so a layout's stylesheet can lighten every hand-picked colour in dark mode
 * without knowing in advance which colours were used.
 */
export function runsToHtml(runs) {
  const out = [];
  for (const run of runs) {
    // Python escapes with quote=True here, which also turns ' into &#x27;.
    let text = escapeHtml(run.text).replace(/ {2}/g, " &nbsp;");
    if (!text) continue;
    if (run.bold) text = `<strong>${text}</strong>`;
    if (run.italic) text = `<em>${text}</em>`;
    if (run.color) {
      const ink = escapeHtml(run.color);
      text = `<span style="--ink:${ink};color:var(--ink)">${text}</span>`;
    }
    out.push(text);
  }
  return out.join("") || "&nbsp;";
}
