import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { tick } from 'svelte';
import { render, fireEvent } from '@testing-library/svelte';
import { ApiError } from '$lib/api';
import { lastWsEvent } from '$lib/health';

const toastError = vi.fn();
const toastSuccess = vi.fn();
vi.mock('$lib/ui/toast', () => ({
	toast: {
		error: (...a: unknown[]) => toastError(...a),
		success: (...a: unknown[]) => toastSuccess(...a),
		info: vi.fn()
	}
}));

const list = vi.fn();
const create = vi.fn();
const activate = vi.fn();
const remove = vi.fn();
const snapshots = vi.fn();
const snapshot = vi.fn();
const removeSnapshot = vi.fn();
const rollback = vi.fn();
const purgeArchives = vi.fn();
vi.mock('$lib/worlds', async (orig) => {
	const real = await orig<typeof import('$lib/worlds')>();
	return {
		...real,
		worldsApi: {
			list: (...a: unknown[]) => list(...a),
			create: (...a: unknown[]) => create(...a),
			activate: (...a: unknown[]) => activate(...a),
			remove: (...a: unknown[]) => remove(...a),
			snapshots: (...a: unknown[]) => snapshots(...a),
			snapshot: (...a: unknown[]) => snapshot(...a),
			removeSnapshot: (...a: unknown[]) => removeSnapshot(...a),
			rollback: (...a: unknown[]) => rollback(...a),
			purgeArchives: (...a: unknown[]) => purgeArchives(...a)
		}
	};
});

import Worlds from './+page.svelte';
import { worldErrorMessage } from '$lib/worlds';

const settle = async () => {
	await tick();
	await Promise.resolve();
	await Promise.resolve();
	await tick();
};

const DATA = {
	active: 'default', default: 'default', snapshot_retention: 5,
	worlds: [
		{ name: 'default', label: '主世界', tenant: 'default', created_at: '', active: true,
		  db_bytes: 2_500_000_000, live_bytes: 60_000_000, statements: 3632, engrams: 101,
		  snapshots: 0, snapshot_bytes: 0, archives: 0, archive_bytes: 0 },
		{ name: 'sim-1', label: '', tenant: 'sim-1', created_at: '', active: false,
		  db_bytes: 0, live_bytes: 0, statements: 0, engrams: 0, snapshots: 0, snapshot_bytes: 0,
		  archives: 0, archive_bytes: 0 }
	]
};

const button = (c: HTMLElement, text: string) =>
	[...c.querySelectorAll('button')].find((b) => b.textContent?.trim() === text) as
		| HTMLButtonElement
		| undefined;

describe('/worlds', () => {
	beforeEach(() => {
		list.mockReset().mockResolvedValue(DATA);
		create.mockReset();
		activate.mockReset();
		remove.mockReset();
		snapshots.mockReset().mockResolvedValue({ snapshots: [] });
		snapshot.mockReset();
		removeSnapshot.mockReset();
		toastError.mockReset();
		toastSuccess.mockReset();
		lastWsEvent.set(null);
	});

	it('列出世界，当前与默认有标记，活动世界没有切换按钮', async () => {
		const { container } = render(Worlds);
		await settle();
		expect(container.textContent).toContain('default');
		expect(container.textContent).toContain('sim-1');
		expect(container.textContent).toContain('当前');
		expect(container.textContent).toContain('默认');
		expect(container.textContent).toContain('3632');
		const switches = [...container.querySelectorAll('button')].filter(
			(b) => b.textContent?.trim() === '切换到此世界'
		);
		expect(switches.length).toBe(1);   // 只有 sim-1 有
	});

	it('世界名不合法时新建按钮禁用，且不调用 API', async () => {
		const { container } = render(Worlds);
		await settle();
		const input = container.querySelector('input[name="world-name"]') as HTMLInputElement;
		await fireEvent.input(input, { target: { value: 'Bad Name' } });
		await tick();
		const btn = button(container, '新建世界')!;
		expect(btn.disabled).toBe(true);
		await fireEvent.click(btn);
		expect(create).not.toHaveBeenCalled();
	});

	it('合法名称可以新建', async () => {
		create.mockResolvedValue({ ...DATA.worlds[1], name: 'sim-2' });
		const { container } = render(Worlds);
		await settle();
		const input = container.querySelector('input[name="world-name"]') as HTMLInputElement;
		await fireEvent.input(input, { target: { value: 'sim-2' } });
		await tick();
		await fireEvent.click(button(container, '新建世界')!);
		await settle();
		expect(create).toHaveBeenCalledWith('sim-2', '');
	});

	it('加载失败显示错误态', async () => {
		list.mockReset().mockRejectedValue(new Error('500 boom'));
		const { container } = render(Worlds);
		await settle();
		expect(container.textContent).toContain('加载失败');
	});
});

