# PROJECTS DOWNLOADER — README

**By Xeo Studio** • [Github](https://github.com/XeoStudio) 

This is the official README for **Projects Downloader**, a single-file, open-source Python CLI tool to collect, validate and download projects (GitHub repos and direct files). Pragmatic, no-nonsense — exactly what you asked for.

# Quick facts

* **Name:** PROJECTS DOWNLOADER
* **Developer:** Xeo Studio
* **Language:** Python 3 (standard library only; `colorama` optional)
* **License:** MIT
* **Install:** copy the single file `project-cli.py` (or `project_downloader.py`) to your machine
* **Platforms:** Linux, macOS, Windows (PowerShell / Windows Terminal recommended)

# What it does (short)

You keep a list of project records (local JSON file or remote URL). The tool shows the list, validates links, and downloads what you choose — as a `.git` clone for repos or as a file download for direct assets. It supports resume, retry, SHA256 verification, archive extraction, logging and central sync/production packaging.

# Key features

* Interactive CLI and non-interactive flags for scripting
* Local (`projects.json`) or remote (`projects_url`) project lists
* Git clone support for GitHub repositories (requires `git` on PATH)
* Direct HTTP(S) downloads with resume and retries
* Automatic archive extraction (`.zip`, `.tar`, `.tar.gz`, etc.)
* Optional SHA256 verification per-project
* Validation (HEAD/GET probing) with cache to avoid repeat network checks
* Production mode: create `production_config.json` to lock advanced settings
* Central sync: merge projects from a central URL
* Download logging (`downloads.log`) and CSV export
* Hooks (pre/post) and webhook notifications on events
* Basic plugin loader (drop-in `.py` modules in `~/.project_downloader/plugins`)
* Optional colorized output (uses `colorama` if installed; otherwise tries to enable ANSI)
* Bandwidth limiting, proxy support, GitHub token support
* Daemon mode (poll central URL at interval)
* CLI flags: `--list`, `--get N`, `--add`, `--sync`, `--daemon`, `--dry-run`, `--export-log` etc.

# Requirements

* Python 3.8+ (should work on 3.7 in most cases)
* `git` binary if you want to clone repositories
* Optional: `colorama` for consistent colors on Windows (`pip install --user colorama`)
* Optional: `pyinstaller` if you plan to build a standalone executable

# Files and locations

By default the tool stores user data under your home directory:

* `~/.project_downloader/config.json` — tool configuration
* `~/.project_downloader/projects.json` — local projects list (created when needed)
* `~/.project_downloader/downloads/` — default download folder
* `~/.project_downloader/downloads.log` — download audit log
* `~/.project_downloader/production_config.json` — produced when you freeze settings for distribution
* `~/.project_downloader/validation_cache.json` — validation cache
* `~/.project_downloader/plugins/` — drop-in plugin folder

# Project record format

Each project is a JSON object with fields (example):

```json
[
  {
    "name": "Requests (example)",
    "url": "https://github.com/psf/requests.git"
  },
  {
    "name": "Requests ZIP",
    "url": "https://github.com/psf/requests/archive/refs/heads/main.zip",
    "sha256": "",
    "tags": ["http", "python"]
  }
]
```

* `name` (required) — display name
* `url` (required) — `.git` repo or a downloadable file URL
* `sha256` (optional) — SHA256 hex to verify downloaded file
* `tags` (optional) — for searching
* `pre_hook` / `post_hook` (optional) — shell command to run

# Usage

Interactive mode (default):

```bash
python project-cli.py
```

Non-interactive examples:

* List projects:

```bash
python project-cli.py --list
```

* Download project #2 to default path:

```bash
python project-cli.py --get 2
```

* Dry-run download #2 (shows what would happen):

```bash
python project-cli.py --get 2 --dry-run
```

* Add project from CLI:

```bash
python project-cli.py --add "My Project" "https://github.com/owner/repo.git"
```

* Sync from central configured URL:

```bash
python project-cli.py --sync
```

* Run as daemon (long-running poller):

```bash
python project-cli.py --daemon
```

* Export audit log to CSV:

```bash
python project-cli.py --export-log mylog.csv
```

# Settings (what you can change)

Run `Settings` from the interactive menu or edit `~/.project_downloader/config.json`.
Key settings:

* `download_path` — default download root
* `source` — `local` or `remote`
* `projects_file` — path to local projects JSON
* `projects_url` — remote projects URL (if `source` == `remote`)
* `retries` — download retries
* `parallel` — (config only; current implementation provides the option but large parallel runs may need tuning)
* `bandwidth_limit` — bytes/sec (0 = unlimited)
* `proxy` — http/https proxy
* `github_token` — personal token (optional) for private repos / rate limit relief
* `validate_cache_ttl` — seconds for validation cache
* `daemon_poll_interval` — seconds between central sync polls
* `webhook_on_event` — POST URL to notify on download events

Note: In production mode (`production_config.json`) some advanced settings are locked and cannot be changed via the interactive UI.

# How to verify & test (step-by-step)

Follow these steps to verify the tool is installed and working. Each step has the expected result.

1. **Run the CLI**

```bash
python project-cli.py
```

Expected: You see a banner `PROJECTS DOWNLOADER` and the numbered menu.

2. **Install colorama (optional, Windows)**

```bash
pip install --user colorama
```

Expected: colored output in Windows terminals.

3. **Add a GitHub repo project (interactive)**

* Choose `Manage projects -> Add` and enter:

  * Name: `Requests (git)`
  * URL: `https://github.com/psf/requests.git`

Expected: Project added message.

4. **Add a direct ZIP download (interactive)**

* Name: `Requests ZIP`
* URL: `https://github.com/psf/requests/archive/refs/heads/main.zip`

Expected: Project added.

5. **List projects**

* Choose `Show & download projects`. You should see both entries and validation status (OK/INVALID).

6. **Dry-run download**

* Choose one project and select `Dry-run` when prompted.

Expected: The tool prints what it *would* do (git clone or file download) without changing disk.

7. **Actual download**

* Download the ZIP project.

Expected: File saved under `~/.project_downloader/downloads/Requests ZIP/` and extracted if it’s an archive. `downloads.log` receives a record.

8. **SHA256 mismatch handling**

* Add a project with `sha256` set to an incorrect value and attempt download.

Expected: The tool reports `Checksum mismatch!` and logs the failure.

9. **Git clone test**

* Download the git project.

Expected: `git` clones the repo into the download folder.

10. **Export audit log**

* Use Export audit log from menu or `--export-log`.

Expected: CSV file with timestamp, project, url, result, path.

11. **Validation run**

* Use `Validate links now` from menu.

Expected: A printed report of OK/INVALID and reasons.

12. **Production config test**

* Choose `Make production package` and confirm.

Expected: `production_config.json` created with `locked: true`. Re-open settings; locked options cannot be changed.

13. **Daemon test**

* Configure `central_url` in settings to a test JSON file URL and run `Run daemon`.

Expected: The tool periodically polls, syncs new projects, and logs activity.

14. **CLI scripting**

* Run a scripted download from another machine using `--get` and `--path`.

Expected: The file downloads non-interactively and prints progress.

# Troubleshooting (common issues)

* **Tool exits immediately without output** — Run `python -u project-cli.py` to see buffered errors and `echo %ERRORLEVEL%` on Windows. Use PowerShell / Windows Terminal instead of old `cmd.exe`.

* **You see `[35m` style sequences instead of colors** — install `colorama` on Windows or run inside Windows Terminal/PowerShell. Command: `pip install --user colorama`.

* **`git` clone fails** — ensure `git` is installed and available on PATH.

* **Downloads fail silently / time out** — check proxy settings or `projects.json` URL correctness. Use `Validate links now` to see HTTP error codes.

* **Extraction fails** — archive may be corrupted or unsupported. Check `downloads.log` for details.

* **Checksum mismatch** — verify the `sha256` value. Compute manually with `sha256sum` or PowerShell `Get-FileHash`.

* **Permissions issues writing to `~/.project_downloader`** — ensure you have write permissions to your home folder.

* **Long-running daemon not updating** — check `daemon_poll_interval` and ensure `central_url` points to a valid JSON list.

# Security notes (read this)

* The tool may run arbitrary shell `pre_hook`/`post_hook` commands — **only use hooks you trust**.
* When using `github_token` store a token with only the required scopes. Do **not** store highly privileged tokens in shared environments.
* Downloading and executing code from untrusted URLs is dangerous. Use checksums and secure sources.

# How to test automatically (recommended test sequence)

You can write a small script that:

1. Ensures a fresh config: move `~/.project_downloader` out of the way.
2. Creates a `projects.json` with two entries (git + zip URL shown above).
3. Runs `python project-cli.py --list` and asserts output contains both names.
4. Runs `python project-cli.py --get 2 --dry-run` and asserts `Dry-run` printed.
5. Runs `python project-cli.py --get 2` and checks that the download folder exists and `downloads.log` contains a recent entry.

Example (pseudo-batch):

```bash
mv ~/.project_downloader ~/.project_downloader.bak 2>/dev/null || true
mkdir -p ~/.project_downloader
cat > ~/.project_downloader/projects.json <<'JSON'
[
  {"name": "Requests (git)", "url": "https://github.com/psf/requests.git"},
  {"name": "Requests ZIP", "url": "https://github.com/psf/requests/archive/refs/heads/main.zip"}
]
JSON
python project-cli.py --list
python project-cli.py --get 2 --dry-run
python project-cli.py --get 2
# then assert files exist and logs updated
```

# Contributing

* Fork the repo, submit PRs. Keep changes small and documented. Add tests where possible.
* If you add features that require new Python packages, please make that optional and handle the missing dependency gracefully.

# License

MIT — see `LICENSE` in repo. Short version: do whatever you want, keep the notice.

# Contact & support

* GitHub: [XeoStudio](https://github.com/XeoStudio)
* Discord XeoStudio Owner: [Discord](https://discord.com/users/.9.m.)

# Final notes

This README is intentionally pragmatic. It documents how to run, verify, and test the tool. If you want, I can:

* add a `tests/` directory with automated pytest scripts that perform the above checks;
* add a `Makefile` to automate build + test + package steps;
* add CI config (GitHub Actions) to run the verification on each push.

Tell me which of those you want and I’ll add them next.
