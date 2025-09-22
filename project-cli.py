#!/usr/bin/env python3
"""
Project Downloader CLI - Single-file
Developer: Xeo Studio

Stable corrected runnable version. Fixed string literal issues and other bugs that caused silent exits.
"""

import json
import os
import sys
import shutil
import subprocess
import urllib.request
import urllib.error
import hashlib
import time
from urllib.parse import urlparse
from pathlib import Path
from typing import List, Dict, Optional
import csv
from concurrent.futures import ThreadPoolExecutor

# ------------------------- Color support (robust) -------------------------
_COLOR_SUPPORTED = False
try:
    import colorama
    colorama.init()
    _COLOR_SUPPORTED = True
except Exception:
    # try enabling VT on recent Windows
    if os.name == 'nt':
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.GetStdHandle(-11)
            mode = ctypes.c_uint()
            if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
                new_mode = mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING
                kernel32.SetConsoleMode(handle, new_mode)
                _COLOR_SUPPORTED = True
        except Exception:
            _COLOR_SUPPORTED = False
    else:
        _COLOR_SUPPORTED = True

# Use explicit \x1b sequences so the source file contains no literal control chars
_RESET = '\x1b[0m'
_COLORS = {
    'bold': '\x1b[1m',
    'cyan': '\x1b[36m',
    'green': '\x1b[32m',
    'red': '\x1b[31m',
    'yellow': '\x1b[33m',
    'magenta': '\x1b[35m',
    'blue': '\x1b[34m',
    'white': '\x1b[37m'
}


def color(text: str, name: str) -> str:
    if not _COLOR_SUPPORTED:
        return text
    code = _COLORS.get(name, '')
    return f"{code}{text}{_RESET}" if code else text


def style_bold(s: str) -> str:
    return color(s, 'bold')


def style_green(s: str) -> str:
    return color(s, 'green')


def style_red(s: str) -> str:
    return color(s, 'red')


def style_cyan(s: str) -> str:
    return color(s, 'cyan')


def clear_screen() -> None:
    try:
        if os.name == 'nt':
            os.system('cls')
        else:
            os.system('clear')
    except Exception:
        pass

# ------------------------- Header / Branding -------------------------
BANNER_WIDTH = 70


def center(text: str, width: int) -> str:
    text = text[:width]
    pad = max(0, width - len(text))
    left = pad // 2
    right = pad - left
    return ' ' * left + text + ' ' * right


def print_header() -> None:
    top = '╔' + '═' * BANNER_WIDTH + '╗'
    bot = '╚' + '═' * BANNER_WIDTH + '╝'
    title = 'PROJECTS DOWNLOADER'
    subtitle = 'By Xeo Studio  •  https://github.com/XeoStudio  •  @XeoStudio'

    print(color(top, 'magenta'))
    print(color('║' + center(title, BANNER_WIDTH) + '║', 'cyan'))
    print(color('║' + center(subtitle, BANNER_WIDTH) + '║', 'green'))
    print(color(bot, 'magenta'))
    print()

# ------------------------- Constants & Defaults -------------------------
HOME = Path.home()
APP_DIR = HOME / '.project_downloader'
APP_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_PATH = APP_DIR / 'config.json'
DEFAULT_PROJECTS_FILE = APP_DIR / 'projects.json'
LOG_FILE = APP_DIR / 'downloads.log'
VALIDATION_CACHE = APP_DIR / 'validation_cache.json'
PLUGINS_DIR = APP_DIR / 'plugins'
PLUGINS_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_CONFIG = {
    'download_path': str(APP_DIR / 'downloads'),
    'source': 'local',
    'projects_file': str(DEFAULT_PROJECTS_FILE),
    'projects_url': '',
    'language': 'en',
    'central_url': '',
    'locked': False,
    'retries': 2,
    'parallel': 3,
    'bandwidth_limit': 0,
    'proxy': '',
    'github_token': '',
    'validate_cache_ttl': 3600,
    'daemon_poll_interval': 300,
    'webhook_on_event': ''
}

# ------------------------- Config & Projects -------------------------

def load_config() -> Dict:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
        except Exception:
            print(style_red('Warning: failed to read config file; recreating defaults.'))
    cfg = DEFAULT_CONFIG.copy()
    save_config(cfg)
    return cfg


