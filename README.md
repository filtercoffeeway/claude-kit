# claude-kit

Tools, skills, and agents for Claude Code.

| Tool | Folder | What it does |
|------|--------|--------------|
| Status line | [`statusline/`](statusline/) | Model, branch, PR status, context size, prompt-cache time left, API-equivalent cost |
| Claude usage | _planned_ | — |

Docs live in [`docs/`](docs/).

## Install

```bash
git clone <repo-url> claude-kit && cd claude-kit
./setup.sh                 # install every tool
./setup.sh statusline      # or only some
./setup.sh --uninstall     # remove them again
```

Setup edits `~/.claude/settings.json` (or `$CLAUDE_CONFIG_DIR/settings.json`). It backs the file up first, keeps every other setting, and won't replace a setting you already have unless you pass `--force`. Needs `python3`.

## Layout

```
claude-kit/
├── setup.sh        # installs every tool (runs */setup.sh)
├── lib/settings.py # safe settings.json add/remove, shared by setup scripts
├── docs/           # docs for every tool
├── statusline/     # Claude Code status line script + setup.sh
└── <next-tool>/    # one folder per tool, each with its own setup.sh
```
