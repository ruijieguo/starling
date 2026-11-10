<script lang="ts">
	// 顶栏下的世界状态横幅(第 5 期 Task 5.1,spec §14):只读、被客户端占用、schema 落后,各一条。
	// 取数沿用设置页的做法:当前世界(URL ?world=)的详情 worldsApi.detail,不另开轮询。重取的时机:
	//   · 换世界;
	//   · 换页(路径变了)——客户端开关句柄不发 WS 事件,换页时顺带刷新一次占用状态;
	//   · 当前世界改变可见状态的 WS 事件(与各页同一判据 refetchOnEvent,纯读的 recall 不算);
	//   · 写入被后端拒绝(world_held / world_read_only,noteWriteRejected 计数变了):前端以为可写,状态旧了(裁定 R113 I-1);
	//   · WS 断开后重连:服务重启会断开所有客户端会话,占用随之解除(裁定 R113 M1)。首次连上不算,挂载时刚取过。
	// 取到的标记登记给 world.svelte(noteWorldStatus),各页写入按钮的置灰读同一份(currentWriteBlockedReason)。
	// 取不到时保留上一次的结果(属于别的世界的不算),没有结果就什么都不渲染。
	import { untrack } from 'svelte';
	import { page } from '$app/state';
	import { lastWsEvent, wsConn } from '$lib/health';
	import {
		currentWorld, noteWorldStatus, refetchOnEvent, worldStatusOf, writeRejectionCount
	} from '$lib/world.svelte';
	import { WORLD_STATUS_TEXT, worldStatusNotices, worldsApi, type WorldNotice } from '$lib/worlds';

	let world = $derived(currentWorld());
	let path = $derived(page.url.pathname);
	let notices = $derived(worldStatusNotices(worldStatusOf(world)));

	let req = 0; // 防陈旧:换世界后只让最新一次的详情落地
	async function load(w: string) {
		const mine = ++req;
		try {
			const d = await worldsApi.detail(w);
			if (mine === req) noteWorldStatus(w, d);
		} catch {
			/* 横幅只是提示:取不到不打扰页面,写入的最终判定在后端 */
		}
	}

	$effect(() => {
		const w = world;
		void path;
		untrack(() => void load(w));
	});
	$effect(() => {
		if (refetchOnEvent($lastWsEvent)) untrack(() => void load(world));
	});
	let seenRejections = untrack(writeRejectionCount);
	$effect(() => {
		const n = writeRejectionCount();
		if (n === seenRejections) return;
		seenRejections = n;
		untrack(() => void load(world));
	});
	let seenOpen = false; // 连上过一次之后,再变成 open 才是重连
	$effect(() => {
		if ($wsConn !== 'open') return;
		if (!seenOpen) {
			seenOpen = true;
			return;
		}
		untrack(() => void load(world));
	});

	const TONE: Record<WorldNotice, string> = {
		read_only: 'border-info/40 bg-info/10 text-info',
		held: 'border-warn/40 bg-warn/10 text-warn',
		schema_behind: 'border-warn/40 bg-warn/10 text-warn'
	};
</script>

{#if notices.length}
	<div class="space-y-2 px-6 pt-4">
		{#each notices as n (n)}
			<p role="status" class="break-words rounded-control border px-3 py-2 text-xs {TONE[n]}">
				{WORLD_STATUS_TEXT[n]}
			</p>
		{/each}
	</div>
{/if}
