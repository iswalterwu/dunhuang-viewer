# AGENTS.md — dunhuang-viewer 工作手册

> 本仓库内所有 agent 的上下文入口：先读本文件，再按任务进入对应文档。
> 产品设计与决策的权威在 `docs/`。实现与 docs 冲突时以 docs 为准，并回修代码。
> 2026-10-30公开发布边界：D-019及`specs/public-release-privacy/spec.md`为准；用户已批准Gate1并授权清理公开历史/提交者信息、受保护更新origin的main与功能分支。先Plan/独立核对/指定模型实施与验证；其他远端和部署不动，新差异仍须Review及必要Gate2，不擅自提前发布。

## 0. 这是什么

本项目（仓库 `dunhuang-viewer`）是**面向所有敦煌研究者的开放资源整理平台**（D-010）：长期目标是梳理全球可开放获取的敦煌资源——
写卷、壁画、研究论文、参考资料、评论及其相互联系；当前阶段（Phase 1）只整理现有材料：NAS 上的敦煌写卷影像（书法相关），
做标注、分类与命名规范。项目将前后端分离（D-011）。

运行中的 **v0** 是部署在NAS Docker 里的高清查看器：直读 NAS 磁盘上的 TIFF，在本地生成 DZI 图块与缩略图，
供浏览器按卷浏览、无级缩放、下载原图，并可手动拼接分段（architecture.md）。迁移完成前 v0 继续在线。

核心循环（目标）：影像 + 目录信息 → 统一编目（稳定 ID + 多编号对照）→ 标注（带来源）→ 关联 → 检索与浏览。
核心循环（v0）：原图 TIFF → 索引 + DZI 图块 / 缩略图（`cache/`）→ FastAPI 服务 → 浏览器（OpenSeadragon）。

## 1. 文档地图

| 文档 | 内容 | 何时读 |
|---|---|---|
| `docs/plan.md` | 总方案：定位、现有材料与沿革、决策汇总（§3）、编号与命名、原则（§5）、架构方向、领域模型、路线图、待确认决策（PD）、风险（RK）与 v0 已知问题（KI） | 任何任务前先读 |
| `docs/architecture.md` | v0 系统架构：组件、ID 与缓存布局、图块管线、拼接工作台、认证、部署拓扑、内存红线 | 动后端 / 容器 / 部署前 |
| `docs/designUI.md` | v0 设计理念：配色、页面形态、查看器交互约定 | 动前端 / 样式前 |
| `docs/decisions/` | ADR 决策记录 | 新决策先登记再实现 |
| `specs/` | 功能规格（目录结构与状态表见 `specs/README.md`） | 开发任何功能时（唯一实施入口） |
| `templates/` | 工作流模板 | 新建功能规格时 |
| `README-部署.md` | v0 部署与日常运维（人读；数值以 `docker-compose.yml` 为准，部分已过时，见 plan.md §10） | 部署 / 运维时 |

## 2. 工作流：spec-driven（固定流程，所有功能开发必须遵守）

```
Constitution → Spec → Clarify → 【Gate 1】 → Plan → Checklist → Tasks → Analyze → Implement → Converge → Review → 【Gate 2】 → Handoff
```

**总规则**：每一步开始时重新读取对应文件（AGENTS.md、docs/、`specs/<feature>/` 产物），不依赖会话记忆；每一步都遵守下面的工程约束。

**工程约束**（贯穿各步骤：写 spec、plan、tasks，实现与评审都适用）：

1. **不为臆测的边界情况加复杂度**：不为猜测出来、几乎不会发生的竞态或安全边界情况加规则或代码。确有必要时，先说清楚具体会怎么出错、概率多大、要写多少代码，用户同意后再做；不悄悄扩大改动范围
2. **只在系统边界校验**：外部传入的数据（用户输入、外部 API、网络、文件系统）只在入口层校验，往里传已确定类型的值；内部不反复做防御性检查
3. **不提前抽函数**：只有会复用、包住了确实复杂的逻辑，或代表一个能起清楚名字的概念时才抽；只用一次的不抽
4. **主函数只写正常流程**：校验与细节放到它下面的小函数里
5. **自动生成的文件不手改**：改源头，再重新生成
6. **测试测真实实现**：不把业务逻辑抄一份进测试；尽量少用 mock，只在外部边界用替身
7. **按仓库现有流程走**：不引入仓库没在用的工具或流程

