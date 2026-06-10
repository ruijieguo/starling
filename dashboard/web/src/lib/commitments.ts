// Shared commitment derivations for the Commitments / Reminders panels —
// both consume GET /api/commitments and previously duplicated these.

export type CommitmentTrigger = { commitment_stmt_id: string; status: string };

/** stmt_ids whose trigger fired → render the ⚠ DUE badge. */
export function deriveFired(triggers: CommitmentTrigger[] | undefined): Set<string> {
	return new Set(
		(triggers ?? []).filter((t) => t.status === 'fired').map((t) => t.commitment_stmt_id)
	);
}

/** Ascending deadline order; rows without a deadline sort last. */
export function byDeadline(
	a: { deadline?: string | null },
	b: { deadline?: string | null }
): number {
	return (a.deadline ?? '9999').localeCompare(b.deadline ?? '9999');
}

/** ISO-string comparison works because deadlines are ISO-8601 UTC. */
export function isOverdue(deadline: string | null | undefined, nowIso: string): boolean {
	return !!deadline && deadline < nowIso;
}
