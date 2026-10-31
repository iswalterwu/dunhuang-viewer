# 公开验证摘要：catalog-foundation 历史软件证据

> **脱敏衍生摘要，不是模型逐字原文。** 第1～6节是历史候选证据，不是隐私修订后代码的新测试；第7节另记合并后main的隔离目标回归。 原提示词、命令、日志、JSON、清单与候选映射已在非公开档案保全。这里保留实际模型/角色、候选范围、数字、失败、跳过、退出和限制，不公开私人身份、路径、网络、设备实例、接收操作或账户接入详情。

## 1. 候选与证据规则

- `private-candidate-NNN` 是共享私有映射中的稳定别名，不包含旧提交片段；**不是 Git ref、不是重写后公开提交、不可直接传给 git archive/diff**。同一别名在规格与本摘要中表示同一旧输入；完整映射仅非公开留存。
- 原件完整性校验与公开衍生文档不是同一件事。本文不沿用原快照/原报告哈希冒充当前文件校验和；原清单含私人来源路径，不继续发布。
- 旧归档命令仅是当时操作证据，不是可直接复用的公共入口。本机文档检查已迁移到 `tools/check_docs.py .`；未来获准测试/部署入口见 [catalog说明](../catalog/README.md)。
- 实施模型为 **openai/gpt-6-astra**；独立审核员A为 **claude-fable-5-1**。R1首选桥失败后，实际审核走 Anthropic；后续轮次引用既有接入不可用证据未重试桥，不伪称桥已审核。具体账户原因与位置非公开。
- 测试由主会话/协调员独立执行时，不把它记成模型亲跑或独立审核。下文“passed / failed / skipped”是测试计数；进程exit0不等于审核通过，也不证明没有跳过。

## 2. 实施与本机阶段

下表全部实施/分析进程的记录退出码为 **0**；P11只读分析不是实施或独立Claude审核。候选列是派发输入，不是实施后已验证提交。完整修改范围与原历史任务结论见 [tasks](../specs/catalog-foundation/tasks.md)。本机环境为 Windows / Python 3.14（后续记录具体为3.14.2），缺DB/仅Linux项不能算通过。

| 阶段 | 派发别名 | 实际角色/模型 | 范围与原结果 |
|---|---|---|---|
| P1/T13、T14 | private-candidate-026 | openai/gpt-6-astra，两独立任务 | 国图36通过、派生35通过；主会话完整266 passed / 15 db skipped / 1警告 |
| P2/M5、P2-fix | private-candidate-027 | openai/gpt-6-astra | 原指定47 passed / 30 skipped；发现四项集成缺口后修复指定51 / 30；主会话完整303 / 30 / 1警告 |
| P3/M6 | private-candidate-028 | openai/gpt-6-astra | API/CLI及关联；指定73 / 27；主会话完整311 / 42 / 1警告 |
| P4/T22 | private-candidate-029 | openai/gpt-6-astra | 运行文件与静态契约；主会话318 / 42 / 1警告，7项运行文本契约通过；不是Compose运行证明 |
| P5/T23 | private-candidate-031 | openai/gpt-6-astra | 34项固定基线、42项比较测试、A1～A7入口；非DB360 passed / 42 deselected，完整360 passed / 42 skipped / 1警告；两口径不混用 |
| P6/T24修复 | private-candidate-034 | openai/gpt-6-astra | 仅两个CLI测试的4行夹具/环境传值；指定41 / 27，完整360 / 42 / 1警告；不改生产/认证 |
| P7/T27 C1 | private-candidate-037 | openai/gpt-6-astra | JPEG具体安全异常捕获及两条真实文件回归；指定56 / 15，完整362 / 42 / 1警告；未关闭Pillow保护 |
| P8/T28、T29；P9/T30 | private-candidate-041 | openai/gpt-6-astra，非冲突范围并行 | 依据复用/pending与同号说明；P8指定78 / 28 / 1警告，P9 identity38通过；集成369 / 43 / 1警告（412项） |
| P10/T31 | private-candidate-046 | openai/gpt-6-astra | loader与测试两文件，128行服务端游标；完整369 / 54 / 1警告（423项）；54=51缺DB+3Linux |
| P11/T33 | private-candidate-049 | openai/gpt-6-astra，只读分析 | 生命周期/候选分析，未修改产品、未亲跑目标测量；非CodeReview |
| P12/T34 C | private-candidate-054 | openai/gpt-6-astra | 两文件消除策略自捕获环；6新增测试，完整375 / 54 / 1警告（429项） |
| P13/T35 A | private-candidate-055 | openai/gpt-6-astra | 四类影像只读Mapping/64形状池/Jsonb边界；12新单测+1PG测试，完整387 / 55 / 1警告（442项）；55=52缺DB+3Linux |
| P14/T37 N1 | private-candidate-060 | openai/gpt-6-astra | 两生产函数+6/-1及两个测试文件；主会话指定53 / 42 / 1警告，完整389 / 57 / 1警告（446项，10.15秒）；57=54缺DB+3Linux |
| P15/T38期望修正 | private-candidate-062 | openai/gpt-6-astra | 仅新增HTTP断言一行；指定3 / 13 / 1警告，完整389 / 57 / 1警告；本机新HTTP仍skip，不能代目标A2 |

