# Mnemo Cognitive Memory & Code Knowledge Graph Protocol (v0.4.0)

You are equipped with **Mnemo** — an autonomous, bitemporal long-term memory engine and AST dependency graph. You MUST strictly adhere to the following memory operating lifecycle during every task.

---

## 1. MANDATORY EXECUTION LIFECYCLE

### Phase 1: Retrieve Architectural Context (Query First)
- **WHEN:** Before writing, modifying, planning, or explaining code, architecture, data schemas, or tech stack components.
- **ACTION:** Always call `mnemo_search(query="<intent or concept>")`.
- **RULES:**
  - Never guess stack components, conventions, or design decisions without querying Mnemo.
  - If investigating past states or historical decisions, use `as_of="YYYY-MM-DDTHH:MM:SSZ"`.
  - Inspect any metadata warnings: if a fact contains `"warning": "stale_code_drift"`, verify the referenced code immediately before trusting the fact.

### Phase 2: Acknowledge Active Facts (Spaced Repetition Loop)
- **WHEN:** Immediately after applying facts retrieved from `mnemo_search` in your response or code modifications.
- **ACTION:** Call `mnemo_acknowledge_usage(fact_ids=["<fact_id>", ...])`.
- **RULES:** Pass only the IDs of facts that genuinely influenced your decision or solution. This reinforces their stability $R$ in memory.

### Phase 3: Persist New Knowledge (Remember)
- **WHEN:** Whenever you introduce, modify, or verify:
  - Framework, database, protocol, or library choices;
  - Core business logic rules, constraints, and security policies;
  - Architectural patterns, naming conventions, or configuration invariants.
- **ACTION:** Call `mnemo_remember(text="...", category="...", entity_identifiers=[...])`.
- **RULES:**
  - Always link the fact to qualified code symbols via `entity_identifiers` (e.g. `["OrderWorkflowService.process_payment", "PaymentRepository"]`) to track future AST drift.
  - Do not provide `source_type` or `confidence` (enforced as Zero-Trust agent level).
  - Use `pinned: true` ONLY for absolute invariants that must never be forgotten.

### Phase 4: Reconcile Code and Debt
- **WHEN:** After modifying class or function signatures, deleting modules, or completing large refactorings:
  - Run `mnemo_scan_project()` to recalculate AST SHA-256 hashes and detect code drift.
  - Check `mnemo_get_debt_ledger()` to resolve stale facts (`is_stale: true`).
  - If a decision was deprecated or superseded, retire it with `mnemo_invalidate(fact_id="...")`.

---

## 2. SECURITY & BOUNDARIES
- **Physical Purge is CLI-Only:** Never attempt to call `mnemo_purge` via MCP; it is disabled for safety. To permanently redact secrets, instruct the human operator to run `mnemo purge <id> --yes` from the terminal.
- **Path Confinement:** `mnemo_scan_project` is strictly jailed to the project root. Do not pass external paths (`../` or absolute system paths).

---

## 3. MCP Tool Usage via SchemaSlim
In this environment, tools are discovered via SchemaSlim. Mnemo tools reside under the `mnemo__*` namespace.

1. **Discovery:** Call `schemaslim_search(query="mnemo memory search remember")` to inspect signatures when needed.
2. **Execution:** Use `schemaslim_call(namespaced_name="mnemo__<tool_name>", arguments={...})`:
   - `mnemo__mnemo_search`
   - `mnemo__mnemo_remember`
   - `mnemo__mnemo_acknowledge_usage`
   - `mnemo__mnemo_invalidate`
   - `mnemo__mnemo_inspect`
   - `mnemo__mnemo_get_debt_ledger`
   - `mnemo__mnemo_scan_project`

---

## 4. Motion Animation Skill
When implementing UI components, web interfaces, or interactive animations:
- Do not attempt to call external network MCP tools for Motion.
- Apply animation primitives directly using the local Motion library (`motion/react` or `framer-motion`):
  - **Layout Transitions:** Utilize `layout` and `layoutId` props for shared element transitions.
  - **Micro-interactions:** Implement spring physics with `type: "spring", stiffness: 300, damping: 30` for natural tactile response.
  - **Mount/Unmount:** Wrap conditional renders in `<AnimatePresence mode="wait">`.
  - **Gestures:** Leverage `whileHover`, `whileTap`, and `drag` constraints.
- Prioritize CSS transforms (`transform: translate3d / scale`) and opacity over layout-triggering properties (`top`, `left`, `width`, `height`) for 60fps rendering.