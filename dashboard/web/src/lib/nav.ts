// 导航的单一来源(Phase 3 片 1:类脑 IA 重组,经 plan-design-review 定稿)。
// 脑区按记忆流排序,组名统一「功能 · 脑区 gloss」全中文。subtraction default:
// 尚未落地的脑区不在此渲染——空组不出占位(透视镜 · Lens 已随片 3 落地,加入下方)。
// 后续 i18n(跟随系统语言):把 label 改成 { zh, en } 字典并按
// navigator.language 解析成当前文案——壳与面包屑只读这里,届时不动调用方。
export type NavItem = { href: string; label: string; icon: string };
export type NavGroup = { title: string; items: NavItem[] };

export const NAV_GROUPS: NavGroup[] = [
	{
		title: '总览',
		items: [
			{ href: '/brain', label: '脑区地图', icon: 'brain' },
			{ href: '/', label: '概览', icon: 'dashboard' }
		]
	},
	{
		// T0a — 原始数据·证据(engram):记忆流最上游的不可变原文来源,排在
		// 「总览」之后、「对话」之前(先于海马快记忆/新皮层慢记忆)。NavIcon 不
		// 支持 'database',借用已支持的 'file-text'(原文本证据的语义近似;
		// nav.ts 中图标本就有跨组复用先例,如 'zap' 用于冲突与运行时健康两组)。
		title: '原始数据 · 证据',
		items: [{ href: '/engrams', label: '原始数据', icon: 'file-text' }]
	},
	{
		title: '对话',
		items: [
			{ href: '/converse', label: '对话', icon: 'message' },
			{ href: '/interact', label: '交互', icon: 'terminal' },
			// T0c — working-set 从「短期记忆 · 海马」组归位到这里(它是对话侧的
			// 上下文预算视角,不是海马生理状态视角;海马组现由 T0b 的短期记忆
			// 快捷视角深链填充,见下方)。
			{ href: '/working-set', label: '工作集', icon: 'layers' }
		]
	},
	{
		// T0b — 海马组不再指向 working-set(那是对话侧视角,已迁移到「对话」组),
		// 换成 statements 页的 consolidation_state 深链:VOLATILE + 两个
		// REPLAYING_* 态一次筛(海马快记忆三态,值域以 C++ ConsolidationState
		// 枚举为准)。若不填充此项,空组按 subtraction default 不渲染,组会消失。
		title: '短期记忆 · 海马',
		items: [
			{
				href: '/statements?consolidation_state=volatile,replaying_consolidating,replaying_reconsolidating',
				label: '短期记忆',
				icon: 'layers'
			}
		]
	},
	{
		// T0d-1 — 新皮层组从裸 /statements 扩为三条深链:保留「全部语句」,
		// 加 Semantic(modality=believes,knows)与 Norms(modality=norm_ought,
		// norm_forbid)两个已确证子区(照 T0b 的 consolidation_state 深链范式)。
		// T0d-2 — 再补三条:程序(Skill)、画像(Persona)、共识(CommonGround)。
		// 后两条是 containers/common_ground 只读派生页;程序页 /procedural 是诚实空态
		// ——ConsolidationOp 无 forge_skill、modality 无 SKILL 值,Skill 巩固尚未实装,
		// 故不做任何过滤(会得空结果或误含 norm gist),只显一张说明卡片。三条皆裸 href
		// 无 query,直接受 matchesHref 支持,无需改 +layout.svelte。
		title: '长期记忆 · 新皮层',
		items: [
			{ href: '/statements', label: '全部语句', icon: 'file-text' },
			{
				href: '/statements?modality=believes,knows',
				label: '语义',
				icon: 'file-text'
			},
			{
				href: '/statements?modality=norm_ought,norm_forbid',
				label: '规范',
				icon: 'file-text'
			},
			{ href: '/procedural', label: '程序 · Skill', icon: 'file-text' },
			{ href: '/personae', label: '画像 · Persona', icon: 'users' },
			{ href: '/common-ground', label: '共识 · CommonGround', icon: 'clipboard-check' }
		]
	},
	{
		// T0e ② — 加一条 belief_order=higher 深链(二阶及以上信念视角:我以为你信 X),
		// 照 T0b 海马组深链范式。裸 /cognizers 保留。
		title: '他者心智 · 心智化',
		items: [
			{ href: '/cognizers', label: '认知体', icon: 'users' },
			{ href: '/statements?belief_order=higher', label: '二阶信念视角', icon: 'file-text' }
		]
	},
	{
		title: '意图与承诺 · 前额叶',
		items: [
			{ href: '/commitments', label: '承诺', icon: 'clipboard-check' },
			{ href: '/reminders', label: '提醒', icon: 'bell' }
		]
	},
	{
		title: '睡眠与固化 · 回放',
		items: [
			{ href: '/replay', label: '回放', icon: 'rotate-ccw' },
			{ href: '/gists', label: '固化 gist', icon: 'sparkles' },
			{ href: '/lifecycle', label: '生命周期', icon: 'git-branch' },
			{ href: '/forecast', label: '衰减预报', icon: 'trending-down' },
			{ href: '/conflicts', label: '冲突', icon: 'zap' }
		]
	},
	{
		title: '透视镜',
		items: [{ href: '/lens', label: '透视镜', icon: 'eye' }]
	},
	{
		title: '生命体征 · 脑干',
		items: [
			{ href: '/vitals', label: '生命体征', icon: 'activity' },
			{ href: '/queues', label: '队列', icon: 'list' },
			{ href: '/eval', label: '评测', icon: 'bar-chart' },
			{ href: '/runtime-health', label: '运行时健康', icon: 'zap' }
		]
	},
	{
		title: '配置',
		items: [{ href: '/settings', label: '设置', icon: 'sliders' }]
	}
];