P14先红的 **2 failed / 48 passed / 28 skipped、4.28秒** 是实施报告自述，逐工具原输出未在原归档中，不伪称已保全。主会话后来以真实旧源码配最终测试做独立反事实：**2 failed / 48 passed / 29 skipped、1.43秒、exit1**，多1个新增PG skip；这是事后复核，不是先红原输出。P15末尾范围检查曾因主会话同期创建操作记录失败；该文件不是P15修改，原失败记录保留，不能伪称范围检查始终通过。

历史工作副本迁移：6,049文件逐一SHA-256一致，重生17个环境入口后完整 **360 passed / 42 db skipped / 1警告**；pip check、Git fsck、模块help与调度语法通过。私人迁移路径与调度位置非公开，不改变软件测试结论。

## 3. 目标Python / 真PostgreSQL回归

以下均为主会话在当时获准的隔离测试范围执行，不是实施模型或审核员亲跑。Python **3.12.15**、PostgreSQL **17.4**，构建/API **512m=memswap**、PG **384m=memswap**；PG参数64MB shared_buffers / 20连接 / 4MB work_mem。没有真实材料、v0认证/cache或正式pgdata宿主挂载，无宿主端口、无正式Compose服务启动；仅外部v0 HTTP用替身。不能代实际v0健康/认证或真实材料验收。

| 阶段 | 实测旧候选 | passed / failed / skipped | db项实际执行 | 秒 | 测试exit | 结论与修复边界 |
|---|---|---|---:|---:|---:|---|
| T24-A1 | private-candidate-034 | 400 / 2 / 0 | 42 | 47.10 | 1 | 两CLI测试误用不含口令的DSN；失败保留，不放宽认证 |
| T24-A2 | private-candidate-035 | 402 / 0 / 0 | 42 | 47.62 | 0 | P6只修夹具传值后全通过 |
| T24-A3 | private-candidate-038 | 404 / 0 / 0 | 42 | 48.27 | 0 | 含C1安全异常及真实compute回归，旧402不是新候选证据 |
| T28-scale-A4 | private-candidate-042 | 412 / 0 / 0 | 43 | 46.08 | 0 | P8/P9后真库通过，但36k资源目标当时未完成 |
| T32-A1 | private-candidate-047 | 423 / 0 / 0 | 54 | 59.66 | 0 | 游标新增11参数项实际执行；资源仍未过放大条件 |
| T36-A1 | private-candidate-056 | 442 / 0 / 0 | 55 | 64.37 | 0 | A+C新回归与后述36k合成测量 |
| T38-A1 | private-candidate-061 | 445 / 1 / 0 | 57 | 72.66 | 1 | 新HTTP断言漏掉requested_run随请求变化；其他3项内容一致，API契约未改 |
| T38-A2 | private-candidate-063 | 446 / 0 / 0 | 57 | 73.22 | 0 | P15只修一行期望后全套通过；完整快照/run_id/basis比较保留 |

各轮均保留原有 **1条Starlette/httpx警告**；未为消警告升级或屏蔽。Docker24.0.2；T24记录Compose v2.20.1-6047-g6817716。T36未改显式requirements/Dockerfile，但间接opentelemetry-api从旧T32/T33的1.45.1解析为1.45.2，不能称环境完全相同。T38 A1/A2完整freeze逐字相同，不表示全部历史批次相同。

