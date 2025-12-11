#!/usr/bin/env python3
"""Safe JSON configuration merging for Claude Code configs."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def merge_mcp_server(
    config: dict[str, Any], server_name: str, server_config: dict[str, Any]
) -> tuple[dict[str, Any], bool]:
    """Merge MCP server into config, preserving existing servers.

    Returns:
        Tuple of (merged_config, was_changed)
    """
    if "mcpServers" not in config:
        config["mcpServers"] = {}

    changed = False
    if server_name not in config["mcpServers"]:
        config["mcpServers"][server_name] = server_config
        changed = True
    elif config["mcpServers"][server_name] != server_config:
        # Server exists but config differs - update it
        config["mcpServers"][server_name] = server_config
        changed = True

    return config, changed


def merge_hooks(
    config: dict[str, Any], hook_configs: dict[str, list[dict[str, Any]]]
) -> tuple[dict[str, Any], bool]:
    """Merge hooks into config, preserving existing hooks.

    Args:
        config: Existing settings.json content
        hook_configs: Dict mapping hook event name to list of hook entries
            Example: {
                "SessionStart": [
                    {
                        "matcher": "startup",
                        "hooks": [{"type": "command", "command": "/path/to/script.sh"}]
                    }
                ],
                "UserPromptSubmit": [
                    {
                        "hooks": [{"type": "command", "command": "/path/to/script.sh"}]
                    }
                ]
            }

    Returns:
        Tuple of (merged_config, was_changed)
    """
    if "hooks" not in config:
        config["hooks"] = {}

    changed = False

    for event_name, hook_entries in hook_configs.items():
        if event_name not in config["hooks"]:
            config["hooks"][event_name] = []

        # For each hook entry to add
        for new_entry in hook_entries:
            # Check if this exact hook entry already exists
            # Compare by the command path in the hooks list
            new_command = new_entry.get("hooks", [{}])[0].get("command")

            # Check if any existing entry has this command
            exists = False
            for idx, existing_entry in enumerate(config["hooks"][event_name]):
                existing_command = existing_entry.get("hooks", [{}])[0].get("command")
                if existing_command == new_command:
                    # Update the entry if it differs
                    if existing_entry != new_entry:
                        config["hooks"][event_name][idx] = new_entry
                        changed = True
                    exists = True
                    break

            # Add if not found
            if not exists:
                config["hooks"][event_name].append(new_entry)
                changed = True

    return config, changed


def remove_mcp_server(
    config: dict[str, Any], server_name: str
) -> tuple[dict[str, Any], bool]:
    """Remove MCP server from config.

    Returns:
        Tuple of (modified_config, was_changed)
    """
    if "mcpServers" not in config or server_name not in config["mcpServers"]:
        return config, False

    del config["mcpServers"][server_name]
    return config, True


def remove_hooks(
    config: dict[str, Any], commands_to_remove: list[str]
) -> tuple[dict[str, Any], bool]:
    """Remove hook entries with specified commands.

    Args:
        config: Existing settings.json content
        commands_to_remove: List of absolute paths to hook commands

    Returns:
        Tuple of (modified_config, was_changed)
    """
    if "hooks" not in config:
        return config, False

    changed = False

    for event_name, entries in config["hooks"].items():
        original_count = len(entries)

        # Filter out entries with matching commands
        config["hooks"][event_name] = [
            entry for entry in entries
            if entry.get("hooks", [{}])[0].get("command") not in commands_to_remove
        ]

        if len(config["hooks"][event_name]) < original_count:
            changed = True

    return config, changed


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Merge JSON configurations safely"
    )
    parser.add_argument(
        "command",
        choices=["add-server", "add-hooks", "remove-server", "remove-hooks"],
    )
    parser.add_argument(
        "--config-file", required=True, help="Path to config file"
    )
    parser.add_argument(
        "--data", required=True, help="JSON data to merge/remove"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show changes without writing"
    )

    args = parser.parse_args()

    config_path = Path(args.config_file).expanduser()

    # Parse JSON data with error handling
    try:
        data = json.loads(args.data)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON data: {e}", file=sys.stderr)
        sys.exit(1)

    # Load existing config or create new
    if config_path.exists():
        try:
            with open(config_path) as f:
                config = json.load(f)
        except json.JSONDecodeError as e:
            print(
                f"Error: Invalid JSON in config file {config_path}: {e}",
                file=sys.stderr,
            )
            sys.exit(1)
    else:
        config = {}

    # Perform operation
    changed = False
    if args.command == "add-server":
        config, changed = merge_mcp_server(config, data["name"], data["config"])
    elif args.command == "add-hooks":
        config, changed = merge_hooks(config, data)
    elif args.command == "remove-server":
        config, changed = remove_mcp_server(config, data["name"])
    elif args.command == "remove-hooks":
        config, changed = remove_hooks(config, data["commands"])

    # Write result
    if changed:
        if args.dry_run:
            print(json.dumps(config, indent=2))
        else:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(config_path, "w") as f:
                json.dump(config, f, indent=2)
            print(f"Updated {config_path}")
    else:
        print("No changes needed")

    sys.exit(0 if changed or args.dry_run else 1)


if __name__ == "__main__":
    main()