// ConfirmDialog / Drawer 走 bits-ui 的 Portal,渲染在 document.body 而不是 container 里。
const inBody = (text: string) => button(document.body, text);
const apiErr = (status: number, detail: string) => new ApiError(status, '', `${status} ${detail}`);

const SNAPS = [
	{ id: 's-auto', kind: 'auto', reason: 'pre_switch', note: '', created_at: '2026-10-25T08:00:00Z',
	  world_time: '', size_bytes: 57 * 1024 * 1024 },
	{ id: 's-man', kind: 'manual', reason: 'manual', note: '切换前留底', created_at: '2026-10-25T09:00:00Z',
	  world_time: '2026-03-01T00:00:00Z', size_bytes: 1536 }
];

describe('/worlds 切换', () => {
	const reload = vi.fn();
	beforeEach(() => {
		list.mockReset().mockResolvedValue(DATA);
		activate.mockReset();
		reload.mockReset();
		toastError.mockReset();
		vi.stubGlobal('location', { ...window.location, reload });
	});
	afterEach(() => {
		vi.unstubAllGlobals();
	});

	it('点「切换到此世界」只弹确认框,不直接切换', async () => {
		const { container } = render(Worlds);
		await settle();
		await fireEvent.click(button(container, '切换到此世界')!);
		await settle();
		expect(document.body.textContent).toContain('切换到 sim-1？');
		expect(document.body.textContent).toContain('切换会停止当前世界的后台维护与摄入，并重建引擎。');
		expect(activate).not.toHaveBeenCalled();
		expect(reload).not.toHaveBeenCalled();
	});

	it('确认后调用 activate,成功则整页刷新', async () => {
		activate.mockResolvedValue({ active: 'sim-1' });
		const { container } = render(Worlds);
		await settle();
		await fireEvent.click(button(container, '切换到此世界')!);
		await settle();
		await fireEvent.click(inBody('切换')!);
		await settle();
		expect(activate).toHaveBeenCalledWith('sim-1');
		expect(reload).toHaveBeenCalledTimes(1);
	});

	it('切换失败:toast 中文提示,不刷新页面,按钮恢复可点', async () => {
		activate.mockRejectedValue(apiErr(409, 'ingest_busy'));
		const { container } = render(Worlds);
		await settle();
		await fireEvent.click(button(container, '切换到此世界')!);
		await settle();
		await fireEvent.click(inBody('切换')!);
		await settle();
		expect(toastError).toHaveBeenCalledWith('摄入任务正在进行，暂时不能切换，请稍后再试');
		expect(reload).not.toHaveBeenCalled();
		expect(button(container, '切换到此世界')!.disabled).toBe(false);
	});
});