各轮临时库、容器、匿名卷、网络、镜像、隔离快照与临时凭据按记录清理，v0未重启；现场主机ID、启动时刻、free memory等原值仅私下保全。T38-A1首个清理检查因异步删除未结束而 **exit1**，后续等待确认成功，两日志均保留。T32操作printf错误发生在建库前；T33曾遇PG初始化临时服务器退出，改操作readiness后成功，均不掩盖为产品测试通过。最终Docker events为有限缓冲，部分早先退出需单独日志核对，不能宣称events覆盖全部历史。

## 4. 内存诊断、停止与36k支持边界

所有RSS为进程峰值，cgroup包含页缓存，两者不可混用。真实prepare/execute两次且第二次重新从PG加载S0；合成微型TIFF头/国图JSON不代表完整大光栅I/O、真实长路径、复杂派生或并发服务。

| 阶段/旧候选 | 规模与实际测量 | 结论 |
|---|---|---|
| R1协调员本机复核 / private-candidate-038 | 2k首轮101.28 / 重导114.86MiB；6k191.29 / 232.25MiB；36k线性估算865.5 / 1111.4MiB | 无数据库的真实compute/DTO路径，估算不是NAS实际OOM |
| T28-A4 / private-candidate-042 | 真PG 2k首轮94.72 / 重导109.96MiB，6k133.24 / 175.71MiB；36k趋势668.83MiB；6k S0进程峰值143.17MiB | 未36k、未OOM，按约定停止，P1当时未闭 |
| T32 / private-candidate-047 | same2k重导102.37、same6k153.01、varied6k160.58MiB；S0峰值109.02MiB；36k投影532.8164 / 586.5352MiB | 两投影未同时≤480MiB，未创建36k测试资源，停止；≤480只是放大操作门槛，不是新增AC |
| T33 / private-candidate-047（协调记录private-candidate-049） | 无hook6k160.48MiB / 102.46秒；阶段hook160.99 / 372.09秒，约3.63倍；图seen约33MiB额外 | 联合图71.677MiB、两状态四类外层25.269、循环独占4.108MiB均为容量，不是已释放RSS；不是新423回归 |
| T36 / private-candidate-056 | same2k/6k重导97.09 / 135.48MiB、varied6k140.55；投影423.4141 / 465.3008MiB均≤480 | 门槛实际通过后才做36k；不预扣C容量或理想tuple收益 |

T36校准与足规模原精度结果：

| 数据 / 影像 / 写卷 | 首轮RSS MiB | 真PG重导RSS MiB | 首轮 / 重导cgroup MiB | 首轮 / 重导秒 |
|---|---:|---:|---:|---:|
| same / 2k / 334 | 92.44 | 97.09 | 171.18 / 173.64 | 18.251 / 15.762 |
| same / 6k / 1k | 121.11 | 135.48 | 225.38 / 225.38 | 54.210 / 47.550 |
| varied / 6k / 1k | 124.65 | 140.55 | 233.53 / 249.61 | 55.614 / 48.715 |
| varied / 36k / 6k | 341.98 | 435.05 | 512 / 512 | 343.115 / 307.414 |

T36各点exit0、无OOM；36k第二轮36,000事实复用，ID/basis/facts摘要稳定、变化零，history保持42,000。独立尺寸数与宽度和正确。原S0同口径6k读取后102.34MiB，field_basis文本均值4803bytes、总28,818,000bytes、facts2,346,000bytes保持，不是缩字段。

**435.05MiB RSS与512MiB上限差约77MiB，不是容器总可用余量。** cgroup实测已触硬限；审核员估计真实450～480MiB/6～9分钟只是推理，不是实测。T33完整观察器开销、可达子集与候选比较见[诊断的隐私修订](../specs/catalog-foundation/memory-diagnosis.md)，不把理想tuple载荷105.47MiB/36k上界当实际收益。

## 5. 独立审核阶段

