import importlib.resources
import sqlite3
import tomllib


def load_defaults():
    pkg = importlib.resources.files("sinchai")
    return tomllib.loads((pkg / "defaults.toml").read_bytes().decode())


def load_db_settings(db_path):
    try:
        con = sqlite3.connect(db_path)
        rows = con.execute("SELECT key, value FROM settings").fetchall()
        con.close()
        return dict(rows)
    except Exception:
        return {}


def apply_settings(cfg, db_settings):
    for dotkey, raw in db_settings.items():
        parts = dotkey.split(".")
        node = cfg
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        if raw.lower() in ("true", "false"):
            node[parts[-1]] = raw.lower() == "true"
        else:
            try:
                node[parts[-1]] = int(raw)
            except ValueError:
                try:
                    node[parts[-1]] = float(raw)
                except ValueError:
                    node[parts[-1]] = raw
    return cfg


def get_config(db_path):
    cfg = load_defaults()
    return apply_settings(cfg, load_db_settings(db_path))
