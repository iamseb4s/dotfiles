import { Plugin } from "@opencode/plugin";
import { userInfo } from "os";
import { basename } from "path";
import { randomBytes } from "crypto";

// mem0-lan: opencode v2 plugin for the self-hosted mem0 server on the LAN.
// Talks to the OSS REST API (not the mem0 cloud): POST /memories, /search,
// GET/PUT/DELETE /memories. Zero dependencies beyond @opencode/plugin,
// global fetch only.
//
// Required env (export in ~/.zshrc.local, never commit values):
//   MEM0_API_KEY  per-machine key (m0sk_...) created in the dashboard
// Optional env:
//   MEM0_HOST     default https://mem0-api.iamsebas.xyz (override per machine)
//   MEM0_USER_ID  shared identity across machines, default = OS username
//                 (set the SAME value everywhere to share one memory)
//   MEM0_APP_ID   project override, default = current directory name
// Scopes: project (default: user + repo), session (+ run), global (user only).

const MEM0_HOST = (process.env.MEM0_HOST || "https://mem0-api.iamsebas.xyz").replace(/\/$/, "");
const MEM0_API_KEY = process.env.MEM0_API_KEY || "";
const SESSION_ID = `ses_${Math.floor(Date.now() / 1000)}_${randomBytes(3).toString("hex")}`;

function userId(): string {
  return process.env.MEM0_USER_ID || userInfo().username;
}

function appId(directory?: string): string {
  if (process.env.MEM0_APP_ID) return process.env.MEM0_APP_ID;
  const dir = directory || process.cwd();
  return basename(dir);
}

function scopeFilters(scope: string | undefined, directory?: string): Record<string, string> {
  const s = scope || "project";
  if (s === "global") return { user_id: userId() };
  const f: Record<string, string> = { user_id: userId(), agent_id: appId(directory) };
  if (s === "session") f.run_id = SESSION_ID;
  return f;
}