| 阶段 / 候选 | 实际模型/通道与exit | 原结论与范围 |
|---|---|---|
| R1首选 / private-candidate-039 | claude-bridge/claude-fable-5-1，exit1 | 接入失败、stdout为空，无评审结论，不计通过 |
| R1有效 / private-candidate-039（源码private-candidate-038） | anthropic/claude-fable-5-1，exit0 | **需修复后重审**；CR1-01为P1；本机362 passed / 42 skipped / 1警告；只核目标404原件，未亲跑目标PG |
| Checklist12 / private-candidate-044 | anthropic/claude-fable-5-1，exit0 | 10通过 / 0不通过 / 2不评，允许Tasks，不是Implement许可 |
| Analyze13 / private-candidate-045 | anthropic/claude-fable-5-1，exit0 | 12通过 / 0不通过 / 0不评，仅T31/T32允许Implement |
| T33口径校读 / private-candidate-050 | anthropic/claude-fable-5-1，exit0 | 补GC回收时点非固定、理想容量与缺口同量级后可交用户选择；不是CodeReview或Plan10批准 |
| Checklist14 / private-candidate-052 | anthropic/claude-fable-5-1，exit0 | 10通过 / 0不通过 / 2不评；尚不能Implement |
| Analyze15 / private-candidate-053 | anthropic/claude-fable-5-1，exit0 | 12通过 / 0不通过 / 0不评，仅T34～T36 |
| R2 / private-candidate-057（源码private-candidate-056） | anthropic/claude-fable-5-1，exit0 | **软件通过**，CR1-01代码级/02/05关闭，无新P0/P1/P2；N1/P3是旧基线问题、修复时机待用户决定；亲跑本机387 / 55 / 1警告、12.10秒，仅核442/36k原件 |
| Analyze16 / private-candidate-059 | anthropic/claude-fable-5-1，exit0 | 12通过 / 0不通过 / 0不评，仅T37/T38；不改需求、不代代码Review |
| R3 / private-candidate-064（源码private-candidate-063） | anthropic/claude-fable-5-1，exit0 | **软件通过、N1关闭**，无新P0/P1/P2；亲跑本机389 / 57 / 1警告、10.14秒，仅核目标446与5目录完整性，不代用户Gate2 |

审核阅读范围并非穷尽：R1完整读生产/运行配置、关键测试，其余部分测试只核清单/部分断言；R2未全文重读derivation及若干未改旧测试；R3核实际diff、相关生产/测试和原证据，未亲跑目标服务/数据库。具体原范围和工具输出非公开保全。

早期第1～11轮的通过/不通过/不评、双人共识及通道变化仍逐轮保留在[checklist隐私修订](../specs/catalog-foundation/checklist.md)，不修改原勾选。第8轮起取消审核员B；此前A/B结果不冒称为单人A已通过。原报告自述分钟级时间与调度meta/status的差异只在原件核对，本文不伪改原报告为逐字原文。

## 6. 未验事项与本轮发布边界

- R3仅据当时两函数差异认为旧T36支持当时N1候选的首轮/同版本无变化重导，不要求该轮重做36k；**没有N1候选直接36k实测，更没有本轮隐私代码36k实测**。规则版本升级足规模history/WAL/编号更新成本仍未验。
- historical是完整编号记录历史，不保证编号值曾改变。同号而source/path/is_primary等业务值变化仍会历史化并重插；要改变此语义必须先Clarify，不能借隐私修订扩修。
- CR1-03裸号紧邻扩展名尚未证实，CR1-04备份根散放为低概率；不改冻结编号/归并规则，留T26实物核查。
- T25正式只读挂载、外部PG、LAN/Tailscale绑定、默认CMD/health及真实v0认证；T26基线/对象/谱系/画布/只读/512MiB与连续v0健康、全量≤1h/无变化≤10min/P95≤1秒及20链接均待单独许可。软件Gate2不等于这些已通过。
- 用户已批准原软件Gate2；后续公开隐私Gate1和origin两分支历史清理授权不代新差异Review/必要Gate2。当前树修订不等于历史清理；平台旧对象、缓存、分叉及第三方副本不能保证撤回，平台固有发布者身份不隐藏。
- 第1～6节由PRIV-03核对历史原件编写；源码回归、全树机密规则扫描、历史演练与最终审核属于后续集成任务，**不能据本文宣布全树已清理或最终验收通过**。当前状态权威见[公开发布规格](../specs/public-release-privacy/spec.md)与[任务](../specs/public-release-privacy/tasks.md)。

