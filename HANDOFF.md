# 会话交接 — catalog-foundation

> **状态：T-23 本机实现与复验完成，功能分支已同步 GitHub，停在 T-24 用户许可之前。** 这只是会话恢复入口，不代表工作流已到 Handoff 阶段。
> 更新日期：2026-10-28。恢复时以本文件、`AGENTS.md`、feature 规范与当前 git 工作区为准；prior-handoff.txt（非公开历史记录） 及旧暂停日志仅作历史参考。

## 1. 当前任务与闸门

目录底座 `specs/catalog-foundation/`：只读导入 NAS 写卷影像、编号、来源与许可，提供稳定身份、变化历史、报告和授权只读 API；不改运行中的 v0。

- 当前阶段仍为 **Implement**。spec 第 7 版已获 Gate 1 批准并冻结（13 条需求、58 条 AC、25 条最终决策），plan 第 8 版。
- Checklist / Analyze 第 11 轮由审核员 A 判定 12 项全部通过；**只是设计质量通过，尚未独立 Review 实际实现，也未过 Gate 2**。实施期间不改 checklist，不重复请求 Gate 1。
- T-01、T-04～T-16 原有本机模块已完成；T-02/03、T-17～T-21 的代码已写成，真实数据库路径未验，不能标全部完成。
- T-22 运行配置已恢复复核：源码与静态契约通过；Compose 语法、镜像与真实运行仍待 T-24 / T-25。不要重跑 P4 生成过程。
- **T-23 本机完成**：Astra 提供真实 `catalog/acceptance/` 基线、compare、测试及 README A1～A7 入口，主会话已复验。Dockerfile 的 COPY acceptance 前置已具备，**不等于镜像已成功构建**。
- **下一步是先申请 T-24 许可**。NAS 隔离候选快照、构建、一次性数据库/API 测试容器均未执行，用户本轮“按照 HANDOFF 继续”未授权这些操作。T-25 正式部署、T-26 全量验收也仍未获许可。

## 2. git 安全点与未做的操作

- 仓库：**`/srv/example/project`**；分支：`feat/catalog-foundation`。2026-10-28 按用户要求从 `/srv/example/project` 迁移，旧目录已在完整校验与新路径回归后移除；后续命令只使用新目录。
- 迁移原样复制阶段对包含 `.git` 与本地忽略环境的 6,049 个文件逐一核对 SHA-256，一致后才继续。保留已安装依赖，使用标准 venv 与已安装包元数据重新生成激活脚本、17 个命令入口；清除可再生的旧字节码缓存，未下载/升级依赖。旧路径移除后 pip/pytest/模块入口与完整回归均在 D 盘验证，Git fsck 通过。
- 本轮起点为暂停 WIP `private-candidate-030`；恢复复核 T-22 的记录已本地提交为 `private-candidate-031`。
- T-23 实现、任务状态、本文件及非敏感证据随本轮安全提交保存；**实际最新 SHA 用 `git log -1 --oneline` / `git rev-parse HEAD` 查看**，不把未知的自引用 SHA 写入本文。T-24 必须记录最终候选完整 SHA，不能拿子 agent 派发时的旧 HEAD 代替。
- 用户于 2026-10-28 批准 GitHub 同步后，已将截至 `private-candidate-032` 的 9 个实施提交推送至 `origin/feat/catalog-foundation`，并建立 upstream；已用 `git ls-remote` 核对远端 SHA 与本机一致。此同步状态修订也随文档提交推送同一功能分支；最新 SHA 以分支 HEAD 为准。
- GitHub 分支：`origin 的 feat/catalog-foundation 分支（项目角色描述，非网址）`。后续已验证阶段及时同步此功能分支；本机编辑 → commit → push，不要求在 GitHub 网页直接编辑。推送功能分支不代表批准合并或部署。
- 已只读核实 GitHub `main` 仍为 `private-candidate-023`，未 merge、未推送 NAS、未部署。
- 已核对 v0 源码、根 Dockerfile / compose / requirements、冻结 spec / feature plan / checklist 与批准的 main 无差异。
- 没有安装 Docker、下载依赖、连接 NAS、启动 HTTP / PostgreSQL / Docker 服务；没有重启或停止 v0、NAS 现有服务。pytest 使用 TestClient / 合成材料，不代表监听了真实服务。

