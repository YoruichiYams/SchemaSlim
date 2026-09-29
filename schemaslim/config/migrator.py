"""Configuration discovery, virtualization wrapper, and rollback engine for SchemaSlim."""

import asyncio
import json
import os
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from schemaslim.config.loader import load_config
from schemaslim.config.models import Config
from schemaslim.core.harvester import SchemaHarvester
from schemaslim.storage.vector_store import VectorStore
from schemaslim.utils.logger import get_logger

logger = get_logger("migrator")

GLOBAL_CONFIG_DIR = Path.home() / ".schemaslim"
GLOBAL_CONFIG_PATH = GLOBAL_CONFIG_DIR / "config.json"


class MigrationError(Exception):
    """Base exception for client configuration migration failures."""


@dataclass
class DetectedClient:
    """Represents a discovered MCP client configuration on the local machine."""

    name: str
    path: Path
    server_count: int
    servers: Dict[str, Any] = field(default_factory=dict)
    is_wrapped: bool = False


@dataclass
class MigrationResult:
    """Outcome of a wrap or unwrap operation."""

    success: bool
    client_name: str
    target_path: Path
    backup_path: Optional[Path] = None
    servers_migrated: int = 0
    cancelled: bool = False
    message: str = ""


def get_standard_client_candidates() -> List[Tuple[str, Path]]:
    """Return platform-specific standard paths for popular MCP client configs."""
    candidates: List[Tuple[str, Path]] = []

    # 1. Claude Desktop
    if sys.platform == "win32":
        appdata = os.getenv("APPDATA")
        if appdata:
            candidates.append(
                ("Claude Desktop", Path(appdata) / "Claude" / "claude_desktop_config.json")
            )
    elif sys.platform == "darwin":
        candidates.append(
            (
                "Claude Desktop",
                Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json",
            )
        )
    else:
        candidates.append(
            ("Claude Desktop", Path.home() / ".config" / "Claude" / "claude_desktop_config.json")
        )

    # 2. Antigravity IDE / Gemini MCP configs
    candidates.append(("Antigravity IDE", Path.home() / ".antigravity" / "mcp.json"))
    candidates.append(("Antigravity Global", Path.home() / ".gemini" / "config" / "mcp_config.json"))

    # 3. Cursor
    candidates.append(("Cursor", Path.home() / ".cursor" / "mcp.json"))

    # 4. VS Code (project workspace & global)
    candidates.append(("VS Code Workspace", Path.cwd() / ".vscode" / "mcp.json"))
    candidates.append(("VS Code Global", Path.home() / ".vscode" / "mcp.json"))

    return candidates


