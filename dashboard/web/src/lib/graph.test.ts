import { describe, it, expect } from 'vitest';
import {
	COGNIZER_KINDS,
	kindColorVar,
	kindLabel,
	kindLegend,
	edgeWidth,
	edgeOpacity,
	powerDirection,
	powerDash,
	relationTooltip,
	partitionByConnectivity,
	layoutForce,
	fitToBox,
	clampZoom,
	zoomBy,
	normalizeAngle,
	viewTransform,
	counterTransform,
	showLabel,
	truncateLabel,
	MIN_ZOOM,
	MAX_ZOOM,
	IDENTITY_VIEW
} from './graph';

// T0e ① — CognizerKind 分类映射(值域全小写,C++ statement_enums.cpp + DB 0008
// CHECK 一致:self/human/agent/group/role/external)。
describe('kindColorVar / kindLabel / kindLegend', () => {
	it('maps every known kind to a distinct CSS var', () => {
		const vars = COGNIZER_KINDS.map((k) => kindColorVar(k));
		expect(new Set(vars).size).toBe(COGNIZER_KINDS.length);
		for (const v of vars) expect(v).toMatch(/^var\(--color-/);
	});

	it('falls back to subtle for an unknown kind (forward-compat with new enum values)', () => {
		expect(kindColorVar('unknown_future_kind')).toBe('var(--color-subtle)');
		expect(kindColorVar(null)).toBe('var(--color-subtle)');
		expect(kindColorVar(undefined)).toBe('var(--color-subtle)');
	});

	it('gives every known kind a non-empty Chinese label', () => {
		for (const k of COGNIZER_KINDS) {
			expect(kindLabel(k)).toBeTruthy();
		}
	});

	it('falls back to the raw string for an unknown kind label', () => {
		expect(kindLabel('mystery')).toBe('mystery');
		expect(kindLabel(null)).toBe('未知');
	});

	it('legend covers exactly the 6 kinds, fixed order', () => {
		const legend = kindLegend();
		expect(legend.map((e) => e.kind)).toEqual([...COGNIZER_KINDS]);
		for (const e of legend) {
			expect(e.label).toBeTruthy();
			expect(e.colorVar).toMatch(/^var\(--color-/);
		}
	});
});

// T3 — affinity ∈ [0,1] → 边粗细/透明度映射。
describe('edgeWidth / edgeOpacity — affinity mapping', () => {
	it('affinity=0 gives the minimum width/opacity', () => {
		expect(edgeWidth(0)).toBeCloseTo(1, 5);
		expect(edgeOpacity(0)).toBeCloseTo(0.15, 5);
	});

	it('affinity=1 gives the maximum width/opacity', () => {
		expect(edgeWidth(1)).toBeCloseTo(6, 5);
		expect(edgeOpacity(1)).toBeCloseTo(0.85, 5);
	});

	it('is monotonically increasing with affinity', () => {
		expect(edgeWidth(0.8)).toBeGreaterThan(edgeWidth(0.2));
		expect(edgeOpacity(0.8)).toBeGreaterThan(edgeOpacity(0.2));
	});

	it('clamps out-of-range / missing affinity instead of producing invalid visuals', () => {
		expect(edgeWidth(-1)).toBe(edgeWidth(0));
		expect(edgeWidth(2)).toBe(edgeWidth(1));
		expect(edgeWidth(null)).toBe(edgeWidth(0));
		expect(edgeWidth(undefined)).toBe(edgeWidth(0));
		expect(edgeWidth(NaN)).toBe(edgeWidth(0));
	});
});

// T3 — power_asymmetry(有符号)→ 方向分类 + 虚线标记。
describe('powerDirection / powerDash — power_asymmetry mapping', () => {
	it('positive → a_over_b', () => {
		expect(powerDirection(0.5)).toBe('a_over_b');
	});

	it('negative → b_over_a', () => {
		expect(powerDirection(-0.5)).toBe('b_over_a');
	});

	it('near zero (within epsilon) → symmetric', () => {
		expect(powerDirection(0)).toBe('symmetric');
		expect(powerDirection(0.01)).toBe('symmetric');
		expect(powerDirection(-0.01)).toBe('symmetric');
	});

	it('missing power defaults to symmetric (no fabricated asymmetry)', () => {
		expect(powerDirection(null)).toBe('symmetric');
		expect(powerDirection(undefined)).toBe('symmetric');
	});

	it('symmetric relations get a solid line (no dash), asymmetric get dashed', () => {
		expect(powerDash(0)).toBeUndefined();
		expect(powerDash(0.5)).toBe('4 2');
		expect(powerDash(-0.5)).toBe('4 2');
	});
});

describe('relationTooltip', () => {
	it('formats affinity + power + direction in Chinese', () => {
		const t = relationTooltip(0.75, 0.3);
		expect(t).toContain('0.75');
		expect(t).toContain('0.30');
		expect(t).toContain('a→b 更高');
	});

	it('handles missing values without throwing', () => {
		expect(() => relationTooltip(null, null)).not.toThrow();
		expect(relationTooltip(null, null)).toContain('未知');
	});
});

// ── 布局重做:实测本机 233 个 cognizer 只有 6 条边(227 个孤立点)。旧实现把全部
// 节点等分到一个圆上 → 233 个标签叠成一圈,读不了也点不中。以下函数是新布局的
// 全部纯逻辑。
describe('partitionByConnectivity', () => {
	it('把有边的与孤立的分开(这是可读性的关键:孤立点不进关系图)', () => {
		const p = partitionByConnectivity(['a', 'b', 'c', 'd'], [{ a: 'a', b: 'b' }]);
		expect(p.connected).toEqual(['a', 'b']);
		expect(p.isolated).toEqual(['c', 'd']);
	});

	it('自环不算「有关系」—— 连的是自己,说明不了社会关系', () => {
		const p = partitionByConnectivity(['a', 'b'], [{ a: 'a', b: 'a' }]);
		expect(p.connected).toEqual([]);
		expect(p.isolated).toEqual(['a', 'b']);
	});

	it('边指向不存在的节点时不把另一端算成 connected', () => {
		const p = partitionByConnectivity(['a'], [{ a: 'a', b: 'ghost' }]);
		expect(p.connected).toEqual([]);
		expect(p.isolated).toEqual(['a']);
	});

	it('保持输入顺序,且两组无交集、并集为全体', () => {
		const ids = ['x', 'y', 'z'];
		const p = partitionByConnectivity(ids, [{ a: 'z', b: 'x' }]);
		expect([...p.connected, ...p.isolated].sort()).toEqual([...ids].sort());
		expect(p.connected.filter((i) => p.isolated.includes(i))).toEqual([]);
	});
});

describe('layoutForce', () => {
	const ids = ['a', 'b', 'c', 'd', 'e'];
	const edges = [
		{ a: 'a', b: 'b' },
		{ a: 'b', b: 'c' }
	];

	// 确定性是可测性的前提,也是「刷新页面布局不乱跳」的前提。用了 Math.random 就两者皆失。
	it('确定性:同输入两次运行得到逐点相同的坐标', () => {
		const p1 = layoutForce(ids, edges);
		const p2 = layoutForce(ids, edges);
		for (const id of ids) {
			expect(p1.get(id)!.x).toBe(p2.get(id)!.x);
			expect(p1.get(id)!.y).toBe(p2.get(id)!.y);
		}
	});

	it('边弹簧真的起作用:相连的点比全体平均距离更近', () => {
		const pos = layoutForce(ids, edges, { iterations: 400 });
		const dist = (i: string, j: string) => Math.hypot(pos.get(i)!.x - pos.get(j)!.x, pos.get(i)!.y - pos.get(j)!.y);
		const all: number[] = [];
		for (let i = 0; i < ids.length; i++)
			for (let j = i + 1; j < ids.length; j++) all.push(dist(ids[i], ids[j]));
		const avg = all.reduce((s, v) => s + v, 0) / all.length;
		expect(dist('a', 'b')).toBeLessThan(avg);
		expect(dist('b', 'c')).toBeLessThan(avg);
	});

	it('斥力真的起作用:没有任何点重合', () => {
		const pos = layoutForce(ids, edges);
		const seen = new Set<string>();
		for (const id of ids) {
			const p = pos.get(id)!;
			seen.add(`${Math.round(p.x)},${Math.round(p.y)}`);
		}
		expect(seen.size).toBe(ids.length);
	});

	it('产出的坐标全是有限数(NaN 会让整个 SVG transform 失效且无报错)', () => {
		const pos = layoutForce(ids, edges);
		for (const id of ids) {
			expect(Number.isFinite(pos.get(id)!.x)).toBe(true);
			expect(Number.isFinite(pos.get(id)!.y)).toBe(true);
		}
	});

	it('退化输入:空 → 空;单点 → 落在中心', () => {
		expect(layoutForce([], []).size).toBe(0);
		const one = layoutForce(['solo'], [], { width: 400, height: 340 });
		expect(one.get('solo')).toEqual({ x: 200, y: 170 });
	});

	it('边引用不存在的节点不抛异常', () => {
		expect(() => layoutForce(['a', 'b'], [{ a: 'a', b: 'ghost' }])).not.toThrow();
	});
});

describe('fitToBox', () => {
	it('把布局缩放进画布并留出 margin', () => {
		const src = new Map([
			['a', { x: 0, y: 0 }],
			['b', { x: 1000, y: 800 }]
		]);
		const out = fitToBox(src, { width: 400, height: 340, margin: 20 });
		for (const p of out.values()) {
			expect(p.x).toBeGreaterThanOrEqual(0);
			expect(p.x).toBeLessThanOrEqual(400);
			expect(p.y).toBeGreaterThanOrEqual(0);
			expect(p.y).toBeLessThanOrEqual(340);
		}
	});

	it('全部点重合时不除零,居中即可', () => {
		const src = new Map([
			['a', { x: 5, y: 5 }],
			['b', { x: 5, y: 5 }]
		]);
		const out = fitToBox(src, { width: 400, height: 340 });
		for (const p of out.values()) {
			expect(Number.isFinite(p.x)).toBe(true);
			expect(Number.isFinite(p.y)).toBe(true);
		}
	});

	it('空输入返回空', () => {
		expect(fitToBox(new Map(), { width: 400, height: 340 }).size).toBe(0);
	});
});

describe('缩放 / 旋转 / 变换', () => {
	it('clampZoom 钳制到上下限,并把 NaN/Infinity 挡成 1', () => {
		expect(clampZoom(0.0001)).toBe(MIN_ZOOM);
		expect(clampZoom(999)).toBe(MAX_ZOOM);
		expect(clampZoom(NaN)).toBe(1); // NaN 无序,只能回退
		expect(clampZoom(Infinity)).toBe(MAX_ZOOM); // ±Infinity 有序,照常钳制
		expect(clampZoom(-Infinity)).toBe(MIN_ZOOM);
	});

	it('zoomBy 是指数步进(每格比例相同),且方向正确:上滚放大', () => {
		expect(zoomBy(1, -100)).toBeGreaterThan(1);
		expect(zoomBy(1, 100)).toBeLessThan(1);
		// 比例一致性:连续两次同样的滚动,比值相同
		const a = zoomBy(1, -100);
		const b = zoomBy(a, -100);
		expect(b / a).toBeCloseTo(a / 1, 6);
	});

	it('zoomBy 永不越界', () => {
		expect(zoomBy(MAX_ZOOM, -100000)).toBe(MAX_ZOOM);
		expect(zoomBy(MIN_ZOOM, 100000)).toBe(MIN_ZOOM);
	});

	it('normalizeAngle 归一到 [0,360) 且处理负角与非有限值', () => {
		expect(normalizeAngle(0)).toBe(0);
		expect(normalizeAngle(360)).toBe(0);
		expect(normalizeAngle(-90)).toBe(270);
		expect(normalizeAngle(450)).toBe(90);
		expect(normalizeAngle(NaN)).toBe(0);
	});

	it('viewTransform 顺序正确:绕画布中心缩放旋转,不是绕原点', () => {
		// 先 translate(cx,cy) → scale/rotate → translate(-cx,-cy) 才是绕中心。
		// 顺序写反会绕原点转,画面直接飞出视野 —— 故这里钉住顺序本身。
		const t = viewTransform({ zoom: 2, rotation: 30, panX: 0, panY: 0 }, 200, 170);
		expect(t.indexOf('translate(200 170)')).toBeLessThan(t.indexOf('scale(2)'));
		expect(t.indexOf('scale(2)')).toBeLessThan(t.indexOf('rotate(30)'));
		expect(t.indexOf('rotate(30)')).toBeLessThan(t.indexOf('translate(-200 -170)'));
	});

	it('counterTransform 恰好抵消画布的缩放与旋转(标签才能保持水平且大小恒定)', () => {
		const c = counterTransform({ zoom: 4, rotation: 30, panX: 0, panY: 0 });
		expect(c).toContain('scale(0.25)');
		expect(c).toContain('rotate(-30)');
	});

	it('恒等视图产出恒等的正反变换', () => {
		expect(counterTransform(IDENTITY_VIEW)).toBe('scale(1) rotate(0)');
	});
});

describe('标签去拥挤', () => {
	it('未放大到阈值不画标签(233 个名字全画必然糊成一片)', () => {
		expect(showLabel(1)).toBe(false);
		expect(showLabel(3)).toBe(true);
	});

	it('悬停/选中的节点无视阈值 —— 那是用户明确的指向', () => {
		expect(showLabel(1, { hovered: true })).toBe(true);
		expect(showLabel(1, { selected: true })).toBe(true);
	});

	it('truncateLabel 截断超长名字(实测最长 53 字符)并加省略号', () => {
		expect(truncateLabel('short')).toBe('short');
		const long = 'FLA chunk backward kernel with a very long tail';
		const out = truncateLabel(long, 18);
		expect(out.length).toBe(18);
		expect(out.endsWith('…')).toBe(true);
	});

	it('恰好等于上限时不截断(边界)', () => {
		expect(truncateLabel('123456789012345678', 18)).toBe('123456789012345678');
	});
});
