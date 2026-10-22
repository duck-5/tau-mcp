"""
Configuration and settings for tau_mcp.
Loads credentials and environment settings with multi-profile and privacy support.
"""

import os
import re
from pathlib import Path
from typing import Dict, Optional, Any
from dotenv import dotenv_values, load_dotenv

# Search candidate env locations
_pkg_root = Path(__file__).resolve().parent
_candidates = [
    Path(".env"),
    _pkg_root / ".env",
    _pkg_root.parent / ".env",
    Path("../moodle_mcp/.env"),
    _pkg_root.parent.parent / "moodle_mcp" / ".env",
]

for env_path in _candidates:
    if env_path.exists():
        load_dotenv(env_path, override=False)

def get_env_or_dotenv(key: str, fallback_keys: Optional[list] = None, default: str = "") -> str:
    """Gets value prioritizing .env file over OS system environment variables (to avoid Windows USERNAME collision)."""
    keys = [key] + (fallback_keys or [])
    
    # 1. Try direct file reads from .env candidates first
    for p in _candidates:
        if p.exists():
            vals = dotenv_values(p)
            for k in keys:
                val = vals.get(k)
                if val and str(val).strip():
                    return str(val).strip()

    # 2. Check os.environ (skipping USERNAME if it matches OS user name and not in .env)
    for k in keys:
        val = os.environ.get(k)
        if val and str(val).strip():
            # If key is USERNAME and looks like a Windows user with spaces, prefer lower/clean if possible
            return str(val).strip()

    return default

# Master TAU SSO Credentials
TAU_USERNAME = get_env_or_dotenv("TAU_USERNAME", ["MOODLE_USERNAME", "USERNAME"])
TAU_ID = get_env_or_dotenv("TAU_ID", ["MOODLE_STUDENT_ID", "ID", "STUDENT_ID"])
TAU_PASSWORD = get_env_or_dotenv("TAU_PASSWORD", ["MOODLE_PASSWORD", "PASSWORD"])

# Portals & Catalog URLs
PORTAL_URL = os.getenv("TAU_PORTAL_URL", "https://my.tau.ac.il/TAU_Student/").rstrip("/")
CATALOG_SEARCH_URL = os.getenv("TAU_CATALOG_URL", "https://www.ims.tau.ac.il/tal/kr/Search_L.aspx")

# Settings
TIMEZONE = os.getenv("TIMEZONE", "Asia/Jerusalem")
TAU_INCLUDE_MOODLE = os.getenv("TAU_INCLUDE_MOODLE", "1").lower() in ("1", "true", "yes")

# Base Storage Directory (~/.tau_mcp)
TAU_STORAGE_DIR = Path(os.getenv("TAU_STORAGE_DIR", str(Path.home() / ".tau_mcp")))
PROFILES_DIR = TAU_STORAGE_DIR / "profiles"

# Active Profile Name
TAU_PROFILE = os.getenv("TAU_PROFILE", TAU_USERNAME or "default").strip() or "default"

def sanitize_profile_name(profile: Optional[str] = None) -> str:
    """Sanitizes a profile or username into a safe directory name."""
    raw = (profile or os.getenv("TAU_PROFILE") or TAU_PROFILE or "default").strip()
    sanitized = re.sub(r"[^a-zA-Z0-9_.-]", "_", raw)
    return sanitized or "default"

def get_profile_dir(profile: Optional[str] = None) -> Path:
    """Returns the isolated storage directory for a user profile."""
    return PROFILES_DIR / sanitize_profile_name(profile)

def get_profile_paths(profile: Optional[str] = None) -> Dict[str, Path]:
    """Returns isolated paths for session, cache, and saved data."""
    pdir = get_profile_dir(profile)
    return {
        "profile_dir": pdir,
        "portal_session_file": pdir / "portal_session.json",
        "moodle_session_file": pdir / "moodle_session.json",
        "cache_file": pdir / "cache.json",
        "saved_data_file": pdir / "saved_data.json",
    }