def save_config(cfg: Dict) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding='utf-8')


def load_projects(cfg: Dict) -> List[Dict]:
    source = cfg.get('source', 'local')
    if source == 'remote':
        url = cfg.get('projects_url')
        if not url:
            print(style_red('No remote projects URL in settings.'))
            return []
        try:
            with urllib.request.urlopen(url, timeout=15) as r:
                data = r.read()
                return json.loads(data.decode('utf-8'))
        except Exception as e:
            print(style_red(f'Failed to fetch remote projects: {e}'))
            return []
    else:
        path = Path(cfg.get('projects_file', str(DEFAULT_PROJECTS_FILE)))
        if not path.exists():
            path.write_text('[]', encoding='utf-8')
            return []
        try:
            return json.loads(path.read_text(encoding='utf-8'))
        except Exception as e:
            print(style_red(f'Failed to read local projects file: {e}'))
            return []


def save_local_projects(cfg: Dict, projects: List[Dict]) -> None:
    path = Path(cfg.get('projects_file', str(DEFAULT_PROJECTS_FILE)))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(projects, indent=2, ensure_ascii=False), encoding='utf-8')

# ------------------------- Validation cache -------------------------

def load_validation_cache() -> Dict:
    if VALIDATION_CACHE.exists():
        try:
            return json.loads(VALIDATION_CACHE.read_text(encoding='utf-8'))
        except Exception:
            return {}
    return {}


def save_validation_cache(cache: Dict) -> None:
    VALIDATION_CACHE.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding='utf-8')

# ------------------------- Logging -------------------------

def log_download(entry: Dict) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    record = {'timestamp': timestamp, **entry}
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
    except Exception:
        pass


def export_audit_csv(outpath: Path) -> None:
    if not LOG_FILE.exists():
        print(style_red('No log to export.'))
        return
    try:
        with open(LOG_FILE, 'r', encoding='utf-8') as r, open(outpath, 'w', encoding='utf-8', newline='') as w:
            writer = csv.writer(w)
            writer.writerow(['timestamp', 'project', 'url', 'result', 'path', 'info'])
            for line in r:
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                writer.writerow([obj.get('timestamp'), obj.get('project'), obj.get('url'), obj.get('result'), obj.get('path'), obj.get('info', '')])
        print(style_green(f'Exported audit log to {outpath}'))
    except Exception as e:
        print(style_red(f'Export failed: {e}'))

# ------------------------- Helpers: checksums, extraction, file type -------------------------

def sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def is_archive_file(path: Path) -> bool:
    return str(path).lower().endswith(('.zip', '.tar', '.tar.gz', '.tgz', '.tar.bz2'))


def extract_archive(path: Path, dest_folder: Path) -> bool:
    try:
        dest_folder.mkdir(parents=True, exist_ok=True)
        shutil.unpack_archive(str(path), extract_dir=str(dest_folder))
        return True
    except shutil.ReadError:
        print(style_red('Not a supported archive or archive is corrupted.'))
    except Exception as e:
        print(style_red(f'Extraction failed: {e}'))
    return False

# ------------------------- Plugin loader (simple) -------------------------

def load_plugins() -> List:
    sys.path.insert(0, str(PLUGINS_DIR))
    plugins = []
    for p in PLUGINS_DIR.glob('*.py'):
        name = p.stem
        try:
            mod = __import__(name)
            if hasattr(mod, 'fetch'):
                plugins.append(mod)
        except Exception:
            continue
    return plugins

# ------------------------- Network helpers & validation -------------------------

def make_opener(cfg: Dict):
    handlers = []
    proxy = cfg.get('proxy')
    if proxy:
        handlers.append(urllib.request.ProxyHandler({'http': proxy, 'https': proxy}))
    opener = urllib.request.build_opener(*handlers)
    token = cfg.get('github_token')
    if token:
        opener.addheaders = [('User-Agent', 'ProjectDownloader/1.0'), ('Authorization', f'token {token}')]
    else:
        opener.addheaders = [('User-Agent', 'ProjectDownloader/1.0')]
    return opener