class ConfigMigrator:
    """Discovers MCP client configs and manages wrap/unwrap lifecycle."""

    def __init__(self, global_config_path: Optional[Path] = None) -> None:
        self.global_config_path = global_config_path or GLOBAL_CONFIG_PATH

    def discover_clients(self) -> List[DetectedClient]:
        """Scan standard filesystem locations for active MCP client configurations.

        Returns:
            List of detected clients with non-empty mcpServers.
        """
        results: List[DetectedClient] = []
        candidates = get_standard_client_candidates()

        for name, path in candidates:
            if not path.is_file():
                continue

            try:
                content = path.read_text(encoding="utf-8-sig")
                data = json.loads(content)
            except Exception as e:
                logger.debug("Skipping unreadable config at %s: %s", path, e)
                continue

            if not isinstance(data, dict):
                continue

            servers = data.get("mcpServers")
            if not isinstance(servers, dict) or not servers:
                continue

            # Check if this configuration is already virtualized
            is_wrapped = len(servers) == 1 and "schemaslim" in servers

            results.append(
                DetectedClient(
                    name=name,
                    path=path.resolve(),
                    server_count=len(servers),
                    servers=servers,
                    is_wrapped=is_wrapped,
                )
            )

        return results

    def inspect_file(self, path: Path) -> DetectedClient:
        """Inspect a specific file for MCP server configurations."""
        p = path.expanduser().resolve()
        if not p.is_file():
            raise MigrationError(f"Target configuration file does not exist: {p}")

        try:
            content = p.read_text(encoding="utf-8-sig")
            data = json.loads(content)
        except Exception as e:
            raise MigrationError(f"Invalid JSON in {p}: {e}") from e

        if not isinstance(data, dict):
            raise MigrationError(f"Configuration file root must be a JSON object: {p}")

        servers = data.get("mcpServers")
        if not isinstance(servers, dict):
            servers = {}

        is_wrapped = len(servers) == 1 and "schemaslim" in servers

        return DetectedClient(
            name=p.stem,
            path=p,
            server_count=len(servers),
            servers=servers,
            is_wrapped=is_wrapped,
        )

    def backup_config(self, path: Path) -> Path:
        """Create a backup of the client configuration file."""
        backup_path = path.with_name(path.name + ".schemaslim.bak")
        try:
            shutil.copy2(path, backup_path)
            logger.debug("Created backup at: %s", backup_path)
            return backup_path
        except Exception as e:
            raise MigrationError(f"Failed to create backup at {backup_path}: {e}") from e

    def restore_backup(self, path: Path) -> None:
        """Restore configuration from backup file and remove backup."""
        backup_path = path.with_name(path.name + ".schemaslim.bak")
        if not backup_path.is_file():
            raise MigrationError(f"No backup file found at: {backup_path}")

        try:
            shutil.copy2(backup_path, path)
            backup_path.unlink(missing_ok=True)
            logger.debug("Restored configuration from: %s", backup_path)
        except Exception as e:
            raise MigrationError(f"Failed to restore from backup {backup_path}: {e}") from e

    def merge_to_global(self, servers_to_merge: Dict[str, Any]) -> Tuple[Path, int]:
        """Merge client servers into SchemaSlim global config (~/.schemaslim/config.json)."""
        target = self.global_config_path.resolve()
        target.parent.mkdir(parents=True, exist_ok=True)

        existing_data: Dict[str, Any] = {}
        if target.is_file():
            try:
                existing_data = json.loads(target.read_text(encoding="utf-8-sig"))
            except Exception:
                existing_data = {}

        if not isinstance(existing_data, dict):
            existing_data = {}

        current_servers = existing_data.get("mcpServers", {})
        if not isinstance(current_servers, dict):
            current_servers = {}

        # Merge extracted servers (ignoring any existing schemaslim entry)
        added_or_updated = 0
        for s_name, s_def in servers_to_merge.items():
            if s_name == "schemaslim":
                continue
            current_servers[s_name] = s_def
            added_or_updated += 1

        existing_data["mcpServers"] = current_servers

        if "settings" not in existing_data or not isinstance(existing_data["settings"], dict):
            existing_data["settings"] = {
                "db_path": "~/.schemaslim/index.db",
                "embedding_model": "BAAI/bge-small-en-v1.5",
                "top_k": 3,
                "log_level": "INFO",
            }

        target.write_text(
            json.dumps(existing_data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        logger.info(
            "Merged %d servers into global config: %s", added_or_updated, target
        )
        return target, added_or_updated

    def rewrite_client_config(self, path: Path) -> None:
        """Replace mcpServers in client config with virtualizing SchemaSlim proxy."""
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception as e:
            raise MigrationError(f"Failed to read client config {path}: {e}") from e

        if not isinstance(data, dict):
            data = {}

        # Virtualized entrypoint
        data["mcpServers"] = {
            "schemaslim": {
                "command": "uvx",
                "args": ["schemaslim", "serve"],
            }
        }

        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        logger.info("Updated client config %s to use SchemaSlim virtualizer.", path)

    def trigger_index(self, config_path: Path) -> int:
        """Harvest schemas and index tools for the merged configuration."""
        try:
            cfg = load_config(config_path, allow_cwd=True)
            harvester = SchemaHarvester(default_timeout=8.0)
            tools, failures = asyncio.run(harvester.harvest_all(cfg))
            if tools:
                with VectorStore(
                    db_path=cfg.settings.resolved_db_path,
                    embedding_model=cfg.settings.embedding_model,
                ) as store:
                    return store.upsert_tools(tools)
            return 0
        except Exception as exc:
            logger.warning("Auto-indexing encountered an issue: %s", exc)
            return 0

    def wrap(
        self,
        target_path: Optional[Path] = None,
        auto_confirm: bool = False,
        run_index: bool = True,
    ) -> MigrationResult:
        """Execute the wrap migration lifecycle on a target client configuration."""
        # 1. Select target
        if target_path:
            client = self.inspect_file(target_path)
        else:
            detected = self.discover_clients()
            if not detected:
                raise MigrationError(
                    "No active MCP client configurations detected on standard paths.\n"
                    "Specify target file explicitly via: schemaslim wrap --path /path/to/config.json"
                )
            client = detected[0]

        if client.is_wrapped:
            return MigrationResult(
                success=True,
                client_name=client.name,
                target_path=client.path,
                servers_migrated=0,
                message=f"Configuration '{client.name}' is already virtualized with SchemaSlim.",
            )

        # Filter servers to migrate (exclude schemaslim itself)
        servers_to_migrate = {
            k: v for k, v in client.servers.items() if k != "schemaslim"
        }
        if not servers_to_migrate:
            return MigrationResult(
                success=True,
                client_name=client.name,
                target_path=client.path,
                servers_migrated=0,
                message=f"No external servers found in '{client.name}' to migrate.",
            )

        # 2. Interactive confirmation if not auto-confirmed
        if not auto_confirm:
            from schemaslim.ui.menu import prompt_confirmation

            server_list = ", ".join(list(servers_to_migrate.keys())[:5])
            if len(servers_to_migrate) > 5:
                server_list += f", +{len(servers_to_migrate) - 5} more"

            confirmed = prompt_confirmation(
                title="MIGRATION CONFIRMATION",
                lines=[
                    ("target", f"{client.name} ({client.path.name})"),
                    ("action", "backup original & route traffic via SchemaSlim"),
                    ("servers", f"{len(servers_to_migrate)} to migrate • {server_list}"),
                ],
                confirm_label="Apply migration",
                cancel_label="Cancel",
                default=True,
            )
            if not confirmed:
                return MigrationResult(
                    success=False,
                    client_name=client.name,
                    target_path=client.path,
                    servers_migrated=0,
                    cancelled=True,
                    message="Migration cancelled by user.",
                )

        # 3. Create backup
        backup_path = self.backup_config(client.path)

        # 4. Merge servers to global config
        global_path, count = self.merge_to_global(servers_to_migrate)

        # 5. Background / sync indexing
        indexed_count = 0
        if run_index:
            indexed_count = self.trigger_index(global_path)

        # 6. Rewrite client config
        self.rewrite_client_config(client.path)

        return MigrationResult(
            success=True,
            client_name=client.name,
            target_path=client.path,
            backup_path=backup_path,
            servers_migrated=count,
            message=(
                f"Successfully wrapped {client.name}. "
                f"{count} servers migrated to {global_path} ({indexed_count} tools indexed)."
            ),
        )

    def unwrap(
        self,
        target_path: Optional[Path] = None,
        auto_confirm: bool = False,
    ) -> MigrationResult:
        """Rollback SchemaSlim virtualization by restoring from the backup file."""
        if target_path:
            p = target_path.expanduser().resolve()
        else:
            # Find client with an existing backup
            detected = self.discover_clients()
            p = None
            for cl in detected:
                candidate_bak = cl.path.with_name(cl.path.name + ".schemaslim.bak")
                if candidate_bak.is_file():
                    p = cl.path
                    break
            if p is None:
                raise MigrationError(
                    "No backup (.schemaslim.bak) found among standard client locations.\n"
                    "Specify target file explicitly via: schemaslim unwrap --path /path/to/config.json"
                )

        backup_path = p.with_name(p.name + ".schemaslim.bak")
        if not backup_path.is_file():
            raise MigrationError(f"Backup file not found at: {backup_path}")

        if not auto_confirm:
            from schemaslim.ui.menu import prompt_confirmation

            confirmed = prompt_confirmation(
                title="ROLLBACK CONFIRMATION",
                lines=[
                    ("target", f"{p.name}"),
                    ("backup", f"{backup_path.name}"),
                    ("action", "restore original configuration & remove backup"),
                ],
                confirm_label="Restore original configuration",
                cancel_label="Cancel",
                default=True,
            )
            if not confirmed:
                return MigrationResult(
                    success=False,
                    client_name=p.stem,
                    target_path=p,
                    cancelled=True,
                    message="Rollback cancelled by user.",
                )

        self.restore_backup(p)

        return MigrationResult(
            success=True,
            client_name=p.stem,
            target_path=p,
            backup_path=backup_path,
            message=f"Successfully restored original configuration for {p}.",
        )
