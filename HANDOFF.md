# 暂停交接 — catalog-foundation

> **状态：已按用户要求暂停，不自动续跑。** 本文件是项目根目录的会话交接入口，不代表工作流已到 Handoff 阶段。
> 保存时间：2026-10-28。恢复时以本文件、`AGENTS.md` 与当前 git 工作区为准；prior-handoff.txt（非公开历史记录） 仅作历史参考。

## 1. 任务目标与停点

目录底座 `specs/catalog-foundation/`：只读导入 NAS 写卷影像、编号、来源与许可，提供稳定身份、变化历史、报告和授权只读 API；不改运行中的 v0。

- 当前阶段：**Implement**。spec 第 7 版已获 Gate 1 批准并冻结（13 条需求、58 条 AC、25 条最终决策），plan 第 8 版。
- Checklist / Analyze 第 11 轮由审核员 A 判定 12 项全部通过；**只是设计质量通过，尚未独立 Review 实际实现，也未过 Gate 2**。实施期间不改 checklist。
- 14 项本机基础模块完成（T-01、T-04～T-16）。T-02/03、T-17～T-21 代码已写成，但真实数据库路径仍待验证，不能标全部完成。
- **停在 T-22 运行文件落盘后、主会话复验之前。** P4 子 agent 已自然完成，exit=0，自报 7 项静态检查通过；主会话收到暂停后没有启动新测试或新任务。
- T-23 基线对照与验收入口**未开始**，`catalog/acceptance/` 尚不存在。Dockerfile 明确 COPY 此目录，因此现在不能构建；先完成 T-23，不造占位验收文件绕过前置条件。
- T-24 真实 PostgreSQL / Python 3.12 镜像测试、T-25 正式部署、T-26 全量验收均未执行，且尚未获得相应许可。

## 2. git、安全点与进程状态

- 仓库：`/srv/example/project`，当前分支 `feat/catalog-foundation`。
- 暂停前最后一个已验证实现提交：`private-candidate-029`。
- 本次暂停 WIP 提交包含：P4 的六个文件、任务状态、本文件及非敏感交接产物。**本次提交号用 `git log -1 --oneline` 查看**，不将尚未知的自引用 SHA 写入本文。
- `main` 与本地 `origin/main` 记录仍为 `private-candidate-023`。功能实现尚未推送、合并或部署；本次交接也**不 push**。
- P4 于 **17:01:12** 自然结束。暂停收尾曾尝试向其 launcher（MSYS PID 5470）发 SIGINT，但进程已退出，返回 No such process；没有强杀未知进程。
- 所有本会话派发的子 agent 均已结束；无停不掉的后台任务。记录在 pause-process-check.txt（非公开历史记录）。
- 本会话没有启动 HTTP / PostgreSQL / Docker 服务，没有需要重启的监听进程。v0 及 NAS 现有服务未停止、未重启；不要误停它们。

## 3. 已完成改动与证据

| 提交 | 文件 / 范围 | 已有验证与限制 |
|---|---|---|
| `private-candidate-024` | `catalog/src/dh_catalog/{config,scan,identifiers,units,identity,rules}.py` 初始模块及 `catalog/tests/` | 首批本机 103 项通过，影像身份、扫描与单元规则；不是数据库证据 |
| `private-candidate-025` | 写卷身份、规则、`api.py` 认证框架、`v0.py`、`db.py`、`__main__.py`、`catalog/migrations/0001_init.sql` 及相应测试 | 当时 195 通过 / 15 db 跳过；数据库未验 |
| `private-candidate-026` | `AGENTS.md`、`templates/tasks.md`、feature 任务实施记录 | 实施与修复改由 GPT 6 Astra 子 agent；主会话协调 / 集成 / 复验 |
| `private-candidate-027` | `catalog/src/dh_catalog/nlc.py`、`derivation.py`；`test_nlc.py`、`test_derivation.py` | 两个 Astra 独立进程并行实现，分别 36 / 35 通过；主会话全套复验 266 通过 / 15 db 跳过 |
| `private-candidate-028` | `importer.py`、`test_import.py`、report CLI、真实 DB 共享夹具；修复四处集成遗漏 | 主会话复验 303 通过 / 30 db 跳过；SQL、事务、数据库历史未验 |
| `private-candidate-029` | `api.py` 查询 / 触发、`config.py` 的 DH_CODE_VERSION、health CLI、`test_api.py` / 配置测试；合并建议异常双端关联 | **最后一次主会话完整回归：311 passed / 42 db skipped / 1 条原有依赖警告**。编译、Python 3.12 AST 语法、UTF-8 LF、文档一致性及差异空白检查通过；不是 Python 3.12 运行或 SQL 证据 |
| 本次暂停 WIP | `catalog/Dockerfile`、`docker-compose.yml`、`.env.example`、`.dockerignore`、`tests/test_runtime.py`、`catalog/README.md` | P4 Astra 自报静态测试 **7 passed**，主会话未复验；Compose 语法、镜像构建、真实挂载 / 限额均未验证 |

