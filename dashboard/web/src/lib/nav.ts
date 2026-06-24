// 导航的单一来源(P2.n 收尾:标题全中文 + 条目图标)。
// 后续 i18n(跟随系统语言):把 label 改成 { zh, en } 字典并按
// navigator.language 解析成当前文案——壳与面包屑只读这里,届时不动调用方。
export type NavItem = { href: string; label: string; icon: string };
export type NavGroup = { title: string; items: NavItem[] };

export const NAV_GROUPS: NavGroup[] = [
	{
		title: '观测',
		items: [
			{ href: '/', label: '总览', icon: 'dashboard' },
			{ href: '/statements', label: '语句', icon: 'file-text' },
			{ href: '/cognizers', label: '认知体', icon: 'users' },
			{ href: '/commitments', label: '承诺', icon: 'clipboard-check' }
		]
	},
	{
		title: '交互',
		items: [
			{ href: '/converse', label: '对话', icon: 'message' },
			{ href: '/interact', label: '交互', icon: 'terminal' },
			{ href: '/working-set', label: '工作集', icon: 'layers' },
			{ href: '/reminders', label: '承诺提醒', icon: 'bell' }
		]
	},
	{
		title: '诊断',
		items: [
			{ href: '/vitals', label: '生命体征', icon: 'activity' },
			{ href: '/queues', label: '队列', icon: 'list' },
			{ href: '/conflicts', label: '冲突', icon: 'zap' },
			{ href: '/replay', label: '回放', icon: 'rotate-ccw' },
			{ href: '/eval', label: '评测', icon: 'bar-chart' }
		]
	},
	{ title: '设置', items: [{ href: '/settings', label: '设置', icon: 'sliders' }] }
];

export const ALL_NAV_ITEMS = NAV_GROUPS.flatMap((g) =>
	g.items.map((i) => ({ ...i, group: g.title }))
);
