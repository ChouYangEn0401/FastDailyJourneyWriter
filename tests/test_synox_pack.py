"""The SYNOX skill pack under synox-pack/ declares exactly the command line that exists.

The pack is a ``kind: cli`` manifest (see C:/Users/user/Documents/SYNOX/docs/pack-format.md): every
command is an argv template that SYNOX fills in and runs through its own job runner. These tests
check the manifest against this repo's parser, and - when a SYNOX checkout is next to this one -
against SYNOX's own ``manifest.validate``.
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "synox-pack"
os.environ.setdefault("JOURNAL_DATA_DIR", tempfile.mkdtemp(prefix="journal-test-"))
sys.path.insert(0, str(ROOT))

#: Where a SYNOX checkout would be: next to this repo (or next to the worktrees
#: folder this repo sits in), or wherever SYNOX_SRC points.
SYNOX_SRC = Path(os.environ.get("SYNOX_SRC") or next(
    (p for p in (ROOT.parent / "SYNOX" / "src", ROOT.parent.parent / "SYNOX" / "src") if p.is_dir()),
    ROOT.parent / "SYNOX" / "src",
))

EFFECTS = {"READ", "WRITE", "DANGER"}
PLACEHOLDER = re.compile(r"\{([a-z_]+)\}")


class SynoxPack(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = json.loads((PACK / "pack.json").read_text(encoding="utf-8-sig"))

    def test_manifest_basics(self):
        raw = self.raw
        self.assertEqual((raw["name"], raw["kind"], raw["access"]), ("diary", "cli", "member"))
        self.assertEqual(raw["title"], "📔 日記")
        self.assertIn("subprocess", raw["capabilities"])
        self.assertEqual(raw["cli"]["python"], "venv")
        self.assertEqual(raw["cli"]["argv"][:3], ["{python}", "-m", "backend.cli"])
        self.assertEqual(raw["cli"]["json_flag"], "--json")
        for name in ("SKILL.md", "README.md"):
            self.assertTrue((PACK / name).is_file(), name)
        skill = (PACK / raw["skill"]).read_text(encoding="utf-8")
        self.assertTrue(skill.startswith("---\nname: diary\ndescription: "))

    def test_every_command_is_a_real_verb_with_an_effect(self):
        from backend.cli import _parser

        parser = _parser()

        def find(words):
            node = parser
            for w in words:
                subs = [a for a in node._actions if a.__class__.__name__ == "_SubParsersAction"]
                self.assertTrue(subs, f"{words}: {w} is not a sub-command")
                self.assertIn(w, subs[0].choices, f"{words}: no sub-command {w}")
                node = subs[0].choices[w]
            return node

        names = set()
        for cmd in self.raw["cli"]["commands"]:
            with self.subTest(command=cmd["name"]):
                self.assertNotIn(cmd["name"], names, "command names are unique")
                names.add(cmd["name"])
                self.assertIn(cmd["effect"], EFFECTS)
                self.assertTrue(cmd.get("summary"))
                words = [a for a in cmd["argv"] if not a.startswith("-")]
                verb = find(words)
                flags = {o for a in verb._actions for o in a.option_strings}
                flags |= {"--json", "--data-dir"}
                declared = {f["name"] for f in cmd.get("fields", [])}
                used = set()
                for arg in cmd["argv"]:
                    if arg.startswith("--"):
                        flag = arg.split("=")[0]
                        self.assertIn(flag, flags, f"{cmd['name']}: {flag} is not a flag of `{' '.join(words)}`")
                        self.assertTrue("=" in arg or arg in ("--brief", "--json"), f"{cmd['name']}: write {flag}=value")
                    used |= set(PLACEHOLDER.findall(arg))
                used |= set(PLACEHOLDER.findall(cmd.get("stdin", "")))
                for ph in used - {"python", "user_data_dir"}:
                    self.assertIn(ph, declared, f"{cmd['name']}: placeholder {{{ph}}} has no field")
                for field in cmd.get("fields", []):
                    self.assertTrue(field.get("ask"), f"{cmd['name']}: field {field['name']} needs an ask")
                    if field.get("required"):
                        self.assertIn(field["name"], used, f"{cmd['name']}: required field {field['name']} unused")
                # Writes that can replace text are DANGER; reads are READ.
                if any("--overwrite" in a for a in cmd["argv"]):
                    self.assertEqual(cmd["effect"], "DANGER")
                if words[0] in ("templates", "layouts") or words[:2] in (["entry", "show"], ["entry", "list"]):
                    if words[:2] != ["templates", "restore"]:
                        self.assertEqual(cmd["effect"], "READ", cmd["name"])
                # The data folder is always the user's, never the repo's data/.
                self.assertTrue(any(a.startswith("--data-dir={user_data_dir}") for a in cmd["argv"]), cmd["name"])
        self.assertTrue(any(c.get("default") for c in self.raw["cli"]["commands"]), "one command is the default")

    def test_skill_names_every_command(self):
        skill = (PACK / "SKILL.md").read_text(encoding="utf-8")
        for cmd in self.raw["cli"]["commands"]:
            self.assertIn(f"diary__{cmd['name']}", skill, f"SKILL.md explains diary__{cmd['name']}")

    @unittest.skipUnless((SYNOX_SRC / "synox" / "packs" / "manifest.py").is_file(), "no SYNOX checkout next to this repo")
    def test_synox_validates_the_manifest(self):
        # manifest.py is standard library only; loaded by path so that
        # synox.packs.__init__ (which pulls in the whole host) stays out.
        import importlib.util

        spec = importlib.util.spec_from_file_location("synox_manifest", SYNOX_SRC / "synox" / "packs" / "manifest.py")
        manifest = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = manifest        # dataclasses look the module up here
        spec.loader.exec_module(manifest)
        m = manifest.read(str(PACK))
        self.assertEqual((m.name, m.kind, m.group, m.access), ("diary", "cli", "diary", "member"))
        self.assertTrue(m.cli["commands"])


if __name__ == "__main__":
    unittest.main()