42 个跳过项：`test_db.py` 15、`test_import.py` 15、`test_api.py` 12；原因均为未配置 `DH_TEST_DATABASE_URL`。不要把 skip 计为 pass。唯一已知警告是 Starlette TestClient 对 httpx 的弃用提示，未升级依赖或屏蔽警告。

T-22 文件已保存完整，没有正在写的文件。P4 只写上述六个分配文件，未修改依赖、v0 或任务状态；其实际模型为 `openai/gpt-6-astra`。

暂停收尾仅做短的文件完整性核查，没有重跑产品测试：UTF-8 LF、Python 3.12 源码语法（不是运行验证）、凭证模式与冻结文件 / v0 未变检查通过，记录见 pause-integrity.txt（非公开历史记录）。原样归档的 `P4-runtime.out.txt` 第 3 行保留模型原 Markdown 的两个换行空格，差异空白检查有这一处已知提示；不手改生成证据，不影响源码。

## 4. 下一步（仅在用户明确恢复后，按顺序执行）

### 4.1 确认安全点并重读规范

在项目根目录：

```bash
cd /srv/example/project
git status --short
git log --oneline -8
git branch -vv
```

然后读取本文件、`AGENTS.md`、`docs/plan.md`、`docs/architecture.md` 与 `specs/catalog-foundation/{spec,plan,tasks}.md`。不依赖旧会话记忆，不重复请求已经批准的 Gate 1。

### 4.2 复核 P4 已落盘文件，再做一次本机回归

先检查 `catalog/` 运行文件、`test_runtime.py` 与 README，重点核对 D-018 的 384m / 512m、memswap 相等、四项 ro 挂载、工作区外 pgdata、无数据库宿主端口、LAN / Tailscale 显式绑定、无凭证默认值。

```bash
catalog/.venv/Scripts/python.exe -I -X utf8 -m pytest -c catalog/pytest.ini
# 历史命令（非公开历史记录，不可执行）：python -I -X utf8 private-audit-record .
git diff --check
```

这轮实际通过 / 跳过数届时重新记录，**不要预填 P4 后的新总数**。不在本机安装 Docker，也不为“验证配置”偷偷连接 NAS。

本机 venv 可用但不入库；若环境丢失，按 `catalog/README.md` 用现有 Python / pip 和固定 requirements 重建。Python 3.14 本机通过不能代替 Python 3.12 镜像验证。

### 4.3 继续 T-23，仍使用 Astra 子 agent

- 先复核 T-22 并回写任务状态，再按依赖实现基线 JSON、compare 与 A1～A7 可执行验收步骤。
- 已批准基线固定为 2026-10-27；6,096 是影像目录数，不是写卷总数。新增 A077 资料的六个 txt 只说明差异，不改旧基线凑通过。
- compare 只读取既有报告计数，不再扫描材料或复制归并算法；完整报告在数据库 `import_run.counts`，内部 `counts` 才是统计。API 明确返回 `report`，计数位于 `report.counts`。
- 配置 / 镜像 / SQL 无实际证据前保持待验。之后申请 T-24 许可，不自行进入正式部署。
- P4 已结束且成果已在仓库，**不用重启或重跑 P4 生成过程**。需要新子 agent 时，用新批次 ID 和当前 HEAD 的新提示词，不覆盖历史日志。

## 5. 实施分工与后续关键接口

所有业务编码与语义修复由独立 **`openai/gpt-6-astra`** 子 agent 完成；主会话派发、约定接口、集成、复验、记录。独立文件可并行，共享文件串行；不可用时报告并请用户决定，不擅自换模型。审核员 A 仍为独立 Claude 会话，不由 Astra 的自测代审。

- `prepare_import(pool, triggered_by=..., code_version=..., session_cookie=..., v0_url=...)` 同步持连接与咨询锁后创建批次。API 先准备再返回 202；已有批次转 409，不能提前归还连接。
- `PreparedImport.execute(roots, cache_dir)` 后台执行，派发失败才 `cancel()`；不是用户取消 API。新 API 已接入这些接口，真实线程 / SQL / 资源生命周期测试待 T-24。
- `compute_import` 是可本机验证的真实文件流水线；附件读到即消费，不保存全量原文。CatalogState 不模拟数据库。
- `latest_valid_snapshot` 按 import_run 的 valid 状态取最近批次；有效空快照、失败批次的有效快照都不能错误退回旧非空记录。
- `preserved_items` 只冻结编号 / 线索 / 出处；新影像的严格展示策略、原始位置追加与新附件关联仍须更新。原主编号在待确认时不丢失。
- NLC 权威只覆盖一级国图写卷目录，不清除词表外子单元自身编号；画布序号从 0 起。派生仅信成功记录，不能将 raw 完成或退出码 0 当最终 TIFF 成功。
- 合并建议按参与端各有一条结构化异常（每对两条），不改变归并；不要只关联左端或重新解析自然语言猜对象。
- 只读接口、参数和路径的设计权威在 feature plan；实际实现与受保护 OpenAPI 见 `api.py`。没有目录写操作、CLI 导入、取消 / 回滚 API。
- `DH_CODE_VERSION` 本机默认 development，镜像构建和运行必须注入真实候选 / 已合并 SHA；不在容器里运行 git。

