# Desktop AI Assistant - Project Architecture

This document is the source of truth for future agents working on this project.
It describes the project as it exists now, including intended design, current
implementation, known bugs, and likely roadmap.

Last reviewed: 2026-05-27

## 1. Original Project Goal

The project is a Windows desktop assistant that accepts natural-language
commands in a terminal and routes them to local desktop actions before falling
back to AI chat.

The original goal appears to be:

- Open local apps, files, folders, media, and Windows settings from natural
  language.
- Search the web or open known websites in the default or requested browser.
- Maintain a fast SQLite index of user files and installed apps.
- Keep the index fresh through background filesystem watching and incremental
  updates.
- Use deterministic, offline routing first.
- Use optional AI only when deterministic routing cannot handle the request.

The README emphasizes indexed search and live updates, while newer modules show
a broader multi-stage routing pipeline for intent, entities, candidates,
scoring, confidence, and action execution.

## 2. Current Architecture

Normal entry point:

```powershell
python main.py
```

In practice, use the project virtualenv if running from this workspace:

```powershell
.\.venv\Scripts\python.exe main.py
```

High-level runtime flow:

```text
main.py
  -> actions.try_run_action()
  -> router.handle_request()
     -> reference resolution
     -> AI-chat precheck
     -> normalization and alias expansion
     -> settings priority route
     -> rule-based intent detection
     -> optional parse_intent compatibility layer
     -> entity extraction
     -> browser/settings/system-app shortcuts
     -> indexed candidate generation
     -> scoring
     -> confidence decision
     -> launch/open/search/clarify
  -> optional OpenAI chat fallback
```

The architecture is mostly deterministic and local-first. The project currently
does not contain a real Ollama/Qwen integration.

## 3. Main Modules

### Entry And Chat

- `main.py`
  - Starts the assistant.
  - Ensures the index exists.
  - Loads the index cache.
  - Starts the background watcher.
  - Runs the input loop.
  - Sends each user line to `actions.try_run_action()` first.
  - Falls back to `ai.ask_ai()` only when local routing returns `None` and
    `OPENAI_API_KEY` is configured.

- `actions.py`
  - Thin wrapper.
  - Calls `router.handle_request(user_text.strip())`.

- `ai.py`
  - Optional OpenAI chat integration.
  - Uses `OPENAI_API_KEY` and optional `OPENAI_MODEL`.
  - Default model is `gpt-4.1-mini`.
  - This is not used for local deterministic routing.

- `memory.py`
  - Simple OpenAI-style chat history for the terminal session.
  - Separate from routing/session memory.

### Routing Pipeline

- `router.py`
  - Main deterministic routing engine.
  - Coordinates normalization, intent, entities, candidate search, scoring,
    confidence, and execution.
  - Stores pending disambiguation choices in module-level `_pending_choices`.
  - Calls `parse_intent()` only when rule-based intent is `unknown` or no raw
    verb is found.

- `intent_engine.py`
  - Rule-based semantic intent detector.
  - Defines intents such as `play_media`, `launch_app`, `open_file`,
    `open_folder`, `web_search`, `close_app`, and `open_settings`.
  - Maps verbs like `open`, `launch`, `play`, `watch`, `search`, and `close`.
  - Gives known system/app targets priority via `system_apps.reserved_system_names()`.

- `intent_parser.py`
  - Compatibility wrapper added because `router.py` imports `parse_intent`
    from this module.
  - Delegates to the existing deterministic `parser.py`.
  - Returns the dict shape expected by `router.py`.
  - It is not a real LLM parser.

- `parser.py`
  - Legacy parser for normalized commands.
  - Produces `ParsedCommand`.
  - Still used by `intent_parser.py` and old ranking/opener code.

- `entity_extractor.py`
  - Extracts target, browser, platform, search query, website token, local path,
    and browser-forcing flags.

- `semantic_intent.py`
  - Offline semantic layer for Windows Settings.
  - Handles short commands and synonyms such as `bluetooth`, `wifi`, `sound`,
    `display`, `battery`, and `night light`.

