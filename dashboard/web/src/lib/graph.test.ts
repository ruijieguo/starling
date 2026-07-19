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
	relationTooltip
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
