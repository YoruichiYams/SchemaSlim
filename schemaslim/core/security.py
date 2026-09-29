"""Security classification engine for identifying destructive MCP tools."""

import re
from typing import Any, Dict, Optional

from schemaslim.config.models import DEFAULT_DESTRUCTIVE_PATTERNS, SecurityPolicy
from schemaslim.utils.logger import get_logger

logger = get_logger("security")


def is_destructive(
    tool_name: str,
    description: str = "",
    parameters: Optional[Dict[str, Any]] = None,
    policy: Optional[SecurityPolicy] = None,
) -> bool:
    """Deterministically classify whether an MCP tool is destructive or mutating.

    Precedence order:
      1. Explicit blocked_tools -> always True (blocked).
      2. Explicit allowed_tools -> always False (exempted).
      3. Destructive patterns evaluated against tool_name (lowercased, snake_case split).
      4. Destructive patterns evaluated against tool description.

    Args:
        tool_name: Full namespaced or raw tool name (e.g. 'fs__delete_file' or 'delete_file').
        description: Human-readable tool description.
        parameters: Optional JSON Schema dictionary of tool parameters.
        policy: SecurityPolicy instance to evaluate against.

    Returns:
        True if tool is considered destructive/mutating under the policy, False otherwise.
    """
    effective_policy = policy or SecurityPolicy()
    clean_name = (tool_name or "").strip()
    base_tool_name = clean_name.split("__")[-1] if "__" in clean_name else clean_name

    # 1. Permanent blacklist check
    if clean_name in effective_policy.blocked_tools or base_tool_name in effective_policy.blocked_tools:
        logger.debug("Tool '%s' matched explicit blocked_tools list.", clean_name)
        return True

    # 2. Permanent whitelist check
    if clean_name in effective_policy.allowed_tools or base_tool_name in effective_policy.allowed_tools:
        logger.debug("Tool '%s' matched explicit allowed_tools list.", clean_name)
        return False

    # 3. Pattern evaluation against tool_name (snake_case / kebab-case / camelCase tokens)
    tokens = [t.lower() for t in re.findall(r"[a-zA-Z0-9]+", base_tool_name) if t]
    name_lower = clean_name.lower()
    base_lower = base_tool_name.lower()

    for pattern in effective_policy.destructive_patterns:
        pat_lower = pattern.lower()

        # Token-level match (e.g., 'delete' in ['fs', 'delete', 'file'])
        if pat_lower in tokens:
            logger.debug(
                "Tool '%s' flagged destructive: token '%s' in tool name tokens %s.",
                clean_name,
                pat_lower,
                tokens,
            )
            return True

        # Regex / substring match on tool name
        try:
            regex = re.compile(pattern, re.IGNORECASE)
            if regex.search(base_lower) or regex.search(name_lower):
                logger.debug(
                    "Tool '%s' flagged destructive: pattern '%s' matched tool name.",
                    clean_name,
                    pattern,
                )
                return True
        except re.error:
            if pat_lower in base_lower or pat_lower in name_lower:
                return True

    # 4. Pattern evaluation against tool description
    if description:
        clean_desc = description.strip()
        for pattern in effective_policy.destructive_patterns:
            try:
                # Use word boundaries for simple word patterns to prevent false positives
                if re.match(r"^\w+$", pattern):
                    regex = re.compile(r"\b" + pattern + r"\b", re.IGNORECASE)
                else:
                    regex = re.compile(pattern, re.IGNORECASE)

                if regex.search(clean_desc):
                    logger.debug(
                        "Tool '%s' flagged destructive: pattern '%s' matched description.",
                        clean_name,
                        pattern,
                    )
                    return True
            except re.error:
                if pattern.lower() in clean_desc.lower():
                    return True

    return False
