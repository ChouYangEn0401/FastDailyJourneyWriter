# Changelog

格式參考 [Keep a Changelog 1.1.0](https://keepachangelog.com/zh-TW/1.1.0/)，版號遵循 [SemVer 2.0.0](https://semver.org/lang/zh-TW/)。
規則全文：全域 `knowledge/conventions/versioning.md`。小改動只動版本號與這份檔案、不打 tag；只有 release 才打 annotated tag `vX.Y.Z`。

## [Unreleased]

## [0.1.0] - 2026-11-12

### Added
- 導入版本號系統（版本來源：pyproject.toml（既有 tag `v1.0` 與之不一致，保留不動））。以 0.1.0 作為基準版本；此前的歷史不逐版回溯，見 `git log`（共 43 個 commit，第一個在 2026-07-31）。

## 導入前的近期歷史（自 git log 擷取，僅供參考，非正式版本）

- 2026-11-09 synox-pack: type a diary line straight from Telegram (/diary 今天很好); entry put takes plain text; envelope carries the human message
- 2026-11-09 docs: data contract for the classification, every setting, overwrite, AI author, presets; changelog
- 2026-11-09 synox-pack + tests: declare the command line as a SYNOX cli pack; cover taxonomy, overwrite, AI author, settings, presets
- 2026-11-09 cli: overwrite named fields, AI-authored entries with the original kept, settings and setup verbs
- 2026-11-09 content+taxonomy: classify every question set (structure/reflection/flow), suggest by rule, presets
- 2026-11-04 Make the command line clear: docs/cli.md, Chinese -h with examples, cp950-safe
- 2026-11-04 Back up before upgrading untouched default question sets
- 2026-11-02 Give every question set the same structure, and add a command line
- 2026-08-11 Lay the interface out for phones, and add the PWA shell
- 2026-08-11 Add core/, the JavaScript output core, with parity tests
- 2026-08-10 Add platforms/, and package the desktop build
- 2026-08-06 Rename app/ to backend/
- 2026-08-06 Document install steps per OS, and the multi-platform roadmap
- 2026-08-06 Add LICENSE (AGPL-3.0) and a contributor guide
- 2026-08-06 Require Python 3.11; add a macOS/Linux launcher
