<script lang="ts">
	import { untrack } from 'svelte';
	import { createQuery } from '$lib/query.svelte';
	import { lastWsEvent } from '$lib/health';
	import { mutatesMemory } from '$lib/ws';
	import { toast } from '$lib/ui/toast';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import {
		Badge,
		Button,
		Card,
		ConfirmDialog,
		Drawer,
		EmptyState,
		Field,
		Input,
		Skeleton
	} from '$lib/components/ui';
	import {
		apiDetail,
		formatBytes,
		isValidWorldName,
		worldErrorMessage,
		worldsApi,
		type SnapshotRow,
		type WorldRow
	} from '$lib/worlds';

	// W1/W2 — 世界管理:一个世界 = 一个库文件 + 一个租户(HTTP 契约见 $lib/worlds)。
	const q = createQuery(() => worldsApi.list());
	$effect(() => {
		q.refetch();
	});
	// world_switched / snapshot_created 都归入 mutatesMemory 的「会改变可见状态」一侧
	// (只有 recall 是纯读,见 $lib/ws),所以这一个判据同时覆盖两种事件。
	// 快照抽屉开着时一并重取它的列表;抽屉状态用 untrack 读,免得开关抽屉本身触发重取。
	$effect(() => {
		if (!mutatesMemory($lastWsEvent)) return;
		untrack(() => {
			void q.refetch();
			if (snapOpen && snapWorld) void loadSnaps(snapWorld);
		});
	});

	let worlds = $derived(q.data?.worlds ?? []);
	let defaultName = $derived(q.data?.default ?? '');
	let retention = $derived(q.data?.snapshot_retention);

	const errText = (e: unknown) => worldErrorMessage(apiDetail(e));
	const worldTitle = (w: WorldRow) => (w.label ? `${w.name} · ${w.label}` : w.name);
	const statsLine = (w: WorldRow) =>
		`语句 ${w.statements} · 原始数据 ${w.engrams} · 活数据 ${formatBytes(w.live_bytes)} · ` +
		`文件 ${formatBytes(w.db_bytes)} · 快照 ${w.snapshots} 份（${formatBytes(w.snapshot_bytes)}）`;
	// 默认世界和活动世界不可删;后端同样拒绝(world_protected),前端不给入口。
	const isDeletable = (w: WorldRow) => !w.active && w.name !== defaultName;

	// ── 新建 ──────────────────────────────────────────────────────────────
	let newName = $state('');
	let newLabel = $state('');
	let creating = $state(false);
	let nameValid = $derived(isValidWorldName(newName));
	// 空输入不标红:还没写不算写错,只是不能提交。
	let nameInvalid = $derived(newName !== '' && !nameValid);

	async function doCreate() {
		if (creating || !nameValid) return; // 函数级守卫:不依赖按钮的 disabled
		const name = newName;
		creating = true;
		try {
			await worldsApi.create(name, newLabel.trim());
			toast.success(`已创建世界「${name}」`);
			newName = '';
			newLabel = '';
			await q.refetch();
		} catch (e) {
			toast.error(errText(e));
		} finally {
			creating = false;
		}
	}

	// ── 切换 ──────────────────────────────────────────────────────────────
	let switchOpen = $state(false);
	let switchTarget = $state('');
	let switching = $state<string | null>(null);

	function askSwitch(name: string) {
		switchTarget = name;
		switchOpen = true;
	}

	async function doSwitch() {
		const name = switchTarget;
		if (!name || switching !== null) return;
		switching = name;
		try {
			await worldsApi.activate(name);
		} catch (e) {
			toast.error(errText(e));
			switching = null;
			return;
		}
		// 成功后不复位 switching:页面马上整页重载,别让按钮在重载前的空档里重新可点。
		// 其他页面都按旧世界缓存了数据;整页刷新是唯一可靠的清法(spec §8:切换后新请求都走新引擎)。
		location.reload();
	}

	// ── 删除(抽屉 + 手输世界名) ─────────────────────────────────────────
	let deleteOpen = $state(false);
	let deleteTarget = $state('');
	let deleteConfirm = $state('');
	let deleting = $state(false);
	let deleteRow = $derived(worlds.find((w) => w.name === deleteTarget));
	// 抽屉开着时列表可能因 ws 事件刷新(目标恰好成了活动世界),所以每次都按最新行重判。
	let canDelete = $derived(
		!!deleteRow &&
			isDeletable(deleteRow) &&
			deleteConfirm === deleteRow.name &&
			switching === null &&
			!deleting
	);

	function askDelete(name: string) {
		deleteTarget = name;
		deleteConfirm = '';
		deleteOpen = true;
	}

	async function doDelete() {
		if (!canDelete) return; // 函数级守卫:前端校验一次,后端 confirm_mismatch 再校验一次
		const name = deleteTarget;
		deleting = true;
		try {
			await worldsApi.remove(name, deleteConfirm);
			toast.success(`已删除世界「${name}」`);
			deleteOpen = false;
			deleteConfirm = '';
			await q.refetch();
		} catch (e) {
			toast.error(errText(e));
		} finally {
			deleting = false;
		}
	}

	// ── 快照 ──────────────────────────────────────────────────────────────
	let snapOpen = $state(false);
	let snapWorld = $state('');
	let snaps = $state<SnapshotRow[]>([]);
	let snapsLoading = $state(false);
	let snapsErr = $state('');
	let snapNote = $state('');
	let snapshotting = $state(false);
	let removeSnapOpen = $state(false);
	let removeSnapTarget = $state<SnapshotRow | null>(null);
	let removingSnap = $state<string | null>(null);
	let snapReq = 0; // 防陈旧:连点不同世界时,只让最新一次的列表落地

	async function loadSnaps(name: string) {
		const mine = ++snapReq;
		snapsLoading = true;
		snapsErr = '';
		try {
			const r = await worldsApi.snapshots(name);
			if (mine !== snapReq) return;
			snaps = r.snapshots;
		} catch (e) {
			if (mine !== snapReq) return;
			snaps = [];
			snapsErr = errText(e);
			toast.error(snapsErr);
		} finally {
			if (mine === snapReq) snapsLoading = false;
		}
	}

	function openSnapshots(name: string) {
		snapWorld = name;
		snapNote = '';
		snaps = [];
		snapOpen = true;
		void loadSnaps(name);
	}

	async function doSnapshot() {
		const name = snapWorld;
		if (!name || snapshotting) return;
		snapshotting = true;
		try {
			await worldsApi.snapshot(name, snapNote.trim());
			toast.success(`已为「${name}」拍下快照`);
			if (snapWorld === name) {
				snapNote = '';
				await loadSnaps(name);
			}
			void q.refetch();
		} catch (e) {
			toast.error(errText(e));
		} finally {
			snapshotting = false;
		}
	}

	function askRemoveSnap(s: SnapshotRow) {
		removeSnapTarget = s;
		removeSnapOpen = true;
	}

	async function doRemoveSnap() {
		const target = removeSnapTarget;
		const name = snapWorld;
		if (!target || !name || removingSnap !== null) return;
		removingSnap = target.id;
		try {
			await worldsApi.removeSnapshot(name, target.id);
			toast.success('已删除快照');
			if (snapWorld === name) await loadSnaps(name);
			void q.refetch();
		} catch (e) {
			toast.error(errText(e));
		} finally {
			removingSnap = null;
		}
	}
