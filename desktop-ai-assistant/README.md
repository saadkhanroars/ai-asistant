# Desktop Assistant — Indexed Search + Live Updates

SQLite index with **background incremental updates** (no full rescan each search).

## Index update flow

```
Filesystem event (watchdog or polling)
  → debounce (1s)
  → incremental_indexer (upsert / delete one path)
  → database.py (SQLite)
  → search_engine.py (patch in-memory cache)
```

**Full rebuild** only when: first run, or `rebuild index` command.

## Modules

| Module | Role |
|--------|------|
| `watcher.py` | Background watch (watchdog → polling fallback) |
| `incremental_indexer.py` | Per-file add/update/delete |
| `indexer.py` | Full build + startup sync |
| `database.py` | SQLite storage |
| `search_engine.py` | Fast search + live cache patches |

## Startup

1. Load index into memory  
2. `startup_sync` — remove deleted files, refresh changed mtimes (batched)  
3. Start background watcher  

## Commands

| Command | Action |
|---------|--------|
| `refresh index` | Incremental sync (not full rescan) |
| `rebuild index` | Full rebuild |
| `show indexed folders` | List paths + stats |

## Install

```powershell
pip install -r requirements.txt
python main.py
```

Requires `watchdog` for best performance. Without it, lightweight polling is used.

## Debug

```
[watch] modified: C:\Users\...\file.pdf
[index+] updated file.pdf (2.1 ms)
[sync] checked=900 removed=2 updated=5 (0.31s)
```

`set ASSISTANT_DEBUG=0` to hide.
