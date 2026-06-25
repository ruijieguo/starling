// Phase 3 片 5 — 衰减预报(Forecast)纯逻辑:S(t)(retrievability)→ 百分比 / 风险色 / 标签。
// S(t) 与「预计时点」都由 C++ forgetting_curve 算出(只读投影);这里只做展示映射。
// 风险阈值对齐 op_decay:S(t)<0.05 即达归档阈值。

export type Tone = 'neutral' | 'brand' | 'success' | 'warn' | 'danger' | 'info';

export function retrievabilityPct(s: number): number {
	return Math.round(Math.max(0, Math.min(1, s)) * 100);
}

export function riskTone(s: number): Tone {
	if (s < 0.05) return 'danger'; // 已达 op_decay 归档阈值
	if (s < 0.2) return 'warn';
	if (s < 0.5) return 'info';
	return 'success';
}

export function riskLabel(s: number): string {
	if (s < 0.05) return '濒临归档';
	if (s < 0.2) return '高危';
	if (s < 0.5) return '衰减中';
	return '稳固';
}
