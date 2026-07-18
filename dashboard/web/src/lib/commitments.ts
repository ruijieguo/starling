// Shared commitment derivations for the Commitments / Reminders panels —
// both consume GET /api/commitments and previously duplicated these.

// T0f — trigger 四型(值域以 0019 迁移 CHECK 为准:time/event/state/compound;
// status:armed/fired/cleared)。spec_json 是各型的规格明细(后端 T0f 起带出)。
export type CommitmentTrigger = {
	commitment_stmt_id: string;
	kind?: string;
	status: string;
	spec_json?: string;
};

/** stmt_ids whose trigger fired → render the ⚠ DUE badge. */
export function deriveFired(triggers: CommitmentTrigger[] | undefined): Set<string> {
	return new Set(
		(triggers ?? []).filter((t) => t.status === 'fired').map((t) => t.commitment_stmt_id)
	);
}

// T0f — trigger kind 的中文标签(四型 + 未知回退)。值域来自 0019 迁移 CHECK。
const TRIGGER_KIND_LABELS: Record<string, string> = {
	time: '定时',
	event: '事件',
	state: '状态',
	compound: '复合'
};
export function triggerKindLabel(kind: string | undefined): string {
	return (kind && TRIGGER_KIND_LABELS[kind]) || kind || '未知';
}

/** 某承诺的所有 trigger(面板按承诺分组显示各型明细用)。 */
export function triggersFor(
	triggers: CommitmentTrigger[] | undefined,
	stmtId: string
): CommitmentTrigger[] {
	return (triggers ?? []).filter((t) => t.commitment_stmt_id === stmtId);
}

// T0f — 各型 trigger 的一行摘要:从 spec_json 提取该型关心的字段。
// time→到点时间;event→订阅的 event_type;state→扫描的字段谓词;compound→子节点数。
// spec_json 解析失败或缺字段时优雅回退(只读呈现,不因脏数据崩)。
export function describeTrigger(t: CommitmentTrigger): string {
	let spec: Record<string, unknown> = {};
	try {
		spec = t.spec_json ? JSON.parse(t.spec_json) : {};
	} catch {
		return '(规格无法解析)';
	}
	switch (t.kind) {
		case 'time': {
			const at = spec.fire_at ?? spec.at ?? spec.deadline;
			return at ? `到点:${String(at)}` : '定时触发';
		}
		case 'event': {
			const et = spec.event_type ?? spec.event;
			return et ? `订阅事件:${String(et)}` : '事件触发';
		}
		case 'state': {
			const field = spec.field ?? spec.predicate ?? spec.path;
			return field ? `扫描字段:${String(field)}` : '状态触发';
		}
		case 'compound': {
			const children = Array.isArray(spec.children)
				? spec.children.length
				: (spec.child_count ?? spec.count);
			const mode = spec.mode ?? spec.op;
			const modeStr = mode ? `${String(mode)} ` : '';
			return children != null ? `复合(${modeStr}${String(children)} 子条件)` : '复合触发';
		}
		default:
			return t.kind ? `${t.kind} 触发` : '触发';
	}
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
