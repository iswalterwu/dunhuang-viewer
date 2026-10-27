# AGENTS.md — dunhuang-viewer 工作手册

> 本仓库内所有 agent 的上下文入口：先读本文件，再按任务进入对应文档。
> 产品设计与决策的权威在 `docs/`。实现与 docs 冲突时以 docs 为准，并回修代码。

## 0. 这是什么

dunhuang-viewer：敦煌画卷 · NAS 高清查看器（自托管 Web 应用）。部署在NAS 的 Docker 里，直接读取 NAS 磁盘上的
敦煌遗书 TIFF 扫描件（卷数与体量以 `/api/index` 实际扫描为准），在 NAS 本地生成 DZI 缩放图块与缩略图；用户用电脑、手机、
平板的浏览器按卷浏览、无级缩放、查看元数据与说明文字、下载原图，并可在拼接工作台把分段扫描手动拼成整卷。

核心循环：原始 TIFF（只读）→ 索引 + DZI 图块 / 缩略图（`cache/`）→ FastAPI 服务 → 浏览器（OpenSeadragon）。

## 1. 文档地图

| 文档 | 内容 | 何时读 |
|---|---|---|
| `docs/plan.md` | 总方案：目标、决策记录、文档体系、目录结构、路线图、扩展点、风险与已知问题 | 任何任务前先读 |
| `docs/architecture.md` | 系统架构：组件职责、ID 与缓存布局、图块管线、拼接工作台、认证、部署拓扑、内存安全红线 | 动后端/容器/部署相关代码前必读 |
| `docs/designUI.md` | 全局设计理念：配色令牌、页面形态（画廊/查看器/拼接/登录/管理）、查看器交互约定 | 动前端/样式前必读 |
| `docs/decisions/` | ADR 决策记录（编号、日期、背景、取舍） | 新决策先登记再实现 |
| `specs/<feature>/` | 功能规格目录：spec.md / plan.md / tasks.md / review.md | 开发任何功能时（唯一实施入口） |
| `templates/` | spec-driven 工作流模板（spec/plan/tasks/checklist/review） | 新建功能规格时 |
| `README-部署.md` | 部署与日常运维操作（人读；数值以 `docker-compose.yml` 为准，部分内容已过时，见 plan.md §10） | 部署/运维时 |

## 2. 工作流：spec-driven（固定流程，所有功能开发必须遵守）

```
Constitution → Spec → Clarify → 【Gate 1】 → Plan → Checklist → Tasks → Analyze → Implement → Converge → Review → 【Gate 2】 → Handoff
```

**总规则**：每一步开始时重新读取对应文件（AGENTS.md、docs/、`specs/<feature>/` 产物），不依赖会话记忆。

1. **Constitution**：先固化项目原则，明确安全边界、什么该做什么不该做。
   载体：本文件（§3 决策红线、§4 工作约定）+ `docs/`（plan/architecture/designUI）+ `docs/decisions/` ADR。
2. **Spec**：按照 what/why 写 feature 的需求，不写技术方案；每条需求必须能映射到具体的验收规则。
   产物：`specs/<feature>/spec.md`。
3. **Clarify**：AI Agent 追问所有描述不明确的地方和歧义点；能从仓库、文档、既有方案推断的，不问用户；
   将回答融入 spec 中，避免出现模糊不清的情况。产物：更新 `spec.md`（歧义记录表）。

**Gate 1（人工批准，硬闸门）**：Clarify 完成后、Plan 开始前，由用户批准 `spec.md`。批准后 **spec 冻结**；
未批准不得进入 Plan。此后任何需求变更都按第 8 步的变更规则处理。

4. **Plan**：参考技术栈和架构信息，生成来自 spec 规范的设计成果，包括具体的实施细节。
   产物：`specs/<feature>/plan.md`。
