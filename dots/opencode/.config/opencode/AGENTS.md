# Shared memory (mem0-lan)

You have memory tools: add_memory, search_memories, get_memories,
get_memory, update_memory, delete_memory. Identity comes from env
(MEM0_USER_ID is shared across all machines).

Scopes: project (this repo = user + repo name, default), session
(this run only), global (all projects and machines, only on explicit ask).

- BEFORE answering anything that may depend on past work, decisions,
  preferences, or environment: call search_memories. NEVER ask
  permission to search; searching is read-only and expected.
- WHEN the user states a decision, preference, or learning: call
  add_memory immediately, 1 sentence.

## Examples

User: "en este proyecto usamos pnpm, no npm"
-> add_memory({ text: "Proyecto starbien-platform usa pnpm, no npm" })

User: "recuerda que el Postgres de memoria está en ubuntu.server"
-> add_memory({ text: "Postgres de memoria vive en ubuntu.server, base mem0", scope: "global" })

User: "por qué falla el deploy?" (repo con historial)
-> search_memories({ query: "errores y fixes del deploy" }) y luego responder.

User: "qué decidimos del backup?"
-> search_memories({ query: "decisiones sobre respaldos", scope: "global" }).

User: "olvida que usamos npm"
-> search_memories({ query: "uso de npm" }) y delete_memory({ id }) del resultado.