// 扁平条目,每条带回所属组名(面包屑 Starling › 组 › 页 + ⌘K 搜索用,壳只读这里)。
export type NavItemWithGroup = NavItem & { group: string };
export const ALL_NAV_ITEMS: NavItemWithGroup[] = NAV_GROUPS.flatMap((g) =>
	g.items.map((i) => ({ ...i, group: g.title }))
);

// nav item href 是否匹配当前 URL(active 高亮 + 面包屑用)。深链 item 的 href 带
// query(如 /statements?consolidation_state=volatile,...);裸 pathname 精确比较会
// 让深链永不高亮、面包屑消失(T0b+T0c 引入,T0d/T0e/T0f 会复现)。规则:pathname
// 必须相等;href 带的每个 query 参数都要在当前 URL 出现且值相等(当前 URL 可多带别的
// 参数)。href 无 query 时退化为纯 pathname 匹配。壳与 nav.test 共用此单一逻辑。
export function matchesHref(href: string, current: URL): boolean {
	const q = href.indexOf('?');
	const hrefPath = q === -1 ? href : href.slice(0, q);
	if (hrefPath !== current.pathname) return false;
	if (q === -1) return true;
	const hrefParams = new URLSearchParams(href.slice(q + 1));
	for (const [k, v] of hrefParams) {
		if (current.searchParams.get(k) !== v) return false;
	}
	return true;
}

// 当前 URL 对应的 nav 条目(面包屑用)。多个 item 同 pathname 时(裸 /statements 与
// 带 query 的深链),优先返回 query 也匹配的那个,让面包屑指向更具体的深链视角。
export function activeNavItem(current: URL): NavItemWithGroup | undefined {
	const matches = ALL_NAV_ITEMS.filter((i) => matchesHref(i.href, current));
	if (matches.length <= 1) return matches[0];
	// 有 query 的候选更具体,优先。
	return matches.find((i) => i.href.includes('?')) ?? matches[0];
}