5. **Checklist**：生成一个自定义的质量检查清单，包括针对 spec 需求进行的单元测试，以便在工作进行分解前
   确保需求描述完整、清晰且一致。这些自定义检查清单属于审核员所确定的需求质量审查成果；只有当审核员认为
   某项检查标准得到满足时，才会标记该项检查为已通过。虽然某些自定义项已通过检查，但这并不意味着实施工作已经完成。
   **审核员约束**：审核必须是独立会话（新开会话、与实施会话隔离），并使用与实施不同的模型；
   至少配置 2 名审核员（claude-fable-5-1 与 gpt-6.1-sol）并行审核，各自产出勾选结果，
   按共识取通过项；有分歧的项视为未通过并附说明。
   产物：`specs/<feature>/checklist.md`（实施者不勾选）。
6. **Tasks**：把方案拆成 0.5 到 2 小时可完成的任务，每个任务包含上下文、修改范围、完成标准和验证命令。
   **完成标准必须引用 spec 的 AC 编号**（如“满足 AC-001-1”），验证命令与完成标准一一对应。
   产物：`specs/<feature>/tasks.md`。
7. **Analyze**：报告在 spec.md、plan.md 和 tasks.md 之间存在的冲突、差距和模糊之处。该报告是只读的；
   如果发现了问题请进行修复，然后在实施之前重新运行该报告。
8. **Implement**：按照依赖顺序执行 tasks.md 中的任务。在执行之前，会读取检查清单中的复选框状态作为前置条件，
   并在继续之前确认所有检查清单项都已勾选；过程中不会修改任何检查清单文件或标记。可以一次性运行以构建整个系统，
   或者将任务划分为多个阶段来处理大型功能。
   **需求变更规则**：Implement 中途需求发生变化 → 回到 Clarify 重新走流水线（更新 spec → 重新过 Gate 1 →
   更新 plan/tasks），不许直接改 tasks.md 偷跑。
9. **Converge**：对比代码库与规范、计划以及任务列表进行检查。如果发现差距，就在 tasks.md 处添加新的任务，
   然后运行 Implement 工作流再次进行比对，直到报告"已收敛"为止。否则任务完成，可以继续完成评审。
10. **Review**：调用第三方 agent（新开独立会话，与实施会话隔离）参考 **spec.md + plan.md + tasks.md + 实际代码差异**
    （git diff），按 bug、架构风险、测试缺口、目标是否对齐进行评审，禁止只做风格化总结。

**Gate 2（人工批准，硬闸门）**：Review 完成后，由用户确认评审结论（bug 修复 / 风险接受 / 缺口补齐），确认后方可进入 Handoff。

11. **Handoff**：更新 feature 的 review.md，记录完成项、未完成项、风险和下一步任务，并附**验收证据**：
    测试命令输出摘要、Converge 报告结论。然后**提交 PR 并 merge 到 main**；若出现 conflict，先 resolve 冲突
    （涉及实现语义的冲突解决后回到 Analyze/Converge 复查），再完成 merge。

### 功能规格目录约定

```
specs/<feature>/          # 每个功能性 feature 一个独立规格目录（如 stitch-workbench）
├── spec.md               # 需求：what/why + 验收规则（不含技术方案）
├── plan.md               # 实施设计：技术方案与细节（Plan 阶段）
├── tasks.md              # 任务分解（0.5–2h/任务，含验证命令）
├── review.md             # 评审与交接记录（Handoff 阶段更新）
└── checklist.md          # 质量检查清单（Checklist 阶段生成，有则必读）
```

### 多 feature 并行

`specs/README.md` 维护一张**状态表**（feature / 状态 / 依赖 / 最近更新）。feature 开始、阻塞、完成时必须更新；
依赖未满足的 feature 不得进入 Plan。

新建 feature 一律从 `templates/` 模板起稿，走完整个工作流。

## 3. 已确认的关键决策（实现不得偏离）