def probe_url(opener, url: str, timeout: int = 10) -> Dict:
    """Return dict: {'ok': bool, 'type': 'github'|'file'|'unknown', 'code': int or None, 'reason': str}"""
    try:
        req = urllib.request.Request(url, method='HEAD')
        with opener.open(req, timeout=timeout) as r:
            headers = r.info()
            code = getattr(r, 'status', None) or getattr(r, 'getcode', lambda: None)()
            cdisp = headers.get('Content-Disposition')
            ctype = headers.get('Content-Type', '')
            netloc = urlparse(url).netloc.lower()
            if 'github.com' in netloc and not url.rstrip().endswith(('.zip', '.tar.gz')):
                return {'ok': True, 'type': 'github', 'code': code, 'reason': 'GitHub repo (HEAD ok)'}
            if cdisp or ctype.startswith(('application/', 'binary/', 'application/octet-stream', 'application/zip')):
                return {'ok': True, 'type': 'file', 'code': code, 'reason': f'Content-Type: {ctype}'}
            return {'ok': True, 'type': 'unknown', 'code': code, 'reason': f'Content-Type: {ctype}'}
    except urllib.error.HTTPError as e:
        return {'ok': False, 'type': 'error', 'code': e.code, 'reason': str(e)}
    except Exception:
        try:
            req = urllib.request.Request(url, method='GET')
            with opener.open(req, timeout=timeout) as r:
                headers = r.info()
                cdisp = headers.get('Content-Disposition')
                ctype = headers.get('Content-Type', '')
                if cdisp or ctype.startswith(('application/', 'binary/', 'application/octet-stream', 'application/zip')):
                    return {'ok': True, 'type': 'file', 'code': None, 'reason': f'Content-Type: {ctype}'}
                return {'ok': True, 'type': 'unknown', 'code': None, 'reason': f'Content-Type: {ctype}'}
        except Exception as e2:
            return {'ok': False, 'type': 'error', 'code': None, 'reason': str(e2)}

# ------------------------- Download logic (with resume, throttling, hooks) -------------------------

def is_git_url(url: str) -> bool:
    try:
        return 'github.com' in urlparse(url).netloc and (url.strip().endswith('.git') or ('/blob/' not in url and '/releases/' not in url))
    except Exception:
        return False


def run_git_clone(url: str, dest: Path, cfg: Dict) -> bool:
    try:
        print(f'Running git clone {url} -> {dest}')
        env = os.environ.copy()
        token = cfg.get('github_token')
        if token and 'github.com' in url:
            if url.startswith('https://'):
                url_with_token = url.replace('https://', f'https://{token}@')
            else:
                url_with_token = url
            subprocess.check_call(['git', 'clone', url_with_token, str(dest)], env=env)
        else:
            subprocess.check_call(['git', 'clone', url, str(dest)], env=env)
        return True
    except FileNotFoundError:
        print(style_red('git is not installed or not in PATH.'))
        return False
    except subprocess.CalledProcessError as e:
        print(style_red(f'git clone failed: {e}'))
        return False


def download_http(url: str, dest: Path, cfg: Dict, opener=None, resume=True) -> bool:
    if opener is None:
        opener = make_opener(cfg)
    attempt = 0
    retries = cfg.get('retries', 2)
    bandwidth_limit = cfg.get('bandwidth_limit', 0)
    while attempt <= retries:
        try:
            headers = {}
            mode = 'wb'
            existing = dest.exists()
            existing_size = dest.stat().st_size if existing else 0
            if resume and existing_size > 0:
                headers['Range'] = f'bytes={existing_size}-'
                mode = 'ab'
            req = urllib.request.Request(url, headers=headers)
            with opener.open(req, timeout=30) as resp:
                total = resp.getheader('Content-Length')
                if total is not None:
                    try:
                        total = int(total) + (existing_size if 'Range' in headers else 0)
                    except Exception:
                        total = None
                chunk_size = 8192
                dest.parent.mkdir(parents=True, exist_ok=True)
                with open(dest, mode) as f:
                    downloaded = existing_size
                    last_print = 0
                    while True:
                        chunk = resp.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if bandwidth_limit and bandwidth_limit > 0:
                            sleep_time = len(chunk) / float(bandwidth_limit)
                            if sleep_time > 0:
                                time.sleep(sleep_time)
                        if total:
                            now = time.time()
                            if now - last_print > 0.5:
                                percent = downloaded * 100 // total
                                # carriage return without breaking string literals
                                print(f"Downloading... {percent}% ({downloaded}/{total} bytes)", end='\r')
                                last_print = now
                if total:
                    print()
            return True
        except Exception as e:
            attempt += 1
            print(style_red(f'Download attempt {attempt} failed: {e}'))
            if attempt > retries:
                return False
            time.sleep(1)
    return False


