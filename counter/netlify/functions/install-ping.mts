// RockForge's opt-in install counter (src/rockforge/infrastructure/install_counter.py).
//   POST {install_id, version, kind, os}   record that this install reached this version
//   POST {action: "forget", install_id}    delete what this install sent (the user turned it off)
//   GET                                    the totals: installs, by version, kind and OS
// Nothing else is stored — not the IP, not a name. The app has no key to send,
// so the body is validated here.
//
// Storage: one Netlify Blobs entry per (install, version), with everything in
// the key — `<install_id>/<version>/<kind>/<os>` — and the first-seen time as
// the value, so the totals come from one listing and no entry is ever
// read-modified-written.
//
// POST {action: "import", rows: [...]} with `Authorization: Bearer <IMPORT_TOKEN>`
// loads rows exported from the old Supabase table; it only exists while the
// IMPORT_TOKEN environment variable is set (unset it after a migration).
import { getStore } from "@netlify/blobs";
import type { Config } from "@netlify/functions";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const VERSION = /^\d{1,4}\.\d{1,4}\.\d{1,4}(-[0-9A-Za-z.]{1,24})?$/;
const KINDS = new Set(["exe", "git", "source"]);
const OSES = new Set(["windows", "macos", "linux", "other"]);
const MAX_BODY = 1024;
const MAX_IMPORT_BODY = 256 * 1024;

// EU, like the Supabase project it replaces. Site-wide stores take the region
// on every call, so it lives in this one helper.
const store = () =>
  getStore({ name: "install-versions", region: "eu-central-1", consistency: "strong" });

function reply(status: number, body?: unknown): Response {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
  });
}

interface Row {
  install_id: string;
  version: string;
  kind: string;
  os: string;
}

function validRow(r: Record<string, unknown>): r is Record<string, unknown> & Row {
  return (
    typeof r.install_id === "string" && UUID.test(r.install_id) &&
    typeof r.version === "string" && VERSION.test(r.version) &&
    typeof r.kind === "string" && KINDS.has(r.kind) &&
    typeof r.os === "string" && OSES.has(r.os)
  );
}

/** Adds the row unless this install already reported this version. */
async function record(r: Row, firstSeen = new Date().toISOString()): Promise<boolean> {
  const s = store();
  const { blobs } = await s.list({ prefix: `${r.install_id}/${r.version}/` });
  if (blobs.length > 0) return false;
  await s.set(`${r.install_id}/${r.version}/${r.kind}/${r.os}`, firstSeen);
  return true;
}

async function forget(id: string): Promise<void> {
  const s = store();
  const { blobs } = await s.list({ prefix: `${id}/` });
  await Promise.all(blobs.map((b) => s.delete(b.key)));
}

/** Same shape as the old install_counts(): {installs, by_version, by_kind, by_os}. */
async function totals() {
  const { blobs } = await store().list();
  const installs = new Set<string>();
  const byVersion: Record<string, number> = {};
  const kindIds: Record<string, Set<string>> = {};
  const osIds: Record<string, Set<string>> = {};
  for (const { key } of blobs) {
    const [id, version, kind, os] = key.split("/");
    if (!id || !version || !kind || !os) continue;
    installs.add(id);
    byVersion[version] = (byVersion[version] ?? 0) + 1;
    (kindIds[kind] ??= new Set()).add(id);
    (osIds[os] ??= new Set()).add(id);
  }
  const sizes = (m: Record<string, Set<string>>) =>
    Object.fromEntries(Object.entries(m).map(([k, v]) => [k, v.size]));
  return {
    installs: installs.size,
    by_version: Object.fromEntries(Object.keys(byVersion).sort().map((v) => [v, byVersion[v]])),
    by_kind: sizes(kindIds),
    by_os: sizes(osIds),
  };
}

function sameToken(given: string, expected: string): boolean {
  if (given.length !== expected.length) return false;
  let diff = 0;
  for (let i = 0; i < given.length; i++) diff |= given.charCodeAt(i) ^ expected.charCodeAt(i);
  return diff === 0;
}

async function importRows(req: Request, body: Record<string, unknown>): Promise<Response> {
  const token = Netlify.env.get("IMPORT_TOKEN") ?? "";
  const given = (req.headers.get("authorization") ?? "").replace(/^Bearer\s+/i, "");
  if (token.length < 32 || !sameToken(given, token)) return reply(404, { error: "not found" });
  if (!Array.isArray(body.rows)) return reply(400, { error: "rows" });
  let added = 0;
  let skipped = 0;
  for (const raw of body.rows) {
    if (!raw || typeof raw !== "object" || !validRow(raw as Record<string, unknown>)) {
      skipped++;
      continue;
    }
    const r = raw as Row & { first_seen?: unknown };
    const seen = typeof r.first_seen === "string" && !Number.isNaN(Date.parse(r.first_seen))
      ? new Date(r.first_seen).toISOString()
      : undefined;
    if (await record(r, seen)) added++;
    else skipped++;
  }
  return reply(200, { added, skipped, totals: await totals() });
}

export default async (req: Request): Promise<Response> => {
  try {
    if (req.method === "GET") return reply(200, await totals());
    if (req.method !== "POST") return reply(405, { error: "method" });

    const text = await req.text();
    if (text.length > MAX_IMPORT_BODY) return reply(413, { error: "too large" });
    let body: Record<string, unknown>;
    try {
      const parsed = JSON.parse(text);
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error();
      body = parsed;
    } catch {
      return reply(400, { error: "json" });
    }
    if (body.action === "import") return await importRows(req, body);
    if (text.length > MAX_BODY) return reply(413, { error: "too large" });

    const id = body.install_id;
    if (typeof id !== "string" || !UUID.test(id)) return reply(400, { error: "install_id" });
    if (body.action === "forget") {
      await forget(id);
      return reply(204);
    }
    const { version, kind, os } = body;
    if (typeof version !== "string" || !VERSION.test(version)) return reply(400, { error: "version" });
    if (typeof kind !== "string" || !KINDS.has(kind)) return reply(400, { error: "kind" });
    if (typeof os !== "string" || !OSES.has(os)) return reply(400, { error: "os" });
    await record({ install_id: id, version, kind, os });
    return reply(204);
  } catch (err) {
    console.error("install-ping:", err instanceof Error ? err.message : err);
    return reply(500, { error: "unavailable" });
  }
};

export const config: Config = {
  path: "/install-ping",
  method: ["GET", "POST"],
};