- `reference_resolver.py`
  - Resolves pronouns and ordinals using session memory.
  - Handles examples like `open the first one`, `open it in brave`,
    `search it on youtube`, and `open latest image`.

- `session_memory.py`
  - Structured routing memory.
  - Tracks last opened item, search results, selected result, browser, app,
    folder, settings page, and context type.

- `context_memory.py`
  - Backward-compatible facade over `session_memory.py`.

### Search And Indexing

- `search_config.py`
  - Search roots, index DB path, file extensions, limits, watcher settings,
    folder nicknames, and program/start-menu roots.

- `database.py`
  - SQLite schema and CRUD operations for indexed items and metadata.
  - Stores `items` with name, path, extension, kind, category, search text,
    mtime, and source root.

- `indexer.py`
  - Full index build and startup index assurance.
  - Scans user folders, Start Menu, and shallow Program Files executables.
  - Creates rows for files/folders/apps.

- `incremental_indexer.py`
  - Incremental upsert/delete/move handling.
  - Startup sync repairs stale rows and modified mtimes.
  - Patches in-memory search cache after DB changes.

- `watcher.py`
  - Starts watchdog observer if available.
  - Falls back to lightweight polling.
  - Debounces filesystem events before sending them to `incremental_indexer`.

- `search_engine.py`
  - Loads indexed rows into an in-memory cache.
  - Searches cache or SQL prefilter depending on index size.
  - Records candidate counts and elapsed time.

- `search.py`
  - Public search wrapper used by candidate generation.

### Candidate, Scoring, Confidence

- `models.py`
  - Shared dataclasses:
    - `SearchItem`
    - `Candidate`
    - `ScoreBreakdown`
    - `ScoredCandidate`
    - `RoutingDecision`

- `candidate_generator.py`
  - Converts indexed search results into `Candidate` objects.
  - Uses `type_mapper.attach_type_to_item()`.

- `type_mapper.py`
  - Maps index kinds to routing item types such as `app`, `folder`, `document`,
    `image`, `video`, `audio`, and `system_app`.

- `scoring_config.py`
  - Weights and thresholds for scoring and confidence decisions.

- `scoring_engine.py`
  - Scores candidates using exact match, fuzzy match, keyword match, type bias,
    aliases, recency, path boost, boosts, and penalties.

- `confidence_engine.py`
  - Converts scored candidates into a routing decision:
    - `open`
    - `ask_user`
    - `clarify`
  - Avoids opening random weak matches.

### Execution

- `launcher.py`
  - Opens local files/folders/apps with `os.startfile()`.
  - Delegates system-app launching to `system_apps.py`.

- `system_apps.py`
  - Registry of reserved Windows apps:
    - Settings
    - Notepad
    - Calculator
    - Paint
    - Command Prompt
    - PowerShell
    - Task Manager
  - Resolves aliases and launches via URI, executable, or `cmd /c start`.

- `settings_router.py`
  - Maps semantic settings IDs to `ms-settings:` URIs.
  - Opens Windows Settings pages with `os.startfile()`.

- `browser_registry.py`
  - Detects installed browsers using common paths, Start Menu shortcuts, and
    registry.
  - Launches URLs in requested browser or default browser.

- `browser.py`
  - Thin compatibility wrapper around `browser_registry.py`.

- `websites.py`
  - Known website map and platform search URL templates.

### Alias And Legacy Helpers

- `alias_engine.py`
  - Current alias expansion used by normalization and scoring.

- `aliases.py`
  - Older alias system. Appears unused by current router path.

- `opener.py`
  - Older local open flow.
  - Uses `ranking.py`.
  - Appears unused by current router path.

- `ranking.py`
  - Older ranking system.
  - Still imported by `opener.py`, but current router uses `scoring_engine.py`.

- `debug_log.py`
  - Debug output controlled by `ASSISTANT_DEBUG`.