## 6. 命令、端口与日志

### 当前需要重启的命令

**无。** 子 agent 全部已退出，未启动服务，也未创建 NAS 隔离测试环境。不要运行 docker stop 或关闭用户既有服务。

设计端口（并非本会话已监听）：新 API 宿主 8504 → 容器 8000；DB 5432 仅项目内部、不发布；既有 v0 8503 保持原状。具体绑定与限额以 `catalog/docker-compose.yml` 为准，尚未通过真实 Compose / 容器验证。

### 子 agent 调度（恢复后创建新任务才使用）

现有脚本 `/srv/example/private-audit/implement/run_task.sh`，仓库备份为 run_task.sh（非公开历史记录）。固定 Astra、独立 pi --no-session、read/bash/edit/write、2400 秒超时，不是新 agent 框架。

该脚本当前固定 cwd 为 `~/dunhuang-viewer`、输出为 `~/dh-audit/implement`；换机器 / 路径时先改调度脚本路径。先准备并核对新任务提示词，再调用 `bash <脚本> <新批次ID> <提示词绝对路径>`。不要现在执行，也不要直接重放归档的旧 HEAD 提示词。

原日志目录：`/srv/example/private-audit/implement/`，包含 P1-T13、P1-T14、P2-M5、P2-fix、P3-M6、P4-runtime 的 `.meta` / `.status` / `.out.md` / `.err`。均 exit=0，stderr 为空。P4 16:53:17～17:01:12；本次暂停后未再启动新 agent、构建、下载或长验证。

审核工具原目录：`/srv/example/private-audit/review/`。A 优先 claude-bridge，接入不可用时 anthropic/claude-fable-5-1；先前接入不可用原因非公开，每轮仍需记实际通道与切换原因。实现尚未进入独立 Review。

## 7. 已拷入项目的重要临时产物

全部位于 **历史归档（非公开历史记录）**：

- `prompts/prompt-*.txt`：P1～P4 的实际派发提示词（历史证据，不直接重放）。
- `logs/<批次>.meta`、`.status`、`.out.txt`：实际模型、起止与退出码、自测报告。stdout 原为 Markdown，归档成 txt，以免被文档一致性工具当规格解析。
- `logs/pause-process-check.txt`：暂停收尾进程检查与自然结束记录；`logs/pause-integrity.txt`：短的交接完整性检查及归档格式提示。
- `tools/run_task.sh`：实施调度原脚本；`tools/consistency.py`：可从根目录直接调用的机械检查。
- `tools/run_round.sh`、`tools/fill_result.py`：审核 / 结果填入工具备份，保留了原本外部目录约定；将来使用前核对路径，不在 Implement 改 checklist。
- `prior-handoff.txt`：较早外部交接，可能有旧进度，以根 HANDOFF 为准。

没有需要抢救的 NAS `/tmp` 数据库 / 容器产物。本机 pytest 合成材料、venv 和缓存可再生，不入库。

以下**非恢复必需的原始 NAS 抽查内容不复制、不提交**，遵守 AGENTS 的私有 / 原始材料红线：`/srv/example/private-audit/protocol-facts-20261028.txt`、`protocol-log-blocks-20261028.txt`。程序与合成测试已在仓库，恢复不依赖这些原文；必要时只读按名核查，不遍历 cache。没有复制真实 .env、users.json、密钥或 pi 认证配置。

## 8. 需要用户拍板

1. 何时明确恢复推进；未恢复前保持暂停。
2. T-23 完成后，是否允许 T-24：NAS 隔离候选快照、受限构建、一次性 PostgreSQL / API 测试容器，仅合成材料和认证，禁挂真实材料 / 正式 pgdata，不启动正式 Compose、不影响 v0。现在尚未批准。
3. 是否推送功能分支到 origin；当前没有 push 本轮实现，也没有 merge main。
4. 独立 Review 后的 Gate 2、正式部署许可、全量导入 / A1～A7 许可分别仍需确认，不能由“继续”或换模型授权替代。
5. 是否同步 related-project 的 AGENTS / 模板仍待单独确认；那个仓库有用户未提交改动，本轮未动。

## 9. 下次恢复后发给用户的第一句话

**我先复验已落盘的运行配置，再由 GPT 6 Astra 补验收入口；未经批准不启动 NAS 测试或部署。**