def prepare_target_for_download(name: str, download_root: Path, url: str) -> Path:
    safe_name = ''.join(c for c in name if c.isalnum() or c in (' ', '-', '_')).rstrip()
    parsed = urlparse(url)
    filename = os.path.basename(parsed.path) or (safe_name + '.download')
    folder = download_root / safe_name
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / filename
    i = 1
    while dest.exists():
        dest = folder / (dest.stem + f'_{i}' + dest.suffix)
        i += 1
    return dest


def run_hooks(project: Dict, stage: str) -> bool:
    cmd = project.get(f'{stage}_hook')
    if not cmd:
        return True
    try:
        print(f'Running {stage}-hook: {cmd}')
        subprocess.check_call(cmd, shell=True)
        return True
    except Exception as e:
        print(style_red(f'Hook {stage} failed: {e}'))
        return False


def notify_webhook(cfg: Dict, payload: Dict) -> bool:
    url = cfg.get('webhook_on_event')
    if not url:
        return False
    try:
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'}, method='POST')
        opener = make_opener(cfg)
        with opener.open(req, timeout=10) as r:
            return True
    except Exception:
        return False


def download_project_item(project: Dict, cfg: Dict, custom_path: Optional[str] = None, dry_run: bool = False) -> bool:
    url = project.get('url') or project.get('link') or ''
    name = project.get('name') or project.get('title') or 'project'
    expected_sha256 = project.get('sha256')
    if not url:
        print(style_red('Project has no download URL.'))
        return False
    download_root = Path(custom_path) if custom_path else Path(cfg.get('download_path', DEFAULT_CONFIG['download_path']))
    download_root.mkdir(parents=True, exist_ok=True)

    if not run_hooks(project, 'pre'):
        log_download({'project': name, 'url': url, 'result': 'pre_hook_failed', 'path': ''})
        notify_webhook(cfg, {'project': name, 'url': url, 'result': 'pre_hook_failed'})
        return False

    opener = make_opener(cfg)
    probe = probe_url(opener, url)
    if not probe.get('ok'):
        print(style_red(f"URL not valid: {probe.get('reason')}"))
        log_download({'project': name, 'url': url, 'result': 'invalid_url', 'path': '', 'info': probe.get('reason')})
        notify_webhook(cfg, {'project': name, 'url': url, 'result': 'invalid_url', 'info': probe.get('reason')})
        return False

    if dry_run:
        print(style_green(f"Dry-run: would download {name} from {url} as {probe.get('type')}"))
        return True

    if probe.get('type') == 'github' or is_git_url(url):
        target = download_root / name
        if target.exists():
            target = Path(str(target) + '_new')
        ok = run_git_clone(url, target, cfg)
        log_download({'project': name, 'url': url, 'result': 'git_clone' if ok else 'git_failed', 'path': str(target)})
        notify_webhook(cfg, {'project': name, 'url': url, 'result': 'git_clone' if ok else 'git_failed', 'path': str(target)})
        if ok:
            run_hooks(project, 'post')
        return ok
    else:
        dest = prepare_target_for_download(name, download_root, url)
        ok = download_http(url, dest, cfg, opener=opener, resume=True)
        if not ok:
            log_download({'project': name, 'url': url, 'result': 'download_failed', 'path': str(dest)})
            notify_webhook(cfg, {'project': name, 'url': url, 'result': 'download_failed'})
            return False
        if expected_sha256:
            actual = sha256_of_file(dest)
            if actual.lower() != expected_sha256.lower():
                print(style_red('Checksum mismatch!'))
                print(style_red(f'Expected: {expected_sha256}'))
                print(style_red(f'Actual:   {actual}'))
                log_download({'project': name, 'url': url, 'result': 'checksum_mismatch', 'path': str(dest)})
                notify_webhook(cfg, {'project': name, 'url': url, 'result': 'checksum_mismatch'})
                return False
            else:
                print(style_green('Checksum OK.'))
        if is_archive_file(dest):
            extracted_to = dest.parent / (dest.stem + '_extracted')
            ok2 = extract_archive(dest, extracted_to)
            if ok2:
                print(style_green(f'Extracted to {extracted_to}'))
                log_download({'project': name, 'url': url, 'result': 'download_and_extracted', 'path': str(extracted_to)})
                notify_webhook(cfg, {'project': name, 'url': url, 'result': 'download_and_extracted', 'path': str(extracted_to)})
            else:
                log_download({'project': name, 'url': url, 'result': 'download_but_extract_failed', 'path': str(dest)})
                notify_webhook(cfg, {'project': name, 'url': url, 'result': 'download_but_extract_failed', 'path': str(dest)})
            run_hooks(project, 'post')
            return ok2
        print(style_green(f'Download saved to {dest}'))
        log_download({'project': name, 'url': url, 'result': 'downloaded', 'path': str(dest)})
        notify_webhook(cfg, {'project': name, 'url': url, 'result': 'downloaded', 'path': str(dest)})
        run_hooks(project, 'post')
        return True