## 4. Data Flow

### Startup Data Flow

```text
main.main()
  -> ensure_index()
     -> if DB missing: rebuild_index()
     -> else: startup_sync()
  -> load_index_cache()
  -> start_background_watcher()
  -> run_loop()
```

Index build flow:

```text
indexer.rebuild_index()
  -> scan folder nicknames
  -> scan user folders
  -> scan Start Menu apps
  -> scan Program Files shallow executables
  -> database.insert_items()
  -> database.save_build_metadata()
  -> search_engine.invalidate_cache()
  -> search_engine.load_index_cache()
```

Background update flow:

```text
watcher event or polling
  -> debounce
  -> incremental_indexer.handle_filesystem_event()
  -> upsert_path/remove_path/handle_move
  -> database upsert/delete
  -> search_engine patch/remove cache item
```

### User Command Data Flow

```text
user input
  -> main.run_loop()
  -> actions.try_run_action()
  -> router.handle_request()
  -> local result string or None
  -> if None and OpenAI key exists: ai.ask_ai()
  -> print assistant response
```

Inside `router.handle_request()`:

```text
raw text
  -> resolve_user_input()
  -> numeric choice handling
  -> looks_like_ai_chat() precheck
  -> normalize_input()
  -> expand_aliases()
  -> _try_settings_route()
  -> detect_intent()
  -> optional parse_intent()
  -> extract_entities()
  -> browser action shortcut
  -> close app shortcut
  -> settings shortcut
  -> system app shortcut
  -> should_skip_file_search()
  -> generate_index_candidates()
  -> build_search_query()
  -> score_candidates()
  -> evaluate()
  -> _execute_decision()
```

## 5. Intent Flow

Current intent constants are defined in `intent_engine.py`:

- `INTENT_PLAY_MEDIA = "play_media"`
- `INTENT_LAUNCH_APP = "launch_app"`
- `INTENT_OPEN_FILE = "open_file"`
- `INTENT_OPEN_FOLDER = "open_folder"`
- `INTENT_WEB_SEARCH = "web_search"`
- `INTENT_OPEN_WEBSITE = "open_website"`
- `INTENT_BROWSER_ACTION = "browser_action"`
- `INTENT_CLOSE_APP = "close_app"`
- `INTENT_FIND = "find"`
- `INTENT_OPEN_SETTINGS = "open_settings"`
- `INTENT_UNKNOWN = "unknown"`

Verb mapping:

- `open` -> `open_file`, unless target looks like a folder or known app.
- `launch`, `start`, `run` -> `launch_app`.
- `play`, `watch` -> `play_media`.
- `search`, `google` -> `web_search`.
- `find` -> currently converted to `open_file`.
- `close`, `kill` -> `close_app`.

Special intent behavior:

- Settings are detected before normal file/app intent.
- Conversational prefixes like `please`, `can you`, `let's`, and
  `i want to` are stripped inside `intent_engine`.
- Known app targets can convert `open <app>` into `launch_app`.
- Bare known app names become `launch_app`.
- Bare unknown text becomes `open_file`.

Important current behavior:

- `parse_intent()` is called only when the rule intent is `unknown` or
  `raw_verb` is empty.
- Commands with known verbs such as `watch` do not reach `parse_intent()`.

## 6. LLM Integration Design

There are two separate AI concepts:

### OpenAI Chat Fallback

Implemented in `ai.py`.

Design:

- If local routing returns `None`, `main.py` may call `ask_ai()`.
- Requires `OPENAI_API_KEY`.
- Uses `OPENAI_MODEL` or default `gpt-4.1-mini`.
- This is general chat, not structured command parsing.

### Intended Qwen/Ollama Intent Parser

Not implemented.

Evidence:

- `router.py` comments mention "Qwen" in the optional parser block.
- `router.py` imports `parse_intent()` from `intent_parser.py`.
- The original repository did not contain `intent_parser.py`.
- The current `intent_parser.py` is a compatibility wrapper that delegates to
  deterministic `parser.py`.