1. **Constitution**：固化项目原则与安全边界。载体：本文件（§3 红线、§4 工作约定）+ `docs/` + `docs/decisions/`。
2. **Spec**：按 what / why 写需求，不写技术方案；每条需求都能映射到具体的验收规则。产物：`spec.md`。
3. **Clarify**：追问不明确和有歧义的地方；能从仓库、文档、既有方案推断的不问用户；回答融入 spec。产物：更新 `spec.md`（歧义记录表）。

**Gate 1（人工批准，硬闸门）**：Clarify 完成后、Plan 开始前，由用户批准 `spec.md`。批准后 spec 冻结；未批准不得进入 Plan。之后的需求变更按第 8 步的规则处理。

4. **Plan**：参考技术栈与架构，由 spec 生成设计与实施细节。产物：`plan.md`。
5. **Checklist**：审核员针对 spec 与 plan 检查需求是否完整、清晰、一致（需求的「单元测试」），在拆任务前完成；只有审核员认为满足的项才勾选，勾选不代表已经实现。
   **审核员**：只设审核员 A（claude-fable-5-1），在独立会话中审核（新开会话、与实施会话隔离、模型与实施不同）。
   接入通道优先 `claude-bridge`（`--model claude-bridge/claude-fable-5-1`），不可用时（额度耗尽、鉴权失败、launcher 异常等）改走 Anthropic API（`--model anthropic/claude-fable-5-1`）；两条通道同为 Claude 模型，只换接入路径。每轮在 checklist 中记录实际通道及切换原因。
   产物：`checklist.md`（实施者不勾选）。
6. **Tasks**：把方案拆成 0.5–2 小时的任务，每个任务写明上下文、修改范围、完成标准（必须引用 AC 编号，如「满足 AC-001-1」）和与之对应的验证命令。产物：`tasks.md`。
7. **Analyze**：只读地检查 spec、plan、tasks 之间的冲突、缺口与模糊之处；发现问题先修复再重新检查，然后才实施。
8. **Implement**：开始前确认 checklist 全部勾选；按依赖顺序执行任务，过程中不改 checklist。
   **实施子 agent**：编码与实现修复交给独立的 **GPT 6 Astra** 子 agent（`--model openai/gpt-6-astra`）；主会话负责派发、接口约定、集成、验证与状态记录。模型不可用时报告原因并请用户决定，不擅自替换模型。
   **按需并行**：只并行依赖已满足、修改范围互不冲突的任务；派发须带任务编号、AC、文件边界与验证命令。共享文件串行处理，不覆盖其他 agent 的改动。沿用现有 pi 独立会话，不另加 agent 框架；子 agent 同样遵守本文件，不自行改冻结规格或 checklist、不提交推送、合并或部署。主会话复核差异并复跑测试，在 tasks.md 记录实际模型 / 通道及验证结果；子 agent 自报通过不代替独立审核员 A 的结论。
   **需求变更规则**：中途需求变化 → 回到 Clarify（更新 spec → 重新过 Gate 1 → 更新 plan / tasks），不许直接改 tasks.md 偷跑。
9. **Converge**：对照 spec、plan、tasks 检查代码；有差距就在 tasks.md 加任务并继续实施，直到「已收敛」。
10. **Review**：审核员 A 在独立会话中参考 spec、plan、tasks 与实际代码差异（git diff），按 bug、架构风险、测试缺口、目标是否对齐评审，禁止只做风格化总结。

**Gate 2（人工批准，硬闸门）**：用户确认评审结论（bug 修复 / 风险接受 / 缺口补齐）后方可 Handoff。

