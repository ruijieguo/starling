<script lang="ts">
	import { Field, Input } from '$lib/components/ui';
	import { MAX_INTERVAL_HOURS, parseIntervalHours, worldErrorMessage } from '$lib/worlds';

	// W4 — 自动快照配置的两个字段(按会话 + 间隔小时数),新建世界表单与「设置」抽屉共用。
	// hours 由 type=number 的 input 绑定:可能是 number、空(null)或越界值,由调用方用
	// parseIntervalHours 解析后再提交;这里只负责标红与提示。
	let {
		onSession = $bindable(true),
		hours = $bindable<number | string | null>(0),
		idPrefix
	}: {
		onSession?: boolean;
		hours?: number | string | null;
		/** 元素 id/name 前缀:同一页上两份表单不能撞 id。 */
		idPrefix: string;
	} = $props();

	let invalid = $derived(parseIntervalHours(hours) === null);
</script>

<fieldset class="space-y-2">
	<legend class="text-xs font-medium text-muted">自动快照</legend>
	<div>
		<label class="inline-flex items-center gap-2 text-sm text-fg" for={`${idPrefix}-on-session`}>
			<input
				type="checkbox"
				id={`${idPrefix}-on-session`}
				name={`${idPrefix}-on-session`}
				class="size-4 accent-brand"
				aria-describedby={`${idPrefix}-on-session-hint`}
				bind:checked={onSession}
			/>
			按会话
		</label>
		<p id={`${idPrefix}-on-session-hint`} class="text-xs text-subtle">
			每个会话第一次写入之前先拍一份快照，作为回滚到该会话之前的锚点
		</p>
	</div>
	<Field
		label="间隔小时数"
		for={`${idPrefix}-interval`}
		hint="0 表示关闭；距上一份自动快照超过这么多小时、且期间有新写入时拍一份"
		error={invalid ? worldErrorMessage('invalid_auto_snapshot') : ''}
	>
		<Input
			id={`${idPrefix}-interval`}
			name={`${idPrefix}-interval`}
			type="number"
			min="0"
			max={MAX_INTERVAL_HOURS}
			step="1"
			inputmode="numeric"
			bind:value={hours}
			{invalid}
			autocomplete="off"
			class="max-w-32"
		/>
	</Field>
</fieldset>