- There is no Ollama import, no Qwen model name, no local HTTP call to
  `localhost:11434`, and no subprocess invocation for Ollama.

Expected future design, based on router contract:

```text
parse_intent(text) -> dict

Possible return examples:
  {"action": "launch_app", "app": "calculator"}
  {"action": "search_web", "query": "cat videos"}
  {"action": "open_latest_image"}
  {"action": "unknown", "query": "..."}
```

The router currently expects only these actions:

- `launch_app`
- `search_web`
- `open_latest_image`

Any real LLM parser should preserve this contract unless the router is updated
deliberately.

## 7. Expected Behavior Examples

These examples describe intended behavior, not guaranteed current behavior.

### `open calculator`

Expected:

```text
open calculator
  -> normalize
  -> intent launch_app or open_file with target calculator
  -> entity target calculator
  -> resolve_system_app("calculator")
  -> launch calc.exe
  -> "Opened system app: Calculator"
```

Current known bug: alias expansion can corrupt `calculator` into
`calculatorulatorulator`, preventing system-app resolution.

### `launch chrome`

Expected:

```text
launch chrome
  -> launch_app
  -> target chrome
  -> search indexed apps/shortcuts
  -> score app candidates
  -> open high-confidence match or ask user
```

### `search cats on brave`

Expected:

```text
search cats on brave
  -> web_search
  -> query cats
  -> browser brave
  -> launch URL in Brave if installed
```

### `open youtube in chrome`

Expected:

```text
open youtube in chrome
  -> website token youtube
  -> browser chrome
  -> launch https://www.youtube.com in Chrome
```

### `open bluetooth settings`

Expected:

```text
open bluetooth settings
  -> semantic settings match
  -> setting_id bluetooth
  -> ms-settings:bluetooth
```

### `cat videos`

Expected design direction:

```text
cat videos
  -> no explicit launcher verb
  -> optional structured parser or web/video intent
  -> likely web search or LLM fallback
```

Current behavior may remain local-file oriented because bare unknown text
defaults to `open_file`.

### `asdfghjkl`

Expected design direction:

```text
asdfghjkl
  -> no meaningful local match
  -> should not open random files
  -> should clarify or fall back to AI depending product decision
```

Current behavior likely clarifies after local search, not LLM parser/chat.

### `let's watch something fun`

Expected product direction:

```text
let's watch something fun
  -> likely needs semantic/LLM interpretation
  -> probably web/video recommendation or YouTube search
```

Current routing treats `watch` as `play_media`, so it searches local media and
does not call `parse_intent()`.

## 8. Known Bugs

Critical issues fixed in Phase 2:

- `router.py` previously failed to compile because a large block was dedented
  outside `handle_request()`.
- `router.py` imported missing `intent_parser.py`.
- `ai.py` used undefined `api_key` in `get_client()`.

Current known bugs and risks:

### Alias Expansion Corrupts Words

`alias_engine.expand_aliases()` uses substring replacement. Because `calc`
maps to `calculator`, the word `calculator` contains `calc` and can expand
repeatedly when aliases are applied more than once.

Observed:

```text
open calculator -> open calculatorulatorulator
```

Impact:

- `open calculator` fails to resolve the system app.
- Other aliases may corrupt larger words.

Likely fix:

- Use word-boundary or token-based alias replacement.
- Avoid re-expanding canonical strings that contain their alias.

### Real Qwen/Ollama Parser Missing

There is no real LLM intent parser. `intent_parser.py` is compatibility glue.

Impact:

- Router comments promise Qwen refinement, but no model is called.
- Ambiguous natural language cannot benefit from local LLM parsing.

### Parser Exceptions Are Swallowed

`router.py` catches all exceptions around `parse_intent()` and silently passes.

Impact:

- Missing parser, bad schema, JSON errors, and future LLM failures can be
  invisible.
- Debugging intent-parser behavior is harder.

