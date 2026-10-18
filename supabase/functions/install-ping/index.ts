// RockForge's opt-in install counter (src/rockforge/infrastructure/install_counter.py).
//   POST {install_id, version, kind, os}   record that this install reached this version
//   POST {action: "forget", install_id}    delete what this install sent (the user turned it off)
//   GET                                    the totals: installs, by version, kind and OS
// Nothing else is stored — not the IP, not a name. The app has no key to send,
// so the body is validated here instead (deployed with verify_jwt off).
import { createClient } from "npm:@supabase/supabase-js@2.45.4";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const VERSION = /^\d{1,4}\.\d{1,4}\.\d{1,4}(-[0-9A-Za-z.]{1,24})?$/;
const KINDS = new Set(["exe", "git", "source"]);
const OSES = new Set(["windows", "macos", "linux", "other"]);
const MAX_BODY = 1024;

const db = createClient(
  Deno.env.get("SUPABASE_URL")!,
  Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
  { auth: { persistSession: false } },
);

function reply(status: number, body?: unknown): Response {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
  });
}

Deno.serve(async (req: Request) => {
  if (req.method === "GET") {
    const { data, error } = await db.rpc("install_counts");
    if (error) return reply(500, { error: "unavailable" });
    return reply(200, data);
  }
  if (req.method !== "POST") return reply(405, { error: "method" });
  const text = await req.text();
  if (text.length > MAX_BODY) return reply(413, { error: "too large" });
  let body: Record<string, unknown>;
  try {
    const parsed = JSON.parse(text);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error();
    body = parsed;
  } catch {
    return reply(400, { error: "json" });
  }
  const id = body.install_id;
  if (typeof id !== "string" || !UUID.test(id)) return reply(400, { error: "install_id" });

  if (body.action === "forget") {
    const { error } = await db.from("install_versions").delete().eq("install_id", id);
    return error ? reply(500, { error: "unavailable" }) : reply(204);
  }
  const { version, kind, os } = body;
  if (typeof version !== "string" || !VERSION.test(version)) return reply(400, { error: "version" });
  if (typeof kind !== "string" || !KINDS.has(kind)) return reply(400, { error: "kind" });
  if (typeof os !== "string" || !OSES.has(os)) return reply(400, { error: "os" });
  const { error } = await db.from("install_versions").upsert(
    { install_id: id, version, kind, os },
    { onConflict: "install_id,version", ignoreDuplicates: true },
  );
  return error ? reply(500, { error: "unavailable" }) : reply(204);
});
