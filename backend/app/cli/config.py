import json
import os
from pathlib import Path
from typing import Any, Optional

DEFAULT_CONFIG_DIR = Path.home() / ".mgops"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.json"
DEFAULT_API_URL = "http://localhost:8000"


def get_config_path() -> Path:
    env_path = os.getenv("MGOPS_CONFIG")
    if env_path:
        return Path(env_path)
    return DEFAULT_CONFIG_FILE


def load_config() -> dict[str, Any]:
    path = get_config_path()
    if not path.exists():
        return {"api_url": DEFAULT_API_URL, "access_token": None, "refresh_token": None}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "api_url" not in data:
                data["api_url"] = DEFAULT_API_URL
            return data
    except Exception:
        return {"api_url": DEFAULT_API_URL, "access_token": None, "refresh_token": None}


def save_config(config_data: dict[str, Any]) -> Path:
    path = get_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=2)
    
    # Set restricted file permissions (0600 - read/write owner only)
    try:
        os.chmod(path, 0o600)
    except Exception:
        pass
        
    return path


def update_tokens(access_token: str, refresh_token: Optional[str] = None, api_url: Optional[str] = None) -> dict[str, Any]:
    cfg = load_config()
    if api_url:
        cfg["api_url"] = api_url.rstrip("/")
    cfg["access_token"] = access_token
    if refresh_token is not None:
        cfg["refresh_token"] = refresh_token
    save_config(cfg)
    return cfg


def clear_tokens() -> None:
    cfg = load_config()
    cfg["access_token"] = None
    cfg["refresh_token"] = None
    save_config(cfg)
