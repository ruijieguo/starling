# P2.n — Dashboard 品味对齐(对标 OpenClaw Control UI)

> 背景:用户反馈「dashboard 设计还是不够有品味,参考 OpenClaw」。对本机
> OpenClaw 2026.6.1 Control UI(http://127.0.0.1:18789)做了实测对标
> (亮/暗截图 + computed-style 扒取),据此做一轮纯前端品味对齐。
> 范围:token / 组件 / 壳 / 12 面板;零后端改动。

## 对标实测值(OpenClaw,2026-06-10)

- 字体:Inter 14px 基准(与我们相同——差距不在字体)
- 卡片:`border-radius 14px`、`1px solid rgb(229,229,234)`、无阴影、`padding 18px`
- 激活导航:品牌色 ~19% alpha tint 填充、`radius 10px`
- soft 按钮:品牌色 ~9% tint 底 + 品牌调边框、`radius 10px`、13px 字
- 页标题:32px/700、直接用品牌色;每页带一句话副题
- 底色:亮 `#f8f9fa`(暖纸感)/ 侧栏独立浅灰层;暗 `#0e1015`
- 手法:面包屑 + ⌘K 全局搜索;小型大写分组眉标;侧栏底版本 chip + 状态点;
  KPI 瓷砖(小型大写标签 + 大数值 + 语义色);语义 tinted chip;pill 标签组;
  三态主题切换簇

## 决策(用户拍板)

1. **品牌色:椋鸟翠绿**(亮 `#0f766e` teal-700 / 暗 `#2dd4bf` teal-400)——
   学 OpenClaw 的「单一品牌色 + tint 水洗」技法,但不抄它的红(撞身份),
   也不留烂大街 indigo。
2. **范围:完整品味对齐**(token + 壳 + 组件 + 12 面板一遍过),一个里程碑。

## 实施

- **token(app.css)**:brand 改 teal;新增 `--brand-tint`(8%/10%)、
  `--brand-tint-strong`(16%/18%)、`--brand-border`(32%/36%,color-mix);
  中性阶暖化分层 bg `#f8f9fa`/surface `#f1f3f5`/card 白(暗:`#0e1015`/
  `#13161c`/`#181b22`,border `#262a33`);radius 阶 card 14px + control 10px。
- **组件**:Button 新增 `soft` 变体(tint 底+品牌边,页面内主要动作默认用,
  primary 留给全页唯一强 CTA);Card 加 `description`/`actions`;StatCard 升级
  KPI 瓷砖(11px 大写标签 + 28px 粗数值 + `tone` 语义色);新增 Chip(pill)、
  PageHeader(品牌色标题 + 副题);ThemeToggle 循环单钮 → 三态分段簇。
- **壳(+layout)**:侧栏 `bg-surface` 分层 + 品牌块(🪶 Starling)+ 眉标分组 +
  tint 激活 + 底部版本 chip(/health version + 状态点);顶栏 面包屑
  (Starling › 组 › 页,当前页品牌色)+ ⌘K 面板搜索(过滤跳转)+ 健康三灯 +
  主题簇。
- **面板**:全 12 面板 PageHeader 化(每页一句话副题);总览改 KPI 瓷砖行 +
  双列卡片 + 活动流 Badge 化;Statements 筛选行改标签式;主要动作按钮 soft 化;
  圆角统一 card/control 两档。

## 不抄的

OpenClaw 的正红(品牌冲突)、右侧 workspace 文件栏(无对应内容)、更新横幅。

## 验收

svelte-check 0/0 · vitest 全绿 · build ✔ · /browse 亮暗双主题目检对照截图。
