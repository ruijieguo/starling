// 当前页面选中的世界。
//
// 选中的世界只存在 URL 查询参数 ?world= 里(裁定 R44):刷新、分享链接、浏览器后退都自然带着它,
// 没有任何全局"活动世界"状态。缺省(没有 ?world=)就是注册表的默认世界,此时请求走旧路径 /api/x。
//
// 本模块不依赖 api.ts(api.ts 的 worldPath 反过来要读这里),默认世界名由壳层(+layout.svelte)
// 启动时取一次 GET /api/worlds 后用 noteDefaultWorld 登记。

import { page } from '$app/state';
import { goto } from '$app/navigation';
import { untrack } from 'svelte';
import { shouldRefetch } from './feed';
import type { WsEvent } from './ws';
import type { WorldStatusFlags } from './worlds'; // 只取类型:运行时仍不依赖 worlds.ts / api.ts

const PARAM = 'world';

// 默认世界名。登记之前先假定 "default"(没有注册表时后端也叫这个名字,裁定 R6)。
let defaultName = $state('default');

/** 登记注册表的默认世界名(GET /api/worlds 的 default)。 */
export function noteDefaultWorld(name: string): void {
	if (name) defaultName = name;
}

export function defaultWorld(): string {
	return defaultName;
}

// 当前世界的状态标记(第 5 期,spec §14)。壳层的 WorldStatusBanner 取当前世界的详情后登记在这里,
// 各页的写入按钮读它置灰(lib/worlds.ts 的 currentWriteBlockedReason),不各自再取一次。只存一份,
// 并记着它属于哪个世界:换世界后、新详情回来之前,worldStatusOf(新世界) 为 null(按未知处理,不置灰)。
let worldStatus = $state<{ world: string; flags: WorldStatusFlags } | null>(null);

/** 登记 world 的状态标记;flags 为 null 时清掉(只清属于 world 的那份)。 */
export function noteWorldStatus(world: string, flags: WorldStatusFlags | null): void {
	if (flags) {
		const { seed, read_only, reclaimable, open_mode, schema_behind, held_by_client } = flags;
		worldStatus = {
			world,
			flags: { seed, read_only, reclaimable, open_mode, schema_behind, held_by_client }
		};
	} else if (worldStatus?.world === world) {
		worldStatus = null;
	}
}

/** world 已登记的状态标记;没登记、或登记的是别的世界时为 null。 */
export function worldStatusOf(world: string): WorldStatusFlags | null {
	return worldStatus && worldStatus.world === world ? worldStatus.flags : null;
}

// 写入被后端拒绝的次数(裁定 R113 I-1)。客户端开、关句柄不发 WS 事件(裁定 R109-1),横幅可能还停在「可写」;
// 这时写入被拒(world_held / world_read_only)就说明状态旧了。横幅读这个计数,变了就重取当前世界的详情,
// 不另开轮询。计数只增不减,读到的具体值没有意义。
const REJECTION_CODES = new Set(['world_held', 'world_read_only']);
let writeRejections = $state(0);

/**
 * 写入的错误码是 world_held / world_read_only 就登记一次,横幅随之重取;其他码不登记。
 * api.ts 的 req 对 POST/PUT/DELETE 的错误响应调它,/ws/converse 的 error 帧由对话页调它。
 */
export function noteWriteRejected(code: string): void {
	if (REJECTION_CODES.has(code)) writeRejections++;
}

/** 写入被拒的累计次数(横幅的取数 effect 读它)。 */
export function writeRejectionCount(): number {
	return writeRejections;
}

/** URL 里显式写的 ?world=;没写为 null。 */
export function explicitWorld(): string | null {
	return page.url.searchParams.get(PARAM) || null;
}

/** URL ?world= 指定的世界;没有则是默认世界。 */
export function currentWorld(): string {
	return page.url.searchParams.get(PARAM) || defaultName;
}

/**
 * 切换当前世界:只改 URL,不发任何请求。各页的查询取数时读 currentWorld(),
 * 世界变了它们自己重取。选默认世界时去掉 ?world=,地址栏回到旧样子。
 */
export function setWorld(name: string): void {
	const url = new URL(page.url);
	if (!name || name === defaultName) url.searchParams.delete(PARAM);
	else url.searchParams.set(PARAM, name);
	void goto(url.pathname + url.search + url.hash, {
		replaceState: true,
		keepFocus: true,
		noScroll: true
	});
}

/** 站内链接保留当前 ?world=:URL 里带着它时,把它写进 href;否则原样返回。 */
export function withWorld(href: string): string {
	const w = page.url.searchParams.get(PARAM);
	if (!w) return href;
	const u = new URL(href, 'http://x');
	u.searchParams.set(PARAM, w);
	return u.pathname + u.search + u.hash;
}

/**
 * 页面的 WS 增量刷新判据:这条消息改变了当前世界的可见状态吗?
 * 当前世界用 untrack 读:只在消息到来时比对,世界本身变化由各页查询的取数 effect 负责重取,
 * 不在这里再触发一次。
 */
export function refetchOnEvent(e: WsEvent | null | undefined): boolean {
	return shouldRefetch(e, untrack(currentWorld));
}

/**
 * 当前世界变了就调 cb(组件初始化时调用)。详情抽屉、确认框这类"属于某个世界的某一行"的状态
 * 用它在换世界时关掉/清空,免得上一个世界的行挂在新世界的名字下面。首次运行不触发。
 */
export function onWorldChange(cb: () => void): void {
	let last = currentWorld();
	$effect(() => {
		const w = currentWorld();
		if (w === last) return;
		last = w;
		untrack(cb);
	});
}
