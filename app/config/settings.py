import os
import sys
from pathlib import Path

APP_NAME = "ChickenWholesale"
APP_TITLE = "Chicken Wholesale Shop Management"
APP_VERSION = "1.0.0"

def get_user_data_dir() -> Path:
    """
    Returns cross-platform directory for user application data.
    macOS: ~/Library/Application Support/ChickenWholesale
    Windows: %APPDATA%\ChickenWholesale
    Linux: ~/.local/share/ChickenWholesale
    """
    home = Path.home()
    if sys.platform == "win32":
        app_data = Path(os.getenv("APPDATA", home / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        app_data = home / "Library" / "Application Support"
    else:
        app_data = Path(os.getenv("XDG_DATA_HOME", home / ".local" / "share"))
    
    target_dir = app_data / APP_NAME
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir

def get_db_path() -> Path:
    """Returns absolute path to the SQLite database file."""
    env_db = os.getenv("CHICKEN_WHOLESALE_DB_PATH")
    if env_db:
        path = Path(env_db)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path
    return get_user_data_dir() / "chicken_wholesale.db"

def get_database_uri(db_path: Path | None = None) -> str:
    """Returns SQLite database URI string for SQLAlchemy."""
    target_path = db_path or get_db_path()
    return f"sqlite:///{target_path.as_posix()}"
