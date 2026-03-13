# Repository Guidelines

## Project Structure & Module Organization
`main.py` is the core automation entry point and coordinates the MVC-style workflow. `Run.py` is the Windows launcher that checks dependencies, requests admin rights, and starts the app. Reusable logic lives in `mod/` (`image_processor.py`, `ld_controller.py`, `telegram_bot.py`, `web_ui.py`, `input_handler.py`). HTML templates are in `templates/`. Runtime assets and sample images live in `mouse/`, `get/`, and `screenshots/`. Logs are written to `logs/`. Experimental scripts and regression checks are kept in `Test/`.

## Build, Test, and Development Commands
Use Python 3.10+ on Windows.

- `python -m pip install -r requirements.txt` installs runtime dependencies.
- `python Run.py` starts the launcher with dependency checks and elevation prompts.
- `python main.py` runs the automation directly when the environment is already prepared.
- `python Test/analyze_stars_test.py --image screenshots/sample.png` runs the image-analysis helper.
- `python Test/ld_demo_test.py list` verifies ADB device detection.

## Coding Style & Naming Conventions
Follow existing Python style: 4-space indentation, `snake_case` for functions/modules/variables, `PascalCase` for classes, and short docstrings only where behavior is not obvious. Keep modules focused by responsibility; new automation integrations belong in `mod/`. Preserve the current pattern of descriptive Chinese-facing log messages and English code identifiers.

## Testing Guidelines
This repository uses script-based tests rather than a single formal test suite. Add new checks under `Test/` and prefer names like `test_*.py` for runnable validation scripts. For image-processing changes, include a reproducible sample image path and expected output. For emulator or Telegram work, document required local setup in the script header or PR notes.

## Commit & Pull Request Guidelines
Recent commits use concise, scope-first messages such as `Telegram: 精簡主選單` or `WebUI: 新增 enabled/port 設定開關`. Keep that format: `<area>: <change summary>`. PRs should include the behavioral impact, any config changes, manual test steps, and screenshots when `templates/` or Web UI behavior changes.

## Security & Configuration Tips
Treat `config.ini` as local machine configuration. Do not commit real Telegram tokens, chat IDs, passwords, or machine-specific `adb_path` values. When sharing examples, replace secrets with placeholders and keep generated logs or screenshots free of sensitive data.
