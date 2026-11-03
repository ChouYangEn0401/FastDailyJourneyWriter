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
                    inner = walk(child, key + " ")
                    found.update(inner or {key: child})
        return found

    return walk(_parser())


class ShippedTemplates(unittest.TestCase):
    def test_every_set_is_complete(self):
        self.assertEqual(len(TEMPLATES), 20)
        for path in TEMPLATES:
            raw = json.loads(path.read_text(encoding="utf-8"))
            t = JournalTemplate.model_validate(raw)
            with self.subTest(template=t.id):
                self.assertEqual(t.id, path.stem)
                self.assertTrue(t.when and t.minutes > 0 and t.moods and t.tags, "when/minutes/moods/tags")
                # Same keys in every file, so they read the same and diff cleanly.
                for key in ("description", "group", "order", "when", "minutes", "moods", "tags",
                            "default_theme", "default_layout", "closing_label", "closing_hint",
                            "closing_placeholder"):
                    self.assertIn(key, raw)
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
        self.assertEqual(out["result"]["count"], 20)
        self.assertNotIn("sections", out["result"]["templates"][0])
        code, out = cli(self.data, "templates", "--id=scripture-fill")
        field = out["result"]["template"]["sections"][0]["fields"][0]
        self.assertEqual((field["kind"], field["blanks"]), ("fill", 2))
        self.assertIn("ai_hint", field)
        code, out = cli(self.data, "templates", "--id=nope")
        self.assertEqual((code, out["ok"]), (1, False))
        self.assertIn("找不到題組", out["error"])

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
