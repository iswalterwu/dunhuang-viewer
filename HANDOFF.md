# 会话交接 — catalog-foundation

> **状态：已进入 Converge；发现 JPEG 头安全异常会意外中断整批（C1/T-27），待 Astra 修复，尚未收敛或启动独立 Review。** 原 T-24 为 402 passed / 0 skipped，资源已清理；原测试数不能替代新增缺口验证。
> 更新日期：2026-10-28。这是会话恢复入口，不代表工作流已到 Handoff 阶段；尚未过 Gate 2、未合并 main、未正式部署或全量导入。

## 1. 当前任务与闸门

目录底座 `specs/catalog-foundation/`：只读导入 NAS 写卷影像、编号、来源与许可，提供稳定身份、变化历史、报告和授权只读 API；不改运行中的 v0。

- spec 第 7 版已获 Gate 1 批准并冻结（13 条需求、58 条 AC、25 条最终决策），feature plan 第 8 版；不重复申请 Gate 1，不修改冻结规格或 checklist。
- Checklist / Analyze 第 11 轮由独立审核员 A 判定 12 项全部通过，**只是设计质量结论，不是实际实现 Review**。
- T-01～T-24 的实现及对应自动化验证已完成。最新真实 PostgreSQL/Python 3.12 测试包括原来跳过的全部 42 个 db 项，均已执行通过；T-22 隔离构建及合成 Compose 配置校验亦通过。
- 当前为 Converge。主会话已完整核对主要源码，利用 631 字节合成 JPEG（头声明400M像素、未解码）复现 DecompressionBombError 逃出 read_facts 导致 compute_import 中断，违反 AC-005-1；已登记 T-27。需 Astra 最小修复并补回归、新候选 T-24 后再收敛/Review。**还没有实际实现的独立 Review、Gate 2 或全量收敛结论**。
- T-25 正式部署、T-26 用户触发真实全量导入与 A1～A7 仍未执行、未获许可；合并也不等于 feature 全量验收完成。

## 2. 本机、GitHub 与候选身份

- 唯一本机工作副本：**`/srv/example/project`**；分支 `feat/catalog-foundation`，跟踪 `origin/feat/catalog-foundation`。
- 2026-10-28 已按用户要求从 `/srv/example/project` 迁移；原样复制阶段对含 .git/忽略的本地环境共 6,049 个文件逐一 SHA-256 验证一致，重生虚拟环境激活/17 个入口后移除旧目录。依赖未在本机下载或升级；后续命令只用 D 盘路径。
- 用户已批准后续已验证阶段及时同步 GitHub 功能分支，不需重复询问普通分支 push。GitHub：`origin 的 feat/catalog-foundation 分支（项目角色描述，非网址）`。不擅自 merge main、push nas 或部署。
- 上一安全提交 **`private-candidate-035`**：Astra 两处 CLI 测试最小修复及首轮失败/清理证据，已 push；**它也是最新实际通过 NAS 全套测试的候选 SHA**。
- 本轮其后的完成状态/证据文档提交，不改变被测生产源码、迁移、运行配置或测试。实际最新 HEAD 用 `git log -1 --oneline` / `git rev-parse HEAD` 查看，不把未知的自引用 SHA 写入本文。未来部署镜像仍须用实际获准/合并提交 SHA 构建，不能冒用旧候选版本。
- 本地 main 与 origin/main 记录仍为 `private-candidate-023`；本轮没有合并或推送 NAS。

## 3. T-24 两轮真实证据

用户在明确隔离测试范围后回复「开始」，批准候选快照、受限构建、一次性 PG/API 测试与本轮清理；仅合成材料/认证，禁真实材料、v0 文件、正式 pgdata 挂载，禁正式 Compose。该批准不包含 T-25/T-26。

共同环境：NAS Docker **24.0.2**、Compose **v2.20.1-6047-g6817716**；候选镜像 Python **3.12.15**，一次性 PostgreSQL **17.4**。主会话预检通过（门槛 ≥2GB）；宿主即时内存与交换状态非公开，仍严格保持硬限额且不增加 swap，不放宽红线。

| 轮次 | 候选 | 完整测试结果 | 结果/限制 |
|---|---|---|---|
| A1 | `private-candidate-034` | **400 passed / 2 failed / 0 skipped / 1 warning，47.10 秒** | report/health 两个 CLI 子进程测试使用不含口令的 connection.info.dsn；诊断确认原始测试 URL 能连、info.dsn 无口令重连失败 |
| A2 | `private-candidate-035` | **402 passed / 0 failed / 0 skipped / 1 warning，47.62 秒** | P6 最小修复后，两处 CLI 与全部数据库/HTTP测试通过；Docker die 事件 exitCode=0 |
| 本机修复复验 | P6 后相同测试源码 | **360 passed / 42 db skipped / 1 warning** | Python 3.14.2，本机无数据库，不将 skip 算 pass |

