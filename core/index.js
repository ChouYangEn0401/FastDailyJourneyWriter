// The single entry point for the shared JavaScript output core.
//
// Import from here, not from the individual files — it keeps the surface small
// enough to see at a glance which pieces have been ported.

export { normalizeColor, Run, sanitize, toPlain, toRuns, unescapeHtml } from "./richtext.js";
export { DEFAULT_THEME, getTheme, themeSummaries, THEMES } from "./themes.js";
export {
  buildDocument,
  Chip,
  FieldKind,
  parseISODate,
  RenderedDoc,
  RenderedField,
  RenderedSection,
  weekdayIndex,
  WEEKDAYS_ZH,
} from "./document.js";
export { escapeHtml, runsToHtml } from "./artifact_html.js";