- **部署形态**：NAS（设备实例非公开）本机 Docker Compose 服务，直读 NAS 磁盘原图，不拷贝、不全量转码（D-001）
- **技术栈**：Python 3.12（镜像 `python:3.12-slim`）+ FastAPI/uvicorn 单体 `app.py`；前端原生 HTML/CSS/JS + OpenSeadragon，无构建步骤（D-002、D-004）
- **图像管线**：libvips（pyvips）流式解码 + DZI 图块（`dzsave`，JPEG）；tifffile 读元数据并对未压缩 TIFF 做按行/按区域流式读取；Pillow 只作无 libvips 时的兜底（D-003）
- **图块生成**：在线按需（单并发）+ 后台全量生成器 `pyramid-builder` + 超巨卷专用 `pyramid-huge`，断点续跑状态在 `cache/pyramid_build_state.json`（D-006）
- **内存安全红线**（2026-10-18 事故后）：容器硬上限且禁用额外 swap、`VIPS_CONCURRENCY=1`、`MEM_GUARD_MB` 内存守卫、超大卷降级为预览分辨率；只许收紧，放宽须先登记 ADR（D-005）
- **原始数据只读**：`/srv/example/data` 是唯一权威原图；唯一写入例外是拼接工作台写回卷目录的 `合并长卷.tif`（临时文件 + 原子替换）（D-008）
- **ID 与缓存映射**：卷/文件 ID = 相对路径的 base64url，缓存键 = `sha1(file_id)[:16]`；`app.py`、`pyramid_worker.py`、`stitch_apply.py` 三处必须保持同一映射（architecture.md §3）
- **访问与认证**：局域网 + Tailscale + 可选公网入口（私人拓扑非公开）；因公网可达，登录墙必须开启（`.env` 的 `AUTH_USER`/`AUTH_PASS`/`AUTH_SECRET` 三项齐全，缺一项即全站匿名可访问）；用户表 `cache/users.json`（pbkdf2）（D-007）
- **代码与部署通道**：GitHub 私有仓库 `contributor/dunhuang-viewer` 是代码权威；NAS 部署目录是 git 仓库（`receive.denyCurrentBranch=updateInstead`），只接收本机工作副本的推送（D-009）

## 4. 工作约定

- 所有功能开发必须走 §2 spec-driven 工作流；`specs/<feature>/` 是实施的唯一入口
- 决策先写 ADR（`docs/decisions/`）再改代码；方案变更先改 docs 再动实现
- 原始扫描件、缓存产物、私有数据、凭证永不入库；`.gitignore` 锚点（`.env`、`cache/`、`pyramids/`、`thumbs/`）不得移除
- 凭证只在 NAS 部署目录的 `.env`（权限 600），代码零 fallback 字面量
- 写原始数据目录只允许经拼接工作台（临时文件 + 原子替换）；新增任何写原始数据的路径必须先登记 ADR
- 部署：只部署已 merge 到 main 的提交（`git push origin main` → `git push nas main`）；禁止在 NAS 上直接改代码（工作区不干净会让推送被拒）。`static/` 挂载进容器，推送即生效；改 `app.py`/`pyramid_worker.py`/`Dockerfile`/`requirements.txt` 须重建镜像，**重建/重启容器前必须先征得用户确认**（查看器会中断），且只针对目标服务（`docker-compose up -d --build dunhuang-viewer`；不带服务名会同时拉起两个图块生成器）
- NAS 操作：文件用 `ssh nas`（operator），容器用 `ssh nasroot` + `/usr/local/bin/docker`、`/usr/local/bin/docker-compose`；禁止对 `cache/` 做全量遍历（`du`/`find` 会长时间占用 NAS IO）
- 环境：本机开发（Windows 11 + Git Bash + Python 3.14，无 WSL），运行在 NAS 容器（Python 3.12 + libvips）；提交前跑测试（`tests/` 建立前至少 `python -m py_compile app.py pyramid_worker.py stitch_apply.py`）