- A2 快照 SHA-256：`d2c9f1c845747c4c2fdec1ed49afe765e7a5f04b9816ce8f24f6103ea3877c5d`；传输到 NAS 后核对一致。
- A2 镜像 ID：`sha256:b849fc8b9af3e4c386e3864d0677981f6ce1a5cccd9d1e564dc19f780dd35777`（测试后已删除）。镜像包含真实 tests、acceptance、pytest.ini、migrations 与固定直接依赖，pip check 通过。
- legacy builder 使用 `--memory 512m --memory-swap 512m --rm --force-rm`；A1 构建探针在真实 cgroup 读取 memory/memsw 均为 **536870912**。未删限额、未换无上限构建。
- API 测试容器 **512m**、PG **384m**，memswap 分别相等；实际 inspect 与 cgroup 核对留证。测试 API 没有挂载，PG 只有自身匿名临时卷；无宿主绑定目录、无发布端口，临时网络互通。不是正式 Compose 或 HTTP 服务部署。
- 两候选均用合成 .env 做 `docker-compose -p dunhuang-catalog config -q`，只静默检查、不执行 up。正式挂载、端口、默认启动与生产凭证仍待 T-25。
- pytest 唯一警告是原有 Starlette/httpx 弃用提示，未升级依赖或屏蔽。构建/SSH 原输出还保留 legacy builder 弃用、pip root、SSH 非后量子密钥交换提示；没有改 NAS/SSH/Docker 版本或安全配置来消除提示。

## 4. 修复范围与清理结果

P6 实际模型 **openai/gpt-6-astra**，派发 HEAD `private-candidate-034`，22:26:19～22:28:04 自然结束，exit=0、stderr 为空。仅修改：

- `catalog/tests/test_api.py::test_health_cli_readonly_and_migration_check`
- `catalog/tests/test_import.py::test_report_cli_readonly_without_auth_files`

两测试各增加 `test_database_url` 夹具参数并传给子进程，共替换四行。保留真实 subprocess 与全部原断言，不 mock、不 skip/xfail、不改生产 API/CLI、不增加隐式凭证 fallback、不放宽 PG 认证。主会话本机复核后形成 A2，真实库全部通过。

两轮资源已确认清理：临时数据库（显式 DROP）、API/DB/诊断容器、两匿名 PG 卷、两临时网络、三测试/探针镜像标签、两隔离目录、远端 raw 输出及临时合成 .env。**没有本轮遗留运行资源或需重启命令**；P1～P6 子 agent 均已结束。未全局 prune，原有 Python/PG 基础镜像 ID 未变。

- 已删除 `/tmp/dh-catalog-t24-20261028-221119-private-candidate-034` 与 `/tmp/dh-catalog-t24-20261028-223110-private-candidate-035`。
- v0 容器始终为同一 ID `cb29d6cf59e9694ce1a35ecdb2f52a8f25a3164d8fcc46e037d93a295e254ac2`、启动时间 `2026-10-24T23:21:23.021250776Z`、restarts=0、running=true；未停/重启。**这不代替 T-26 全量期间 v0 健康连续采样**。
- 没有访问原材料、备份、v0 .env/users.json/cache，也未遍历 cache；没有真实登录/正式导入、NAS git push 或正式服务启动。

## 5. 下一步（Converge / 独立 Review，不是部署）

1. 在 D 盘仓库核对 git 状态/HEAD，重读 AGENTS、docs、spec/plan/tasks。T-24 已完成且已清理，不重复申请既有测试许可或重放旧快照。
2. **Converge**：继续逐条对照 58 条 AC/实际测试，先修 T-27/C1。保留 Pillow 安全限制，不能关闭 MAX_IMAGE_PIXELS 或宽泛吞异常。主会话只协调/复验；业务代码和回归由新 Astra 子 agent 修改。因生产代码改变，需新候选 T-24 隔离复验；不把旧 402 通过写成新版本证据。
3. **独立 Review**：审核员 A 为独立 Claude 会话，与实施隔离；审查相对 main 的实际代码差异，按 bug/架构风险/测试缺口/目标对齐给结论，不以 Astra 自测或主会话代审。目前尚未启动本次实际实现 Review。
4. Review 产物明列 T-25/T-26 待验项，交用户 **Gate 2** 确认。未批准不得合并 main。之后正式部署、真实全量导入/重跑分别另获许可；全量导入由用户在受保护 OpenAPI 触发，不代签会话。
5. 部署后任何代码修复仍须 Review → Gate 2 → merge → 获准部署。真实材料/性能未验前 feature 保持 in-progress，不宣称全量收敛或验收完成。

