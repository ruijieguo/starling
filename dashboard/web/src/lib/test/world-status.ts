// 测试共用的世界状态标记(第 5 期 Task 5.1,裁定 R110 M4)。页面测试用 noteWorldStatus 登记当前世界的状态,
// 再断言写入按钮的 disabled / title;各测试不再各写一份同样的常量。
// 只放标记本身,不放文案:断言里的文案仍写字面量,改了文案测试要红。
import type { WorldStatusFlags } from '$lib/worlds';

/** 一个可写、没被占用、库版本不落后的世界。 */
export const WRITABLE_FLAGS: WorldStatusFlags = {
	seed: false,
	read_only: false,
	reclaimable: false,
	open_mode: 'rw',
	schema_behind: false,
	held_by_client: false
};

/**
 * 在 WRITABLE_FLAGS 上改几项。参数放宽成 unknown:it.each 的表格里 open_mode: 'ro' 会被推成 string,
 * 这样调用方不用再写类型断言。
 */
export function flagsWith(
	over: Partial<{ [K in keyof WorldStatusFlags]: unknown }> = {}
): WorldStatusFlags {
	return { ...WRITABLE_FLAGS, ...over } as WorldStatusFlags;
}
