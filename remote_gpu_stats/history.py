import json
import os
from datetime import datetime

MAX_SNAPSHOTS = 50

FILENAME_PREFIX = "snapshot-"
FILENAME_SUFFIX = ".json"


def history_dir() -> str:
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.path.join(
            os.path.expanduser("~"), "AppData", "Local"
        )
    else:
        base = os.environ.get("XDG_CACHE_HOME") or os.path.join(
            os.path.expanduser("~"), ".cache"
        )
    return os.path.join(base, "remote-gpu-stats")


def _snapshot_paths() -> list[str]:
    directory = history_dir()
    if not os.path.isdir(directory):
        return []
    paths = [
        os.path.join(directory, name)
        for name in os.listdir(directory)
        if name.startswith(FILENAME_PREFIX) and name.endswith(FILENAME_SUFFIX)
    ]
    # Filenames embed a sortable timestamp; newest first.
    paths.sort(reverse=True)
    return paths


def save_snapshot(results: dict, username: str) -> str | None:
    """Persist a successful collection run. Returns the snapshot path, or
    None if nothing was saved. Never raises: a cache failure must not break
    a run that already succeeded."""
    if not results:
        return None
    try:
        directory = history_dir()
        os.makedirs(directory, exist_ok=True)
        now = datetime.now().astimezone()
        base = now.strftime(FILENAME_PREFIX + "%Y%m%d-%H%M%S")
        filename = base + FILENAME_SUFFIX
        path = os.path.join(directory, filename)
        # Two runs landing in the same second must not overwrite each other.
        suffix = 2
        while os.path.exists(path):
            path = os.path.join(directory, f"{base}-{suffix}{FILENAME_SUFFIX}")
            suffix += 1
        envelope = {
            "saved_at": now.isoformat(timespec="seconds"),
            "username": username,
            "host_count": len(results),
            "results": results,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(envelope, f)
        _prune(directory)
        return path
    except OSError as e:
        print(f"warning: could not save snapshot: {e}")
        return None


def _prune(directory: str) -> None:
    for path in _snapshot_paths()[MAX_SNAPSHOTS:]:
        try:
            os.remove(path)
        except OSError:
            pass


def load_snapshot(path: str) -> dict:
    """Load a snapshot envelope. Raises OSError/ValueError/KeyError on
    missing or corrupt files."""
    with open(path, encoding="utf-8") as f:
        envelope = json.load(f)
    envelope["results"]  # KeyError if corrupt
    return envelope


def _parse_saved_at(envelope: dict) -> datetime | None:
    raw = envelope.get("saved_at")
    if not raw:
        return None
    try:
        saved_at = datetime.fromisoformat(raw)
        return saved_at.astimezone() if saved_at.tzinfo else saved_at
    except ValueError:
        return None


def format_age(saved_at: datetime | None, now: datetime | None = None) -> str:
    if saved_at is None:
        return "unknown"
    now = now or datetime.now().astimezone()
    if saved_at.tzinfo is None:
        saved_at = saved_at.astimezone()
    seconds = max(0, int((now - saved_at).total_seconds()))
    if seconds < 60:
        return f"{seconds}s ago"
    if seconds < 3600:
        return f"{seconds // 60}m ago"
    if seconds < 86400:
        return f"{seconds // 3600}h ago"
    return f"{seconds // 86400}d ago"


def list_snapshots() -> list[dict]:
    """Newest-first list of snapshot metadata. Corrupt files are skipped."""
    snapshots = []
    for path in _snapshot_paths():
        try:
            envelope = load_snapshot(path)
        except (OSError, ValueError, KeyError):
            continue
        saved_at = _parse_saved_at(envelope)
        snapshots.append(
            {
                "path": path,
                "saved_at": saved_at,
                "age": format_age(saved_at),
                "username": envelope.get("username", "?"),
                "host_count": envelope.get("host_count", len(envelope["results"])),
            }
        )
    return snapshots