# ------------------------- Management: add / edit / delete / search -------------------------

def print_projects(projects: List[Dict], cfg: Dict) -> None:
    if not projects:
        print('No projects available.')
        return
    cache = load_validation_cache()
    ttl = cfg.get('validate_cache_ttl', 3600)
    opener = make_opener(cfg)
    print('\nProjects list:')
    for idx, p in enumerate(projects, start=1):
        name = p.get('name') or 'unnamed'
        url = p.get('url') or ''
        note = ''
        if p.get('sha256'):
            note = ' [sha256]'
        cached = cache.get(url)
        status = '[Unknown]'
        ttype = '[Unknown]'
        if cached and (time.time() - cached.get('ts', 0) < ttl):
            status = '[OK]' if cached.get('ok') else '[INVALID]'
            ttype = f"[{cached.get('type').upper()}]"
        else:
            probe = probe_url(opener, url)
            cache[url] = {'ok': probe.get('ok'), 'type': probe.get('type'), 'reason': probe.get('reason'), 'ts': time.time()}
            status = '[OK]' if probe.get('ok') else '[INVALID]'
            ttype = f"[{probe.get('type').upper()}]"
        color_status = status if status == '[OK]' else style_red(status)
        print(f"{idx}. {name}{note} {ttype} {color_status}\n    -> {url}")
    save_validation_cache(cache)


def add_project(cfg: Dict) -> None:
    if cfg.get('locked'):
        print(style_red('Production mode enabled. Cannot add projects locally.'))
        return
    projects = load_projects(cfg)
    name = input('Project name: ').strip()
    url = input('Download URL (GitHub repo or direct file): ').strip()
    sha = input('Optional SHA256 checksum (leave empty if none): ').strip()
    tags = input('Optional tags (comma separated): ').strip()
    if not name or not url:
        print(style_red('Name or URL invalid.'))
        return
    opener = make_opener(cfg)
    probe = probe_url(opener, url)
    if not probe.get('ok'):
        print(style_red(f'URL validation failed: {probe.get("reason")}'))
        return
    p = {'name': name, 'url': url}
    if sha:
        p['sha256'] = sha
    if tags:
        p['tags'] = [t.strip() for t in tags.split(',') if t.strip()]
    projects.append(p)
    save_local_projects(cfg, projects)
    print(style_green('Project added.'))


def edit_project(cfg: Dict) -> None:
    if cfg.get('locked'):
        print(style_red('Production mode enabled. Cannot edit projects.'))
        return
    projects = load_projects(cfg)
    print_projects(projects, cfg)
    sel = input('Enter project number to edit (or ENTER to cancel): ').strip()
    if not sel:
        return
    try:
        idx = int(sel) - 1
        if idx < 0 or idx >= len(projects):
            print(style_red('Invalid selection.'))
            return
    except ValueError:
        print(style_red('Enter a valid number.'))
        return
    p = projects[idx]
    print(f"Current name: {p.get('name')}")
    new_name = input('New name (ENTER to keep): ').strip()
    if new_name:
        p['name'] = new_name
    print(f"Current URL: {p.get('url')}")
    new_url = input('New URL (ENTER to keep): ').strip()
    if new_url:
        opener = make_opener(cfg)
        probe = probe_url(opener, new_url)
        if not probe.get('ok'):
            print(style_red(f'URL validation failed: {probe.get("reason")}'))
            return
        p['url'] = new_url
    new_sha = input('New SHA256 (ENTER to keep): ').strip()
    if new_sha:
        p['sha256'] = new_sha
    new_tags = input('New tags (comma separated, ENTER to keep): ').strip()
    if new_tags:
        p['tags'] = [t.strip() for t in new_tags.split(',') if t.strip()]
    projects[idx] = p
    save_local_projects(cfg, projects)
    print(style_green('Project updated.'))