describe('/worlds 删除', () => {
	beforeEach(() => {
		list.mockReset().mockResolvedValue(DATA);
		remove.mockReset();
		toastError.mockReset();
		toastSuccess.mockReset();
	});

	it('默认世界与活动世界没有删除按钮,只有 sim-1 有', async () => {
		const { container } = render(Worlds);
		await settle();
		const dels = [...container.querySelectorAll('button')].filter(
			(b) => b.textContent?.trim() === '删除'
		);
		expect(dels.length).toBe(1);
		expect(dels[0].getAttribute('aria-label')).toBe('删除 sim-1');
	});

	it('手输世界名一致之前确认键禁用;一致后才调用 remove(name, confirm)', async () => {
		remove.mockResolvedValue({ deleted: 'sim-1' });
		const { container } = render(Worlds);
		await settle();
		await fireEvent.click(button(container, '删除')!);
		await settle();

		const confirm = inBody('确认删除')!;
		expect(confirm.disabled).toBe(true);
		await fireEvent.click(confirm);
		expect(remove).not.toHaveBeenCalled();

		const input = document.body.querySelector('input[name="world-delete-confirm"]') as HTMLInputElement;
		await fireEvent.input(input, { target: { value: 'sim' } });
		await tick();
		expect(inBody('确认删除')!.disabled).toBe(true);

		await fireEvent.input(input, { target: { value: 'sim-1' } });
		await tick();
		expect(inBody('确认删除')!.disabled).toBe(false);
		await fireEvent.click(inBody('确认删除')!);
		await settle();
		expect(remove).toHaveBeenCalledWith('sim-1', 'sim-1');
		expect(toastSuccess).toHaveBeenCalled();
		expect(list.mock.calls.length).toBeGreaterThanOrEqual(2); // 删除成功后重取
	});

	it('函数级守卫:绕过按钮的 disabled 也不会在名称不符时调用 remove', async () => {
		const { container } = render(Worlds);
		await settle();
		await fireEvent.click(button(container, '删除')!);
		await settle();
		const confirm = inBody('确认删除')!;
		confirm.disabled = false; // 模拟日后多出一条绕过按钮的调用路径
		await fireEvent.click(confirm);
		await settle();
		expect(remove).not.toHaveBeenCalled();
	});

	it('后端拒绝(world_protected)时 toast 中文提示', async () => {
		remove.mockRejectedValue(apiErr(409, 'world_protected'));
		const { container } = render(Worlds);
		await settle();
		await fireEvent.click(button(container, '删除')!);
		await settle();
		const input = document.body.querySelector('input[name="world-delete-confirm"]') as HTMLInputElement;
		await fireEvent.input(input, { target: { value: 'sim-1' } });
		await tick();
		await fireEvent.click(inBody('确认删除')!);
		await settle();
		expect(toastError).toHaveBeenCalledWith('默认世界和当前活动世界不能删除');
	});
});

describe('/worlds 新建的错误与 label', () => {
	beforeEach(() => {
		list.mockReset().mockResolvedValue(DATA);
		create.mockReset();
		toastError.mockReset();
	});

	it('名称不合法时显示字段错误并标 aria-invalid', async () => {
		const { container } = render(Worlds);
		await settle();
		const input = container.querySelector('input[name="world-name"]') as HTMLInputElement;
		await fireEvent.input(input, { target: { value: 'Bad Name' } });
		await tick();
		expect(input.getAttribute('aria-invalid')).toBe('true');
		expect(container.textContent).toContain('世界名只能用小写字母');
	});

	it('显示名随名称一起提交,world_exists 走中文 toast', async () => {
		create.mockRejectedValue(apiErr(409, 'world_exists'));
		const { container } = render(Worlds);
		await settle();
		await fireEvent.input(container.querySelector('input[name="world-name"]')!, { target: { value: 'sim-1' } });
		await fireEvent.input(container.querySelector('input[name="world-label"]')!, { target: { value: ' 推演 ' } });
		await tick();
		await fireEvent.click(button(container, '新建世界')!);
		await settle();
		expect(create).toHaveBeenCalledWith('sim-1', '推演');
		expect(toastError).toHaveBeenCalledWith('同名世界已存在');
	});

	it('label 非空时标题显示「name · label」', async () => {
		const { container } = render(Worlds);
		await settle();
		expect(container.textContent).toContain('default · 主世界');
	});

	it('stats_error 的世界显示「统计不可用」,只出现在那一行', async () => {
		list.mockReset().mockResolvedValue({
			...DATA,
			worlds: [DATA.worlds[0], { ...DATA.worlds[1], stats_error: true }]
		});
		const { container } = render(Worlds);
		await settle();
		expect(container.textContent?.match(/统计不可用/g)?.length).toBe(1);
	});

	it('没有 stats_error 时不显示「统计不可用」', async () => {
		const { container } = render(Worlds);
		await settle();
		expect(container.textContent).not.toContain('统计不可用');
	});
});