后续仍待证明：真实材料完整覆盖/基线/谱系/画布/对象关系，四项 ro 挂载与外部 pgdata/端口绑定，原图/备份前后元数据归因、cache 访问审计，512 MB 全量完成与 v0 连续健康，全量 ≤1小时、无变化重跑 ≤10分钟，列表/详情各100次 P95 ≤1秒，20个真实 v0 链接抽查。详见 README A1～A7 与 T-25/T-26。

## 6. 关键接口与不可回退的实现约定

- `prepare_import(pool, triggered_by=..., code_version=..., session_cookie=..., v0_url=...)` 同步持连接/咨询锁并创建批次；API 先准备再 202，ImportBusy 同步 409，不能提前归还连接。
- `PreparedImport.execute(roots, cache_dir)` 后台执行，只有派发失败才 `cancel()`；不是用户取消 API。`compute_import` 走真实扫描/规则计算，CatalogState 不模拟数据库；附件读取即消费，不保存全量原文。
- `latest_valid_snapshot` 按 valid 状态取最近批次，正确处理有效空快照与失败批次的有效快照；A1 覆盖必须本批索引有效，不用旧快照冒充。
- `preserved_items` 只冻结编号/线索/出处；新影像严格策略、位置追加、新附件关联继续更新；待确认不丢原主号。
- NLC 权威只覆盖一级国图卷，不清除词表外子单元自己的号；画布序号从 0 起。派生只信最终成功记录，不把 raw 完成/退出码0当最终 TIFF 成功。
- 合并建议每对参与端各一条结构化异常，不改变归并、不只关联左端、不重新解析自然语言猜对象。
- 只读路径/参数以 feature plan 与实际受保护 OpenAPI 为准；无目录写操作、CLI 导入、用户取消/回滚 API。AUTH_SECRET 缺失 fail-closed。
- `import_run.counts` 存完整报告；CLI 整行统计 `counts.counts`，API 单批次统计 `report.counts`，直接报告为 `counts` 但无批次成功状态。
- compare 只读已有报告，不扫描材料/复制算法；固定34项基线，txt477不因 Q-024 的六个新增附件改483。三项（图块JPG性质、P.2504返回5件、12个长卷逐条派生/异常覆盖）固定人工留证，不删指标凑0退出码。
- `report.health` 为 count/failures/max_seconds/samples；`report.cache_access` 为白名单打开记录。镜像/运行注入真实 DH_CODE_VERSION，不在容器内运行 git。

## 7. 证据、调度与恢复命令

仓库 历史归档（非公开历史记录）：

- `logs/T24-A1/`：首轮失败、诊断、构建/cgroup/Compose/清理；`logs/T24-A2/`：新候选完整通过、限额/状态/清理与最终所有权检查。A2 `commands.txt` 是主会话的实际命令记录（无凭证值）。
- 归档文本由源输出自动转 LF、去 ANSI 显示控制符/行尾空白，`archive-manifest.json` 记录源/归档 SHA-256；未改测试结果。临时口令先脱敏再导出；不提交快照 tar、远端 raw 或任何 .env。
- 外部原输出仍在 `/srv/example/private-audit/t24/20261028-221119-private-candidate-034/` 与 `20261028-223110-private-candidate-035/`；只含本轮合成测试/运维证据。早先原始 NAS 抽查私有材料未复制入库。
- `prompts/prompt-P6-T24-cli-fix.txt`、`logs/P6-T24-cli-fix.{meta,status}` / `.out.txt` / `-main-local.txt`：实际 Astra 分工与本机复验。P1～P5/迁移证据保留，不重放历史 HEAD/路径提示词。
- 调度仍用 `/srv/example/private-audit/implement/run_task.sh`（备份在 private-audit-record（tools；非公开历史记录，不是可执行入口））：cwd 已为 D 盘、固定 Astra、独立 pi --no-session、read/bash/edit/write、2400秒。审核原目录 `/srv/example/private-audit/review/`；A 优先 claude-bridge，不可用才 anthropic/claude-fable-5-1，记录实际通道/原因。使用旧审核脚本前核对当前 CLI 工具参数及新 HEAD，不覆盖旧轮次日志，不另建框架。

```bash
cd /srv/example/project
git status --short
git log --oneline -8
git branch -vv
catalog/.venv/Scripts/python.exe -I -X utf8 -m pytest -c catalog/pytest.ini catalog/tests catalog/acceptance/test_compare.py
# 历史命令（非公开历史记录，不可执行）：python -I -X utf8 private-audit-record .
git diff --check
```

本机命令默认仍会跳过42个 db 项；不把它写成 NAS 402 passed。T-24 的完整通过证据已归档，不为状态查看重新连接正式库或 NAS 材料。related-project 仓库/模板未动，其同步仍需单独确认。