def delete_project(cfg: Dict) -> None:
    if cfg.get('locked'):
        print(style_red('Production mode enabled. Cannot delete projects.'))
        return
    projects = load_projects(cfg)
    print_projects(projects, cfg)
    sel = input('Enter project number to delete (or ENTER to cancel): ').strip()
    if not sel:
        return
    try:
        idx = int(sel) - 1
        if idx < 0 or idx >= len(projects):
            print(style_red('Invalid selection.'))
            return
    except ValueError:
        print(style_red('Enter a valid number.'))
        return
    confirm = input('Type YES to confirm deletion: ').strip()
    if confirm != 'YES':
        print('Cancelled.')
        return
    removed = projects.pop(idx)
    save_local_projects(cfg, projects)
    print(style_green(f"Removed project: {removed.get('name')}"))


def search_projects(cfg: Dict) -> None:
    projects = load_projects(cfg)
    q = input('Search query (name/tag): ').strip().lower()
    results = []
    for idx, p in enumerate(projects, start=1):
        if q in (p.get('name') or '').lower() or any(q in t.lower() for t in p.get('tags', [])):
            results.append((idx, p))
    if not results:
        print('No matches.')
        return
    for idx, p in results:
        print(f"{idx}. {p.get('name')} -> {p.get('url')}")

# ------------------------- Validation utilities -------------------------


def validate_all_links(cfg: Dict, detailed: bool = False) -> List:
    projects = load_projects(cfg)
    opener = make_opener(cfg)
    cache = load_validation_cache()
    report = []
    for p in projects:
        url = p.get('url')
        if not url:
            report.append((p.get('name'), url, False, 'no url'))
            continue
        probe = probe_url(opener, url)
        cache[url] = {'ok': probe.get('ok'), 'type': probe.get('type'), 'reason': probe.get('reason'), 'ts': time.time()}
        report.append((p.get('name'), url, probe.get('ok'), probe.get('reason')))
    save_validation_cache(cache)
    if detailed:
        for r in report:
            name, url, ok, reason = r
            print(f"{name} -> {url} : {'OK' if ok else 'INVALID'} ({reason})")
    return report

# ------------------------- Daemon (basic scheduler) -------------------------

def run_daemon(cfg: Dict) -> None:
    print(style_green('Daemon mode started. Polling central URL for updates.'))
    interval = cfg.get('daemon_poll_interval', 300)
    try:
        while True:
            if cfg.get('central_url'):
                try:
                    sync_from_central(cfg)
                except Exception as e:
                    print(style_red(f'Central sync failed in daemon: {e}'))
            time.sleep(interval)
    except KeyboardInterrupt:
        print('Daemon stopped by user.')

# ------------------------- Menus & CLI -------------------------

