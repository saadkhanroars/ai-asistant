"""
main.py — Desktop assistant with indexed search + background index updates.
"""

from actions import try_run_action
from ai import ask_ai, has_api_key, offline_ai_message
from indexer import ensure_index, rebuild_index, show_indexed_folders
from incremental_indexer import incremental_refresh
from memory import SessionMemory
from search_engine import load_index_cache
from watcher import start_background_watcher, stop_background_watcher

QUIT_WORDS = {"quit", "exit", "bye"}

INDEX_COMMANDS = {
    "refresh index": incremental_refresh,
    "rebuild index": rebuild_index,
    "show indexed folders": lambda: show_indexed_folders(),
}

HELP_TEXT = """
Multi-stage launcher (indexed search + offline settings):
  open / launch / play / watch <name>
  bluetooth / wifi / display / sound settings (natural phrasing OK)
  search <query> on brave / open youtube in chrome
  close chrome
  refresh index / rebuild index / show indexed folders
  Pick 1,2,3… when matches are ambiguous
  help / quit
"""


def print_banner() -> None:
    print("=" * 50)
    print("  Desktop Assistant (offline routing + optional AI)")
    mode = "AI enabled" if has_api_key() else "offline-only (no API key)"
    print(f"  Mode: {mode}. Debug: ASSISTANT_DEBUG=1")
    print("=" * 50)
    print()


def _handle_index_command(text: str) -> str | None:
    key = text.strip().lower()
    if key not in INDEX_COMMANDS:
        return None
    result = INDEX_COMMANDS[key]()
    if isinstance(result, dict):
        count = result.get("item_count", "?")
        removed = result.get("removed", 0)
        updated = result.get("updated", 0)
        elapsed = result.get("elapsed_sec", "")
        extra = f" in {elapsed}s" if elapsed else ""
        if removed or updated:
            return (
                f"Index synced: {count} items{extra} "
                f"(removed {removed}, updated {updated})."
            )
        return f"Index synced: {count} items{extra}."
    return str(result)


def run_loop() -> None:
    memory = SessionMemory()

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        lowered = user_input.lower()
        if lowered in QUIT_WORDS:
            print("Assistant: Goodbye!")
            break
        if lowered == "help":
            print(HELP_TEXT)
            continue

        index_msg = _handle_index_command(user_input)
        if index_msg:
            print(f"Assistant: {index_msg}")
            continue

        local_result = try_run_action(user_input)
        if local_result is not None:
            print(f"Assistant: {local_result}")
            continue

        if not has_api_key():
            print(f"Assistant: {offline_ai_message()}")
            continue

        memory.add_user(user_input)
        print("Assistant: Thinking...")
        reply = ask_ai(memory.get_messages())
        memory.add_assistant(reply)
        print(f"Assistant: {reply}")
        print()


def main() -> None:
    print_banner()
    watcher_mode = "off"
    try:
        summary = ensure_index()
        count = load_index_cache()
        watcher_mode = start_background_watcher()
        print(
            f"Assistant: Index ready — {count or summary.get('item_count', 0)} items. "
            f"Background sync: {watcher_mode}.\n"
        )
        run_loop()
    except ValueError as err:
        print(f"\nSetup error: {err}")
    except Exception as err:
        print(f"\nUnexpected error: {err}")
    finally:
        stop_background_watcher()


if __name__ == "__main__":
    main()
