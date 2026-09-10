import type { Plugin } from "@opencode-ai/plugin";
import { tool } from "@opencode-ai/plugin";
import { userInfo } from "os";
import { basename } from "path";
import { randomBytes } from "crypto";

// mem0-lan: opencode plugin for the self-hosted mem0 server on the LAN.
// Talks to the OSS REST API (not the mem0 cloud): POST /memories, /search,
// GET/PUT/DELETE /memories. Zero dependencies, global fetch only.
//
// Required env (export in ~/.zshrc, never commit values):
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

export const Mem0LanPlugin: Plugin = async ({ client }) => {
  if (!MEM0_API_KEY) {
    try {
      await client.app.log({
        body: { service: "mem0-lan", level: "error", message: "MEM0_API_KEY not set. Memory tools will fail until it is exported." },
      });
    } catch {}
  } else {
    try {
      await client.app.log({
        body: { service: "mem0-lan", level: "info", message: `Connected to ${MEM0_HOST} as ${userId()} (session ${SESSION_ID}).` },
      });
    } catch {}
  }

  return {
    "shell.env": async (_input: any, output: any) => {
      if (output?.env) {
        output.env.MEM0_USER_ID = userId();
        output.env.MEM0_SESSION_ID = SESSION_ID;
        output.env.MEM0_HOST = MEM0_HOST;
      }
    },

    "session.idle": async (input: any) => {
      try {
        const dir = input?.directory || input?.cwd;
        await api("/memories", {
          method: "POST",
          body: JSON.stringify({
            messages: [{ role: "user", content: `Session idle. Directory: ${dir || "?"}. Session: ${SESSION_ID}.` }],
            user_id: userId(),
            agent_id: dir ? basename(dir) : undefined,
            metadata: { type: "session_state", source: "idle", session_id: SESSION_ID },
          }),
        });
      } catch {}
    },

    "experimental.session.compacting": async (input: any, output: any) => {
      try {
        const summary = `Session compacting. Directory: ${input?.directory || "?"} Session: ${SESSION_ID}.`;
        await api("/memories", {
          method: "POST",
          body: JSON.stringify({
            messages: [{ role: "user", content: summary }],
            user_id: userId(),
            metadata: { type: "session_state", source: "pre-compaction", session_id: SESSION_ID },
          }),
        }).catch(() => {});
        const res = await api("/search", {
          method: "POST",
          body: JSON.stringify({ query: "session state decisions learnings", filters: scopeFilters("project", input?.directory), top_k: 10 }),
        }).catch(() => null);
        const lines: string[] = ((res?.results || []) as any[]).map((m: any) => `- ${m.memory}`);
        if (lines.length > 0 && output?.context) {
          output.context.push(`## Mem0 Memories (preserve across compaction)\n\n${lines.join("\n")}`);
        }
      } catch {}
    },

    tool: {
      add_memory: tool({
        description: "Save a decision, preference, or learning to shared LAN memory. Call whenever the user states something worth remembering across sessions. Memories are shared with all machines using the same MEM0_USER_ID.",
        args: {
          text: tool.schema.string().describe("Memory text content, 1 sentence"),
          scope: tool.schema.string().optional().describe('"project" (this repo, default), "session" (this run), or "global" (all projects)'),
        },
        async execute(args: any, context: any) {
          const filters = scopeFilters(args.scope, context?.directory);
          const res = await api("/memories", {
            method: "POST",
            body: JSON.stringify({
              messages: [{ role: "user", content: args.text }],
              user_id: filters.user_id,
              agent_id: filters.agent_id,
              run_id: filters.run_id,
              metadata: { source: "opencode", session_id: SESSION_ID },
            }),
          });
          return JSON.stringify(res);
        },
      }),

      search_memories: tool({
        description: "Search shared LAN memory by meaning. Use proactively before answering when the request may depend on past work, decisions, preferences, or environment. Try several phrasings for multi-part questions.",
        args: {
          query: tool.schema.string().describe("Search query"),
          scope: tool.schema.string().optional().describe('"project" (this repo, default), "session" (this run), or "global" (all projects, only when explicitly asked)'),
          limit: tool.schema.number().optional().describe("Max results (default 5)"),
        },
        async execute(args: any, context: any) {
          const res = await api("/search", {
            method: "POST",
            body: JSON.stringify({ query: args.query, filters: scopeFilters(args.scope, context?.directory), top_k: args.limit ?? 5 }),
          });
          return JSON.stringify(res);
        },
      }),

      get_memories: tool({
        description: "List stored memories in a scope without a query. Useful to audit what is remembered.",
        args: {
          scope: tool.schema.string().optional().describe('"project" (default), "session", or "global"'),
          limit: tool.schema.number().optional().describe("Max results (default 20)"),
        },
        async execute(args: any, context: any) {
          const f = scopeFilters(args.scope, context?.directory);
          const q = new URLSearchParams({ user_id: f.user_id, top_k: String(args.limit ?? 20) } as any);
          if (f.agent_id) q.set("agent_id", f.agent_id);
          if (f.run_id) q.set("run_id", f.run_id);
          return JSON.stringify(await api(`/memories?${q.toString()}`));
        },
      }),

      get_memory: tool({
        description: "Fetch one memory by its exact ID.",
        args: { id: tool.schema.string().describe("Memory ID") },
        async execute(args: any) {
          return JSON.stringify(await api(`/memories/${encodeURIComponent(args.id)}`));
        },
      }),

      update_memory: tool({
        description: "Update a stored fact in place when it changed. Preserves ID and history.",
        args: {
          id: tool.schema.string().describe("Memory ID"),
          text: tool.schema.string().optional().describe("New text content"),
        },
        async execute(args: any) {
          return JSON.stringify(
            await api(`/memories/${encodeURIComponent(args.id)}`, {
              method: "PUT",
              body: JSON.stringify({ text: args.text }),
            }),
          );
        },
      }),

      delete_memory: tool({
        description: "Delete one memory by ID when it is wrong or obsolete. Irreversible.",
        args: { id: tool.schema.string().describe("Memory ID") },
        async execute(args: any) {
          return JSON.stringify(
            await api(`/memories/${encodeURIComponent(args.id)}`, { method: "DELETE" }),
          );
        },
      }),
    },
  };
};

export default Mem0LanPlugin;
