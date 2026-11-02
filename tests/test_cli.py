"""Question sets, the untouched-default upgrade, and the command line.

    python -m unittest discover -s tests        (from the repo root; no extra packages)

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


def cli(data_dir: str, *args: str, stdin: str | None = None) -> tuple[int, dict]:
    proc = subprocess.run(
        [sys.executable, "-m", "backend.cli", *args, "--json", f"--data-dir={data_dir}"],
        cwd=ROOT, input=(stdin or "").encode("utf-8"), capture_output=True,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"}, timeout=60,
    )
    lines = [ln for ln in proc.stdout.decode("utf-8").splitlines() if ln.strip()]
    return proc.returncode, json.loads(lines[-1])


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


class UpgradeUntouched(unittest.TestCase):
    def test_only_untouched_copies_are_replaced(self):
        from backend import seed_manager
        from backend.config import settings

        seed_manager.install_seeds()
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
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
