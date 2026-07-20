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

// ── 连通性分区 ───────────────────────────────────────────────────────────
//
// 为什么需要它:实测本机数据 233 个 cognizer 只有 6 条关系边 —— 227 个是孤立点。
// 旧实现把全部节点等分到一个半径 140 的圆上,于是 233 个标签叠成一圈黑边,
// 既读不了也点不中。孤立点在「关系图」里不携带任何关系信息,画进去纯是噪声;
// 它们属于下方那张可搜索表格。故先分区,只把有边的子图交给布局。

export type GraphPartition = {
	/** 至少有一条边的节点 id(按输入顺序)。 */
	connected: string[];
	/** 一条边都没有的节点 id(按输入顺序)。 */
	isolated: string[];
};

/** 按「是否至少有一条边」把节点分成两组。边引用了不存在的节点时忽略该端。 */
export function partitionByConnectivity(
	nodeIds: readonly string[],
	edges: readonly { a: string; b: string }[]
): GraphPartition {
	const present = new Set(nodeIds);
	const touched = new Set<string>();
	for (const e of edges) {
		// 自环不算「有关系」——它连的是自己,画出来也说明不了社会关系。
		if (e.a === e.b) continue;
		if (present.has(e.a) && present.has(e.b)) {
			touched.add(e.a);
			touched.add(e.b);
		}
	}
	const connected: string[] = [];
	const isolated: string[] = [];
	for (const id of nodeIds) (touched.has(id) ? connected : isolated).push(id);
	return { connected, isolated };
}

// ── 力导向布局(确定性:不用 Math.random,同输入必得同输出,故可单测)─────────
//
// 手写而非引入 d3-force:待布局的只有「有边的子图」,本机实测 6 个节点,即便
// 社会图长大到几十个,这个规模下朴素 O(n²) 斥力 + 边弹簧 + 向心收拢已经足够,
// 不值得为它加一个新依赖。

const LAYOUT_ITERATIONS = 300;
const REPULSION = 1600; // 斥力系数:越大节点铺得越开
const SPRING = 0.02; // 边弹簧劲度
const SPRING_REST = 60; // 边的自然长度(px)
const CENTER_PULL = 0.006; // 向心力:防止不相连的分量各自飘走
const DAMPING = 0.85;

export type Point = { x: number; y: number };

/**
 * 确定性初始位置:黄金角螺旋。比同心圆好在——相邻序号不会挤在同一方向,
 * 力学模拟一开始就不容易陷进对称的死局(用圆形初值时,规则图常常纹丝不动)。
 */
function seedPositions(ids: readonly string[], cx: number, cy: number): Map<string, Point> {
	const golden = Math.PI * (3 - Math.sqrt(5));
	const out = new Map<string, Point>();
	ids.forEach((id, i) => {
		const r = 12 * Math.sqrt(i + 1);
		const t = i * golden;
		out.set(id, { x: cx + r * Math.cos(t), y: cy + r * Math.sin(t) });
	});
	return out;
}

/**
 * 力导向布局。返回 id → 坐标。空输入返回空 Map;单节点直接落在中心。
 * 确定性:无随机源,同样的 (ids, edges, opts) 必得同样的坐标。
 */
export function layoutForce(
	ids: readonly string[],
	edges: readonly { a: string; b: string }[],
	opts: { width?: number; height?: number; iterations?: number } = {}
): Map<string, Point> {
	const width = opts.width ?? 400;
	const height = opts.height ?? 340;
	const iterations = opts.iterations ?? LAYOUT_ITERATIONS;
	const cx = width / 2;
	const cy = height / 2;
	if (ids.length === 0) return new Map();
	if (ids.length === 1) return new Map([[ids[0], { x: cx, y: cy }]]);

	const pos = seedPositions(ids, cx, cy);
	const vel = new Map<string, Point>(ids.map((id) => [id, { x: 0, y: 0 }]));
	// 只保留两端都在 ids 里的边,免得斥力/弹簧对着不存在的节点算。
	const inSet = new Set(ids);
	const live = edges.filter((e) => e.a !== e.b && inSet.has(e.a) && inSet.has(e.b));

	for (let step = 0; step < iterations; step++) {
		// 退火:后期步长变小,收敛到稳定解而不是一直抖。
		const cool = 1 - step / iterations;

		for (let i = 0; i < ids.length; i++) {
			const a = pos.get(ids[i])!;
			const va = vel.get(ids[i])!;
			// 斥力(所有节点两两)
			for (let j = 0; j < ids.length; j++) {
				if (i === j) continue;
				const b = pos.get(ids[j])!;
				let dx = a.x - b.x;
				let dy = a.y - b.y;
				let d2 = dx * dx + dy * dy;
				if (d2 < 0.01) {
					// 完全重合时给一个由序号决定的确定性偏移(不能用随机,否则布局不可复现)
					dx = (i - j) * 0.01;
					dy = (i + j) * 0.01 + 0.01;
					d2 = dx * dx + dy * dy;
				}
				const f = REPULSION / d2;
				const d = Math.sqrt(d2);
				va.x += (dx / d) * f;
				va.y += (dy / d) * f;
			}
			// 向心力
			va.x += (cx - a.x) * CENTER_PULL;
			va.y += (cy - a.y) * CENTER_PULL;
		}

		// 边弹簧
		for (const e of live) {
			const a = pos.get(e.a)!;
			const b = pos.get(e.b)!;
			const dx = b.x - a.x;
			const dy = b.y - a.y;
			const d = Math.sqrt(dx * dx + dy * dy) || 0.01;
			const f = SPRING * (d - SPRING_REST);
			const ux = (dx / d) * f;
			const uy = (dy / d) * f;
			const va = vel.get(e.a)!;
			const vb = vel.get(e.b)!;
			va.x += ux;
			va.y += uy;
			vb.x -= ux;
			vb.y -= uy;
		}

		for (const id of ids) {
			const p = pos.get(id)!;
			const v = vel.get(id)!;
			p.x += v.x * cool * 0.05;
			p.y += v.y * cool * 0.05;
			v.x *= DAMPING;
			v.y *= DAMPING;
		}
	}
	return pos;
}

