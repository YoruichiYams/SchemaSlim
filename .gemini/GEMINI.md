# Mnemo Memory Engine Protocol

1. ALWAYS query Mnemo first:
   - Before answering questions about project architecture, dependencies, data models, or prior decisions, call `mnemo_search`.
   - Never assume the architecture without verifying active facts in Mnemo.

2. ALWAYS persist architectural decisions:
   - When a new technology, framework, database, or major pattern is introduced or modified, call `mnemo_remember` with AUDN classification.
   - For fundamental invariant decisions, mark them with `pinned: true`.

3. Graph vs Facts:
   - Structural dependencies (modules/classes) reside in the AST graph (`mnemo_scan_project`).
   - High-level design rationale, stack components, and configurations reside in the fact store (`mnemo_remember`).