11. **Handoff**：更新 `review.md`（完成项、未完成项、风险、下一步，附测试输出摘要与 Converge 结论等验收证据），提交 PR 并 merge 到 main；涉及实现语义的冲突解决后回到 Analyze / Converge 复查。

规格目录结构与多 feature 状态表见 `specs/README.md`；新建 feature 从 `templates/` 起稿。

## 3. 红线（实现不得偏离；全部决策见 plan.md §3 与 `docs/decisions/`）

- **内存安全**（D-005）：容器硬上限且禁用额外 swap、`VIPS_CONCURRENCY=1`、`MEM_GUARD_MB` 内存守卫、超大卷降级为预览分辨率；只许收紧，放宽须先登记 ADR
- **原图目录写入**（D-008）：本仓库代码对 `/srv/example/data` 的唯一写入是拼接工作台写回的 `合并长卷.tif`（临时文件 + 原子替换）；新增任何写原始数据的路径须先登记 ADR。外部写入方见 plan.md §1.4，治理待定（PD-02）
- **ID 与缓存映射**（architecture.md §3）：卷 / 文件 ID = 相对路径的 base64url，缓存键 = `sha1(file_id)[:16]`；`app.py`、`pyramid_worker.py`、`stitch_apply.py` 三处保持同一映射
- **登录墙**（D-007）：公网可达，`.env` 的 `AUTH_USER` / `AUTH_PASS` / `AUTH_SECRET` 必须齐全（缺一项即全站匿名可访问）；用户表 `cache/users.json`
- **目录服务**（D-018）：独立 compose 项目 `dunhuang-catalog`，内存 384m + 512m 硬上限；原图、备份与 v0 `cache/` 只读挂载；只在局域网与 Tailscale 开放；缺少 `AUTH_SECRET` 时拒绝全部请求
- **代码公开与部署通道**（D-009、D-019）：GitHub公开代码仓库为代码权威；私人配置、账户、接收渠道与未脱敏原始审计记录不得作为公开发布内容。部署目录仍为git仓库（updateInstead），仅接收本机已合并提交的获准推送；历史重写/强制推送另需明确授权

## 4. 工作约定

- 所有功能开发走 §2 工作流，`specs/<feature>/` 是实施的唯一入口；决策先写 ADR 再改代码，方案变更先改 docs
- 数据与学术纪律见 plan.md §5（许可合规、可追溯、学术区分、非破坏、身份稳定、开放标准、先整理后扩展、NAS 安全）
- 原始扫描件、缓存产物、私有数据、凭证永不入库；`.gitignore` 锚点（`.env`、`cache/`、`pyramids/`、`thumbs/`）不得移除；凭证只在 NAS 部署目录的 `.env`（权限 600），代码零 fallback 字面量
- 部署：只部署已 merge 到 main 的提交（`git push origin main` → `git push nas main`），禁止在 NAS 上直接改代码。`static/` 挂载进容器，推送即生效；改 `app.py` / `pyramid_worker.py` / `Dockerfile` / `requirements.txt` 须重建镜像，**重建 / 重启容器前先征得用户确认**，且只针对目标服务（`docker-compose up -d --build dunhuang-viewer`；不带服务名会同时拉起两个图块生成器）
- NAS 操作：文件用 `ssh nas`（operator），容器用 `ssh nasroot` + `/usr/local/bin/docker`、`/usr/local/bin/docker-compose`；禁止对 `cache/` 做全量遍历（`du` / `find` 会长时间占用 NAS IO）
- 本机工作副本：`/srv/example/project`（2026-10-28 从 `/srv/example/project` 迁移）；本机命令在此仓库根目录执行，NAS 部署目录不变
- 环境：本机开发（Windows 11 + Git Bash + Python 3.14，无 WSL），运行在 NAS 容器（Python 3.12 + libvips）；提交前跑测试（`tests/` 建立前至少 `python -m py_compile app.py pyramid_worker.py stitch_apply.py`）