/**
 * 把一组坐标缩放平移到给定画布内(留 margin),使布局无论疏密都占满视野。
 * 所有点重合(极差为 0)时不缩放,直接居中 —— 否则会除零。
 */
export function fitToBox(
	pos: Map<string, Point>,
	box: { width: number; height: number; margin?: number }
): Map<string, Point> {
	if (pos.size === 0) return pos;
	const margin = box.margin ?? 40;
	const pts = [...pos.values()];
	const minX = Math.min(...pts.map((p) => p.x));
	const maxX = Math.max(...pts.map((p) => p.x));
	const minY = Math.min(...pts.map((p) => p.y));
	const maxY = Math.max(...pts.map((p) => p.y));
	const spanX = maxX - minX;
	const spanY = maxY - minY;
	const availW = box.width - 2 * margin;
	const availH = box.height - 2 * margin;
	const scale = spanX < 1e-6 && spanY < 1e-6 ? 1 : Math.min(availW / (spanX || 1), availH / (spanY || 1));
	const outMinX = box.width / 2 - (spanX * scale) / 2;
	const outMinY = box.height / 2 - (spanY * scale) / 2;
	const out = new Map<string, Point>();
	for (const [id, p] of pos) {
		out.set(id, { x: outMinX + (p.x - minX) * scale, y: outMinY + (p.y - minY) * scale });
	}
	return out;
}

// ── 视图变换(缩放 / 平移 / 旋转)──────────────────────────────────────────

export const MIN_ZOOM = 0.4;
export const MAX_ZOOM = 6;

/**
 * 钳制缩放到 [MIN_ZOOM, MAX_ZOOM]。
 * NaN 没有序,只能回退 1(否则 Math.max/min 会把 NaN 一路传下去,整个 SVG
 * transform 静默失效且不报错)。±Infinity 有序,照常钳制 —— zoomBy 里的
 * Math.pow 溢出就会产出 Infinity,此时把视图弹回 1× 很突兀,钳到边界才是
 * 「已经放到最大/最小了」的自然手感。
 */
export function clampZoom(z: number): number {
	if (Number.isNaN(z)) return 1;
	return Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, z));
}

export type ViewState = { zoom: number; rotation: number; panX: number; panY: number };

export const IDENTITY_VIEW: ViewState = { zoom: 1, rotation: 0, panX: 0, panY: 0 };

/**
 * 视图 → SVG transform。顺序要紧:先平移到中心再缩放/旋转再移回,
 * 才是「绕画布中心缩放旋转」;顺序写反会绕原点转,画面直接飞出视野。
 */
export function viewTransform(v: ViewState, cx: number, cy: number): string {
	const z = clampZoom(v.zoom);
	return `translate(${v.panX} ${v.panY}) translate(${cx} ${cy}) scale(${z}) rotate(${v.rotation}) translate(${-cx} ${-cy})`;
}

/**
 * 节点内部的反变换:抵消掉画布的缩放与旋转,让圆点大小恒定、标签始终水平。
 * 没有它的话,放大时标签会跟着涨成巨幅文字,旋转时还会倒过来。
 */
export function counterTransform(v: ViewState): string {
	const z = clampZoom(v.zoom);
	return `scale(${1 / z}) rotate(${-v.rotation})`;
}

/** 滚轮增量 → 新缩放(指数步进,手感均匀:每一格缩放比例相同而非固定加减)。 */
export function zoomBy(current: number, deltaY: number): number {
	return clampZoom(current * Math.pow(1.0015, -deltaY));
}

/** 角度归一到 [0,360),供旋转控件显示。 */
export function normalizeAngle(deg: number): number {
	if (!Number.isFinite(deg)) return 0;
	return ((deg % 360) + 360) % 360;
}

// 标签在放大到一定程度前不画:名字实测平均 16 字符、最长 53,全画出来必然糊成一片。
// 悬停/选中的节点不受此限(那是用户明确的指向)。
const LABEL_ZOOM_THRESHOLD = 1.6;

/** 该节点此刻要不要画标签。 */
export function showLabel(zoom: number, opts: { hovered?: boolean; selected?: boolean } = {}): boolean {
	if (opts.hovered || opts.selected) return true;
	return clampZoom(zoom) >= LABEL_ZOOM_THRESHOLD;
}

/** 过长的名字截断,避免单个标签横穿整个画布(最长实测 53 字符)。 */
export function truncateLabel(label: string, max = 18): string {
	if (label.length <= max) return label;
	return label.slice(0, max - 1) + '…';
}
