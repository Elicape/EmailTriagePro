# EmailTriagePro — Agent guide

## Entry points

- `daemon.py` — core. Never import from GUI code. GUIs launch it via **QProcess** (subprocess), not `import`.
  3 entry points: `python daemon.py` (classify once), `python daemon.py --bot` (Telegram callback listener), `from daemon import send_summary` (used only by `resumen_batch.py`).
- `gui_main.py` — GUI with daemon log + config form.
- `main.py` — alternative GUI with pending-emails table + audit log.
- Both GUIs are **duplicates** — V2 plan merges them into `app.py`. Do not add features to both; prefer `gui_main.py` if adding to one.

## Security

- `config.ini` contains **real IMAP passwords and Telegram tokens**. Never commit, share, or package it. It is user-generated from `config.ini.example`.
- `daemon.py` reads `config.ini` from disk at runtime. Tests mock external calls (`imaplib`, `subprocess`, `requests`) so credentials never leave the process.

## Tests

```bash
python3 test_smoke.py           # smoke tests (daemon pipeline + GUI instantiation)
python3 test_telegram_alert.py  # unit tests (parse, escalada, IDs)
```

- Qt tests require `QT_QPA_PLATFORM=offscreen` (set automatically in `test_smoke.py`).
- `test_smoke.py` patches `gui_main.MainWindow._setup_daemon` and `_cleanup` to avoid QThread crashes in headless mode.

## Dependencies (requirements.txt)

`PySide6`, `plyer`, `requests`, `pyTelegramBotAPI` (+ `cryptography` planned for V2).

External binary: `llama-cli` (llama.cpp) + a `.gguf` model in `models/`. Neither is included in the repo.

## Prompts / skills

`skills/system_global.txt` — LLM identity and principles. `skills/system_tarea.txt` — JSON classification schema and escalation rules. These are loaded at runtime by `daemon.py`.

## Architecture notes

- `daemon.py` is self-contained: reads config, connects IMAP, calls llama-cli via `subprocess.run`, sends Telegram alerts via `requests.post`. No async, no daemon loop (called periodically by GUI timer or cron).
- `resumen_batch.py` — only file with a direct `from daemon import send_summary`. Used as a standalone summary script.
- `send_telegram_msg` was removed as dead code (never called). All Telegram sends use `send_telegram_alert` or inline `requests.post`.
- No linter, no typechecker, no build system configured.

## V2 plan (not yet implemented)

See `docs/V2-plan.md` for: SetupWizard, Fernet encryption of secrets, GUI merge into `app.py`, PyInstaller packaging.

## Git

No repository initialized yet. `config.ini` must be in `.gitignore` before any commit.