async function api(path: string, init?: RequestInit): Promise<any> {
  if (!MEM0_API_KEY) {
    throw new Error("MEM0_API_KEY is not set. Create a per-machine key in the mem0 dashboard and export it.");
  }
  const res = await fetch(`${MEM0_HOST}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", "X-API-Key": MEM0_API_KEY, ...(init?.headers || {}) },
  });
  const text = await res.text();
  if (!res.ok) throw new Error(`mem0 ${res.status}: ${text.slice(0, 200)}`);
  return text ? JSON.parse(text) : null;
}

export default Plugin.define({
  id: "mem0-lan",
  async setup(ctx) {
    if (!MEM0_API_KEY) {
      console.log("[mem0-lan] MEM0_API_KEY not set. Memory tools will fail until it is exported.");
    } else {
      console.log(`[mem0-lan] Connected to ${MEM0_HOST} as ${userId()} (session ${SESSION_ID}).`);
    }

    // V1 "shell.env" -> V2 shell create.before: inject identity into tool shells.
    await ctx.shell.hook("create.before", (event) => {
      event.env.MEM0_USER_ID = userId();
      event.env.MEM0_SESSION_ID = SESSION_ID;
      event.env.MEM0_HOST = MEM0_HOST;
    });

    // V1 session.idle save + compaction save/recall.
    await ctx.session.hook("compaction", async (event) => {
      try {
        await api("/memories", {
          method: "POST",
          body: JSON.stringify({
            messages: [{ role: "user", content: `Session compacting. Session: ${SESSION_ID}.` }],
            user_id: userId(),
            metadata: { type: "session_state", source: "pre-compaction", session_id: SESSION_ID },
          }),
        }).catch(() => {});
        const res = await api("/search", {
          method: "POST",
          body: JSON.stringify({ query: "session state decisions learnings", filters: scopeFilters("project"), top_k: 10 }),
        }).catch(() => null);
        const lines: string[] = ((res?.results || []) as any[]).map((m: any) => `- ${m.memory}`);
        if (lines.length > 0) {
          event.system.push({ type: "text", text: `## Mem0 Memories (preserve across compaction)\n\n${lines.join("\n")}` });
        }
      } catch {}
    });

    // V1 "event" (session.idle) -> V2 event subscription.
    const controller = new AbortController();
    void (async () => {
      try {
        for await (const event of ctx.event.subscribe({ signal: controller.signal })) {
          if ((event as any)?.type === "session.idle") {
            try {
              await api("/memories", {
                method: "POST",
                body: JSON.stringify({
                  messages: [{ role: "user", content: `Session idle. Session: ${SESSION_ID}.` }],
                  user_id: userId(),
                  metadata: { type: "session_state", source: "idle", session_id: SESSION_ID },
                }),
              });
            } catch {}
          }
        }
      } catch {}
    })();

    // Resolve the repo directory for scoping: tool context first, then the
    // session record, then the plugin location as fallback.
    async function toolDirectory(context: any): Promise<string | undefined> {
      if (context?.directory) return context.directory as string;
      try {
        const sessionID = context?.sessionID;
        if (sessionID) {
          const info = (await ctx.session.get({ sessionID })) as any;
          if (info?.directory) return info.directory as string;
        }
      } catch {}
      try {
        if (ctx.location?.directory) return ctx.location.directory as string;
      } catch {}
      return undefined;
    }

    const inputObject = (properties: Record<string, unknown>, required: string[]) => ({
      type: "object" as const,
      properties,
      required,
      additionalProperties: false as const,
    });

    // V1 "tool" map -> V2 ctx.tool.transform with JSON Schema inputs.
    await ctx.tool.transform((editor) => {
      editor.add({
        name: "add_memory",
        description:
          "Save a decision, preference, or learning to shared LAN memory. Call whenever the user states something worth remembering across sessions. Memories are shared with all machines using the same MEM0_USER_ID.",
        input: inputObject(
          {
            text: { type: "string", description: "Memory text content, 1 sentence" },
            scope: { type: "string", description: '"project" (this repo, default), "session" (this run), or "global" (all projects)' },
          },
          ["text"],
        ),
        async execute(input, context) {
          const a = input as any;
          const filters = scopeFilters(a.scope, await toolDirectory(context));
          const res = await api("/memories", {
            method: "POST",
            body: JSON.stringify({
              messages: [{ role: "user", content: a.text }],
              user_id: filters.user_id,
              agent_id: filters.agent_id,
              run_id: filters.run_id,
              metadata: { source: "opencode", session_id: SESSION_ID },
            }),
          });
          return { content: JSON.stringify(res) };
        },
      });

      editor.add({
        name: "search_memories",
        description:
          "Search shared LAN memory by meaning. Use proactively before answering when the request may depend on past work, decisions, preferences, or environment. Try several phrasings for multi-part questions.",
        input: inputObject(
          {
            query: { type: "string", description: "Search query" },
            scope: { type: "string", description: '"project" (this repo, default), "session" (this run), or "global" (all projects, only when explicitly asked)' },
            limit: { type: "number", description: "Max results (default 5)" },
          },
          ["query"],
        ),
        async execute(input, context) {
          const a = input as any;
          const res = await api("/search", {
            method: "POST",
            body: JSON.stringify({
              query: a.query,
              filters: scopeFilters(a.scope, await toolDirectory(context)),
              top_k: a.limit ?? 5,
            }),
          });
          return { content: JSON.stringify(res) };
        },
      });

      editor.add({
        name: "get_memories",
        description: "List stored memories in a scope without a query. Useful to audit what is remembered.",
        input: inputObject(
          {
            scope: { type: "string", description: '"project" (default), "session", or "global"' },
            limit: { type: "number", description: "Max results (default 20)" },
          },
          [],
        ),
        async execute(input, context) {
          const a = input as any;
          const f = scopeFilters(a.scope, await toolDirectory(context));
          const q = new URLSearchParams({ user_id: f.user_id, top_k: String(a.limit ?? 20) } as any);
          if (f.agent_id) q.set("agent_id", f.agent_id);
          if (f.run_id) q.set("run_id", f.run_id);
          return { content: JSON.stringify(await api(`/memories?${q.toString()}`)) };
        },
      });

      editor.add({
        name: "get_memory",
        description: "Fetch one memory by its exact ID.",
        input: inputObject({ id: { type: "string", description: "Memory ID" } }, ["id"]),
        async execute(input) {
          const a = input as any;
          return { content: JSON.stringify(await api(`/memories/${encodeURIComponent(a.id)}`)) };
        },
      });

      editor.add({
        name: "update_memory",
        description: "Update a stored fact in place when it changed. Preserves ID and history.",
        input: inputObject(
          {
            id: { type: "string", description: "Memory ID" },
            text: { type: "string", description: "New text content" },
          },
          ["id"],
        ),
        async execute(input) {
          const a = input as any;
          return {
            content: JSON.stringify(
              await api(`/memories/${encodeURIComponent(a.id)}`, {
                method: "PUT",
                body: JSON.stringify({ text: a.text }),
              }),
            ),
          };
        },
      });

      editor.add({
        name: "delete_memory",
        description: "Delete one memory by ID when it is wrong or obsolete. Irreversible.",
        input: inputObject({ id: { type: "string", description: "Memory ID" } }, ["id"]),
        async execute(input) {
          const a = input as any;
          return {
            content: JSON.stringify(await api(`/memories/${encodeURIComponent(a.id)}`, { method: "DELETE" })),
          };
        },
      });
    });

    return () => controller.abort();
  },
});
