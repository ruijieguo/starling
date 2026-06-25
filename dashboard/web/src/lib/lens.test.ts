import { describe, it, expect } from 'vitest';
import { statusLabel, originLabel, nodeSummary } from './lens';

describe('lens helpers (Phase 3 片 3)', () => {
	it('maps extraction status → label + tone, null → 无抽取, unknown → raw/neutral', () => {
		expect(statusLabel('success')).toEqual({ label: '成功', tone: 'success' });
		expect(statusLabel('failed').tone).toBe('danger');
		expect(statusLabel('partial_success').tone).toBe('warn');
		expect(statusLabel(null)).toEqual({ label: '无抽取记录', tone: 'neutral' });
		expect(statusLabel('weird')).toEqual({ label: 'weird', tone: 'neutral' }); // no DB CHECK → 兜底
	});

	it('glosses provenance origin, unknown falls back to raw, empty → —', () => {
		expect(originLabel('user_input')).toBe('用户输入');
		expect(originLabel('tom_inferred')).toBe('心智推断');
		expect(originLabel('reconsolidation_derived')).toBe('再固化派生');
		expect(originLabel('mystery')).toBe('mystery');
		expect(originLabel(null)).toBe('—');
	});

	it('summarizes a node from statement, falls back to summary, then placeholders', () => {
		expect(nodeSummary({ statement: { subject_id: 'Bob', predicate: 'owns', object_value: 'auth' } })).toBe(
			'Bob · owns · auth'
		);
		// 折叠节点(repeat / found=false 补摘要)读 summary
		expect(nodeSummary({ summary: { subject_id: 'A', predicate: 'r', object_value: 'b' } })).toBe(
			'A · r · b'
		);
		expect(nodeSummary({})).toBe('(未解析)');
		expect(nodeSummary({ statement: {} })).toBe('(空)');
	});
});