def interactive_menu() -> None:
    cfg = load_config()
    while True:
        clear_screen()
        print_header()
        print(style_bold('1) Show & download projects'))
        print(style_bold('2) Manage projects (add/edit/delete/search)'))
        print(style_bold('3) Settings'))
        print(style_bold('4) Validate links now'))
        print(style_bold('5) Sync from central'))
        print(style_bold('6) Export audit log (CSV)'))
        print(style_bold('7) Run daemon (poll central)'))
        print(style_bold('0) Exit'))
        choice = input('\nChoose a number: ').strip()
        if choice == '1':
            projects = load_projects(cfg)
            print_projects(projects, cfg)
            if not projects:
                input('Press Enter to continue...')
                continue
            sel = input('Enter project number to download (or ENTER to return): ').strip()
            if not sel:
                continue
            try:
                idx = int(sel) - 1
                if idx < 0 or idx >= len(projects):
                    print(style_red('Invalid selection.'))
                    time.sleep(1)
                    continue
            except ValueError:
                print(style_red('Enter a valid number.'))
                time.sleep(1)
                continue
            project = projects[idx]
            use_default = input('Download to default path from settings? (Y/n): ').strip().lower()
            if use_default in ('', 'y', 'yes'):
                custom = None
            else:
                custom = input('Enter full folder path to download into: ').strip()
                if not custom:
                    custom = None
            dry = input('Dry-run? (shows actions but does not download) (y/N): ').strip().lower()
            dry_run = (dry == 'y')
            ok = download_project_item(project, cfg, custom_path=custom, dry_run=dry_run)
            if ok:
                print(style_green('Download completed successfully.'))
            else:
                print(style_red('Download failed.'))
            input('Press Enter to continue...')
        elif choice == '2':
            print(style_bold('\nManage Projects:'))
            print('1) Add')
            print('2) Edit')
            print('3) Delete')
            print('4) Search')
            print('0) Back')
            c = input('Choose: ').strip()
            if c == '1':
                add_project(cfg)
            elif c == '2':
                edit_project(cfg)
            elif c == '3':
                delete_project(cfg)
            elif c == '4':
                search_projects(cfg)
            else:
                pass
            input('Press Enter to continue...')
        elif choice == '3':
            settings_menu(cfg)
        elif choice == '4':
            print('Validating links...')
            validate_all_links(cfg, detailed=True)
            input('Press Enter to continue...')
        elif choice == '5':
            sync_from_central(cfg)
            input('Press Enter to continue...')
        elif choice == '6':
            out = input('Enter CSV path (default: downloads_audit.csv): ').strip() or 'downloads_audit.csv'
            export_audit_csv(Path(out))
            input('Press Enter to continue...')
        elif choice == '7':
            print('Starting daemon (CTRL+C to stop)...')
            run_daemon(cfg)
        elif choice == '0':
            print('Goodbye.')
            break
        else:
            print(style_red('Unknown selection.'))
            time.sleep(1)


def settings_menu(cfg: Dict) -> None:
    if cfg.get('locked'):
        print(style_red('Production mode enabled. Advanced settings are locked.'))
    while True:
        print('\n----- Settings -----')
        print(f"1) Download path: {cfg.get('download_path')}")
        print(f"2) Projects source: {cfg.get('source')} ({'remote='+cfg.get('projects_url') if cfg.get('source')=='remote' else 'file='+cfg.get('projects_file')})")
        print(f"3) Parallel downloads: {cfg.get('parallel')}")
        print(f"4) Bandwidth limit (bytes/sec, 0=unlimited): {cfg.get('bandwidth_limit')}")
        print(f"5) Proxy: {cfg.get('proxy') or '(not set)'}")
        print(f"6) GitHub token: {'(set)' if cfg.get('github_token') else '(not set)'}")
        print(f"7) Validate cache TTL (s): {cfg.get('validate_cache_ttl')}")
        print(f"8) Daemon poll interval (s): {cfg.get('daemon_poll_interval')}")
        print(f"9) Webhook URL for events: {cfg.get('webhook_on_event') or '(not set)'}")
        print('0) Back')
        choice = input('Choose setting to edit (or 0 to return): ').strip()
        if choice == '0':
            save_config(cfg)
            return
        if cfg.get('locked') and choice in ('2',):
            print(style_red('This option is locked in production mode.'))
            continue
        if choice == '1':
            new = input('Enter new download path: ').strip()
            if new:
                cfg['download_path'] = new
                print(style_green('Download path updated.'))
        elif choice == '2':
            new = input('Choose source (local/remote): ').strip()
            if new in ('local', 'remote'):
                cfg['source'] = new
                if new == 'remote':
                    url = input('Enter full projects.json URL: ').strip()
                    cfg['projects_url'] = url
                else:
                    filep = input(f'Enter local projects file path [{cfg.get("projects_file")}]: ').strip()
                    if filep:
                        cfg['projects_file'] = filep
        elif choice == '3':
            new = input('Parallel downloads (number): ').strip()
            try:
                cfg['parallel'] = int(new)
            except Exception:
                print(style_red('Invalid number.'))
        elif choice == '4':
            new = input('Bandwidth limit (bytes/sec, 0=unlimited): ').strip()
            try:
                cfg['bandwidth_limit'] = int(new)
            except Exception:
                print(style_red('Invalid number.'))
        elif choice == '5':
            new = input('Proxy (e.g. http://127.0.0.1:8080) or empty to unset: ').strip()
            cfg['proxy'] = new
        elif choice == '6':
            new = input('GitHub token (stored in config): ').strip()
            cfg['github_token'] = new
        elif choice == '7':
            new = input('Validate cache TTL seconds: ').strip()
            try:
                cfg['validate_cache_ttl'] = int(new)
            except Exception:
                print(style_red('Invalid number.'))
        elif choice == '8':
            new = input('Daemon poll interval seconds: ').strip()
            try:
                cfg['daemon_poll_interval'] = int(new)
            except Exception:
                print(style_red('Invalid number.'))
        elif choice == '9':
            new = input('Webhook URL for events (empty to unset): ').strip()
            cfg['webhook_on_event'] = new
        else:
            print(style_red('Unknown option.'))


