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
			{ href: '/interact', label: '交互', icon: 'terminal' }
		]
	},
	{
		title: '短期记忆 · 海马',
		items: [{ href: '/working-set', label: '工作集', icon: 'layers' }]
	},
	{
		title: '长期记忆 · 新皮层',
		items: [{ href: '/statements', label: '语句', icon: 'file-text' }]
	},
	{
		title: '他者心智 · 心智化',
		items: [{ href: '/cognizers', label: '认知体', icon: 'users' }]
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
