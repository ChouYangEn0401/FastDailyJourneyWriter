"""Question sets, the untouched-default upgrade, and the command line.

    python -m unittest                          (from the repo root; no extra packages)

Every journal entry used here is invented. Nothing touches your own data/:
each test points JOURNAL_DATA_DIR at a fresh temporary folder.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# backend.config reads this on first import: never let a test see the real journal.
os.environ["JOURNAL_DATA_DIR"] = tempfile.mkdtemp(prefix="journal-test-")
sys.path.insert(0, str(ROOT))

from backend.models import FieldKind, JournalTemplate  # noqa: E402

TEMPLATES = sorted((ROOT / "content" / "templates").glob("*.json"))
DAY = "2026-11-02"


def run(data_dir: str, *args: str, stdin: bytes = b"", encoding: str = "utf-8") -> subprocess.CompletedProcess:
    """The command line as a separate process; ``encoding`` is what the console would be."""
    env = {**os.environ, "PYTHONIOENCODING": encoding, "PYTHONUTF8": "0"}
    return subprocess.run(
        [sys.executable, "-m", "backend.cli", *args, f"--data-dir={data_dir}"],
        cwd=ROOT, input=stdin, capture_output=True, env=env, timeout=60,
    )


def cli(data_dir: str, *args: str, stdin: str | None = None, encoding: str = "utf-8") -> tuple[int, dict]:
    proc = run(data_dir, *args, "--json", stdin=(stdin or "").encode("utf-8"), encoding=encoding)
    lines = [ln for ln in proc.stdout.decode("utf-8").splitlines() if ln.strip()]
    return proc.returncode, json.loads(lines[-1])


def sub_parsers() -> dict:
    """{"templates": parser, "entry put": parser, …} — every verb the command line has."""
    from backend.cli import _parser

    def walk(parser, prefix=""):
        found = {}
        for action in parser._actions:
            if action.__class__.__name__ == "_SubParsersAction":
                for name, child in action.choices.items():
                    key = f"{prefix}{name}"
                    # A parser with sub-commands is a verb of its own when it
                    # runs without one (``templates``, ``settings``, ``setup``);
                    # ``entry`` is only a group.
                    if key not in PURE_GROUPS:
                        found[key] = child
                    found.update(walk(child, key + " "))
        return found

    return walk(_parser())


#: Commands that only hold sub-commands and do nothing on their own.
PURE_GROUPS = {"entry"}


class ShippedTemplates(unittest.TestCase):
    def test_every_set_is_complete(self):
        self.assertEqual(len(TEMPLATES), 21)
        for path in TEMPLATES:
            raw = json.loads(path.read_text(encoding="utf-8"))
            t = JournalTemplate.model_validate(raw)
            with self.subTest(template=t.id):
                self.assertEqual(t.id, path.stem)
                self.assertTrue(t.when and t.minutes > 0 and t.moods and t.tags, "when/minutes/moods/tags")
                # Same keys in every file, so they read the same and diff cleanly.
                for key in ("description", "group", "order", "when", "minutes", "moods", "tags",
                            "structure", "reflection", "flow",
                            "default_theme", "default_layout", "closing_label", "closing_hint",
                            "closing_placeholder"):
                    self.assertIn(key, raw)
                # The classification is declared, not guessed, and agrees with the shape —
                # jot is the one set whose second section is filled by a program, so it
                # is declared one-part on purpose.
                self.assertTrue(t.flow, "flow names the steps")
                n = len(t.sections)
                expected = "one-part" if n == 1 else "three-part" if n == 3 else "n-part"
                if t.id != "jot":
                    self.assertEqual(t.structure, expected)
                if t.reflection in ("devotional", "prayer"):
                    self.assertTrue({"scripture", "prayer", "checkin", "trust", "confession"} & set(t.flow),
                                    "a faith-oriented set walks through a faith step")
                else:
                    self.assertFalse({"scripture", "prayer", "checkin", "confession"} & set(t.flow),
                                     "a set that walks through scripture or prayer is devotional or prayer")
                ids = [f.id for s in t.sections for f in s.fields]
                self.assertEqual(len(ids), len(set(ids)), "field ids are unique")
                for s in t.sections:
                    for f in s.fields:
                        self.assertTrue(f.ai_hint, f"{f.id} has an ai_hint")
                        self.assertNotIn("她", f.ai_hint)
                        if f.kind in (FieldKind.CHOICE, FieldKind.SCALE, FieldKind.MULTI_CHOICE):
                            self.assertTrue(f.options, f"{f.id} has options")
                        if f.kind is FieldKind.FILL:
                            self.assertIn("{}", f.pattern or "")

    def test_docs_and_skill_list_every_set(self):
        skill = (ROOT / "skills" / "diary-templates" / "SKILL.md").read_text(encoding="utf-8")
        doc = (ROOT / "docs" / "templates.md").read_text(encoding="utf-8")
        self.assertTrue(skill.startswith("---\nname: diary-templates\ndescription: "))
        for path in TEMPLATES:
            self.assertIn(f"`{path.stem}`", skill)
            self.assertIn(f"`{path.stem}`", doc)

    def test_docs_and_skill_name_every_command(self):
        """docs/cli.md and the skill describe exactly the command line that exists."""
        from backend.cli import COMMANDS, EXAMPLES

        skill = (ROOT / "skills" / "diary-templates" / "SKILL.md").read_text(encoding="utf-8")
        doc = (ROOT / "docs" / "cli.md").read_text(encoding="utf-8")
        parsers = sub_parsers()
        verbs = {" ".join(k for k in key if k) for key in COMMANDS}
        self.assertEqual(verbs, set(parsers), "every verb has a handler and a parser")
        self.assertEqual(verbs, set(EXAMPLES), "every verb has an example in its -h")
        for verb, parser in parsers.items():
            with self.subTest(verb=verb):
                self.assertIn(f"backend.cli {verb}", skill, "SKILL.md shows how to run it")
                self.assertIn(f"### `{verb}`", doc, "docs/cli.md has a section for it")
                for line in EXAMPLES[verb].splitlines():
                    self.assertIn(line, doc, "the -h example is in docs/cli.md word for word")
                options = {o for a in parser._actions for o in a.option_strings if o.startswith("--")} - {"--help"}
                for option in options:
                    self.assertIn(f"`{option}", doc, f"docs/cli.md explains {option}")
        # …and nothing that does not exist: every --flag on a command line in the skill is a real one.
        real = {o for p in parsers.values() for a in p._actions for o in a.option_strings}
        for line in skill.splitlines():
            if "backend.cli" in line:
                for flag in re.findall(r"(--[a-z][a-z-]*)", line.split("#")[0]):
                    self.assertIn(flag, real, f"SKILL.md: {line.strip()}")

    def test_superseded_table(self):
        from backend.seed_manager import SUPERSEDED, fingerprint

        table = json.loads(SUPERSEDED.read_text(encoding="utf-8"))
        for key, hashes in table.items():
            if key.startswith("_"):
                continue
            with self.subTest(key=key):
                shipped = ROOT / "content" / key
                self.assertTrue(shipped.is_file())
                self.assertTrue(all(re.fullmatch(r"[0-9a-f]{64}", h) for h in hashes))
                self.assertNotIn(fingerprint(shipped), hashes, "the current version is not 'superseded'")


def _rows() -> list[tuple]:
    """Every entry and every revision, exactly as stored."""
    import sqlite3

    from backend.config import settings

    with sqlite3.connect(settings.db_path) as conn:
        return [tuple(r) for r in conn.execute("SELECT * FROM entries ORDER BY id")] + \
               [tuple(r) for r in conn.execute("SELECT * FROM entry_revisions ORDER BY id")]


def _write_some_entries() -> None:
    from datetime import date

    from backend import storage
    from backend.models import EntryCreate

    storage.init_db()
    for i, tid in enumerate(("three-lines", "gratitude", "feelings")):
        storage.create_entry(EntryCreate(entry_date=date(2026, 1, i + 1), template_id=tid, title=f"假的標題 {i}",
                                         answers={"fact": f"假的內容 {i}"}, closing=""))


class UpgradeUntouched(unittest.TestCase):
    def setUp(self):
        from backend import seed_manager

        seed_manager.install_seeds(force=True)
        self.addCleanup(lambda: seed_manager.install_seeds(force=True))

    def _table(self, digest: str, *names: str) -> Path:
        table = Path(tempfile.mkdtemp()) / "superseded.json"
        table.write_text(json.dumps({f"templates/{n}": [digest] for n in names}), encoding="utf-8")
        return table

    def test_entries_are_never_touched_and_a_backup_comes_first(self):
        from backend import backup, seed_manager
        from backend.config import settings

        _write_some_entries()
        before_rows = _rows()
        before_snapshots = {b.name for b in backup.list_backups()}
        untouched = settings.templates_dir / "three-lines.json"
        old = b'{"id": "three-lines", "name": "old"}\n'
        untouched.write_bytes(old)
        table = self._table(seed_manager.fingerprint(untouched), "three-lines.json")
        saved, seed_manager.SUPERSEDED = seed_manager.SUPERSEDED, table
        try:
            self.assertEqual(seed_manager.install_seeds(), [], "nothing new to install")   # runs the upgrade too
        finally:
            seed_manager.SUPERSEDED = saved
        self.assertEqual(seed_manager.fingerprint(untouched),
                         seed_manager.fingerprint(ROOT / "content" / "templates" / "three-lines.json"), "upgraded")
        self.assertEqual(_rows(), before_rows, "not one entry or revision changed")
        new = [b.name for b in backup.list_backups() if b.name not in before_snapshots]
        self.assertTrue(any(n.endswith("-before-template-upgrade.sqlite3") for n in new), new)
        kept = sorted(settings.backups_dir.glob("defaults-*-before-upgrade/templates/three-lines.json"))
        self.assertTrue(kept and kept[-1].read_bytes() == old, "the replaced copy is kept")

    def test_no_backup_no_upgrade(self):
        from backend import backup, seed_manager
        from backend.config import settings

        _write_some_entries()
        untouched = settings.templates_dir / "three-lines.json"
        old = b'{"id": "three-lines", "name": "old"}\n'
        untouched.write_bytes(old)
        table = self._table(seed_manager.fingerprint(untouched), "three-lines.json")

        def broken(*_a, **_k):
            raise OSError("disk full (pretend)")

        saved = seed_manager.SUPERSEDED, backup.snapshot
        seed_manager.SUPERSEDED, backup.snapshot = table, broken
        try:
            self.assertEqual(seed_manager.upgrade_untouched(), [])
        finally:
            seed_manager.SUPERSEDED, backup.snapshot = saved
        self.assertEqual(untouched.read_bytes(), old, "left exactly as it was")

    def test_only_untouched_copies_are_replaced(self):
        from backend import seed_manager
        from backend.config import settings

        shipped = ROOT / "content" / "templates"
        old = b'{"id": "three-lines", "name": "old"}\r\n'
        untouched = settings.templates_dir / "three-lines.json"
        edited = settings.templates_dir / "gratitude.json"
        gone = settings.templates_dir / "feelings.json"
        untouched.write_bytes(old)
        edited.write_bytes(b'{"id": "gratitude", "name": "mine"}')
        gone.unlink()
        table = Path(tempfile.mkdtemp()) / "superseded.json"
        digest = seed_manager.fingerprint(untouched)
        table.write_text(json.dumps({
            "templates/three-lines.json": [digest],
            "templates/gratitude.json": [digest],
            "templates/feelings.json": [digest],
            "templates/../../x.json": [digest],
        }), encoding="utf-8")
        before, seed_manager.SUPERSEDED = seed_manager.SUPERSEDED, table
        try:
            upgraded = seed_manager.upgrade_untouched()
        finally:
            seed_manager.SUPERSEDED = before
        self.assertEqual(upgraded, ["templates/three-lines.json"])
        self.assertEqual(seed_manager.fingerprint(untouched), seed_manager.fingerprint(shipped / "three-lines.json"))
        self.assertEqual(edited.read_bytes(), b'{"id": "gratitude", "name": "mine"}')
        self.assertFalse(gone.exists(), "a deleted default stays deleted")


class CommandLine(unittest.TestCase):
    def setUp(self):
        self.data = tempfile.mkdtemp(prefix="journal-cli-")

    def test_templates(self):
        code, out = cli(self.data, "templates", "--brief")
        self.assertEqual(code, 0)
        self.assertTrue(out["ok"])
        self.assertEqual(out["result"]["count"], 21)
        first = out["result"]["templates"][0]
        self.assertNotIn("sections", first)
        for key in ("structure", "reflection", "flow"):
            self.assertIn(key, first, "the classification is in the brief listing")
        code, out = cli(self.data, "templates", "--id=scripture-fill")
        field = out["result"]["template"]["sections"][0]["fields"][0]
        self.assertEqual((field["kind"], field["blanks"]), ("fill", 2))
        self.assertIn("ai_hint", field)
        code, out = cli(self.data, "templates", "--id=nope")
        self.assertEqual((code, out["ok"]), (1, False))
        self.assertIn("找不到題組", out["error"])

    def test_templates_filters_categories_suggest(self):
        code, out = cli(self.data, "templates", "--brief", "--reflection=none,reflection", "--structure=three-part")
        ids = {t["id"] for t in out["result"]["templates"]}
        self.assertEqual(ids, {"feelings", "day-review", "become"})
        self.assertEqual(out["result"]["filters"], {"structure": "three-part", "reflection": "none,reflection"})
        code, out = cli(self.data, "templates", "--brief", "--flow=scripture,prayer")
        self.assertTrue({"three-part", "walk-with-jesus", "scripture-fill"} <= {t["id"] for t in out["result"]["templates"]})
        self.assertFalse({"capsule", "jot"} & {t["id"] for t in out["result"]["templates"]})
        code, out = cli(self.data, "templates", "--brief", "--tag=每週")
        self.assertEqual([t["id"] for t in out["result"]["templates"]], ["week-review"])
        code, out = cli(self.data, "templates", "--brief", "--reflection=bogus")
        self.assertEqual(code, 1)
        self.assertIn("沒有這種 reflection", out["error"])

        code, out = cli(self.data, "templates", "categories")
        cats = out["result"]
        self.assertEqual([c["id"] for c in cats["structure"]], ["one-part", "three-part", "n-part"])
        self.assertEqual([c["id"] for c in cats["reflection"]], ["none", "reflection", "devotional", "prayer"])
        by_id = {c["id"]: c for c in cats["flow"]}
        self.assertIn("three-part", by_id["scripture"]["templates"])
        self.assertTrue(all(c["label"] for c in cats["flow"]))
        self.assertIn("每週", {c["id"] for c in cats["tags"]})

        # A worried sentence about work: the rule names the words it saw and ranks a
        # work or worry set first; faith sets stay back because faith was not mentioned.
        code, out = cli(self.data, "templates", "suggest", "--text=今天跟客戶開會被罵，很擔心案子會不會黃掉")
        res = out["result"]
        self.assertEqual(code, 0, out)
        self.assertIn(res["suggestions"][0]["id"], ("founder-daily", "worry-sort", "hard-day"))
        self.assertTrue(all(s["why"] for s in res["suggestions"]), "every suggestion says why")
        self.assertEqual({s["id"] for s in res["signals"]}, {"worry", "work"})
        self.assertNotIn("quick-checkin", [s["id"] for s in res["suggestions"]])
        self.assertEqual(res["categories"]["flow"], ["worries", "work"])
        # Scripture and prayer: a devotional set, and the picker is told the level.
        code, out = cli(self.data, "templates", "suggest", "--text=讀了詩篇23篇，很感謝主。求主幫助媽媽")
        res = out["result"]
        self.assertEqual(res["suggestions"][0]["reflection"], "prayer")
        self.assertEqual(res["categories"]["reflection"], "prayer")
        # Nothing to go on: the plain sets, with an honest reason.
        code, out = cli(self.data, "templates", "suggest", "--text=嗯")
        self.assertEqual(out["result"]["suggestions"][0]["id"], "jot")
        self.assertEqual(out["result"]["signals"], [])
        code, out = cli(self.data, "templates", "suggest", "--text=  ")
        self.assertEqual(code, 1)
        # suggest_faith=never leaves faith sets out even when faith is mentioned... no:
        # it leaves them out only when faith is *not* mentioned; with faith words they return.
        cli(self.data, "settings", "set", "--key=suggest_faith", "--value=never")
        code, out = cli(self.data, "templates", "suggest", "--text=今天很累")
        self.assertFalse({"quick-checkin", "three-part"} & {s["id"] for s in out["result"]["suggestions"]})
        code, out = cli(self.data, "templates", "suggest", "--text=求主保守")
        self.assertEqual(out["result"]["suggestions"][0]["reflection"], "prayer")

    def test_overwrite_only_the_named_question(self):
        first = {"answers": {"a_what": "假的一件事", "a_verse": "箴言 21:5", "a_learn": "假的學到"}}
        code, out = cli(self.data, "entry", "put", f"--date={DAY}", "--template=capsule", stdin=json.dumps(first))
        self.assertEqual(code, 0, out)
        fuller = {"answers": {"a_verse": "箴言 21:5 殷勤籌劃的，足致豐裕", "a_what": "不要改我"}}
        # fill alone keeps both; this is what the ticket ran into.
        code, out = cli(self.data, "entry", "put", f"--date={DAY}", "--template=capsule", "--merge=fill", stdin=json.dumps(fuller))
        self.assertEqual((out["result"]["filled"], sorted(out["result"]["kept"])), ([], ["a_verse", "a_what"]))
        # --overwrite names the one question; the other stays kept.
        code, out = cli(self.data, "entry", "put", f"--date={DAY}", "--template=capsule", "--merge=fill",
                        "--overwrite=a_verse", stdin=json.dumps(fuller))
        self.assertEqual((out["result"]["overwritten"], out["result"]["kept"]), (["a_verse"], ["a_what"]))
        code, out = cli(self.data, "entry", "show", f"--date={DAY}", "--template=capsule")
        answers = out["result"]["entries"][0]["answers"]
        self.assertEqual(answers["a_what"], "假的一件事")
        self.assertEqual(answers["a_learn"], "假的學到", "a question not mentioned is untouched")
        self.assertIn("豐裕", answers["a_verse"])
        # Export re-renders what is stored now - nothing blocks it.
        code, out = cli(self.data, "export", f"--date={DAY}", "--template=capsule", "--format=html")
        self.assertEqual(code, 0, out)
        page = Path(out["result"]["html"]).read_text(encoding="utf-8")
        self.assertIn("豐裕", page)
        self.assertIn("假的一件事", page)
        # all = every question given; unknown ids are refused before anything is written.
        code, out = cli(self.data, "entry", "put", f"--date={DAY}", "--template=capsule", "--merge=fill",
                        "--overwrite=all", stdin=json.dumps({"answers": {"a_what": "全部換", "a_learn": "也換"}}))
        self.assertEqual(sorted(out["result"]["overwritten"]), ["a_learn", "a_what"])
        code, out = cli(self.data, "entry", "put", f"--date={DAY}", "--template=capsule", "--overwrite=nope",
                        stdin=json.dumps({"answers": {"a_what": "x"}}))
        self.assertEqual(code, 1)
        self.assertIn("nope", out["error"])
        code, out = cli(self.data, "entry", "show", f"--date={DAY}", "--template=capsule")
        self.assertEqual(out["result"]["entries"][0]["answers"]["a_what"], "全部換")

    def test_ai_author_keeps_the_original_and_never_replaces_the_author(self):
        mine = {"answers": {"happened": "我自己寫的", "biggest": "我的一句"}}
        code, out = cli(self.data, "entry", "put", f"--date={DAY}", "--template=day-review", stdin=json.dumps(mine))
        self.assertEqual(code, 0, out)
        # No original -> refused; append -> refused.
        code, out = cli(self.data, "entry", "put", f"--date={DAY}", "--template=day-review", "--author=ai",
                        stdin=json.dumps({"answers": {"learned": "x"}}))
        self.assertEqual(code, 1)
        self.assertIn("原文", out["error"])
        code, out = cli(self.data, "entry", "put", f"--date={DAY}", "--template=day-review", "--author=ai",
                        "--merge=append", stdin=json.dumps({"answers": {"learned": "x"}, "source_text": "o"}))
        self.assertEqual(code, 1)
        self.assertIn("append", out["error"])
        code, out = cli(self.data, "entry", "list")
        self.assertEqual(out["result"]["entries"][0]["ai_fields"], [], "the refused writes changed nothing")

        original = Path(self.data) / "original.txt"
        original.write_text("今天開會被罵 覺得學到不要急著回嘴", encoding="utf-8")
        ai = {"answers": {"happened": "AI 版", "learned": "被罵之後，學到先不急著回嘴。"},
              "sources": {"learned": "覺得學到不要急著回嘴"}}
        code, out = cli(self.data, "entry", "put", f"--date={DAY}", "--template=day-review", "--author=ai",
                        f"--source-text={original}", stdin=json.dumps(ai))
        res = out["result"]
        self.assertEqual(code, 0, out)
        self.assertEqual((res["filled"], res["protected"]), (["learned"], ["happened"]))
        self.assertEqual(res["entry"]["ai_fields"], ["learned"])

        code, out = cli(self.data, "entry", "show", f"--date={DAY}", "--template=day-review")
        entry = out["result"]["entries"][0]
        self.assertEqual(entry["answers"]["happened"], "我自己寫的", "the author's text is untouched")
        self.assertEqual(entry["provenance"]["fields"]["learned"]["author"], "ai")
        self.assertEqual(entry["provenance"]["fields"]["learned"]["source"], "覺得學到不要急著回嘴")
        self.assertIn("今天開會被罵", entry["provenance"]["source_text"])
        text = entry["text"]
        self.assertIn("（AI 整理）", text)
        self.assertIn("作者原文", text)
        self.assertIn("不要急著回嘴", text)
        self.assertNotIn("今天發生的事（AI 整理）", text, "an author-written field carries no mark")

        code, out = cli(self.data, "export", f"--date={DAY}", "--template=day-review")
        page = Path(out["result"]["html"]).read_text(encoding="utf-8")
        card = Path(out["result"]["svg"]).read_text(encoding="utf-8")
        for rendered in (page, card):
            self.assertIn("AI 整理", rendered)
            self.assertIn("作者原文", rendered)

        # Named in --overwrite, the AI may replace the author's text - and it is marked.
        code, out = cli(self.data, "entry", "put", f"--date={DAY}", "--template=day-review", "--author=ai",
                        "--overwrite=happened", stdin=json.dumps({"answers": {"happened": "AI 版"}, "source_text": "原文"}))
        self.assertEqual(out["result"]["overwritten"], ["happened"])
        self.assertEqual(out["result"]["entry"]["ai_fields"], ["happened", "learned"])
        # The author writing the field again takes the mark off.
        code, out = cli(self.data, "entry", "put", f"--date={DAY}", "--template=day-review",
                        stdin=json.dumps({"answers": {"happened": "我改回來"}}))
        self.assertEqual(out["result"]["entry"]["ai_fields"], ["learned"])

    def test_every_setting_is_reachable(self):
        from backend import preferences
        from backend.models import Preferences

        self.assertEqual(set(preferences.FIELDS), set(Preferences.model_fields), "FIELDS names every preference")
        code, out = cli(self.data, "settings")
        rows = {r["key"]: r for r in out["result"]["settings"]}
        self.assertEqual(set(rows), set(Preferences.model_fields))
        self.assertTrue(all(r["what"] and r["how"] for r in rows.values()))
        self.assertEqual(rows["day_start_hour"]["value"], 0)

        code, out = cli(self.data, "settings", "set", "--key=day_start_hour", "--value=4")
        self.assertEqual((code, out["result"]["value"]), (0, 4))
        code, out = cli(self.data, "settings", "get", "--key=day_start_hour")
        self.assertEqual(out["result"]["value"], 4)
        self.assertTrue((Path(self.data) / "preferences.json").is_file())
        for key, value in (("day_start_hour", "99"), ("template_id", "nope"), ("layout", "nope"), ("theme", "pink"),
                           ("card_width", "10"), ("suggest_faith", "maybe"), ("nope", "1"), ("palette", "[]")):
            with self.subTest(key=key):
                code, out = cli(self.data, "settings", "set", f"--key={key}", f"--value={value}")
                self.assertEqual(code, 1, out)
        code, out = cli(self.data, "settings", "get", "--key=day_start_hour")
        self.assertEqual(out["result"]["value"], 4, "a refused value changes nothing")
        code, out = cli(self.data, "settings", "set", "--key=template_id", "--value=three-lines")
        self.assertEqual(out["result"]["value"], "three-lines")
        code, out = cli(self.data, "settings", "set", "--key=use_as_default", "--value=false")
        self.assertIs(out["result"]["value"], False)
        code, out = cli(self.data, "settings", "set", "--key=palette",
                        "--value=" + json.dumps([{"hex": "#123456", "name": "test"}]))
        self.assertEqual(out["result"]["value"], [{"hex": "#123456", "name": "test"}])
        code, out = cli(self.data, "settings", "set", "--key=palette", "--value=default")
        self.assertEqual(len(out["result"]["value"]), 6)
        out_dir = Path(self.data) / "elsewhere"
        code, out = cli(self.data, "settings", "set", "--key=export_dir", f"--value={out_dir}")
        cli(self.data, "entry", "put", f"--date={DAY}", "--template=three-lines", stdin=json.dumps({"answers": {"fact": "假"}}))
        code, out = cli(self.data, "export", f"--date={DAY}", "--template=three-lines", "--format=html")
        self.assertEqual(Path(out["result"]["html"]).parent, out_dir.resolve())
        # today/yesterday follow day_start_hour (4 here): whatever the clock says, both resolve to a date.
        code, out = cli(self.data, "entry", "show", "--date=today")
        self.assertEqual(code, 0, out)
        code, out = cli(self.data, "entry", "show", "--date=yesterday")
        self.assertEqual(code, 0, out)

    def test_setup_init_presets(self):
        code, out = cli(self.data, "setup")
        self.assertEqual((out["result"]["preset"], out["result"]["templates"]), ("", 21))
        fresh = tempfile.mkdtemp(prefix="journal-generic-")
        code, out = cli(fresh, "setup", "init", "--preset=generic")
        self.assertEqual(code, 0, out)
        res = out["result"]
        self.assertEqual(res["already_had"], [])
        self.assertEqual(set(res["templates_now"]), {"jot", "three-lines", "gratitude", "day-review", "feelings",
                                                      "hard-day", "worry-sort", "week-review"})
        self.assertEqual(res["settings"], {"preset": "generic", "suggest_faith": "never", "template_id": "three-lines"})
        # The next start installs nothing more; faith sets stay out of suggestions.
        code, out = cli(fresh, "templates", "--brief")
        self.assertEqual(out["result"]["count"], 8)
        self.assertFalse(any(t["reflection"] in ("devotional", "prayer") for t in out["result"]["templates"]))
        code, out = cli(fresh, "templates", "suggest", "--text=求主保守")
        self.assertFalse(any(s["reflection"] in ("devotional", "prayer") for s in out["result"]["suggestions"]))
        # One set back on request; nothing else changes.
        code, out = cli(fresh, "templates", "restore", "--id=capsule")
        self.assertEqual(out["result"]["template"]["id"], "capsule")
        code, out = cli(fresh, "setup")
        self.assertEqual((out["result"]["preset"], out["result"]["templates"]), ("generic", 9))
        code, out = cli(fresh, "templates", "restore", "--id=../x")
        self.assertEqual(code, 1)
        # On an install that has everything, devotional only records the preset and its settings.
        code, out = cli(self.data, "setup", "init", "--preset=devotional")
        self.assertEqual((out["result"]["templates_added"], len(out["result"]["already_had"])), ([], 21))
        self.assertEqual(out["result"]["settings"], {"preset": "devotional", "suggest_faith": "prefer"})
        code, out = cli(self.data, "setup", "init", "--preset=other")
        self.assertEqual(code, 1)

    def test_put_show_export(self):
        notes = {"answers": {"notes": ["假的第一則 <b>不是粗體</b>", "假的第二則\n第二行"]}}
        code, out = cli(self.data, "entry", "put", f"--date={DAY}", "--template=jot", stdin=json.dumps(notes))
        self.assertEqual(code, 0, out)
        entry = out["result"]["entry"]
        self.assertTrue(out["result"]["created"])
        self.assertEqual((entry["template"], entry["layout"]), ("jot", "letter"))

        more = {"answers": {"notes": ["假的第三則"], "verses": ["<b>詩篇 23:1</b>　（假的）"]}}
        code, out = cli(self.data, "entry", "put", f"--date={DAY}", "--template=jot", "--merge=append",
                        "--format=html", stdin=json.dumps(more))
        self.assertFalse(out["result"]["created"])
        self.assertEqual(out["result"]["entry"]["id"], entry["id"], "same day + same set = the same entry")

        code, out = cli(self.data, "entry", "show", f"--date={DAY}", "--template=jot")
        answers = out["result"]["entries"][0]["answers"]
        self.assertEqual(len(answers["notes"]), 3)
        self.assertEqual(answers["notes"][0], "假的第一則 &lt;b&gt;不是粗體&lt;/b&gt;", "plain text is escaped")
        self.assertEqual(answers["notes"][1], "假的第二則<br>第二行")
        self.assertEqual(answers["verses"], ["<b>詩篇 23:1</b>　（假的）"])

        # A second set on the same day is a second entry; choices accept labels.
        tl = {"answers": {"fact": "假的一件事", "overall": "普通", "nope": "x", "feel": ""}}
        code, out = cli(self.data, "entry", "put", f"--date={DAY}", "--template=three-lines", stdin=json.dumps(tl))
        self.assertNotEqual(out["result"]["entry"]["id"], entry["id"])
        self.assertEqual(out["result"]["filled"], ["fact", "overall"])
        self.assertEqual(out["result"]["ignored"], [{"field": "nope", "why": "這個題組沒有這一題"}])

        # fill never overwrites what is already written.
        code, out = cli(self.data, "entry", "put", f"--date={DAY}", "--template=three-lines", "--merge=fill",
                        stdin=json.dumps({"answers": {"fact": "改掉", "thanks": "假的謝謝"}}))
        self.assertEqual((out["result"]["filled"], out["result"]["kept"]), (["thanks"], ["fact"]))

        code, out = cli(self.data, "entry", "show", f"--date={DAY}")
        self.assertEqual(out["result"]["count"], 2)
        text = out["result"]["entries"][1]["text"]
        self.assertIn("假的一件事", text)
        self.assertIn("今天整體：普通", text)

        code, out = cli(self.data, "export", f"--date={DAY}", "--template=three-lines")
        self.assertEqual(code, 0, out)
        res = out["result"]
        self.assertTrue(Path(res["html"]).is_file() and Path(res["svg"]).is_file())
        self.assertEqual(Path(res["html"]).parent, Path(self.data).resolve() / "exports")
        self.assertGreater(res["height"], 400)
        self.assertIn("假的一件事", Path(res["html"]).read_text(encoding="utf-8"))

        code, out = cli(self.data, "export", "--id=999")
        self.assertEqual((code, out["error"]), (1, "找不到日記 #999"))

    def test_bad_input_is_one_sentence(self):
        code, out = cli(self.data, "entry", "put", "--date=11/2", "--template=jot", stdin="{}")
        self.assertEqual((code, out["ok"]), (1, False))
        self.assertIn("YYYY-MM-DD", out["error"])
        code, out = cli(self.data, "entry", "put", f"--date={DAY}", "--template=jot", stdin="not json")
        self.assertIn("不是 JSON", out["error"])
        code, out = cli(self.data, "nonsense")
        self.assertEqual((code, out["error"].split("（")[0]), (1, "參數有誤：沒有這個指令：'nonsense'"))
        code, out = cli(self.data, "entry", "put", f"--date={DAY}", stdin="{}")
        self.assertIn("少了必填的參數：--template", out["error"])
        code, out = cli(self.data, "entry", "show", "--id=abc")
        self.assertIn("--id 要是整數", out["error"])
        code, out = cli(self.data, "entry")
        self.assertEqual(code, 1)
        self.assertIn("entry put|show|list", out["error"])

    def test_every_command_has_help_with_an_example(self):
        for verb in sub_parsers():
            with self.subTest(verb=verb):
                proc = run(self.data, *verb.split(), "-h", encoding="cp950")
                self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
                text = proc.stdout.decode("utf-8")
                self.assertIn("例：", text)
                self.assertIn(f"python -m backend.cli {verb}", text)

    def test_a_cp950_console_does_not_break_anything(self):
        """Windows consoles are often cp950, which has no emoji. Output is UTF-8 regardless."""
        text = "假的一句 😀 還有 ✓ 和 \U0001f64f"
        payload = Path(self.data) / "in.json"
        payload.write_text(json.dumps({"answers": {"notes": [text]}}, ensure_ascii=False), encoding="utf-8")
        code, out = cli(self.data, "entry", "put", f"--date={DAY}", "--template=jot", f"--input={payload}",
                        encoding="cp950")
        self.assertEqual(code, 0, out)
        code, out = cli(self.data, "entry", "show", f"--date={DAY}", encoding="cp950")
        self.assertEqual(code, 0, out)
        self.assertIn("😀", out["result"]["entries"][0]["answers"]["notes"][0])
        proc = run(self.data, "entry", "show", f"--date={DAY}", encoding="cp950")     # the human-readable form
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        self.assertIn("😀", proc.stdout.decode("utf-8"))
        proc = run(self.data, "entry", "put", "--date=nope", "--template=jot", encoding="cp950")
        self.assertEqual(proc.returncode, 1)
        self.assertNotIn(b"Traceback", proc.stderr)
        self.assertIn("YYYY-MM-DD", proc.stderr.decode("utf-8"))

    def test_input_must_be_utf8(self):
        big5 = json.dumps({"answers": {"fact": "假的一件事"}}, ensure_ascii=False).encode("cp950")
        proc = run(self.data, "entry", "put", f"--date={DAY}", "--template=three-lines", "--json", stdin=big5)
        out = json.loads(proc.stdout.decode("utf-8").splitlines()[-1])
        self.assertEqual((proc.returncode, out["ok"]), (1, False))
        self.assertIn("UTF-8", out["error"])
        code, out = cli(self.data, "entry", "put", f"--date={DAY}", "--template=jot",
                        f"--input={Path(self.data) / 'missing.json'}")
        self.assertIn("讀不到 --input", out["error"])
        code, out = cli(self.data, "entry", "list")
        self.assertEqual(out["result"]["entries"], [], "nothing was written by the bad attempts")


if __name__ == "__main__":
    unittest.main()