def sync_from_central(cfg: Dict) -> None:
    central = cfg.get('central_url')
    if not central:
        print(style_red('Central URL not configured in settings.'))
        return
    try:
        opener = make_opener(cfg)
        with opener.open(central, timeout=15) as r:
            data = json.loads(r.read().decode('utf-8'))
            if not isinstance(data, list):
                print(style_red('Central data is not a list of projects.'))
                return
            local = load_projects(cfg)
            local_urls = {p.get('url') for p in local}
            added = 0
            for item in data:
                if item.get('url') not in local_urls:
                    local.append(item)
                    added += 1
            save_local_projects(cfg, local)
            print(style_green(f'Sync complete. Added {added} projects.'))
    except Exception as e:
        print(style_red(f'Sync failed: {e}'))

# ------------------------- CLI flags (non-interactive) -------------------------

def list_projects_cli(cfg: Dict) -> None:
    projects = load_projects(cfg)
    print_projects(projects, cfg)


def get_project_cli(cfg: Dict, idx: int, custom_path: Optional[str] = None, dry_run: bool = False) -> None:
    projects = load_projects(cfg)
    if idx <= 0 or idx > len(projects):
        print(style_red('Project number out of range.'))
        return
    project = projects[idx - 1]
    ok = download_project_item(project, cfg, custom_path=custom_path, dry_run=dry_run)
    if ok:
        print(style_green('Download succeeded.'))
    else:
        print(style_red('Download failed.'))


def add_project_cli(cfg: Dict, name: str, url: str, sha: Optional[str] = None) -> None:
    projects = load_projects(cfg)
    p = {'name': name, 'url': url}
    if sha:
        p['sha256'] = sha
    projects.append(p)
    save_local_projects(cfg, projects)
    print(style_green('Project added (CLI).'))

# ------------------------- Entry point & arg parsing -------------------------

def print_usage() -> None:
    print('Usage: python project_cli.py [--list] [--get N] [--add "Name" "URL" [sha256]] [--sync] [--daemon] [--dry-run] [--export-log path]')


def main() -> None:
    cfg = load_config()
    args = sys.argv[1:]
    if not args:
        interactive_menu()
        return
    if '--help' in args or '-h' in args:
        print_usage()
        return
    if '--list' in args:
        list_projects_cli(cfg)
        return
    if '--get' in args:
        try:
            i = args.index('--get')
            n = int(args[i + 1])
        except Exception:
            print('Use --get N where N is project number.')
            return
    if '--add' in args:
        try:
            i = args.index('--add')
            name = args[i + 1]
            url = args[i + 2]
            sha = args[i + 3] if len(args) > i + 3 else None
            add_project_cli(cfg, name, url, sha)
        except Exception:
            print('Usage: --add "Name" "URL" [sha256]')
        return
    if '--sync' in args:
        sync_from_central(cfg)
        return
    if '--daemon' in args:
        run_daemon(cfg)
        return
    if '--export-log' in args:
        try:
            i = args.index('--export-log')
            out = args[i + 1]
            export_audit_csv(Path(out))
        except Exception:
            print('Usage: --export-log <path>')
        return
    print('Unknown arguments. Entering interactive mode...')
    interactive_menu()


if __name__ == '__main__':
    main()
