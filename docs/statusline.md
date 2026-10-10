# Status line

`statusline/statusline.py` renders the Claude Code status line. It uses only the Python standard library.

```
Opus 5.5 │ cache 59m │ ctx 44k/200k 22% │ $1.23 │ PR #42 open approved ✓ │ MyTools ⎇ main
```

## Segments

| Segment | Source |
|---------|--------|
| Model | `model.display_name` from the stdin JSON |
| Folder + branch | `workspace.current_dir`, `git branch --show-current` |
| PR | `gh pr view <branch>` gives the number, state (open/draft/merged/closed), review decision, and checks (✓ pass, ● pending, ✗ fail). The result is cached for 60s in `~/.cache/mytools/statusline/` and refreshed by a detached background process, so the status line never waits on the network. Hidden when the branch has no PR. |
| Context | Tokens sent in the last request (`input + cache_creation + cache_read`) vs. the context window size. Uses `context_window.current_usage` when Claude Code provides it, otherwise the last assistant entry in the transcript. Green < 50%, yellow < 80%, red after that. |
| Cache | Time left before the prompt cache expires: the timestamp of the last API call plus the TTL. The TTL is 1h if recent requests wrote `ephemeral_1h` cache entries, otherwise 5m. Every API call that reads the cache resets the timer. |
| Cost | `cost.total_cost_usd`: Claude Code's API-equivalent cost for the session. |

## Setup

`~/.claude/settings.json` points at the script, so it applies to every session and repo on this machine:

```json
"statusLine": {
  "type": "command",
  "command": "python3 /Users/mahesh/Documents/MyTools/statusline/statusline.py",
  "padding": 0
}
```

If you move this repo, update that path.

## Notes

- The status line only redraws when the conversation updates, so the cache countdown is as of the last redraw. When it shows `cache expired`, your next message will pay to rebuild the cache.
- Test it by hand:
  ```bash
  echo '{"model":{"display_name":"Opus"},"cwd":"'$PWD'","cost":{"total_cost_usd":1.2}}' | python3 statusline/statusline.py
  ```