## 3. 本轮验证与证据

| 范围 | 主会话实际结果 | 限制 |
|---|---|---|
| 恢复后 T-22 全套本机回归 | **318 passed / 42 db skipped / 1 条原有警告**，其中 test_runtime.py 7 项通过 | 源码契约，不是 Compose / 构建 / 挂载证据 |
| T-23 完整非 DB 回归 | **360 passed / 42 deselected / 1 条原有警告** | db 被排除，绝非通过 |
| T-23 显式包含 acceptance 的完整回归 | **360 passed / 42 db skipped / 1 条原有警告** | 未配置 DH_TEST_DATABASE_URL，SQL 未运行 |
| 验收比较测试独立执行 | **42 passed** | 合成报告与真实 compute_import → build_report 流水线，不是 NAS 基线结果 |
| 编译与语法 | v0 三文件 py_compile；31 个 catalog Python 文件的 Python 3.12 AST；README 12 段 Bash、9 段 JavaScript、3 段 Python 均通过语法检查 | 本机 Python 3.14.2；未运行 Python 3.12、浏览器或 NAS 操作片段 |
| 机械检查 | UTF-8 LF / 无 BOM、文档一致性、差异空白检查通过；pip check 无依赖冲突 | 未升级依赖或屏蔽警告 |
| 迁移到 D 盘后（旧目录已移除） | **360 passed / 42 db skipped / 1 条原有警告**；虚拟环境激活、pip/pytest 启动、模块 help 与 Git 完整性通过 | 仅本机目录迁移验证，不是 T-24 / NAS 验证 |

42 个数据库跳过项仍为：`test_db.py` 15、`test_import.py` 15、`test_api.py` 12。唯一已知警告仍是 Starlette TestClient 对固定版本 httpx 的弃用提示。

最新完整回归须显式包含 acceptance：默认 `catalog/pytest.ini` 的 testpaths 仍只有 tests，不要只跑默认命令后误报涵盖了比较器。

```bash
cd /srv/example/project
catalog/.venv/Scripts/python.exe -I -X utf8 -m pytest -c catalog/pytest.ini catalog/tests catalog/acceptance/test_compare.py
# 历史命令（非公开历史记录，不可执行）：python -I -X utf8 private-audit-record .
git diff --check
```

测试前若环境意外存在 `DH_TEST_DATABASE_URL`，先核实目标与许可，不能误连真实库。本机 venv 可用但不入库；Python 3.14 通过不能代替容器验证。

## 4. T-23 文件与比较器边界

Astra 本轮只写四个分配文件，主会话只复核、验证和记录：

- `catalog/acceptance/baseline-2026-10-27.json`：34 项，固定为 2026-10-27。6,096 是影像目录数，不是写卷总数；TIFF 导入基线 32,058，不含隐藏目录 .pages 中的 63 个；txt 仍为 477。
- `catalog/acceptance/compare.py`：仅标准库、只读已导出报告与基线，不扫描材料、不连接网络/数据库、不复制归并或规则算法。
- `catalog/acceptance/test_compare.py`：42 项，含实际合成文件流水线、CLI/API 包裹形状、Q-024 六个 txt 的真实附件流水线、错误输入、退出码、只读审计、稀疏 Counter 与缺失容器的区别。
- `catalog/README.md`：A1～A7 可执行步骤、对象级人工核查、证据位置、资源采样、真实用户登录态及同源浏览器 GET、T-24/T-25 受限构建和许可边界。**这些 NAS/浏览器步骤尚未执行。**

报告形状：

| 输入 | 实际统计位置 |
|---|---|
| report CLI 导出的 import_run 整行 | `counts.counts`（数据库 counts 列保存完整报告） |
| GET `/api/v1/imports/{id}` | `report.counts` |
| build_report 直接报告 | `counts`，没有批次成功状态，不能据此验收 |

比较器退出码：0 所选计数相同且无缺证据；1 存在差异；2 缺证据；3 输入无效；4 批次 running/failed。0 也不代表完整 AC / A1～A7 通过。完整默认基线有三项固定 `unverified`，因此不能只凭比较器获得全项通过：