describe('/worlds 快照抽屉', () => {
	beforeEach(() => {
		list.mockReset().mockResolvedValue(DATA);
		snapshots.mockReset().mockResolvedValue({ snapshots: SNAPS });
		snapshot.mockReset();
		removeSnapshot.mockReset();
		toastError.mockReset();
		toastSuccess.mockReset();
	});

	const openSnaps = async (container: HTMLElement) => {
		const btn = [...container.querySelectorAll('button')].find(
			(b) => b.getAttribute('aria-label') === '快照 sim-1'
		)!;
		await fireEvent.click(btn);
		await settle();
	};

	it('展示标题、行内容与保留策略说明', async () => {
		const { container } = render(Worlds);
		await settle();
		await openSnaps(container);
		expect(snapshots).toHaveBeenCalledWith('sim-1');
		const text = document.body.textContent ?? '';
		expect(text).toContain('sim-1 的快照');
		expect(text).toContain('2026-10-25T08:00:00Z');
		expect(text).toContain('auto');
		expect(text).toContain('manual');
		expect(text).toContain('57.0 MB');
		expect(text).toContain('1.5 KB');
		expect(text).toContain('切换前留底');
		expect(text).toContain('世界时间 —'); // world_time 为空
		expect(text).toContain('保留最近 5 份，超出时优先清理自动快照，并至少保留 1 份自动快照作为回滚锚点。');
	});

	it('文件缺失的快照显示「文件缺失」,仍可删除', async () => {
		snapshots.mockReset().mockResolvedValue({
			snapshots: [{ ...SNAPS[0], size_bytes: 0, missing: true }, SNAPS[1]]
		});
		const { container } = render(Worlds);
		await settle();
		await openSnaps(container);
		const text = document.body.textContent ?? '';
		expect(text.match(/文件缺失/g)?.length).toBe(1);
		const del = [...document.body.querySelectorAll('button')].filter((b) =>
			b.getAttribute('aria-label')?.startsWith('删除快照')
		);
		expect(del.length).toBe(2);
		expect(del.every((b) => !b.disabled)).toBe(true);
	});

	it('「立即拍快照」带备注调用 snapshot,成功后重取列表', async () => {
		snapshot.mockResolvedValue(SNAPS[1]);
		const { container } = render(Worlds);
		await settle();
		await openSnaps(container);
		const note = document.body.querySelector('input[name="snapshot-note"]') as HTMLInputElement;
		await fireEvent.input(note, { target: { value: ' 手工留底 ' } });
		await tick();
		await fireEvent.click(inBody('立即拍快照')!);
		await settle();
		expect(snapshot).toHaveBeenCalledWith('sim-1', '手工留底');
		expect(snapshots.mock.calls.length).toBe(2);
		expect(toastSuccess).toHaveBeenCalled();
	});

	it('快照失败(insufficient_disk)toast 中文提示', async () => {
		snapshot.mockRejectedValue(apiErr(507, 'insufficient_disk'));
		const { container } = render(Worlds);
		await settle();
		await openSnaps(container);
		await fireEvent.click(inBody('立即拍快照')!);
		await settle();
		expect(toastError).toHaveBeenCalledWith('磁盘空间不足，快照需要至少 3 倍于数据量的可用空间');
	});

	it('删除快照要经 ConfirmDialog 确认', async () => {
		removeSnapshot.mockResolvedValue({ deleted: 's-man' });
		const { container } = render(Worlds);
		await settle();
		await openSnaps(container);
		const del = [...document.body.querySelectorAll('button')].find(
			(b) => b.getAttribute('aria-label') === `删除快照 ${SNAPS[1].created_at}`
		)!;
		await fireEvent.click(del);
		await settle();
		expect(removeSnapshot).not.toHaveBeenCalled();
		expect(document.body.textContent).toContain('删除这份快照？');
		await fireEvent.click(inBody('确认删除')!);
		await settle();
		expect(removeSnapshot).toHaveBeenCalledWith('sim-1', 's-man');
	});

	it('快照列表加载失败:显示错误与重试,不显示「还没有快照」', async () => {
		snapshots.mockRejectedValueOnce(apiErr(404, 'world_not_found')).mockResolvedValue({ snapshots: SNAPS });
		const { container } = render(Worlds);
		await settle();
		await openSnaps(container);
		expect(document.body.textContent).toContain('世界不存在');
		expect(document.body.textContent).not.toContain('还没有快照');
		await fireEvent.click(inBody('重试')!);
		await settle();
		expect(document.body.textContent).toContain('2026-10-25T09:00:00Z');
	});
});