### Vague Known-Verb Commands Skip Parser

Because `watch` is a known verb, `let's watch something fun` becomes
`play_media` and does not reach `parse_intent()`.

Impact:

- Conversational entertainment requests are treated as local media file search.

### Nonsense Bare Text Does Not Cleanly Reach AI

Bare unknown text becomes `open_file`. If local search has no good match,
`confidence_engine` returns `clarify`.

Impact:

- Inputs like `asdfghjkl` may clarify instead of falling through to AI.

### Legacy Duplicate Pipelines

Current active router uses:

- `intent_engine.py`
- `entity_extractor.py`
- `candidate_generator.py`
- `scoring_engine.py`
- `confidence_engine.py`

Older modules still exist:

- `parser.py`
- `opener.py`
- `ranking.py`
- `aliases.py`

Impact:

- Future agents may edit the wrong pipeline.
- Behavior may diverge between old and new systems.

### Exception Swallowing In Watcher/Browser Paths

Several background and browser-detection paths swallow exceptions or only log
when debug mode is enabled.

Impact:

- Watcher or browser issues can fail quietly.

### Search Performance Limits

Known performance risks:

- SQL prefilter uses leading-wildcard `LIKE "%token%"`.
- Fuzzy matching uses `SequenceMatcher` across candidate names.
- Polling watcher opens SQLite repeatedly inside loops.
- Full rebuild scans Program Files shallowly, which can still be costly.

## 9. Future Roadmap

Recommended order for future work:

### Phase A - Stabilize Current Deterministic Routing

- Fix alias expansion to be token-aware and idempotent.
- Add debug visibility for `parse_intent()` failures.
- Add focused tests for:
  - `open calculator`
  - `open notepad`
  - `open bluetooth settings`
  - `search cats on brave`
  - `open youtube in chrome`
  - `asdfghjkl`
  - `let's watch something fun`
- Decide whether no-candidate clarification should return `None` for AI
  fallback or remain local-only clarification.

### Phase B - Clarify Parser Ownership

- Decide whether `parser.py` is legacy or should be the canonical parser.
- If `intent_parser.py` stays, document its schema formally.
- Remove or quarantine old `opener.py`/`ranking.py` only after tests prove the
  current router fully replaces them.

### Phase C - Add Real Local LLM Parser

- Implement Ollama/Qwen only behind `intent_parser.parse_intent()`.
- Preserve the existing return contract first.
- Add timeout, fallback, debug logging, and schema validation.
- Never let LLM output directly launch actions without deterministic safety
  checks.

### Phase D - Improve Natural Language Semantics

- Add handling for vague entertainment/search commands:
  - `cat videos`
  - `let's watch something fun`
  - `play something relaxing`
- Distinguish local media intent from web entertainment intent.
- Use session memory for follow-up commands more consistently.

### Phase E - Improve Index And Search Quality

- Consider FTS5 or token table search instead of leading-wildcard LIKE.
- Cache normalized names and token lists.
- Tune scoring thresholds from real examples.
- Reduce duplicate aliases/scoring/parser systems.

### Phase F - Productize UX

- Add command help for current capabilities.
- Add optional debug mode that shows route, intent, target, and confidence.
- Add safer messages for low confidence.
- Add a small regression test suite runnable before launching the assistant.

## Agent Guidance

When modifying this project:

1. Start at `main.py`, then `actions.py`, then `router.py`.
2. Treat `router.py` as the active pipeline.
3. Treat `parser.py`, `opener.py`, `ranking.py`, and `aliases.py` as legacy
   unless current imports prove otherwise.
4. Preserve deterministic routing before adding AI behavior.
5. Do not add an LLM parser that bypasses scoring/confidence/safety checks.
6. Run full compile validation after edits:

```powershell
.\.venv\Scripts\python.exe -m py_compile *.py
```

7. Verify startup:

```powershell
"quit" | .\.venv\Scripts\python.exe main.py
```

