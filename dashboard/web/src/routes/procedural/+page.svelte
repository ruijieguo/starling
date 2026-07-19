<script lang="ts">
	import PageHeader from '$lib/components/PageHeader.svelte';
	import { EmptyState } from '$lib/components/ui';

	// T0d-2 — 新皮层 · 程序性记忆(Skill):诚实空态。
	// ConsolidationOp 枚举(src/replay/consolidation_ops.cpp)只有
	// Compress/Abstract/Reinforce/Decay/Reconcile,没有 forge_skill;modality 枚举也无
	// SKILL 值。文档中「Procedural=Skill,forge_skill 提升」是设计愿景、尚未实装。
	// 故本页不做任何 provenance/modality 过滤(那会得空结果或误含 norm gist、误导用户),
	// 只诚实说明该能力未落地。落地后此页替换为真实的 Skill 检视。
</script>

<PageHeader title="程序 · Skill" subtitle="程序性记忆:技能的固化与提升。" />

<EmptyState
	title="程序性记忆(Skill)尚未实装"
	description="forge_skill 巩固算子尚未在内核落地(ConsolidationOp 目前只有 Compress/Abstract/Reinforce/Decay/Reconcile),暂无程序性记忆数据。此页为占位说明,待该能力落地后替换为真实检视。"
/>
