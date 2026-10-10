#!/usr/bin/env python3
"""Add or remove a top-level key in Claude Code's settings.json.

    settings.py set   <key> <json-value> [--force]
    settings.py unset <key> <json-value>

`set` is a no-op when the key already holds that value, and refuses to replace a
different value unless --force. `unset` only removes the key when it holds that
value, so it never deletes someone else's setting. The file is backed up before
every write. Honours CLAUDE_CONFIG_DIR. Only uses the standard library.
"""
import json
import os
import shutil
import sys
import time
from pathlib import Path


def settings_path():
    base = os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude"
    return Path(base) / "settings.json"


def load(path):
    if not path.exists():
        return {}
    text = path.read_text()
    return json.loads(text) if text.strip() else {}


def save(path, data):
    if path.exists():
        stamp = time.strftime("%Y%m%d-%H%M%S")
        backup = path.with_name(f"{path.name}.bak-{stamp}")
        n = 1
        while backup.exists():
            backup = path.with_name(f"{path.name}.bak-{stamp}-{n}")
            n += 1
        shutil.copy2(path, backup)
        print(f"  backed up {path} -> {backup.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n")
    tmp.replace(path)


def main(argv):
    force = "--force" in argv
    args = [a for a in argv if a != "--force"]
    if len(args) != 3 or args[0] not in ("set", "unset"):
        print(__doc__.strip(), file=sys.stderr)
        return 2
    action, key, value = args[0], args[1], json.loads(args[2])

    path = settings_path()
    try:
        data = load(path)
    except json.JSONDecodeError as e:
        print(f"  {path} is not valid JSON ({e}); fix it first", file=sys.stderr)
        return 1
    current = data.get(key)

    if action == "set":
        if current == value:
            print(f"  {key} already set in {path}")
            return 0
        if current is not None and not force:
            print(f"  {path} already has a different {key}:", file=sys.stderr)
            print(f"    {json.dumps(current)}", file=sys.stderr)
            print("  re-run with --force to replace it", file=sys.stderr)
            return 1
        data[key] = value
        save(path, data)
        print(f"  set {key} in {path}")
    else:
        if current is None:
            print(f"  {key} not set in {path}")
            return 0
        if current != value:
            print(f"  {key} in {path} was not installed from here; leaving it", file=sys.stderr)
            return 1
        del data[key]
        save(path, data)
        print(f"  removed {key} from {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