1. 排除的 JPG 98 是否全部为图块缓存（已有 excluded_jpg 是全部排除 JPG）。
2. P.2504 母号查询实际是否返回 5 件。
3. 12 个合并长卷逐条是否有派生来源或对应异常（不能把派生总数与异常总数相加抵数）。

README 已给这些事项的 API / 报告逐对象核查入口；P.2002 两套影像、P.0901 三件独立对象、出处建议等亦须对象级证据。Q-024 新 A077 资料六个 txt 只记录 477 → 483 差异及原因，不改变旧基线，不靠删指标或填零凑通过。真实报告、元数据与 cookie 不入库；后续验收证据放在工作区、pgdata、原材料和 cache 之外。

## 5. 下一步顺序（先取得许可）

1. 重读本文件、`AGENTS.md`、`docs/plan.md`、`docs/architecture.md` 与 `specs/catalog-foundation/{spec,plan,tasks}.md`，检查 `git status --short`、`git log --oneline -8`、`git branch -vv`。
2. **等待用户明确允许 T-24**；许可范围应为候选提交的 NAS 隔离快照、受限构建、一次性 PostgreSQL / API 测试，只用合成材料和认证，禁止挂真实材料 / v0 文件 / 正式 pgdata，不启动正式 Compose、不影响 v0。
3. 获准后按 README T-24 执行：记录最终候选完整 SHA、隔离临时目录；低峰且 NAS MemAvailable >=2GB；核实构建后端真正支持并落实硬内存 / swap 限制，不支持就停止报告，不能删限额重试。数据库 384m、测试容器 512m，memswap 分别相等；不发布宿主端口，临时网络，无宿主数据卷。
4. 容器内显式执行 `python -m pytest tests acceptance/test_compare.py`，db 项必须 **0 跳过**。SQL / 事务 / 线程 / 锁 / 历史 / 原文字节 / 迁移路径由这一步补证。失败的语义修复仍由新的 Astra 子 agent 在本机完成，形成新候选快照；NAS 不改代码。
5. 保存镜像、版本、限额、测试输出与实际清理结果。无论成功失败，只清理本轮已识别的一次性资源，不运行全局 prune，不删除未知服务/数据。
6. T-24 补齐后才 Converge / 独立 Review → 用户 Gate 2 → merge。正式部署 T-25、用户触发全量与重跑的 T-26 另获许可；merge 不等于 feature 全量验收完成。部署后修代码仍重走 Review → Gate 2 → merge → 获准部署。

本轮只到 T-23；没有提前派发 T-24、审核员 A 或正式验收。

## 6. 实施分工与关键接口

所有业务编码与语义修复由独立 **`openai/gpt-6-astra`** 子 agent 完成；主会话派发、约定接口、集成、复验、记录。独立文件可并行，共享文件串行；模型不可用时报告并请用户决定，不擅自换模型。审核员 A 仍为独立 Claude 会话，不由 Astra 自测代审。

- `prepare_import(pool, triggered_by=..., code_version=..., session_cookie=..., v0_url=...)` 同步持连接与咨询锁后创建批次。API 先准备再返回 202；已有批次转 409，不能提前归还连接。
- `PreparedImport.execute(roots, cache_dir)` 后台执行，派发失败才 `cancel()`；不是用户取消 API。真实线程 / SQL / 资源生命周期仍待 T-24。
- `compute_import` 是真实文件计算流水线；附件读到即消费，不保存全量原文；CatalogState 不模拟数据库。
- `latest_valid_snapshot` 按 import_run 的 valid 状态取最近批次；有效空快照、失败批次的有效快照都不能错误退回旧非空记录。本批 A1 覆盖必须本批索引有效，不能用旧链接快照代替。
- `preserved_items` 只冻结编号 / 线索 / 出处；新影像的严格展示策略、原始位置追加、新附件关联仍须更新；原主编号在待确认时不丢失。
- NLC 权威只覆盖一级国图写卷目录，不清除词表外子单元自己的编号；画布序号从 0 起。派生仅信成功记录，不能将 raw 完成或退出码 0 当最终 TIFF 成功。
- 合并建议按参与端各有一条结构化异常（每对两条），不改变归并；不要只关联左端或重新解析自然语言猜对象。
- 只读接口、参数和路径设计权威在 feature plan；实际实现与受保护 OpenAPI 见 `api.py`。没有目录写操作、CLI 导入、取消 / 回滚 API。
- `DH_CODE_VERSION` 本机默认 development；镜像构建与运行必须注入真实候选 / 已合并 SHA，不在容器里运行 git。
- `report.health` 字段为 count / failures / max_seconds / samples；`report.cache_access` 是白名单打开记录；只读挂载与测试审计联合证明，不通过遍历 cache 验证。

