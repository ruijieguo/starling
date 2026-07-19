// T0e ①/T3 — cognizer 社交图纯映射函数(可测,不含渲染)。
//
// CognizerKind 值域(全小写,C++ statement_enums.cpp + DB 0008 CHECK 一致):
// self / human / agent / group / role / external。本模块只映射既有语义 token
// (app.css @theme:brand/info/success/warn/danger/subtle),不新增视觉体系。
export const COGNIZER_KINDS = [
	'self',
	'human',
	'agent',
	'group',
	'role',
	'external'
] as const;
export type CognizerKind = (typeof COGNIZER_KINDS)[number];

// 每个 kind → 一个既有语义 token 的 CSS 变量名(供 SVG fill/stroke 用
// `var(--color-x)`)。顺序与视觉意图:self 用品牌色(最突出),human 用 info
// (蓝,人类直觉色),agent 用 success(AI/agent 常绿标健康运行),group 用 warn
// (聚合/需留意),role 用 subtle(抽象角色,弱化),external 用 danger(外部/
// 边界警示)。未知 kind(字典未覆盖,兼容后端新增值)回退到 subtle。
const KIND_COLOR_VAR: Record<CognizerKind, string> = {
	self: 'var(--color-brand)',
	human: 'var(--color-info)',
	agent: 'var(--color-success)',
	group: 'var(--color-warn)',
	role: 'var(--color-subtle)',
	external: 'var(--color-danger)'
};

const KIND_LABEL: Record<CognizerKind, string> = {
	self: '自我',
	human: '人类',
	agent: '智能体',
	group: '群体',
	role: '角色',
	external: '外部'
};

/** kind → CSS 颜色变量(SVG fill/stroke 用);未知 kind 回退 subtle。 */
export function kindColorVar(kind: string | null | undefined): string {
	return KIND_COLOR_VAR[kind as CognizerKind] ?? 'var(--color-subtle)';
}

/** kind → 中文标签(图例/tooltip 用);未知 kind 回退原始字符串。 */
export function kindLabel(kind: string | null | undefined): string {
	if (!kind) return '未知';
	return KIND_LABEL[kind as CognizerKind] ?? kind;
}

/** 图例条目:遍历全部 6 类,供 Graph 组件渲染图例(顺序固定,不随数据变化)。 */
export function kindLegend(): { kind: CognizerKind; label: string; colorVar: string }[] {
	return COGNIZER_KINDS.map((k) => ({ kind: k, label: KIND_LABEL[k], colorVar: KIND_COLOR_VAR[k] }));
}

// ── T3: affinity/power_asymmetry 边映射 ──────────────────────────────────
//
// affinity ∈ [0.0, 1.0](REAL,cognizer_relations 表)。越高越粗/越实。
// 钳制越界输入(防御性:上游数据若越界,视觉不崩、不画出负宽度)。
const MIN_EDGE_WIDTH = 1;
const MAX_EDGE_WIDTH = 6;
const MIN_EDGE_OPACITY = 0.15;
const MAX_EDGE_OPACITY = 0.85;

function clamp01(v: number | null | undefined): number {
	if (v == null || Number.isNaN(v)) return 0;
	return Math.max(0, Math.min(1, v));
}

/** affinity([0,1])→ 边描边宽度(px)。越亲密越粗。缺失/越界值钳制到 [0,1]。 */
export function edgeWidth(affinity: number | null | undefined): number {
	const a = clamp01(affinity);
	return MIN_EDGE_WIDTH + a * (MAX_EDGE_WIDTH - MIN_EDGE_WIDTH);
}

/** affinity([0,1])→ 边透明度。越亲密越实。缺失/越界值钳制到 [0,1]。 */
export function edgeOpacity(affinity: number | null | undefined): number {
	const a = clamp01(affinity);
	return MIN_EDGE_OPACITY + a * (MAX_EDGE_OPACITY - MIN_EDGE_OPACITY);
}

// power_asymmetry 有符号(REAL,方向 a_id→b_id):
//   > 0 → a 对 b 权力更高;< 0 → b 对 a 权力更高;≈0 → 对称。
// 阈值 0.05 之内视为对称(浮点/近零噪声不误判方向)。
const POWER_SYMMETRIC_EPS = 0.05;

export type PowerDirection = 'a_over_b' | 'b_over_a' | 'symmetric';

/** power_asymmetry(有符号 REAL)→ 方向分类,供箭头朝向/样式选择。 */
export function powerDirection(power: number | null | undefined): PowerDirection {
	const p = power ?? 0;
	if (Math.abs(p) < POWER_SYMMETRIC_EPS) return 'symmetric';
	return p > 0 ? 'a_over_b' : 'b_over_a';
}

/** power_asymmetry → 边 stroke-dasharray(对称=实线,不对称=虚线标记方向性)。 */
export function powerDash(power: number | null | undefined): string | undefined {
	return powerDirection(power) === 'symmetric' ? undefined : '4 2';
}

/** relation 详情文本,供 <title> tooltip(中文,数值保留两位小数)。 */
export function relationTooltip(affinity: number | null | undefined, power: number | null | undefined): string {
	const aTxt = affinity == null ? '未知' : affinity.toFixed(2);
	const pTxt = power == null ? '未知' : power.toFixed(2);
	const dir = powerDirection(power);
	const dirTxt = dir === 'symmetric' ? '对称' : dir === 'a_over_b' ? 'a→b 更高' : 'b→a 更高';
	return `亲密度(affinity): ${aTxt} · 权力不对称: ${pTxt}(${dirTxt})`;
}
