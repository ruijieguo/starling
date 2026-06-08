# P2.m 面板深做 Implementation Plan

**Goal:** dashboard 重设计收官——12 面板从「套壳统一态」深化到信息架构 + 交互,并补手动明暗开关。纯前端,零后端/C++ 改,零新依赖。

**Architecture:** 在 P2.k 地基(token/组件库/createQuery/壳)+ P2.l(provider 配置)之上:
- 手动明暗开关:app.css 加 `:root[data-theme]` 覆盖(data-theme=dark/light 显式,缺省跟随 OS),theme store + ThemeToggle 挂壳顶,localStorage 持久。
- 新 Drawer 组件(右侧滑出详情,bits-ui Dialog 变体或自绘)复用于行详情。
- 观测组深做:Overview 实时活动流;Statements faceted 筛选(perspective/modality/polarity Select)+ 行→Drawer 详情(全字段含 perceived_by/scope_parties/affect);Cognizers 交互图(hover tooltip + 点击高亮);Commitments 状态泳道。
- 诊断组打磨:Conflicts 权重可视条;Queues 健康色(积压高→琥珀/红)。
- 用既有 API 数据(不加后端端点);eval markdown 渲染留未来(CodeBlock 已可读)。

**Tech Stack:** Svelte 5 / Tailwind v4 / 既有 ui 组件。零新 npm 依赖。

**约束:** worktree `p2-m-panels-deep`(前端隔离)。explicit-path git add;commit 带 Co-Authored-By trailer;无 --no-verify/--amend。不改后端 API。验收 svelte-check 0/0 + build + vitest + playwright 全绿。自审后合并 push(显式授权)。

## Tasks
0. worktree + npm + 基线(check/vitest/build/playwright 绿)。
1. 明暗开关:app.css data-theme 覆盖 + theme.ts store + ThemeToggle.svelte + 壳顶挂载 + 持久化。Drawer.svelte 组件。
2. Statements 深做:faceted 筛选 Select(perspective/modality/polarity)+ 行点击 → Drawer 详情(全字段)。
3. Cognizers 交互图:hover 显示节点名 + 点击 → 高亮对应表行/详情。
4. Commitments 状态泳道(按 5 态分列)+ ⚠ fired。
5. Overview 活动流(最近 statement,ws 增量)+ 布局。
6. Conflicts 权重条 + Queues 健康色 + 其余微调。
7. 测试(vitest:theme/Drawer/筛选逻辑;playwright:明暗切换 + Statements 抽屉)+ 回归全绿。
8. 自审 + 修 + roadmap 登记 + 合并 push + 清理。

## 非目标
eval markdown 富渲染(CodeBlock 文本已可读,留未来);多租户;移动优先(响应式但桌面为主)。
