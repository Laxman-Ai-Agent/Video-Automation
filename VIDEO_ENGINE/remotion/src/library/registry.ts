// Pure helpers of the builder side of the Resource Library (docs/resources.md): which VERIFIED registry resource stands for a semantic icon, and which layers of a scene are drawn by a
// registered resource (so the composition records `resource_id` + the pinned `resource_sha256` on them). No file access here: build_composition.ts reads the registry and hands the entries in.
// Deterministic (no randomness, stable order). Only status `verified` entries are ever chosen; Stage 10 re-checks hash, files and status.

export interface RegEntry { resource_id: string; category: string; status: string; integrity?: { sha256?: string | null }; tags?: string[]; data?: { aliases?: string[] }; adapter?: { layer_match?: Record<string, string> | null } | null }
export interface IconRes { id: string; sha256: string; tags: string[]; aliases: string[] }

const verified = (reg: RegEntry[]) => reg.filter((e) => e.status === "verified" && !!e.integrity?.sha256);
export const iconsOf = (reg: RegEntry[]): IconRes[] => verified(reg).filter((e) => e.category === "icon").map((e) => ({ id: e.resource_id, sha256: e.integrity!.sha256 as string, tags: e.tags ?? [], aliases: e.data?.aliases ?? [] }));
const stem = (w: string) => w.replace(/s$/, "");

/** The icon a Visual Plan icon element asks for: every word of the icon's NAME (`icon.tabler.map-pin` = map, pin) must be a word of the description. The most specific (most words) wins,
 *  ties by id. A tag alone never selects an icon (`space` would match half the set): no name in the description = no icon, and the caller says so. */
export function pickIcon(desc: string, icons: IconRes[]): IconRes | null {
  const words = new Set((desc.toLowerCase().match(/[a-z]{3,}/g) ?? []).map(stem));
  const hits = icons.map((i) => ({ i, parts: (i.id.split(".").pop() ?? "").split("-").filter((p) => /[a-z]/.test(p)).map(stem) }))
    .filter((x) => x.parts.length > 0 && x.parts.every((p) => words.has(p)));
  hits.sort((a, b) => b.parts.length - a.parts.length || (a.i.id < b.i.id ? -1 : 1));
  return hits[0]?.i ?? null;
}

/** The fallback when no icon NAME is in the description: an icon whose entry lists the word as an explicit ALIAS (`data.aliases`, curated by hand when the icon is imported: `eyeglass` = glasses,
 *  spectacles). Never a tag: only a curated alias selects, so a loose tag cannot pull in an unrelated icon. The caller says the result is APPROXIMATE (the description usually says more than the icon). */
export function pickIconAlias(desc: string, icons: IconRes[]): IconRes | null {
  const words = new Set((desc.toLowerCase().match(/[a-z]{3,}/g) ?? []).map(stem));
  const hits = icons.filter((i) => i.aliases.some((a) => words.has(stem(a.toLowerCase()))));
  hits.sort((a, b) => (a.id < b.id ? -1 : 1));
  return hits[0] ?? null;
}

/** Tag the layers (and motion_scene items) that a registered resource draws: the entry's `adapter.layer_match` ({type, look | kind | preset}) must equal the layer's own fields.
 *  Nothing about how the layer is drawn changes; a layer that already names a resource is left alone. Returns the ids used (in order of first use). */
export function tagLayers(layers: Record<string, any>[], reg: RegEntry[]): string[] {
  const match = verified(reg).filter((e) => e.adapter?.layer_match);
  const used: string[] = [];
  const tag = (l: Record<string, any>, type: string, kind?: string) => {
    if (l.resource_id) return;
    const e = match.find((x) => Object.entries(x.adapter!.layer_match!).every(([k, v]) => String(k === "type" ? type : k === "kind" ? kind ?? l.kind : l[k]) === v));
    if (!e) return;
    l.resource_id = e.resource_id;
    l.resource_sha256 = e.integrity!.sha256;
    if (!used.includes(e.resource_id)) used.push(e.resource_id);
  };
  for (const l of layers) {
    const t = String(l.type ?? "").toLowerCase();
    tag(l, /chart/.test(t) ? "chart" : t, l.kind ?? (/chart/.test(t) ? t.split(" ")[0] : undefined));
    for (const it of Array.isArray(l.items) ? l.items : []) if (it && it.kind === "gfx") tag(it, "motion_gfx");
  }
  return used;
}
