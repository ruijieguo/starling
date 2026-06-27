// Multi-model provider registry (Phase 2a) — types + role-status helper.
// Mirrors python/starling/dashboard/config.py: `providers` (named configs) +
// `roles` (which provider each job uses). GET /api/config returns masked
// providers (key_set bool, never the key).

export type Prov = {
	provider: string;
	model: string;
	base_url: string;
	key_set?: boolean;
	dim?: number;
};

export type Config = {
	providers: Record<string, Prov>;
	roles: Record<string, string>;
	// #38-C v2 threshold surface: NORM-gist knobs (min_holders / min_replay_count /
	// min_confidence). Absent keys → C++ defaults (3 / 1 / 0.6).
	gist_thresholds?: Record<string, number>;
	// Non-fatal heads-up from a save (e.g. the embedding provider rejected the
	// config; the save still succeeded but embeddings won't generate). GET omits it.
	warnings?: string[];
};

// A role is "configured" when it's bound to a provider whose key is set.
// Drives the header status dots. null when the config shape is missing.
export function roleConfigured(c: Config | null | undefined, role: string): boolean | null {
	if (!c || !c.roles) return null;
	const name = c.roles[role];
	if (!name) return false;
	return !!c.providers?.[name]?.key_set;
}