describe('/worlds ws 事件', () => {
	beforeEach(() => {
		list.mockReset().mockResolvedValue(DATA);
	});

	it.each([
		['world_switched', { active: 'sim-1' }],
		['snapshot_created', { world: 'sim-1', id: 's1' }],
		['world_rolled_back', { world: 'sim-1', snapshot_id: 's1' }],
		['statement_added', {}]
	] as const)('收到 %s 事件时重取列表', async (type, payload) => {
		render(Worlds);
		await settle();
		const before = list.mock.calls.length;
		lastWsEvent.set({ type, payload });
		await settle();
		expect(list.mock.calls.length).toBeGreaterThan(before);
	});

	it('recall(纯读)不触发重取', async () => {
		render(Worlds);
		await settle();
		const before = list.mock.calls.length;
		lastWsEvent.set({ type: 'recall', payload: {} });
		await settle();
		expect(list.mock.calls.length).toBe(before);
	});
});

// ── W3:回滚到快照、清理回滚归档 ──────────────────────────────────────────
const byLabel = (root: ParentNode, label: string) =>
	[...root.querySelectorAll('button')].find((b) => b.getAttribute('aria-label') === label) as
		| HTMLButtonElement
		| undefined;

describe('/worlds 回滚到快照', () => {
	const reload = vi.fn();
	beforeEach(() => {
		list.mockReset().mockResolvedValue(DATA);
		snapshots.mockReset().mockResolvedValue({ snapshots: SNAPS });
		rollback.mockReset();
		removeSnapshot.mockReset();
		reload.mockReset();
		toastError.mockReset();
		toastSuccess.mockReset();
		vi.stubGlobal('location', { ...window.location, reload });
	});
	afterEach(() => {
		vi.unstubAllGlobals();
	});

	const openRollback = async (container: HTMLElement, world: string, snap = SNAPS[1]) => {
		await fireEvent.click(byLabel(container, `快照 ${world}`)!);
		await settle();
		await fireEvent.click(byLabel(document.body, `回滚到快照 ${snap.created_at}`)!);
		await settle();
	};
	const confirmInput = () =>
		document.body.querySelector('input[name="world-rollback-confirm"]') as HTMLInputElement;

	it('每个快照行都有「回滚到此」;点开只弹确认框,显示丢弃后续与归档说明,不直接回滚', async () => {
		const { container } = render(Worlds);
		await settle();
		await fireEvent.click(byLabel(container, '快照 sim-1')!);
		await settle();
		const rows = [...document.body.querySelectorAll('button')].filter(
			(b) => b.textContent?.trim() === '回滚到此'
		);
		expect(rows.length).toBe(2);
		await fireEvent.click(byLabel(document.body, `回滚到快照 ${SNAPS[1].created_at}`)!);
		await settle();
		const text = document.body.textContent ?? '';
		expect(text).toContain('回滚世界 sim-1');
		expect(text).toContain(SNAPS[1].created_at);
		expect(text).toContain(
			'该世界在这份快照之后写入的所有记忆都会被丢弃。当前的库会改名保留在该世界的 archive 目录，可手动恢复。'
		);
		expect(rollback).not.toHaveBeenCalled();
	});

	it('文件缺失的快照不给「回滚到此」(后端必回 snapshot_corrupt)', async () => {
		snapshots.mockReset().mockResolvedValue({
			snapshots: [{ ...SNAPS[0], size_bytes: 0, missing: true }, SNAPS[1]]
		});
		const { container } = render(Worlds);
		await settle();
		await fireEvent.click(byLabel(container, '快照 sim-1')!);
		await settle();
		expect(byLabel(document.body, `回滚到快照 ${SNAPS[0].created_at}`)).toBeUndefined();
		expect(byLabel(document.body, `回滚到快照 ${SNAPS[1].created_at}`)).toBeDefined();
	});

	it('手输世界名完全一致之前确认键禁用;一致后才调用 rollback(name, snapshotId, confirm)', async () => {
		rollback.mockResolvedValue({ world: 'sim-1', snapshot_id: 's-man', archived: true, active: false });
		const { container } = render(Worlds);
		await settle();
		await openRollback(container, 'sim-1');

		expect(inBody('确认回滚')!.disabled).toBe(true);
		await fireEvent.click(inBody('确认回滚')!);
		expect(rollback).not.toHaveBeenCalled();

		for (const wrong of ['sim', 'sim-1 ', 'SIM-1', 'default']) {
			await fireEvent.input(confirmInput(), { target: { value: wrong } });
			await tick();
			expect(inBody('确认回滚')!.disabled, wrong).toBe(true);
		}

		await fireEvent.input(confirmInput(), { target: { value: 'sim-1' } });
		await tick();
		expect(inBody('确认回滚')!.disabled).toBe(false);
		await fireEvent.click(inBody('确认回滚')!);
		await settle();
		expect(rollback).toHaveBeenCalledTimes(1);
		expect(rollback).toHaveBeenCalledWith('sim-1', 's-man', 'sim-1');
	});

	it('函数级守卫:绕过按钮的 disabled 也不会在名称不符时调用 rollback', async () => {
		const { container } = render(Worlds);
		await settle();
		await openRollback(container, 'sim-1');
		await fireEvent.input(confirmInput(), { target: { value: 'sim' } });
		await tick();
		const btn = inBody('确认回滚')!;
		btn.disabled = false;
		await fireEvent.click(btn);
		await settle();
		expect(rollback).not.toHaveBeenCalled();
	});

	it('回滚活动世界成功:整页刷新', async () => {
		rollback.mockResolvedValue({ world: 'default', snapshot_id: 's-man', archived: true, active: true });
		const { container } = render(Worlds);
		await settle();
		await openRollback(container, 'default');
		expect(document.body.textContent).toContain('完成后页面会自动刷新');
		await fireEvent.input(confirmInput(), { target: { value: 'default' } });
		await tick();
		await fireEvent.click(inBody('确认回滚')!);
		await settle();
		expect(rollback).toHaveBeenCalledWith('default', 's-man', 'default');
		expect(reload).toHaveBeenCalledTimes(1);
		// 重载前的空档里按钮不复位,免得再点一次
		expect(inBody('确认回滚')!.disabled).toBe(true);
	});

	it('回滚非活动世界成功:toast、关确认框、重取列表,不整页刷新', async () => {
		rollback.mockResolvedValue({ world: 'sim-1', snapshot_id: 's-man', archived: true, active: false });
		const { container } = render(Worlds);
		await settle();
		const before = list.mock.calls.length;
		await openRollback(container, 'sim-1');
		await fireEvent.input(confirmInput(), { target: { value: 'sim-1' } });
		await tick();
		await fireEvent.click(inBody('确认回滚')!);
		await settle();
		expect(reload).not.toHaveBeenCalled();
		expect(list.mock.calls.length).toBeGreaterThan(before);
		expect(toastSuccess).toHaveBeenCalledTimes(1);
		expect(String(toastSuccess.mock.calls[0][0])).toContain('sim-1');
		expect(confirmInput()).toBeNull(); // 确认框已关
	});

	it('请求在途:确认键、各行「回滚到此」与「删除」都禁用,不能重复提交', async () => {
		let resolve!: (v: unknown) => void;
		rollback.mockReturnValue(new Promise((r) => (resolve = r)));
		const { container } = render(Worlds);
		await settle();
		await openRollback(container, 'sim-1');
		await fireEvent.input(confirmInput(), { target: { value: 'sim-1' } });
		await tick();
		await fireEvent.click(inBody('确认回滚')!);
		await settle();
		expect(inBody('确认回滚')!.disabled).toBe(true);
		expect(document.body.textContent).toContain('请不要关闭页面');
		const rowButtons = [...document.body.querySelectorAll('button')].filter((b) => {
			const l = b.getAttribute('aria-label') ?? '';
			return l.startsWith('回滚到快照') || l.startsWith('删除快照');
		});
		expect(rowButtons.length).toBe(4);
		expect(rowButtons.every((b) => b.disabled)).toBe(true);
		expect(button(container, '切换到此世界')!.disabled).toBe(true);
		await fireEvent.click(inBody('确认回滚')!);
		expect(rollback).toHaveBeenCalledTimes(1);
		resolve({ world: 'sim-1', snapshot_id: 's-man', archived: true, active: false });
		await settle();
	});

	it('失败:错误码经 worldErrorMessage 出中文 toast,不刷新页面,确认键恢复可点', async () => {
		rollback.mockRejectedValue(apiErr(409, 'snapshot_corrupt'));
		const { container } = render(Worlds);
		await settle();
		await openRollback(container, 'sim-1');
		await fireEvent.input(confirmInput(), { target: { value: 'sim-1' } });
		await tick();
		await fireEvent.click(inBody('确认回滚')!);
		await settle();
		expect(toastError).toHaveBeenCalledWith('快照文件损坏或缺失，未做任何改动');
		expect(reload).not.toHaveBeenCalled();
		expect(inBody('确认回滚')!.disabled).toBe(false);
	});

	it('活动世界回滚被拒(ingest_busy)同样不刷新页面', async () => {
		rollback.mockRejectedValue(apiErr(409, 'ingest_busy'));
		const { container } = render(Worlds);
		await settle();
		await openRollback(container, 'default');
		await fireEvent.input(confirmInput(), { target: { value: 'default' } });
		await tick();
		await fireEvent.click(inBody('确认回滚')!);
		await settle();
		expect(toastError).toHaveBeenCalledWith(worldErrorMessage('ingest_busy'));
		expect(reload).not.toHaveBeenCalled();
	});
});