## 7. 子 agent、进程与证据位置

本轮 P5：实际模型 **openai/gpt-6-astra**；派发 HEAD `private-candidate-031`；21:28:27～21:45:32 自然完成，exit=0，stderr 为空。只写上述四个文件，无越界修改，无提交/推送。主会话复验后将结果写回 tasks。

P1～P4 全部早已结束，P5 也已确认结束；没有本轮遗留子 agent 或需要重启的服务。**不要重放 P4 / P5 旧提示词或误停用户已有服务。** 设计端口（尚未监听）：新 API 宿主 8504 → 容器 8000，DB 5432 仅项目内部；v0 8503 保持原状。

调度沿用 `/srv/example/private-audit/implement/run_task.sh`（仓库备份 run_task.sh（非公开历史记录））：固定 Astra、独立 pi --no-session、read/bash/edit/write、2400 秒超时。实施与审核的外部调度脚本 cwd 均已改为 `/srv/example/project`，仓库工具备份也已从源脚本重新同步；只做 bash -n，未派发新 agent。外部审计目录仍在 `/srv/example/private-audit`，没有一并搬迁；输出目录不变。历史提示词/日志中的旧项目路径保留为证据，不能直接重放。需新任务时核对新路径、当前 HEAD、新提示词与新批次 ID，不覆盖旧日志；不是新 agent 框架。

新增归档位于 历史归档（非公开历史记录）：

- `prompts/prompt-P5-T23.txt`：实际任务边界、AC、HEAD 与命令。
- `logs/P5-T23.{meta,status}`、`logs/P5-T23.out.txt`：实际模型、起止、退出码与子 agent 原报告。
- `logs/P5-T23-main-local.txt`、`P5-T23-main-full.txt`：主会话两种回归原输出。
- `logs/P5-T23-main-static.txt`：编码、Python 3.12 AST、README 片段语法结果，仅机械证据。
- `logs/local-relocation-tests.txt`：旧目录移除后，在 `/srv/example/project` 完整回归的原始输出（360 passed / 42 db skipped / 1 warning）。

旧暂停归档、P1～P4 日志、工具备份仍保留，不修改原生成证据。P4 历史 out.txt 有两个 Markdown 换行空格的已知提示，与源码无关。原始 NAS 抽查内容仍只在外部 `dh-audit/protocol-facts-20261028.txt` / `protocol-log-blocks-20261028.txt`，不复制入库；不含恢复必需材料。没有复制真实 .env、users.json、密钥或 pi 认证。

审核工具原目录 `/srv/example/private-audit/review/`：A 优先 claude-bridge，不可用才 anthropic/claude-fable-5-1；每轮记录实际通道与切换原因。旧接入不可用记录仅为历史信息，下轮重新核实；当前未进入独立 Review。

## 8. 仍需用户决定

GitHub 功能分支同步已获批准并完成，不再列为待确认；本次批准不包含 NAS 测试、main 合并或部署。

1. **是否允许 T-24 NAS 隔离候选快照 / 受限构建 / 一次性数据库测试**（合成数据，禁真实挂载、禁正式 Compose，不影响 v0）。当前待回复。
2. 独立 Review 后的 Gate 2、正式部署许可、全量导入 / A1～A7 许可分别仍需确认，不由“继续”或换模型自动替代。
3. 是否同步 related-project 的 AGENTS / 模板仍待单独确认；该仓库有用户未提交改动，本轮未动。

下次恢复后的建议开场：**T-23 已完成并复验；我先确认 T-24 的隔离 NAS 测试许可，未经批准不构建、启动容器或部署。**