</script>

<PageHeader
	title="世界"
	subtitle="一个世界 = 一个数据库文件 + 一个租户。切换世界会重建引擎；快照是该世界库的紧凑只读副本。"
/>

{#if q.error && !q.data}
	<EmptyState title="加载失败" description={q.error.message}>
		<Button variant="soft" onclick={() => void q.refetch()}>重试</Button>
	</EmptyState>
{:else if !q.data}
	<div class="space-y-2">{#each Array(2) as _}<Skeleton class="h-24 w-full" />{/each}</div>
{:else}
	{#if q.error}
		<p class="mb-3 text-xs text-danger">刷新失败，下面可能是旧数据：{q.error.message}</p>
	{/if}

	<div class="space-y-3">
		{#each worlds as w (w.name)}
			<Card title={worldTitle(w)}>
				{#snippet actions()}
					{#if w.active}<Badge tone="brand">当前</Badge>{/if}
					{#if w.name === defaultName}<Badge tone="neutral">默认</Badge>{/if}
				{/snippet}
				<p class="text-xs tabular-nums text-muted">{statsLine(w)}</p>
				<div class="mt-3 flex flex-wrap gap-2">
					{#if !w.active}
						<Button
							variant="soft"
							aria-label={`切换到此世界 ${w.name}`}
							loading={switching === w.name}
							disabled={switching !== null || deleting}
							onclick={() => askSwitch(w.name)}>切换到此世界</Button
						>
					{/if}
					<Button
						variant="secondary"
						aria-label={`快照 ${w.name}`}
						onclick={() => openSnapshots(w.name)}>快照</Button
					>
					{#if isDeletable(w)}
						<Button
							variant="secondary"
							aria-label={`删除 ${w.name}`}
							disabled={switching !== null}
							onclick={() => askDelete(w.name)}>删除</Button
						>
					{/if}
				</div>
			</Card>
		{/each}

		<Card
			title="新建世界"
			description="创建一个新世界（独立的数据库文件与租户）。名称创建后不能修改。"
		>
			<form
				class="space-y-3"
				onsubmit={(e) => {
					e.preventDefault();
					void doCreate();
				}}
			>
				<Field
					label="名称"
					for="world-name"
					hint="小写字母或数字开头，可含下划线和连字符，最长 32 个字符"
					error={nameInvalid ? worldErrorMessage('invalid_world_name') : ''}
				>
					<Input
						id="world-name"
						name="world-name"
						bind:value={newName}
						invalid={nameInvalid}
						placeholder="sim-1"
						autocomplete="off"
						class="max-w-64"
					/>
				</Field>
				<Field label="显示名" for="world-label" hint="可选，只用来在列表里辨认">
					<Input
						id="world-label"
						name="world-label"
						bind:value={newLabel}
						autocomplete="off"
						class="max-w-64"
					/>
				</Field>
				<Button type="submit" variant="soft" loading={creating} disabled={!nameValid}
					>新建世界</Button
				>
			</form>
		</Card>
	</div>
{/if}

<ConfirmDialog
	bind:open={switchOpen}
	title={`切换到 ${switchTarget}？`}
	description="切换会停止当前世界的后台维护与摄入，并重建引擎。"
	confirmLabel="切换"
	onconfirm={doSwitch}
/>

<Drawer bind:open={deleteOpen} title={`删除世界 ${deleteTarget}`}>
	{#if deleteRow}
		<div class="space-y-3 text-sm">
			<p class="text-xs text-muted">
				将物理删除世界「{deleteRow.name}」，无法恢复；其他世界不受影响。
			</p>
			<p class="text-xs tabular-nums text-subtle">{statsLine(deleteRow)}</p>
			<Field label={`输入世界名「${deleteRow.name}」以确认`} for="world-delete-confirm">
				<Input
					id="world-delete-confirm"
					name="world-delete-confirm"
					bind:value={deleteConfirm}
					placeholder={deleteRow.name}
					autocomplete="off"
				/>
			</Field>
			<Button variant="danger" loading={deleting} disabled={!canDelete} onclick={doDelete}
				>确认删除</Button
			>
		</div>
	{/if}
</Drawer>

<Drawer bind:open={snapOpen} title={`${snapWorld} 的快照`}>
	<div class="space-y-3 text-sm">
		<div class="space-y-2">
			<Input
				name="snapshot-note"
				bind:value={snapNote}
				placeholder="备注（可选）"
				autocomplete="off"
				aria-label="快照备注"
			/>
			<Button variant="soft" loading={snapshotting} onclick={doSnapshot}>立即拍快照</Button>
			{#if snapshotting}
				<p class="text-xs text-subtle">正在拷贝整库，数据量大时需要一两分钟，请不要关闭页面。</p>
			{/if}
		</div>

		{#if snapsLoading && snaps.length === 0}
			<div class="space-y-2">{#each Array(3) as _}<Skeleton class="h-12 w-full" />{/each}</div>
		{:else if snapsErr}
			<div class="space-y-2">
				<p class="text-xs text-danger">{snapsErr}</p>
				<Button variant="secondary" onclick={() => void loadSnaps(snapWorld)}>重试</Button>
			</div>
		{:else if snaps.length === 0}
			<p class="text-xs text-subtle">还没有快照。</p>
		{:else}
			<ul class="divide-y divide-border">
				{#each snaps as s (s.id)}
					<li class="flex items-start justify-between gap-2 py-2">
						<div class="min-w-0 flex-1 space-y-1">
							<div class="flex flex-wrap items-center gap-2">
								<span class="break-all tabular-nums text-fg">{s.created_at}</span>
								<Badge tone={s.kind === 'auto' ? 'info' : 'neutral'}>{s.kind}</Badge>
							</div>
							<div class="text-xs tabular-nums text-subtle">
								世界时间 {s.world_time || '—'} · {formatBytes(s.size_bytes)}
							</div>
							{#if s.note}<div class="break-words text-xs text-muted">{s.note}</div>{/if}
						</div>
						<Button
							variant="secondary"
							aria-label={`删除快照 ${s.created_at}`}
							loading={removingSnap === s.id}
							disabled={removingSnap !== null}
							onclick={() => askRemoveSnap(s)}>删除</Button
						>
					</li>
				{/each}
			</ul>
		{/if}

		{#if retention != null}
			<p class="text-xs text-subtle">
				保留最近 {retention} 份，超出时优先清理自动快照，并至少保留 1 份自动快照作为回滚锚点。
			</p>
		{/if}
	</div>
</Drawer>

<ConfirmDialog
	bind:open={removeSnapOpen}
	title="删除这份快照？"
	description={removeSnapTarget
		? `${removeSnapTarget.created_at} 的 ${removeSnapTarget.kind} 快照（${formatBytes(removeSnapTarget.size_bytes)}）将被永久删除。`
		: ''}
	confirmLabel="确认删除"
	danger
	onconfirm={doRemoveSnap}
/>