describe('/worlds 回滚归档', () => {
	const WITH_ARCHIVES = {
		...DATA,
		worlds: [DATA.worlds[0], { ...DATA.worlds[1], archives: 2, archive_bytes: 1536 }]
	};
	beforeEach(() => {
		list.mockReset().mockResolvedValue(WITH_ARCHIVES);
		purgeArchives.mockReset();
		toastError.mockReset();
		toastSuccess.mockReset();
	});
	const purgeInput = () =>
		document.body.querySelector('input[name="world-purge-confirm"]') as HTMLInputElement;

	it('archives 为 0 时不显示归档行与「清理归档」', async () => {
		list.mockReset().mockResolvedValue(DATA);
		const { container } = render(Worlds);
		await settle();
		expect(button(container, '清理归档')).toBeUndefined();
		expect(container.textContent).not.toMatch(/归档 \d+ 份/);
	});

	it('archives > 0 时只在那一行显示「归档 N 份 · 大小」与「清理归档」', async () => {
		const { container } = render(Worlds);
		await settle();
		expect(container.textContent).toContain('归档 2 份 · 1.5 KB');
		expect(container.textContent?.match(/归档 \d+ 份/g)?.length).toBe(1);
		const btns = [...container.querySelectorAll('button')].filter(
			(b) => b.textContent?.trim() === '清理归档'
		);
		expect(btns.length).toBe(1);
		expect(btns[0].getAttribute('aria-label')).toBe('清理归档 sim-1');
	});

	it('手输世界名一致后才调用 purgeArchives(name, confirm);成功后 toast 并重取列表', async () => {
		purgeArchives.mockResolvedValue({ deleted: 2 });
		const { container } = render(Worlds);
		await settle();
		const before = list.mock.calls.length;
		await fireEvent.click(button(container, '清理归档')!);
		await settle();
		expect(document.body.textContent).toContain('清理 sim-1 的回滚归档');
		expect(document.body.textContent).toContain('将永久删除世界「sim-1」的 2 份回滚归档（1.5 KB）');

		expect(inBody('确认清理')!.disabled).toBe(true);
		await fireEvent.click(inBody('确认清理')!);
		expect(purgeArchives).not.toHaveBeenCalled();

		await fireEvent.input(purgeInput(), { target: { value: 'sim' } });
		await tick();
		expect(inBody('确认清理')!.disabled).toBe(true);
		await fireEvent.input(purgeInput(), { target: { value: 'sim-1' } });
		await tick();
		expect(inBody('确认清理')!.disabled).toBe(false);
		await fireEvent.click(inBody('确认清理')!);
		await settle();
		expect(purgeArchives).toHaveBeenCalledWith('sim-1', 'sim-1');
		expect(toastSuccess).toHaveBeenCalledTimes(1);
		expect(String(toastSuccess.mock.calls[0][0])).toContain('2');
		expect(list.mock.calls.length).toBeGreaterThan(before);
		expect(purgeInput()).toBeNull();
	});

	it('函数级守卫:绕过 disabled 也不会在名称不符时调用 purgeArchives', async () => {
		const { container } = render(Worlds);
		await settle();
		await fireEvent.click(button(container, '清理归档')!);
		await settle();
		const btn = inBody('确认清理')!;
		btn.disabled = false;
		await fireEvent.click(btn);
		await settle();
		expect(purgeArchives).not.toHaveBeenCalled();
	});

	it('请求在途时确认键禁用,不能重复提交', async () => {
		let resolve!: (v: unknown) => void;
		purgeArchives.mockReturnValue(new Promise((r) => (resolve = r)));
		const { container } = render(Worlds);
		await settle();
		await fireEvent.click(button(container, '清理归档')!);
		await settle();
		await fireEvent.input(purgeInput(), { target: { value: 'sim-1' } });
		await tick();
		await fireEvent.click(inBody('确认清理')!);
		await settle();
		expect(inBody('确认清理')!.disabled).toBe(true);
		await fireEvent.click(inBody('确认清理')!);
		expect(purgeArchives).toHaveBeenCalledTimes(1);
		resolve({ deleted: 2 });
		await settle();
	});

	it('失败:错误码经 worldErrorMessage 出中文 toast', async () => {
		purgeArchives.mockRejectedValue(apiErr(400, 'confirm_mismatch'));
		const { container } = render(Worlds);
		await settle();
		await fireEvent.click(button(container, '清理归档')!);
		await settle();
		await fireEvent.input(purgeInput(), { target: { value: 'sim-1' } });
		await tick();
		await fireEvent.click(inBody('确认清理')!);
		await settle();
		expect(toastError).toHaveBeenCalledWith('输入的名称与世界名不一致');
		expect(inBody('确认清理')!.disabled).toBe(false);
	});
});
