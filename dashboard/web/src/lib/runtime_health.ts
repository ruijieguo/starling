export type RuntimeHealthStatus = 'READY' | 'DEGRADED' | 'DRAINING' | 'UNREADY';

export interface MetricsSnapshot {
	outbox_lag_sequence: number;
	subscriber_failure_rate: number;
	extraction_queue_depth: number;
	projection_lag_seconds: number;
	runtime_event_loop_lag_ms: number;
	vector_delete_lag: number;
	erased_evidence_visible_count: number;
}
export interface RuntimeHealthEvent {
	previous_status: RuntimeHealthStatus;
	current_status: RuntimeHealthStatus;
	trigger: string;
	missing_capabilities: string[];
	metrics_snapshot: MetricsSnapshot;
}
export interface RuntimeHealthResponse {
	status: RuntimeHealthStatus;
	events: RuntimeHealthEvent[];
}

export type Tone = 'success' | 'warn' | 'danger' | 'neutral' | 'info';
export function stateTone(s: RuntimeHealthStatus): Tone {
	return s === 'READY' ? 'success'
		: s === 'DEGRADED' ? 'warn'
		: s === 'DRAINING' ? 'info' // design-review D2: distinct from DEGRADED's warn — intentional wind-down, not a fault ("keep the teal calm")
		: 'danger'; // UNREADY
}
export function isHealthy(r: RuntimeHealthResponse): boolean {
	return r.status === 'READY';
}