## 7. 合并后main隔离目标回归（T-39）

PR #1合并后，用户另行批准一次隔离验证。输入是公开main提交 `646a29ee64ba`，不再使用私有别名。安全范围与§3相同：Python **3.12.15** / PostgreSQL **17.4**，构建/测试容器 **512m=memswap**、PG **384m=memswap**；没有真实材料、v0认证/cache或正式pgdata宿主挂载，无宿主端口、无正式Compose。外部v0 HTTP仍为替身。

| 阶段 | 输入 | passed / failed / skipped | db项实际执行 | 秒 | 测试exit | 结论与边界 |
|---|---|---|---:|---:|---:|---|
| T39-A1 | main `646a29ee64ba` | 未运行 | 0 | — | — | 构建硬限额实证与候选构建成功；PG就绪探针在初始化临时服务阶段过早返回、专用库未可连，按失败即止；仅改仓库外操作就绪条件 |
| T39-A2 | main `646a29ee64ba` | 483 / 0 / 0 | 61 | 84.45 | 0 | 新增4个DB回归及3个仅Linux项均通过；1条原有Starlette弃用警告；freeze与T38-A2逐项相同 |

两批次临时资源与凭据全部清理并复核无残留，v0未重启；现场主机状态、可用内存原值与原始输出仅非公开保全。此结果是合成软件证据，不代T25正式部署，也不代T26真实材料、规模、性能与v0连续健康验收；旧36k不变成本候选实测。

## 8. T-25 正式部署核验（2026-10-30）

经用户批准，部署远端以单 ref 精确租约替换为获准 main `abfd5ff92b15`，v0 的 `.env` 与开机钩子宿主配置已迁移，守护循环已按新钩子重启；v0 容器未重建、未重启。目录服务受限构建并启动后：

| 核验项 | 结果 |
|---|---|
| 两容器健康与 `python -m dh_catalog health` | 通过 |
| 内存限额 | API 512m、DB 384m，各自 memswap 相等 |
| 挂载 | API 恰有4项只读挂载；DB 只挂工作区外专用数据目录 |
| 端口 | API 只绑定局域网地址与回环的 8504（Tailscale 用户态模式经回环转发）；DB 无宿主端口 |
| 运行状态 | 运行中、无 OOM、重启次数 0 |
| 正式依赖清单 | 29 项，与 T39-A2 逐项相同 |
| 匿名访问 | 局域网、回环、Tailscale 三路 `/api/v1/items` 及 `/api/v1/docs` 均为 401 |

登录态冒烟由用户在浏览器完成，服务端访问日志核对为：普通账号读 200、导入被拒 403、管理员读 200，无导入被受理；T26 真实材料导入、资源/耗时/P95 与 v0 连续健康尚未验收。主机路径、地址、私有备份与原始输出仅非公开保全。


## 9. T-26 首次全量导入与 A1～A7 验收（2026-10-30～31）

| 项 | 结果 |
|---|---|
| 导入 | 全量 771 秒、无变化重跑 412 秒，均成功；重跑变化为0 |
| 资源 | 均在 512m 内完成、无 OOM；重跑 API 峰值 95.2%（余量薄）；采样器曾中断，重跑前约3分钟无资源样本 |
| v0 健康 | 154 / 82 次采样，失败0，最长 0.078 秒 |
| 只读 | 原图与备份前后元数据零差异；缓存只访问 13 个白名单文件 |
| A1 覆盖 | valid，未对应0；74 个国图目录未入 v0 索引已单列 |
| A2 基线 | 34 项中 25 项一致；3 项对象核查通过；6 项差异逐项取证，其中 WB 少2个目录无法逐对象指认 |
| A3 谱系 | 总数相符；12 个目录改判逐一取证；1 个净变动目录无法指认 |
| A4 画布 | 84.5%；缺口全部列为异常；发现 F-1：`report.json` 的 `pages` 结构未支持（730 卷），须修复后复验 |
| A6 P95 | 列表 0.079 秒、详情 0.262 秒 |
| A7 链接 | 20/20 通过 |

此为真实材料的首次验收证据；画布映射修复、命名变体澄清与内存余量仍待后续处理。主机路径、地址、原始报告、采样与浏览器取证文件仅非公开保全。