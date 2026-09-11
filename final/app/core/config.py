import os
import shutil
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]

# Project-local .env may contain non-sensitive development defaults only.
load_dotenv(BASE_DIR / ".env", override=False)


def _external_secrets_path() -> Path:
    """Secrets live outside the project so ZIP replacements/uploads do not expose them."""
    if os.name == "nt":
        base = Path(os.getenv("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
        return base / "B2B_SaaS" / "secrets" / "credentials.env"
    return Path.home() / ".config" / "B2B_SaaS" / "secrets" / "credentials.env"


EXTERNAL_SECRETS_FILE = _external_secrets_path()
if EXTERNAL_SECRETS_FILE.exists():
    # Machine-local credentials take precedence over project defaults.
    load_dotenv(EXTERNAL_SECRETS_FILE, override=True)

DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
LEGACY_SQLITE_DB_PATH = DATA_DIR / "b2b_v1.sqlite3"


def _default_persistent_db_path() -> Path:
    """Return a user-specific DB path that survives project ZIP replacement."""
    if os.name == "nt":
        base = Path(os.getenv("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
        return base / "B2B_SaaS" / "data" / "b2b_v1.sqlite3"
    return Path.home() / ".local" / "share" / "B2B_SaaS" / "data" / "b2b_v1.sqlite3"


def _resolve_sqlite_db_path() -> Path:
    configured = os.getenv("SQLITE_DB_PATH", "").strip()
    if configured:
        path = Path(configured).expanduser()
        if not path.is_absolute():
            path = (BASE_DIR / path).resolve()
        return path
    return _default_persistent_db_path()


SQLITE_DB_FILE = _resolve_sqlite_db_path()
SQLITE_DB_FILE.parent.mkdir(parents=True, exist_ok=True)

# V1 -> persistent storage migration. Only copy once; never overwrite an existing
# persistent database. This keeps user accounts/data when project ZIPs are replaced.
if SQLITE_DB_FILE != LEGACY_SQLITE_DB_PATH and not SQLITE_DB_FILE.exists() and LEGACY_SQLITE_DB_PATH.exists():
    shutil.copy2(LEGACY_SQLITE_DB_PATH, SQLITE_DB_FILE)

SQLITE_DB_PATH = str(SQLITE_DB_FILE)
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{SQLITE_DB_FILE}")
SECRET_KEY = os.getenv("SECRET_KEY", "b2b-v1-local-secret-key")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
