# Feature: catalog-foundation 任务清单（tasks.md）

> 公开隐私修订，原件非公开保全，不是逐字原文。仅隐私表述、候选别名与公开链接修订；需求ID、AC、领域/许可/安全语义及原审核勾选、数字、结论保持。旧候选别名不是可用于Git的公开版本指针；证据边界见[公开验证摘要](../../docs/verification.md)。
> 以下阶段状态与执行记录保留其原时间语境，不是本轮隐私实施状态；本轮进度由 `public-release-privacy` 主会话维护，本文件不据文档修订宣布完成。

> 2026-10-28：用户已在 Gate 1 批准 spec 第 7 版（含第 9 轮建议 1～3、5 的措辞澄清）。T01～30原据plan8，T31/T32据plan9/Analyze13；用户现批准A+C的Plan10方向，独立Checklist14无阻断后，新增T34/T35/T36且独立Analyze15现全12项通过允许该范围实施，不以旧13轮许可偷跑。
> **当前（2026-10-30）**：原软件Gate2已批准；用户随后明确保持Public并要求全面隐私脱敏后继续交接/PR/合并。D-019已登记，不再请求改Private；新public-release-privacy完成全树/历史只读盘点、7R/25AC Spec/Clarify待Gate1，运行默认值/接收标签的最小必要改动与历史重写/强推须明确授权。当前未批量脱敏/新推送/PR/merge/部署/真实导入，HEAD=private-candidate-065、main=private-candidate-023，原源码/测试/冻结规格不变；状态与新规格仅本机未提交。
> **Gate2批准前的软件安全点**：N1经Analyze16全12项通过、P14/P15 Astra最小修复与主会话复验后，候选private-candidate-063在T38-A2目标Python3.12.15/PG17.4 **446 passed/0 failed/0 skipped/1原有警告，73.22秒**，57db实际；资源/凭据全清理、v0未重启。独立CodeReview-R3已软件通过、N1关闭（审private-candidate-064/源码private-candidate-063，Anthropic Claude，10:47:51～11:00:57 （原始时刻；时区非公开）、exit0），可请求用户Gate2；未Gate2/merge/部署/真实导入，本轮未新规模测试。A1失败原件保留，旧private-candidate-056/36k不当新候选实测。
> 上轮及本轮实施前：Plan10经独立Checklist14→Tasks→Analyze15全项通过后P12(C)/P13(A)串行实施。候选private-candidate-056在T36/NAS **442 passed/0 skipped/1原有警告，64.37秒**，55db实际；无hook门槛通过后，**36k varied首轮/真PG重导原512限额实测成功，RSS341.98/435.05MiB、343.115/307.414秒，cgroup含缓存触512但exit0无OOM**。资源/凭据已全清理、v0未重启，独立CodeReview-R2现软件通过、CR1-01代码级/02/05关闭，可请求Gate2；新N1/P3为旧基线规则升级重插未变编号；2026-10-30用户回复「同意并继续」，批准Gate2前最小修复、真实临时PG完整回归与独立重审。T37/T38已细化，独立Analyze16于private-candidate-059全12项通过（09:48:03～09:55:40 （原始时刻；时区非公开），Anthropic Claude，exit0），允许仅T37/T38实施；不改冻结spec7/plan10，不以旧Checklist15许可代替本次核对，未Gate2/merge/部署。旧失败门槛/趋势只作历史，不代当前实测；真实材料/并发/连续v0健康仍待T25/T26单独许可。

## 执行约定

- 按依赖执行；每项估时 0.5–2 小时，不含等待许可或下载依赖的时间。完成后在该任务记验证结果，未执行的验证不记通过。
- 2026-10-28 起按用户新要求执行 AGENTS.md §2 的实施子 agent 分工：GPT 6 Astra（openai/gpt-6-astra）；派发范围和主会话复验记录见本文末尾。
- 仅新增 `catalog/`，不改 v0 的代码、镜像、依赖或 compose；不实现 Q-025 删去的机制，不做 PD-07（归 `stitch-hardening`）。
- 实现位置与逐 AC 测试名以 plan §5 为准，本文不另抄测试矩阵。测试调用真实扫描、身份计算、数据库与接口；只有 v0 HTTP 边界用替身。数据全部合成；测试不复制生产逻辑。
- 本机命令均在仓库根执行：先 `python -m venv catalog/.venv`，然后 `source catalog/.venv/Scripts/activate`；`python -m pip install -r catalog/requirements.txt`。pytest 的导入路径、测试目录与数据库标记在 `catalog/pytest.ini` 配置；不用额外脚本包一层测试命令。
- 带 `db` 标记的测试使用 `DH_TEST_DATABASE_URL` 指定的**临时测试库**；变量缺失时跳过，不能误用正式库。本机没有 PostgreSQL / Docker，数据库测试等 NAS 许可后执行。未带该标记的测试不得连接数据库。
- 平时只跑任务对应的完整测试文件，不用 `-k` 模糊筛选；本机模块通过不等于数据库端到端通过，相关证据到 T-24 补齐。T-23 跑一次全部本机测试，T-24 在一次性容器跑一次全部测试；各任务列出的数据库命令只说明对应验证范围，不要求再重复运行。
- T-01～T-24 完成后做 Converge / Review；review.md 显式列出部署后才能证明的 NAS 验收项，由用户在 Gate 2 决定是否接受待验并允许 merge。merge 不代表 feature 验收完成；T-25/T-26 未完成前状态维持 in-progress，不宣称全量已收敛。部署后发现代码缺口，一律新提交重走 Review → Gate 2 → merge → 部署。
- **许可边界**：T-24～T-26 涉及 NAS 测试、建库、构建或启动容器，必须另获用户许可；本次「批准，继续」不是这些操作的许可。正式全量导入由用户在接口文档页触发。只推送 origin，不推送 nas。
- **GitHub 同步**：用户于 2026-10-28 批准同步，已将截至 `private-candidate-032` 的 9 个实施提交（含最新任务、交接文档与验收入口）推送至 `origin/feat/catalog-foundation`，远端 SHA 已核对；此同步记录随文档提交继续推送同一分支。后续已验证阶段及时同步此功能分支，避免只留本机；不合并 main、不部署 NAS，T-24～T-26 许可仍独立。

## 任务

### T-01 服务包、配置与合成测试夹具（1 小时）

- **状态**：本机完成（2026-10-28）；test_config.py 18 项通过（含 CLI 不提供导入入口、不使用数据库默认连接及 health 配置错误拒绝），固定依赖已在独立 venv 安装，pip check 通过；HTTP 协议与真实 DB 验证分别见 T-15/T-21
- **上下文**：M1；建立本机测试入口与明确的外部配置边界，后续模块使用确定类型的配置值。
- **依赖**：无
- **修改范围**：`catalog/README.md`、`catalog/requirements.txt`、`catalog/pytest.ini`、`catalog/src/dh_catalog/__init__.py`、`config.py`、`catalog/tests/conftest.py`、`test_config.py`。现有 `.gitignore` 的 `.env` / `.venv/` 规则已覆盖子目录，不另建一份。
- **完成标准**：为 AC-005-1、AC-011-1、AC-012-1 提供合成小 TIFF / PSB 头 / JPEG、临时目录和配置；入口只读取环境变量及只读 v0 配置，不包含凭证默认值；缺少 `AUTH_SECRET` 保持不可服务的状态，由 API 返回 503（T-15/T-21）；固定依赖版本，v0 本身不动。
- **验证命令**：`python -I -X utf8 -m pytest -c catalog/pytest.ini catalog/tests/test_config.py`。

### T-02 初始数据模型与迁移（2 小时）

- **状态**：实现与数据库验证完成（2026-10-28，T-24 A2）。Python 3.12.15 / PostgreSQL 17.4 全套 402 项通过、0 跳过，其中 test_db.py 15 项实际通过，含迁移重复执行/失败回滚、UUID/多对多/唯一约束/编号约束与 migrate CLI；不以本机语法检查代替数据库证据。独立 Review 仍待执行
- **上下文**：M1；以 plan §3 的表和约束承载稳定 ID、关联、附件、字段依据及历史。
- **依赖**：T-01
- **修改范围**：`catalog/migrations/0001_init.sql`、`db.py`、`__main__.py` 的 migrate、`test_db.py`。
- **完成标准**：为 AC-002-4、AC-003-3、AC-004-5、AC-008-2、AC-009-2、AC-013-3 建表；UUIDv4 与路径解耦；多对多关系、非空 grouping_key 唯一、present 位置唯一、编号索引齐全；迁移重复执行不重复建表，不引入 ORM 或迁移框架。
- **验证命令**：T-24 中执行 `python -m pytest tests/test_db.py`，连接真实临时 PostgreSQL 库；本机只编译 `python -m compileall -q catalog/src`，不能据此宣称数据库验证通过。

### T-03 连接、事务与导入互斥（1 小时）

- **状态**：实现与数据库验证完成（2026-10-28，T-24 A2）。真实 PostgreSQL 双连接验证连接池开闭、事务回滚、咨询锁互斥、回滚不释放会话锁及异常退出后释放；test_db.py 15 项与完整 402 项均实际通过，0 跳过。部署/真实材料验证不在本任务冒充完成
- **上下文**：M1/M5；用同一咨询锁保证只有一批导入，不另建任务队列或进程锁。
- **依赖**：T-02
- **修改范围**：`db.py`、`test_db.py`。
- **完成标准**：为 AC-009-1、AC-009-4、AC-011-1 提供连接池、事务提交 / 回滚、导入咨询锁；锁在任务结束释放；独立保存 import_run 与有效 v0 快照，目录正式数据失败整批回滚。验证并发取锁失败及异常退出后的释放，不增加断电恢复机制。
- **验证命令**：T-24 中执行 `python -m pytest tests/test_db.py`，真实数据库、两个连接验证锁与事务。

### T-04 只读文件清单与排除项（1.5 小时）

- **状态**：本机完成（2026-10-28）；test_scan.py 共 16 项通过，含范围、隐藏目录、附件与原名保留；NAS 数量未验
- **上下文**：M2；扫描是文件系统入口，之后传结构化文件条目。
- **依赖**：T-01
- **修改范围**：`scan.py`、`rules.py` 的分类登记与文件类型、`test_scan.py`。
- **完成标准**：满足 AC-001-2、AC-001-4、AC-008-1；只扫描 data / backup，保留原始 Unicode 名称与隐藏文件；跳过 @/#/. 开头目录并记录原因；国图 JPG 范围、附件、未知文件及 Q-024 新目录的处理与 spec 一致；不遍历 v0 cache，不为拼接临时 TIFF 另加排除模式。
- **验证命令**：`python -I -X utf8 -m pytest -c catalog/pytest.ini catalog/tests/test_scan.py`。

### T-05 文件头事实与读取复用（2 小时）

- **状态**：本机完成（2026-10-28）；test_scan.py 共 16 项通过，含三态事实、读取失败重试、EXIF 不猜分辨率、TIFF/PSB 不读像素；NAS 耗时未验
- **上下文**：M2；只读元数据，不解码整幅影像。
- **依赖**：T-04
- **修改范围**：`scan.py`、`test_scan.py`。
- **完成标准**：满足 AC-005-1，并支持 AC-009-3、AC-012-4；TIFF / PSB / JPG 的 7 个事实按「有值 / 不适用 / 缺失」处理，PSB 只读头，JPEG 位深与分辨率取自文件；未变化且曾读取成功才复用，读取失败下次重读，恢复后取消读取异常；测试从真实临时文件读取，不 mock 文件头解析器。
- **验证命令**：`python -I -X utf8 -m pytest -c catalog/pytest.ini catalog/tests/test_scan.py`。NAS 性能指标由 T-26 验证。

### T-06 编号解析与规范化（2 小时）

- **状态**：本机完成（2026-10-28）；test_identifiers.py 45 项通过；写卷最多一个主编号及存疑不归并的端到端保证已由 T-10/T-24 补验通过
- **上下文**：M3；只解析单元规定的编号来源，不解析写卷内部普通文件名。
- **依赖**：T-01
- **修改范围**：`identifiers.py`、`rules.py` 的号段、`test_identifiers.py`。
- **完成标准**：满足 AC-002-5、AC-002-8、AC-004-1、AC-004-2、AC-004-4、AC-004-5；覆盖分件、多号省略前缀、大小写、分享者编号、带开宝藏上下文的帙号，以及疑似四位数的尺寸 / 年份排除；保留逐字原文，存疑不作主编号。
- **验证命令**：`python -I -X utf8 -m pytest -c catalog/pytest.ini catalog/tests/test_identifiers.py`。

### T-07 单元划分、附件归属与合并建议（2 小时）

- **状态**：本机完成（2026-10-28）；test_units.py 共 20 项通过，含词表、国图页图、散放文件、附件与只提合并建议；持久化关联已由 T-17/T-24 补验通过
- **上下文**：M2；从扫描结果生成 spec §1 的写卷单元。
- **依赖**：T-04、T-06
- **修改范围**：`units.py`、`rules.py` 的词表、`test_units.py`。
- **完成标准**：满足 AC-001-3、AC-002-2、AC-002-3、AC-002-6；按分类 / 批次识别写卷目录，词表内沿用父单元，词表外自成单元且不继承父编号；散放影像各自成单元；无影像不建单元；附件关联所在单元或保持无关联；无号单元只提合并建议、不自动合并。
- **验证命令**：`python -I -X utf8 -m pytest -c catalog/pytest.ini catalog/tests/test_units.py`。

### T-08 备份镜像路径与角色（1 小时）

- **状态**：本机完成（2026-10-28）；test_units.py 共 20 项通过，含备份子目录已迁出 / 写卷目录不存在、角色优先级；真实 925 个分片留 T-26
- **上下文**：M2；备份根独立扫描，但分片按镜像路径归入原写卷单元。
- **依赖**：T-07
- **修改范围**：`units.py`、`rules.py` 的角色、`test_units.py`。
- **完成标准**：满足 AC-002-7，补齐 AC-002-2；区分原目录仍在、分段子目录已迁出、写卷目录也不存在的情况；对不上则自成单元并列异常；角色优先级按 plan §4.4，不靠创建目录或改原文件完成映射。
- **验证命令**：`python -I -X utf8 -m pytest -c catalog/pytest.ini catalog/tests/test_units.py`。

### T-09 影像身份、路径与缺失恢复（1.5 小时）

- **状态**：本机完成（2026-10-28）；首批影像用例 10 项通过，从扫描开始真实改名 / 移动 / 互换 / 原子覆盖 / 回收站还原；新增写卷计算证据见 T-10/T-11，数据库历史已由 T-17/T-18/T-24 补验通过
- **上下文**：M3；在每个根内先匹配文件标识，再按未被认领的位置延续。
- **依赖**：T-05
- **修改范围**：`identity.py`、`test_identity.py`。
- **完成标准**：满足 AC-003-1、AC-003-2、AC-003-3、AC-009-2、AC-009-3、AC-009-5 的影像部分；ID 不复用，改名 / 移动 / 互换随文件，覆盖记变化，缺失只标记，再出现恢复；从真实扫描结果计算，不加入内容指纹或 Q-025 规则。
- **验证命令**：`python -I -X utf8 -m pytest -c catalog/pytest.ini catalog/tests/test_identity.py`。

### T-10 写卷初建、主编号与多影像关联（2 小时）

- **状态**：本机计算完成（2026-10-28）；test_identity.py 共 35 项通过，含同号跨目录、多号共享、分件、无号 / 存疑不合并、新影像归属、整件缺失保留编号 / 线索；preserved_items 给后续导入器保留出处的依据，持久化保证已由 T-18/T-24 补验通过
- **上下文**：M3；实现 plan §4.2.3 D/E 中初建写卷的正常流程。
- **依赖**：T-06、T-08、T-09
- **修改范围**：`identity.py`、`test_identity.py`。
- **完成标准**：满足 AC-002-1、AC-002-4、AC-002-5、AC-002-8、AC-003-1、AC-003-6、AC-005-5；跨谱系同号归并，多编号共享影像，分件记母号，无号分别建卷；新文件归属按已有数量与 serial 判定；全部影像缺失的写卷保留编号、线索与出处。
- **验证命令**：`python -I -X utf8 -m pytest -c catalog/pytest.ini catalog/tests/test_identity.py`。

### T-11 编号变化、同号回退与顺序无关（2 小时）

- **状态**：本机计算完成（2026-10-28）；test_identity.py 共 35 项通过，含五种待确认情形及改回恢复、两件互换 / 三件轮换、增号 / 改号、同号迭代回退、改号后新增目录的归属；数据库端到端互换已在 T-24 实测通过
- **上下文**：M3；已有写卷始终保留 ID，不自动合并 / 拆分。
- **依赖**：T-10
- **修改范围**：`identity.py`、`test_identity.py`。
- **完成标准**：满足 AC-003-4、AC-003-5、AC-003-7、AC-003-8；按导入前 S0 同时计算 A～E；撞号逐步回退，互换 / 三件轮换不撞唯一约束，多编号增号 / 单号改写分别处理；待确认编号不关联到其他持有者；不为备份目录不同步改名增加规则。
- **验证命令**：`python -I -X utf8 -m pytest -c catalog/pytest.ini catalog/tests/test_identity.py`；数据库端到端互换另在 T-17/T-24 验证。

### T-12 谱系、许可与出处规则（2 小时）

- **状态**：本机规则完成（2026-10-28）；test_rules.py 32 项通过，含读失败不误判 BnF、目录混合、严格许可继承、署名来源、出处建议 / 冲突、人工结论保留及不变初值复用；落库保留已在 T-24 补验通过，真实材料基线仍待 T-26
- **上下文**：M4；规则有名称、版本与依据，不把触发者当作者。
- **依赖**：T-05、T-06、T-08
- **修改范围**：`rules.py`、`test_rules.py`。
- **完成标准**：满足 AC-005-2、AC-006-1、AC-006-2、AC-006-3、AC-007-1、AC-007-2、AC-007-3、AC-007-4；谱系逐文件判、目录只汇总直接 TIFF；读不了的不误判 BnF；本地合成取最严格许可；人工出处不覆盖；非敦煌只给建议。规则作者与确定 / 推断明确，为 AC-013-1、AC-013-2 提供依据。
- **验证命令**：`python -I -X utf8 -m pytest -c catalog/pytest.ini catalog/tests/test_rules.py`。

### T-13 国图清单与画布（1.5 小时）

- **状态**：本机完成（2026-10-28，Astra 子 agent P1）；test_nlc.py 36 项通过，主会话已复验；只读抽查确认画布从 0 起、strips 列表 / 整数两种结构。Pressmark 来源、大小写与异常、署名、TIFF / pages 画布映射均已覆盖；原附件落库已由 T-17/T-24 补验通过，NAS 真实全量对应率仍待 T-26
- **上下文**：M4；国图 JSON 是外部输入，在此处解析和校验。
- **依赖**：T-06
- **修改范围**：`nlc.py`、`test_nlc.py`。
- **完成标准**：满足 AC-004-3、AC-005-4，并为 AC-006-1 提供署名；Pressmark 优先，目录号冲突 / 不合规 / 缺清单分别处理；IDP 条目 ID 与画布保留；strips 非列表时按 TIFF 文件名序号回退；pages 序号对应画布；三份 JSON 的原始字节由 T-17 保存。
- **验证命令**：`python -I -X utf8 -m pytest -c catalog/pytest.ini catalog/tests/test_nlc.py`。

### T-14 派生记录白名单解析（1.5 小时）

- **状态**：本机完成（2026-10-28，Astra 子 agent P1）；test_derivation.py 35 项通过，主会话已复验；真实文件审计证明只读尝试打开 13 个白名单文件、不列目录。实际日志格式已只读抽查；来源、时间或替换证据不足均明确列异常，真实 12 个输出覆盖留 T-26
- **上下文**：M4；只打开 plan §4.5 的 13 个文件，不扫描 cache。
- **依赖**：T-08、T-12
- **修改范围**：`derivation.py`、`test_derivation.py`。
- **完成标准**：满足 AC-005-3、AC-012-2；按最后成功的拼接或 PSB 转换关联源影像，带日志文件与行号；读不了 / 缺失 / 不在记录中均给可读原因，不阻断导入；测试用合成日志和真实文件，记录该模块所有打开路径及无目录遍历。
- **验证命令**：`python -I -X utf8 -m pytest -c catalog/pytest.ini catalog/tests/test_derivation.py`。

### T-15 共用会话校验（1.5 小时）

- **状态**：本机完成（2026-10-28）；test_auth.py 14 项通过，含真实签名协议、过期 / 非法 cookie、删用户、管理员位、secret 缺失全请求 503、文档页与 OpenAPI 登录墙；认证本身已验，查询 / 触发路由及 DB 集成状态见 T-20/T-21
- **上下文**：M6；只验证 v0 会话，不创建账号或签发 cookie。
- **依赖**：T-01
- **修改范围**：`api.py` 的认证入口、`test_auth.py`。
- **完成标准**：满足 AC-011-1 的认证部分；正确验证 v0 的签名、过期时间、用户存在与管理员位；缺 secret 拒绝服务；用户表只在请求校验读取，不进入导入器；测试按 app.py 的签名协议生成外部 cookie，调用真实认证函数，不另写被测实现。v0 .env 的 secret 按 env_file 的常见写法读取首尾空白与成对引号，测试含带引号的配置。
- **验证命令**：`python -I -X utf8 -m pytest -c catalog/pytest.ini catalog/tests/test_auth.py`。HTTP 路由权限另由 T-21 验证。

### T-16 v0 快照、健康采样与链接（1.5 小时）

- **状态**：本机完成（2026-10-28）；test_v0.py 19 项通过，HTTP 边界用 MockTransport，验证索引有效 / 未就绪 / 失败 / 有效空快照、原会话传递与释放、健康采样 / 2 秒指标、链接与不给链接原因；未访问实际 v0，快照落库及覆盖报告已由 T-17/T-19/T-24 测试通过，真实 v0 覆盖仍待 T-26
- **上下文**：M4；v0 是外部 HTTP 边界，导入使用触发者原会话，结束丢弃。
- **依赖**：T-04、T-15
- **修改范围**：`v0.py`、`test_v0.py`。
- **完成标准**：满足 AC-001-1、AC-011-4，并支持 AC-012-3；索引失败 / 未 ready 不阻断；快照取最近有效的一份；链接只给快照内且仍在的 TIFF 目录，其他给原因；健康采样每 5 秒，超时 2 秒，输出次数 / 失败数 / 最大耗时；不恢复暂停 / 中止或会话剩余时长规则。
- **验证命令**：`python -I -X utf8 -m pytest -c catalog/pytest.ini catalog/tests/test_v0.py`（仅此 HTTP 边界用替身；链接编码与磁盘检查运行真实实现）。

### T-17 导入主流程与事务写入（2 小时）

- **状态**：实现与数据库集成验证完成（2026-10-28，P2/P3 实现，T-24 A2 实测）。test_import.py 53 项均通过（含 15 项真实 DB），完整回归 402 passed / 0 skipped；同步持锁准备、后台生命周期、单事务/失败回滚、有效快照独立提交、编号/路径互换、附件原字节与重导入均已运行真实 PostgreSQL 测试。真实全量材料覆盖仍留 T-26，独立 Review 尚未执行
- **上下文**：M5；主函数只串正常流程，调用前面各模块，不重新实现规则。
- **依赖**：T-03、T-11、T-12、T-13、T-14、T-16
- **修改范围**：`importer.py`、`test_import.py`。
- **完成标准**：满足 AC-001-3、AC-003-1、AC-003-7、AC-008-1、AC-008-2、AC-009-1；后台线程内持锁，快照单独提交，正式数据单事务；编号与路径互换先用临时值避开唯一约束；附件边读边写，保存最新原文；真实数据库验证失败回滚与成功保留；不加暂存表 / 后备份 / 任务队列。
- **验证命令**：T-24 中执行 `python -m pytest tests/test_import.py`。

### T-18 变化、字段依据与批次历史（2 小时）

- **状态**：实现与数据库集成验证完成（2026-10-28，T-24 A2）。保留人工结论、缺失/重现、编号回退、字段作者/依据、规则变化与按批次历史查询均随真实文件 + PostgreSQL 完整流水线通过；test_import.py 53 项及完整 402 项通过、0 跳过。不是 NAS 全量材料验收或人工标注功能完成
- **上下文**：M5；变化历史与 import_run 分开，能够按批次还原对象。
- **依赖**：T-17
- **修改范围**：`importer.py`、`test_import.py`。
- **完成标准**：满足 AC-007-4、AC-009-2、AC-009-3、AC-009-5、AC-013-1、AC-013-2、AC-013-3；保留人工认定，缺失不删写卷或编号，整件缺失不清空线索 / 出处；改文件与改规则产生可追溯快照，按任一批次取值及来源作者；不把修改和移动混在同一内容变化测试中。
- **验证命令**：T-24 中执行 `python -m pytest tests/test_import.py`。

### T-19 导入记录、报告与异常（1.5 小时）

- **状态**：实现与数据库集成验证完成（2026-10-28，T-24 A2）。18 类异常/计数、覆盖对照、访问审计、报告持久化及只读 report CLI 在真实 PostgreSQL 测试通过；P6 仅修 CLI 测试使用的连接夹具，未改生产代码或减断言。基线比较器已由 T-23 实现，真实 NAS 基线对照仍留 T-26
- **上下文**：M5；报告引用各模块产生的事实与异常，不另做一套判断。
- **依赖**：T-18
- **修改范围**：`importer.py`、`__main__.py` 的 report、`test_import.py`。
- **完成标准**：满足 AC-001-1、AC-001-4、AC-009-4、AC-010-1，并支持 AC-010-2；含统计、变更、异常、无关联附件、有效快照状态、健康采样及 derivation 统一打开函数实际访问的 cache 路径记录；18 类异常均能由合成数据触发；导入期间 cache 访问只有白名单、不含 users.json（AC-012-2）；report 只读导出已保存结果，无 CLI 导入入口。
- **验证命令**：T-24 中执行 `python -m pytest tests/test_import.py`，一次覆盖全部导入行为。

### T-20 只读查询与按批次历史（2 小时）

- **状态**：实现与数据库/API 集成验证完成（2026-10-28，T-24 A2）。test_api.py 15 项均实际通过（12 项 db），覆盖全部 GET、编号解析、筛选分页、附件原文、历史、v0 链接与无写路由；完整回归 402 passed / 0 skipped。全量数据的 NAS P95 与真实链接抽查仍待 T-26，未以合成数据代替
- **上下文**：M6；公开路径按 plan §2.1，统一认证与参数校验后查询数据库。
- **依赖**：T-15、T-19
- **修改范围**：`api.py`、`test_api.py`。
- **完成标准**：满足 AC-011-2、AC-011-3、AC-011-4、AC-011-5、AC-013-3；编号任一写法、不区分大小写，历史 / 待确认编号不查，母号加分件；筛选分页覆盖多影像目录；详情返回依据、关系、原文与路径；附件原字节取回；无目录修改接口。P95 留 T-26 测真实 NAS。
- **验证命令**：T-24 中执行 `python -m pytest tests/test_api.py`，TestClient 调真实路由和临时 PostgreSQL。

### T-21 管理员触发、导入状态与 OpenAPI（1 小时）

- **状态**：实现与数据库/API 集成验证完成（2026-10-28，T-24 A2）。同步持锁准备、真实后台线程、202/409、权限/认证、代码版本与迁移/只读 health 成败路径均通过真实 PostgreSQL + TestClient/子进程验证；两处 CLI 测试经 P6 最小修复后真实库通过。正式容器默认命令启动与运行冒烟仍留 T-25
- **上下文**：M6；使用已实现的后台导入与咨询锁，不引入任务系统。
- **依赖**：T-20
- **修改范围**：`api.py`、`__main__.py` 的 health、`test_api.py`。
- **完成标准**：满足 AC-011-1、AC-011-5，并支持 AC-009-4；管理员 POST 返回 202 / 运行中 409，普通用户仅可查询，匿名 / secret 缺失分别拒绝；导入记录与文档页受认证保护；health 为容器内命令，不借签发 cookie 绕过登录。
- **验证命令**：T-24 中执行 `python -m pytest tests/test_api.py`；CLI 健康命令由 T-25 验证。

### T-22 镜像与独立 compose 配置（1 小时）

- **状态**：运行文件实现、静态契约与隔离构建/合成 Compose 配置验证完成（2026-10-28，T-24 A1/A2）。两候选均以 legacy builder 的 512m=memswap 受限构建，实际 cgroup 探针通过；镜像含 src/migrations/tests/acceptance/pytest.ini，Python 3.12.15 全套 402 项通过，test_runtime.py 7 项实际通过，合成 .env 的 Compose config -q 通过。源码中四项 ro 挂载、外部 pgdata、无 DB 宿主端口、LAN/Tailscale 显式绑定符合设计。正式挂载/端口/默认启动的运行验证仍归 T-25，真实全量内存归 T-26；不能把测试容器证据冒充正式服务已部署
- **上下文**：M7；只写新服务运行文件，不操作 NAS 或 v0 compose。
- **依赖**：T-03、T-21
- **修改范围**：`catalog/Dockerfile`、`catalog/docker-compose.yml`、`catalog/.env.example`、`catalog/README.md`。
- **完成标准**：落实 AC-011-1、AC-012-1、AC-012-3 的部署前提与 D-018：Python 3.12；384m / 512m 硬上限且 memswap 相等；三数据根与 v0 .env 只读，pgdata 在工作区外；数据库无宿主端口，API 8504，文档注明不接入公网；.env.example 不含真实口令；镜像含 tests/、acceptance/、pytest.ini 与 pytest，供一次性测试容器直接执行。构建验证留 T-24，运行验证留 T-25。
- **验证命令**：本机 `git diff --check`；经许可后 T-24 以 `docker build` 构建候选快照（不需要正式 .env），不初始化正式 pgdata；compose 的配置校验留 T-25（正式 .env 就位后执行 `docker-compose -p dunhuang-catalog config -q`，不打印展开凭证）。

### T-23 基线对照、验收入口与本机回归（1.5 小时）

- **状态**：本机完成（2026-10-28，P5 Astra，主会话已独立复核）。34 项固定日期基线、标准库只读比较器、42 项比较测试及 README A1～A7 操作/证据入口已提供。支持 CLI 的 counts.counts、API 的 report.counts 和缺批次状态的直接报告；Q-024 六个 txt 保留差异，不改 477 基线；图块 JPG、母号查询结果、长卷逐条派生覆盖三项明确未验证，不以总数冒充对象级证据。主会话非 DB 回归 360 passed / 42 deselected / 1 条原有警告；显式包含 acceptance 的全套回归 360 passed / 42 db skipped / 1 条原有警告，比较测试单独运行 42 passed。v0 三文件编译、31 个 catalog Python 文件的 3.12 AST 语法、README 12 段 Bash/9 段 JavaScript/3 段 Python 语法、UTF-8 LF、文档一致性及差异空白检查通过；均非 NAS/浏览器/Compose/容器/SQL 运行证据。T-24 已于后续隔离实测完成；真实 A1～A7、T-25/T-26 仍未执行且待许可
- **上下文**：M7；用一份基线与现有 CLI 承载验收，避免多份统计规则和重复命令。
- **依赖**：T-19、T-22
- **修改范围**：`catalog/acceptance/baseline-2026-10-27.json`、`catalog/acceptance/compare.py`、`catalog/acceptance/test_compare.py`、`catalog/README.md`、`specs/catalog-foundation/tasks.md`。
- **完成标准**：为 AC-010-2、AC-011-3、AC-012-1、AC-012-2、AC-012-3、AC-012-4 提供 A1～A7 的可执行步骤与输出位置；基线包含全部核查数，Q-024 的新增附件不改旧基线；compare 只比较导入报告，不再扫描一遍计算业务结果；明确 NAS 许可、低峰与 >=2GB 可用内存的前提。跑一次全部本机测试，未执行的数据库 / NAS 项列待验。
- **验证命令**：`python -I -X utf8 -m pytest -c catalog/pytest.ini -m 'not db' catalog/tests catalog/acceptance/test_compare.py`；`python -m py_compile app.py pyramid_worker.py stitch_apply.py`；`git diff --check`。

### T-24 NAS 临时数据库与完整自动化测试（2 小时；需另获许可）

- **状态**：完成（2026-10-28，经用户批准，主会话在 NAS 独立执行并清理）。**A2：402 passed / 0 failed / 0 skipped / 1 条原有依赖警告，47.62 秒**；候选别名 `private-candidate-035`；快照/镜像校验值与隔离位置仅在非公开原件保全，不是当前公开产物哈希。Docker 24.0.2 / Compose v2.20.1-6047-g6817716，Python 3.12.15 / PostgreSQL 17.4；构建 512m=memswap，API 512m / DB 384m 且各自 memswap 相等，无宿主绑定材料/认证/pgdata、无发布端口，DB 仅匿名临时卷，合成配置 config -q 通过。API die 事件 exitCode=0、无 OOM 事件，DB OOM=false。A1 候选 `private-candidate-034` 为 400 passed / 2 failed / 0 skipped（47.10 秒），真实 cgroup 探针证实硬限额；两处 CLI 测试误用不含口令的 connection.info.dsn，由 P6 仅替换四行夹具/环境传值后在 A2 真库全通过，不改生产代码、不放宽认证、不减断言。两轮库/匿名卷/容器/网络/镜像标签/隔离目录/临时凭据均已清理，v0 容器 ID/启动时间/restart 数未变；未全局 prune、未起正式 Compose/未部署。证据在 [公开验证摘要](../../docs/verification.md)（详细原件非公开） 与 非公开 T24-A2 阶段记录，A2 commands.txt 记录实际受限构建/创建/启动/清理命令；归档文本按 manifest 自动规范化且口令脱敏。T-25/T-26、独立 Review 与 Gate 2 仍未执行
- **上下文**：M7；本机没有 PostgreSQL / Docker，在目标 Python 3.12 环境验证所有数据库与 HTTP 行为。
- **依赖**：T-23、用户测试许可；正式部署仍在 Review / Gate 2 / merge 后。测试前明确候选提交与 NAS 临时目录，以 `git archive <候选提交> catalog` 传入隔离位置；不推送 nas main、不启动正式 compose。
- **修改范围**：代码修复只在本机 `catalog/`；NAS 只接收候选快照并运行 plan §6.2 的一次性测试容器，不挂真实材料、正式 pgdata 或 v0 配置。数据库 `--rm`、384m = memswap；测试 API 容器 `--rm`、512m = memswap；无宿主数据库端口，共用临时 Docker 网络。
- **完成标准**：补齐 T-02、T-03、T-17～T-22 的数据库和镜像证据，验证 AC-003-7、AC-007-4、AC-008-2、AC-009-1、AC-009-2、AC-009-3、AC-009-4、AC-009-5、AC-011-1、AC-011-2、AC-011-3、AC-011-4、AC-011-5、AC-013-1、AC-013-2、AC-013-3；数据库来自一次性 PostgreSQL 容器，不使用正式 `catalog-db`；在其中建独立测试前缀的临时库，设置测试连接，跑完删库并删除容器 / 网络 / 快照。不得因缺测试库静默跳过 db 项后声称全通过。
- **验证命令**：实际采用 `DOCKER_BUILDKIT=0 /usr/local/bin/docker build --pull=false --memory 512m --memory-swap 512m --rm --force-rm --build-arg DH_CODE_VERSION=<候选完整SHA> -t <本轮独立测试标签> <隔离目录>/catalog`；一次性 PG 384m=memswap，测试容器 512m=memswap、--rm、无宿主绑定/端口，先 create 并 inspect 限额，再 start --attach 执行 `python -m pytest tests acceptance/test_compare.py`，完整命令与清理见 A2 commands.txt。退出码与 Docker die 事件均为 0，全部 42 个 db 项实际执行、0 跳过；不使用正式 .env、不执行 compose up。

### T-25 正式部署与只读冒烟（1 小时；需另获许可）

- **状态**：**部署前置与目录服务部署已执行（2026-10-30T20:25Z～20:34Z），登录态冒烟待用户执行；T-26未开始。** 用户批准A（推送方案文档、部署配置迁移、部署远端历史替换、守护循环重启、目录服务部署），并就Tailscale绑定另选A。方案经独立Analyze17（claude-bridge/claude-fable-5-1，19:17Z～19:24Z，exit0，需小修、无P0）修订后，Analyze18（19:26Z～19:30Z，exit0）复核通过；原报告非公开保全。执行结果见下方“执行记录”。

#### T-25 部署前置：部署远端首次同步与 v0 宿主配置迁移（2026-10-30 补充）

- **原因**：公开历史已重写；部署远端 main 仍是旧历史，不是新 main 的祖先，普通 `git push nas main` 会被拒。已部署 v0 的根 Compose、守护/开机脚本与 `stitch_apply.py` 使用旧的写死宿主路径；新版改为必须显式提供 `DH_HOST_*`、`DH_DEPLOY_DIR` 或 `DATA_DIR` / `CACHE_DIR`。若只同步代码、不迁移配置，仍在运行的旧守护循环会以缺环境的方式调用新 `stitch_apply.py` 而失败，拼接后也无法经根 Compose 拉起 `pyramid-huge`；下次开机，旧钩子副本也无法启动新守护循环。
- **v0 运行代码差异（本机只读比对）**：`app.py` 除注释外仅删去无调用的 `_stitch_wait_rescan`；根 Dockerfile 仅注释变化；`static/`、`pyramid_worker.py`、`requirements.txt` 未变；根 Compose 只有宿主挂载来源改为变量，取值与原路径相同即等价。三个脚本的可执行位不变。因此本前置不重建、不重启 v0 容器，也不对 `dunhuang-viewer` 执行 `up`。
- **只读前检**（任一不符即停）：低峰且宿主 MemAvailable≥2GB，图块生成器未运行；部署工作区 HEAD 等于本机私有记录的部署旧 OID；先用 `git check-ignore` 确认 `cache/`、`pyramids/`、`thumbs/` 在忽略规则内（否则不在部署目录运行 status，以免遍历 cache），再执行 `git status --porcelain`（不加 `--ignored`），要求没有已跟踪或索引改动，未跟踪路径与新树无冲突；部署仓库仍为 `receive.denyCurrentBranch=updateInstead` 且 `receive.denyNonFastForwards` 未开启（否则停止另议，不改仓库保护）；记录 v0 容器 ID、启动时间、重启次数与运行状态，记录旧守护进程 PID 与运行用户；部署 `.env` 只核键名、不读出值；目录服务 pgdata 目标在 git 工作区外且尚不存在。
- **私有备份**：部署 `.env` 与开机钩子副本复制到仓库外私有位置（权限 600），记录部署旧 OID；不入库。
- **配置迁移（必须先于历史替换）**：在部署 `.env` 追加 `DH_HOST_DATA_DIR`、`DH_HOST_CACHE_DIR`、`DH_HOST_STATIC_DIR`，取值与旧 Compose 的原路径逐字相同。追加后，以新版根 Compose 的临时副本（项目目录指向部署目录）运行 `config -q`，并在主机内只输出布尔值地确认三个服务插值后的挂载来源与旧路径一致；不打印展开配置（其中含 `env_file` 凭证）。两项通过后才替换历史。这三项同时进入 `dunhuang-viewer` 的 `env_file`，`app.py` 不读取；但 Compose 配置哈希会改变，下次对该服务 `up` 会重新创建容器（不重建镜像），仍须按 AGENTS 另获确认，本前置不执行。守护循环对 `pyramid-huge` 执行 `up` 时，若哈希不同只会用现有镜像重新创建该批处理容器，不影响查看器。开机钩子副本改为显式导出 `DH_DEPLOY_DIR`、`DH_HOST_DATA_DIR`、`DH_HOST_CACHE_DIR` 后调用部署目录的 `auto_huge_boot.sh "$1"`（透传 start/stop），不按自身位置推断。私有值只写在主机，不进入仓库或公开记录。
- **历史替换**：本机单 ref 推送 `git push --force-with-lease=refs/heads/main:<部署旧OID> nas refs/heads/main:refs/heads/main`，只替换部署远端 main；updateInstead 随之更新工作区。租约不符、远端拒绝或工作区更新失败即停，不裸 force、不刷新租约。旧历史留在部署仓库的私有对象/reflog，不回传 origin。
- **同步后验证**：部署工作区 HEAD 为获准 main，`git status --porcelain` 无已跟踪改动；根 Compose `config -q` 通过，挂载来源布尔比对再次一致；v0 容器 ID、启动时间、重启次数不变。
- **守护循环重启**：由容器管理角色执行。经更新后的钩子 `stop`，循环等待前检记录的旧 PID 消失后再 `start`；确认只有一个守护进程、PID 不同于旧 PID、运行用户与原来相同；钩子 `start` 须返回 0，新 PID 出现并持续存在（缺环境时脚本在动作前以非 0 退出，其 stderr 不进入日志）；至少等待一轮（20 秒以上）后，`auto_huge.log` 新增行不得出现 `must be configured`。若当时 deferred 队列非空，新循环按既有行为拉起 `pyramid-huge`（旧循环本也如此），不顺带启动全量生成器。旧拼接通道下线仍归 PD-07 / `stitch-hardening`，本前置不改变其生命周期。
- **回滚**：先经更新后的钩子 `stop` 新守护循环并确认 PID 消失；以新 main OID 为租约推回部署旧 OID（要求部署工作区同样干净；若已创建 `catalog/.env`，它在旧树下是未跟踪文件，不阻止推送，去留写入私有记录）；恢复备份的钩子副本与 `.env`，按旧钩子启动旧守护循环并做同样检查。v0 容器始终不动。回滚窗口内，本机与部署仓库均不运行 `gc`、`prune` 或 `remote prune`。
- **停止条件**：HEAD 与旧 OID 不符、存在已跟踪改动或路径冲突、仓库接收配置不符、内存不足或生成器运行、`config -q` 或挂载比对失败、租约不符或推送被拒、v0 容器 ID/启动时间/重启次数变化、旧守护 PID 未消失、重启后任一确认项不符（钩子返回 0、单进程、PID 变化、运行用户相同）、新循环日志出现上述错误。任一触发即停，按回滚处理已完成的步骤。
- **完成标准**：部署远端与工作区为获准 main；v0 未重建、未重启且挂载来源不变；新守护循环正常运行；私有值只在主机与私有备份。之后才进入下述 T-25 目录服务步骤。

#### T-25 执行记录（2026-10-30，脱敏摘要；原始输出非公开保全）

- **前检**：首轮发现两项不符并停止、未做任何更改：数据库专用目录的上级目录尚未建立（属第5步新建范围，原检查过严）；NAS 的 Tailscale 以用户态网络模式运行，Tailscale 地址不在任何网卡上、无法绑定。用户就后者选择以 `127.0.0.1` 作为 `CATALOG_TAILSCALE_IP`（用户态 tailscaled 把连入 Tailscale 地址的连接转发到本机回环），代码不改。修正后重检全部通过：部署远端与工作区为私有记录的旧 OID、工作区与索引干净且无路径冲突（缓存等目录先经 `git check-ignore` 确认被忽略）、接收配置为 updateInstead 且允许非快进、内存门槛满足、图块生成器未运行、v0 运行中、恰有一个旧守护进程、钩子副本与旧版脚本逐字相同、局域网地址与回环可用、8504 端口空闲、无既有目录服务容器与镜像。
- **配置迁移**：部署 `.env` 与钩子副本已私下备份（仓库外、仅 root 可读）；`.env` 追加三项宿主路径（与旧 Compose 原路径逐字相同），权限仍为 600。推送前以新版根 Compose 临时副本校验：`config -q` 通过，三个服务的挂载来源与旧路径一致。钩子副本改为显式导出三项后调用部署目录脚本并透传参数，权限、属主、inode 不变，语法检查通过。
- **历史替换**：租约再核一致后单 ref 精确租约推送成功；部署远端与工作区均为获准 main（`abfd5ff92b15`），工作区干净，旧私有归档已移出工作区。部署后根 Compose 校验与挂载比对再次一致，v0 容器标识、启动时间、重启次数不变。
- **守护循环重启**：经新钩子 stop 后旧 PID 消失，start 返回 0；恰一个新守护进程、PID 不同于旧值且持续存在、运行用户相同；新日志无配置错误。推送到重启之间，旧循环调用新 `stitch_apply.py` 留下 1 行缺配置报错，此后不再出现。
- **目录服务**：专用数据库目录新建于工作区外；所在共享文件夹带 Synology ACL，新目录先 `chmod 700` 转为 Linux 权限模式，再交 PostgreSQL 初始化。`catalog/.env` 由部署文件属主创建，权限 600，被 git 忽略，口令只在主机生成、未打印。`config -q` 通过；以 legacy builder 按 512m=memswap 受限构建（同日 T-39 已在同一主机实证构建限额生效）；`up -d --no-build` 后两容器均 healthy，`python -m dh_catalog health` 通过。限额 API 512m、DB 384m 且各自 memswap 相等；API 恰有4项只读挂载、DB 只挂专用数据目录；API 只绑定局域网地址与回环的 8504，DB 无宿主端口；均运行中、无 OOM、重启次数 0。正式依赖清单 29 项，与 T-39 逐项相同。
- **匿名冒烟**：经局域网、回环及工作站经 Tailscale 访问 `/api/v1/items` 均得 401，`/api/v1/docs` 亦为 401。v0 状态前后一致，图块生成器未启动，守护进程 PID 自重启后不变。
- **执行中的操作性更正**：以 root 在部署仓库运行 git 被 safe.directory 拒绝，部署 HEAD 改由文件属主核对一致；脚本内 `docker-compose exec` 吞掉后续输入，致首次漏跑若干只读核查，改将其标准输入接 `/dev/null` 后补跑通过。均未影响任何写操作。
- **未完成/待验**：登录态冒烟（普通账号 GET、POST 导入 403、管理员 GET）须用户在浏览器完成；T-26 真实导入与资源、性能、v0 连续健康验收未开始。私有备份保留于主机以备回滚，可在确认稳定后另行清理。

#### T-25 目录服务部署
- **上下文**：M7；正式部署前必须通过独立 Review、Gate 2，并 merge 到 main；这是运行验收，不提前绕过交付闸门。
- **依赖**：T-24、Review / Gate 2 / merge、用户部署许可、NAS 可用内存 >=2GB
- **修改范围**：不改 v0；仅部署已合并的目录服务。若需修代码，回本机任务并重新评审，不在 NAS 工作区编辑。
- **完成标准**：核实 AC-011-1、AC-011-5、AC-012-1 的运行前提：项目独立、只读挂载、硬内存限额、数据库无宿主端口，未登录请求拒绝、普通用户不能 POST、管理员 GET 通过；不重建或重启 v0。secret 缺失拒绝服务与合成导入以 T-24 的测试结果为证，不在正式服务删 secret 或触发导入；正式首次导入留 T-26。
- **目录服务配置补充**：`catalog/.env` 的 `DH_RECORD_DATA_ROOT` / `DH_RECORD_BACKUP_ROOT` 填旧执行记录中实际出现的宿主前缀（私有），否则旧合并长卷的派生记录会作为未配置的绝对路径进入异常；`DH_HOST_PGDATA_DIR` 为新建的专用目录。数据库口令为新生成的 URL 安全随机值，只写权限 600 的 `catalog/.env`。
- **冒烟分工**：匿名 GET 被拒可由主会话验证；普通账号 GET 通过、POST 导入被 403 拒绝、管理员 GET 通过，须由用户在浏览器以真实登录会话执行；主会话不另签 cookie、不读 users.json。若 v0 只有管理员账号，普通账号项依赖用户先在 v0 `/admin` 新增，否则该项记为待验。
- **正式依赖记录**：按 Gate2 待验项，在正式 `catalog-api` 容器内执行 `python -m pip freeze`，与 T-39 的 29 项逐项比对并写入本任务。
- **验证命令**：按 `catalog/README.md` 的获准部署步骤，`git push origin main` 后，首次同步按上述部署前置以精确租约替换部署远端 main，此后恢复普通 `git push nas main`；只启动 `dunhuang-catalog`。`python -m dh_catalog health`、`docker inspect` 核对挂载与限额；只读核验权限与导入记录接口，不执行管理员 POST 导入。

### T-26 全量导入与 A1～A7 验收（2 小时；需另获许可）

- **状态**：待用户许可，未开始
- **上下文**：M7；真实材料、性能与 v0 连续健康只能在部署后证明。用户触发正式导入，不由 agent 代签会话。
- **依赖**：T-25、用户验收许可与低峰时段
- **修改范围**：`specs/catalog-foundation/tasks.md` 的证据；缺口先记任务，不改基线凑数。
- **完成标准**：满足 AC-001-1、AC-001-2、AC-002-1、AC-002-2、AC-002-3、AC-002-4、AC-002-5、AC-002-7、AC-002-8、AC-005-2、AC-005-3、AC-005-4、AC-006-3、AC-007-3、AC-010-2、AC-011-2、AC-011-3、AC-011-4、AC-012-1、AC-012-2、AC-012-3、AC-012-4；按 plan §6.3 A1～A7 执行，差异逐项解释；全量 <=1小时，无变化重跑 <=10分钟，API 各100次 P95 <=1秒；原图 / 备份变化归因，cache 只核对访问记录和只读挂载，不遍历缓存；20个链接抽查无错卷。
- **验证命令**：按 `catalog/README.md` 的 A1～A7，用户在 OpenAPI 触发全量和重跑；agent 只读取导入报告、基线对照、只读挂载与资源采样、性能与链接检查结果。把每项实际输出摘要写回本任务，异常不掩盖；任何代码修复都须新提交并重新 Converge / Review → Gate 2 → merge → 部署，不在 NAS 直接修代码。

### T-27 Converge C1：JPEG 头安全异常不中断整批（0.5 小时）

- **状态**：完成（2026-10-29，P7 Astra修复，主会话独立复验）。原631字节合成JPEG声明20000×20000导致具体安全异常逃逸；P7只在read_facts增加Image.DecompressionBombError，新增两条真实文件/compute_import/build_report回归，不关闭保护、不解码或宽泛吞异常。本机362 passed/42 db skipped/1原有警告；**T-24 A3新候选 `private-candidate-038`，Python3.12.15/PG17.4完整404 passed / 0 failed / 0 skipped / 1 warning，48.27秒**。镜像与快照原校验值非公开保全，不冒充当前公开产物哈希；构建512m=memswap，API512m/DB384m各自swap相等，无真实挂载/端口，Compose合成config -q通过，API实际cgroup memory=memsw=536870912，exitCode=0/无OOM。库/容器/匿名卷/网络/镜像/隔离目录及临时凭据全清理，v0 ID/启动时间/restarts未变。证据在 [公开验证摘要](../../docs/verification.md)（详细原件非公开）；旧402保留历史，不当新版本证据。
- **上下文/依赖**：T-24 后 Converge，修复既有 AC-005-1/AC-010-1，不新增需求或恢复 Q-025 规则；不依赖 T-25/T-26，不部署。
- **修改范围**：仅 `catalog/src/dh_catalog/scan.py`、`catalog/tests/test_scan.py`、`catalog/tests/test_import.py`。
- **完成标准**：保留 Pillow 的安全限制，不设置 MAX_IMAGE_PIXELS=None、不关闭保护、不做像素解码或宽泛吞异常；在文件读取边界按具体库异常返回显式缺失事实与读错误。真实合成文件验证 R-005 要求的失败后继续、下次重读与有效头恢复；通过 compute_import/build_report 证明其他材料仍导入并产生对应异常。不得复制生产规则进测试或 mock 文件头解析。
- **验证命令**：本机 `catalog/.venv/Scripts/python.exe -I -X utf8 -m pytest -c catalog/pytest.ini catalog/tests/test_scan.py catalog/tests/test_import.py`；随后显式包含 acceptance 的完整回归、AST/UTF-8 LF/差异检查；因生产读取代码变化，形成新候选重跑已获准范围内的 T-24 隔离全套，旧 402 不能替代。

### T-28 Review CR1-01：全量内存预算与依据复用（1～2小时，R2代码级关闭，真实材料仍待验）

- **最新状态：Plan10 A+C/T36足规模合成完成，独立R2代码级关闭；真实材料资源与连续健康仍T26/Gate2待验**。以下为T28首轮/A4历史：P8单次独立依据池4096叶/512文本、规则冻结缓存128项含版本，不改JSON/schema/规则；主会话Win3.14同探针2k首轮71.13/重导78.29MiB、6k101.30/125.14MiB，明显改善但仅DTO路径。新候选private-candidate-042在NAS完整412 passed/0 skipped/1原有警告（46.08秒）。真实PG prepare/execute两次，2k RSS94.72/109.96MiB、6k133.24/175.71MiB；第二次事实全复用、ID/basis/history不变。两点36k约668.83MiB仅趋势，**未运行36k、未发生OOM、不宣布P1关闭**。6k S0独立加载前78.94/后143.17MiB；见 [公开验证摘要](../../docs/verification.md)（详细原件非公开）。用户现已批准T31的小幅读取设计修订，先核对plan9再实施，不自行送R2/缩列/扩限。旧R1测量仍原样保留在review与原文。
- **上下文/依赖**：T-24 A3/T-27与独立Review；满足既有AC-012-3/AC-012-4，不新增需求、不放宽D-005/D-018。
- **派发范围**：P8仅 `catalog/src/dh_catalog/importer.py`、必要的 `rules.py`（规则依据对象复用，不改规则值）、`catalog/tests/test_import.py`、必要的 `test_rules.py` / `test_api.py`；不得改依赖、schema、配置、冻结规格或其他模块。只读依据/规则作者/时间对象复用，覆盖真实DB加载后的重复依据；保持所有字段与持久化JSON/历史/规则版本/事务语义不变。预计50～120行实现及相应回归（估计），不得全局无界缓存或共享后就地修改、不得跨批次/版本污染。若最小共享不足则停止讨论/先更新plan，不偷偷改流式架构/缩列丢历史或提高限额。
- **完成标准**：先建立可重复的同规模内存基线，对首轮与真实S0加载后重导分别复测；在目标Python3.12/真实临时PG/512m=memswap环境验证足够预算与行为等价。不能只用共享DTO结果代替DB反序列化路径；不能仅用小规模线性外推宣称全量达标。全部原回归与字段历史正确。
- **验证命令**：现有完整pytest（显式acceptance）+已归档外部两点探针；新候选目标环境受限复验/规模探针由主会话在批准范围内执行，具体规模/输出随实测记录，不预填新通过数。禁止真实材料/正式挂载/部署，随后Review-R2。

### T-29 Review CR1-02：撤销候选号不冒充曾用号（0.5小时，R2关闭）

- **状态/依赖：实现与真库回归完成，独立R2关闭**。P8撤销pending删除当前identifier行，过去history快照保留；真正current旧号仍历史化。新候选private-candidate-042在NAS 412全套/43 db项实际通过，含PG/API当前与过去批次断言；没有新状态、不代R2签通过。
- **修改范围**：`importer.py`、`test_import.py`，必要的API断言在 `test_api.py`；不新增withdrawn状态/表/接口改变既有设计。
- **完成标准**：满足R-004/AC-011-2/AC-013-3；已撤销pending不出现在当前详情的曾用号中，但过去批次history快照保留其待确认值/来源/时间。可优先删除已撤销候选的当前表行并保留不可变历史，不删除真实曾用号、不改变resolve只current的语义。真库补测撞号→改回→当前与历史两端。
- **验证命令**：完整 `test_import.py` / `test_api.py` 与完整pytest、目标临时PG复验；不mock/跳过或减少旧断言。

### T-30 Review CR1-05：同号回退说明列参与写卷（0.5小时，R2关闭）

- **状态/依赖：实现与整合回归完成，独立R2关闭**。P9只在现有说明增本轮全部参与ID并排序，算法不变；两件/三件/原持有者/级联/反向处理覆盖。主会话本机38项、NAS新候选412全套中的38项identity均通过；不代R2关闭。
- **修改范围**：`identity.py`、`test_identity.py`；只在现有待确认说明中加入参与写卷ID及稳定排序，不加新状态/表/API字段，不改变算法。
- **完成标准**：满足AC-003-5/AC-010-1及plan §4.2.3 C；两件/多件同号及级联回退可定位参与者，身份/主号/归并结果与顺序无关性不变。
- **验证命令**：完整 `test_identity.py` 与全套回归；与其他修复集成后新候选真库复验与独立Review-R2。

### T-31 S0有界服务端游标与真库生命周期回归（1.5小时，P10实现/真PG完成，已纳入R2软件通过）

- **状态/上下文**：P10仅两文件实现/本机就绪（2026-10-29），生产loader+26/-9、测试+223；主会话完整369 passed/54 skipped/1原有警告，423项（51无DB/3Linux协议trace）。随后T32候选private-candidate-047在目标3.12/PG全423 passed/0 skipped/1原有警告，54个db项均实际执行，协议多批/两种事务/两种异常路径通过；跳过不算通过。资源目标仍未达成、待独立R2。R1 P1/T28第一版最小共享后仍缺512MiB余量，用户回复「同意」小幅S0读取修订；plan9的独立Checklist12为10通过/0不通过/2本轮不评，无阻断后拆Tasks；Analyze13在private-candidate-045全12项通过允许实施（12:00:38～12:09:43，Anthropic Claude、exit0）。本任务只实现plan §4.1.1，估时不含模型等待/目标环境；旧412不是本版证据。
- **依赖**：Checklist12及独立Analyze13已完成，后者12项全通过，P10 Astra已结束并主会话本机复验，T32可开始。T28整体资源目标继续打开。T31代码/本机集成通过即可标实现就绪进入T32，真库结论由T32补齐；不以T31须先真库通过形成循环。
- **修改范围**：独立Astra仅 `catalog/src/dh_catalog/importer.py` 的load_catalog_state及复用游标上下文、`catalog/tests/test_import.py`。不改db.py/autocommit/row_factory、rules/编号归并/事务编排、schema/依赖/配置/v0；主会话负责集成与记录。
- **完成标准**：支持AC-012-3/AC-012-4并保持AC-003-1/AC-008-1/AC-009-3/AC-013-1/AC-013-3。六查询原列/过滤/顺序完整，命名ServerCursor itersize=128、不fetchall/list、不WITH HOLD；每查询显式关闭。loader内transaction在外事务仅保存点，无外事务则短读事务；返回S0全量/值类型/编号顺序、依据/历史不变，沿用只读叶池，无额外cache/校验机制。不得逐批commit/新连接、当空S0吞异常/缩列/流式全流水线/扩限；达不到预算再停。
- **真实验证**：按plan §5四个固定测试名覆盖≥257影像及六种S0集合与普通SELECT逐字段等价；Linux临时psycopg协议trace确认实际FETCH上界/多批（正常路径可CLOSE），trace关闭删除不归档，不mock连接/业务。autocommit直调、外事务两路径同连接pg_cursors无残留；双连接验证加载后外事务未提前提交、rollback后无新持久化。真实DDL改名引发加载SQL失败时保存点rollback后游标清空/外事务可用，无需错误路径CLOSE；必要行处理异常用真实测试行JSON null触发已有异常，验证正常事务下显式关闭，不新增生产防御规则。保留现有正式导入失败/锁归还/历史等价全部断言。
- **验证命令**：本机 `catalog/.venv/Scripts/python.exe -B -I -X utf8 -m pytest -p no:cacheprovider -c catalog/pytest.ini catalog/tests/test_import.py`，再显式完整 `catalog/tests catalog/acceptance/test_compare.py`；db skip不计通过，3.12 AST不计运行。T32在临时PG执行 `python -m pytest tests acceptance/test_compare.py`，含全部新db项，不模糊-k/删旧断言/屏蔽警告。真实文件UTF-8 LF/无BOM、`git diff --check`。派发与结束真实模型/meta/测试数实施后记录。

### T-32 T31新候选受限规模复验与P1证据（1～2小时，已获准，依赖T31）

- **状态/上下文：有限验证与清理已执行，36k/P1目标未完成，已停止**。新候选private-candidate-047完整423通过/0跳过/1原有警告（59.66秒）；same2k/6k重导RSS102.37/153.01MiB，varied6k160.58，实际btrfs。两种36k投影532.82/586.54MiB未过预先480条件，未运行36k/未OOM、未继续修架构/未R2。原S0探针峰值143.17→109.02MiB、持久化文本大小不变；没有完整对象/阶段归因。所有本轮资源/凭据清理，v0 ID/启动/restarts未变；证据 [公开验证摘要](../../docs/verification.md)（详细原件非公开）。仅已批准的合成隔离测试，不是T25部署/T26真实验收；主会话执行操作/诊断，不由主会话写业务修复。需要新候选完整SHA和T31本机集成通过；不沿用A4通过数。
- **修改范围**：仅任务/收敛/评审/交接状态及 `handoff/` 本轮脱敏证据，外部标准操作探针；任何业务修复派回独立Astra且保持T31范围。用新批次路径/标签，不覆盖A4原件；不改spec/plan/checklist或运行配置。
- **完成标准**：AC-012-3/AC-012-4的软件资源证据及AC-003-1/AC-013-3等价。512m=memswap构建/API、384m=memswap PG，无真实材料/v0/正式pgdata挂载，无宿主端口/正式Compose，MemAvailable≥2GB且低峰。完整目标3.12/PG所有db项实际执行；A4同口径S0-only原探针与2k/6k真实prepare/execute二次加载对比，另做差异化TIFF头维度/事实摘要检查；放大操作安全条件先固定：同质2k/6k重导RSS两点投影36k≤480MiB（给512留32MiB，只用于是否尝试合成规模、不新增产品AC），差异6k按其基线线性投影也≤480MiB，才跑约36k首轮/真实库重导；否则停止讨论，不宣称已发生全量失败。所有值/ID/basis/事实摘要/history/计数稳定，进程RSS/cgroup/退出/失败/OOM明确留证，临时文件位于容器磁盘非tmpfs；不以两点外推当通过、不保证cursor足够，仍不足则停止讨论设计。
- **验证命令/证据**：沿T24已批准git archive候选/受限docker build与一次性PG/API命令；完整pytest显式acceptance。保持非公开原 S0 读取探针不变；下列仅记录当时验证口径，不是新的公开工具入口；规模操作探针 `T31-pg-scale-probe.py <2000|6000|36000> <same|varied>` 仅在受限临时容器/新 `dh_catalog_test_*` 数据库，第二次重新加载S0而非DTO。源/归档哈希、实际完整命令/资源/结果与清理保存本轮新目录，不提交tar/.env/口令/trace/raw；删除所有本轮资源/凭据、v0状态前后不变。目标证据形成后Claude独立Review-R2；设计通过/测试绿均不代实现审核或Gate2。

### T-33 受限阶段/对象内存归因与方案对比（1～2小时，诊断返回，仅建议、未实施新设计）

- **许可/状态**：用户回复「同意，继续」，批准诊断与方案评估，不批准业务修复/新设计实施。T28/P1保持打开；不改冻结spec/plan9/checklist/生产代码/依赖/schema/v0，不全量或放大，不R2冲通过。开始前无资源或运行agent；现诊断已返回并清理。P11只读Astra于16:49:47～16:56:08自然exit0，无写入；主会话NAS原private-candidate-047仅≤6k新数据对照/阶段/对象图，源码未改。对照160.48MiB、阶段160.99，observer耗时3.63倍/图seen约33MiB显式列出。联合业务图71.677MiB、四类image双状态外层25.269MiB、循环独占4.108；子集与容量上界不代RSS收益。报告memory-diagnosis.md，原文/测量在[公开验证摘要](../../docs/verification.md)（原件非公开）与logs/T33-A1；八API/PG/卷/网络/镜像/快照/.env/raw清理，v0状态不变。独立Anthropic Claude诊断校读17:52:47～18:07:10自然exit0，认为补GC回收时点可变及A容量余量薄后可交用户方向选择，原文/哈希在review/T33-diagnostic-check-R1；主会话已补，未改审核原文/业务/冻结计划。A为主/C独立小任务建议待选择，公开内部容器契约/分层停止与无hook测量约束，这是T33结束时状态；本轮用户回复「好的」，已同意A为主/C独立拆项进入Plan10设计核对后Astra实施/受限复验。当前仅Plan10草案待独立Checklist，之后才正式拆本版实施任务/Analyze，尚未新业务代码/CodeReview-R2。
- **范围/方法**：主会话操作外部标准库诊断探针，在现有512m=memswap API/构建、384m=memswap PG合成隔离边界、MemAvailable≥2GB低峰内工作。最多6k合成影像，以真实生产prepare/execute两次/真PG S0加载为基础，只有HTTP外替身。对照无插桩/轻量阶段采样/单点对象图计量，阶段区分S0、扫描/单元/事实、身份、行构造、持久化/报告；不替换业务函数或调整GC/结果/事务。对象计量用标准sys.getsizeof和按id去重的可达数据图，不遍历模块/全局环境、不输出数据/凭据；显式标示共享去重、顺序相关归属、未计C分配和分析器自身额外RSS/时间，诊断峰值不当作生产峰值。若资源不足只减诊断规模、不扩限/外移计算。
- **并行只读分析**：可由独立Astra只读分析现有数据流/对象生命周期和候选范围（不是实现/独立代码Review、不改文件、不连NAS），与主会话实测交叉核对；任何方案数字区分测量/上界/估计。
- **完成标准**：服务既有AC-012-3/AC-012-4，保持AC-003-1/AC-013-1/AC-013-3；核验二次导入ID/JSON/事实/history不变、阶段和对象证据/开销/限制可复核。比较压紧内部只读状态、减少S0/当前结果双份驻留（及若证据支持的更小生命周期改法），给代码触及面/复杂度/可预期收益与必要验证，不许凭估计声明512MiB达标。报告建议后由用户决定，任何新设计先Plan/Analyze再Astra。
- **验证/证据与清理**：在新批次候选快照构建原代码，原T31材生成器不改以保持可比。全新dh_catalog_test_*临时库/容器，无真实材料/v0/正式pgdata绑定、无宿主端口/正式Compose/global prune；对照和插桩分进程/新库，标准JSONL留源哈希、方法及资源/清理。所有本轮库/容器/卷/网络/镜像/快照/凭据删除，v0状态前后核对；不提交env/tar/trace/private raw。不重新计算全量或将本轮诊断冒充423测试的新实现证据。

### T-34 C：移除影像策略解析自环（0.5～1小时，P12实现/目标回归完成，R2软件通过）

- **上下文/状态**：T33明确普通路径存在局部递归policy自捕获，独占4.108MiB/6k且自然GC回收点变化；用户现同意C独立拆项、A为主。Checklist14为10通过/2新Tasks待补评、无阻断可拆任务，随后独立Analyze15在private-candidate-053全12项通过（21:56:02～22:08:52，Anthropic Claude，exit0）允许仅T34～36实施，P12已实现/主会话本机375 passed/54 skipped/1原有警告、429项；新6个许可/无环/异常生命周期用例通过。真PG/目标3.12/资源待T36；目标支持AC-012-3/AC-012-4，保持AC-005-2/AC-005-3/AC-006-1/AC-006-2/AC-013-1。
- **依赖/分工**：独立Analyze15已全项通过，Astra P12于22:13:07～22:18:27 （原始时刻；时区非公开） exit0，仅两文件，主会话全本机复验通过；与T35共享importer/test_import，必须先C后A串行。C仅本机/代码就绪即可进入T35，真库由T36补齐，C不能独立关闭P1。
- **修改范围**：仅`catalog/src/dh_catalog/importer.py`的策略解析/调用和`catalog/tests/test_import.py`，不动rules/derivation/身份/编排/SQL/依赖/配置/v0，不强制GC/调GC或新增恢复机制。短小私有解析器无自捕获/不缓存自身bound method、实例可弱引用，不用方法lru_cache/cached_property钉住self。
- **完成标准/真实测试**：按plan§4.1.3保留源先于输出、memo命中、本批来源、最严格许可/署名等全部值；普通NLC/BnF/真实执行记录的派生源继承均测试。固定`test_image_policy_lifetime_without_gc`沿sys.setprofile实际返回事件登记weakref（不保frame/f_locals、不替换业务），在下一阶段实际进入时确认解析器无环释放；小测试期间可gc.disable并finally恢复原状态，防旧环被自然GC假绿，生产及资源探针不变。异常traceback持帧不误断必释放，保留所有失败回滚/历史/许可断言。
- **验证命令**：本机完整`catalog/.venv/Scripts/python.exe -B -I -X utf8 -m pytest -p no:cacheprovider -c catalog/pytest.ini catalog/tests/test_import.py`，再完整`catalog/tests catalog/acceptance/test_compare.py`；无DB如实skip不计通过，AST3.12/UTF8LF/原警告保留/限定diff检查。后T36真实PG全套。

### T-35 A：影像四类紧凑映射及JSON边界（2小时，P13实现/目标回归完成，R2软件通过）

- **上下文/依赖**：P13已在private-candidate-055上完成四文件/本机就绪（22:21:58～22:30:05，openai/gpt-6-astra、exit0），新12紧凑单测+1PG历史测试；主会话完整387 passed/55 skipped/1原有警告，442项（52无DB/3Linux）。C/旧语义与prepare/cursor AST保留，UTF8LF/3.12 AST/diff通过；真PG/目标运行及预算待T36，skip不计通过。T33测得两状态四类外层25.269MiB/6k；按plan10§4.1.2完整key形状/值tuple减少每行hash索引，不把理想17.58MiB当RSS收益。T34本机就绪且新Analyze全项通过后Astra P13实施，不能覆盖C；完成代码/本机集成即就绪进入T36，真库由T36补齐，无依赖环。
- **修改范围**：新增`catalog/src/dh_catalog/_compact.py`、`catalog/tests/test_compact.py`；修改`catalog/src/dh_catalog/importer.py`、`catalog/tests/test_import.py`，必要只在`catalog/tests/test_api.py`补API JSON断言。不改api.py/db.py/scan/rules/identity/derivation/schema/依赖/运行配置/v0/冻结spec/plan/checklist。200～400行生产/测试另计为估计，若需扩到B/其他行族先停，不偷偷扩大。
- **完成标准**：支持AC-012-3/AC-012-4，保持AC-003-1/AC-003-2/AC-003-7/AC-005-1/AC-007-4/AC-008-1/AC-009-2/AC-009-3/AC-009-5/AC-013-1/AC-013-2/AC-013-3及API外部JSON。只image S0/当前行、facts、field_basis、fact basis外层只读，其他可写行不冻；Mapping.slots保存shape和values tuple，shape是所有keys精确顺序与index，每loader/compute有界64种，不硬编码/缩字段，淘汰不影响旧映射，池不自循环/跨批污染。loader逐行/compute每影像builder完成后立即压紧，missing分支同样；UUID行索引仍dict，叶/JSON list/数值类型/来源版本批次时间/原文完整，无全表展开副本。
- **消费者/序列化清单**：按plan表逐项核_file_entry/_image_state、_read_images、_basis、_image_rows present/missing、_item_rows读policy、_release_unique_values、_upsert、_snapshot、_persist_history、build_report。只item.updated_run/identifier.id/is_primary等继续可写。统一私有JSON default/dumps支持Mapping/UUID/path/datetime/dataclass，_upsert按Mapping/list显式Jsonb dumps或局部展开，history独立field_basis也适配；identifier dict判定可保持、不全局set_json_dumps、不default=str吞未知类型、不改JSONB/schema/事务/锁。核全部Jsonb入口无漏。
- **公开测试契约**：原共享测试物理改文件与另一影像/S0隔离语义保留；外层直接赋值改TypeError及显式新副本赋值不污染。旧规则版本模拟用独立S0的逐层dict builder，不改冻结输出；L317/L329/L807等内部JSON比较用_json_value再JSON，不repr。所有旧文件/ID/历史/数值/list/作者断言不删。新`test_compact.py`最少覆盖完整/额外/缺失keys、同keys不同序形状、64淘汰后旧值、get/iter/items/contains/dict及dict双向/嵌套相等、赋值/删除TypeError、叶list保持、嵌套Map+UUID/time/path JSON精确与未知对象TypeError、无新cache自环（池可weakref，测试可暂禁循环GC/del pool确认即释放并finally恢复）。补absent键KeyError/get默认身份/contains，以及压紧已Compact嵌套值直接沿用的幂等；不额外复制missing旧facts。PG固定`test_compact_images_keep_history_and_json`核六集合/字段/真实增改缺失与历史JSON；完整API当前/历史旧断言仍执行，必要补测不改路由。
- **验证命令**：完整`catalog/.venv/Scripts/python.exe -B -I -X utf8 -m pytest -p no:cacheprovider -c catalog/pytest.ini catalog/tests/test_compact.py catalog/tests/test_import.py catalog/tests/test_api.py`，再完整`catalog/tests catalog/acceptance/test_compare.py`；无DH_TEST_DATABASE_URL时skip不算PG过，拒用DH_DATABASE_URL。实际3.12/PG所有db在T36，原警告不升级/屏蔽；UTF8LF/3.12 AST与git diff--check仅静态证据，模型/范围/真实结果实施后记。

### T-36 A+C新候选目标回归/受限规模与独立R2入口（1～2小时，受限验证/清理完成，R2软件通过，Gate2未批）

- **状态/上下文**：已完成本轮获准受限验证/清理，候选private-candidate-056：NAS3.12.15/PG17.4完整442 passed/0 skipped/1原有警告、64.37秒，55db实际；same2k/6k与varied6k投影423.4141/465.3008均≤480后，36k varied实测首轮RSS341.98MiB/343.115秒、真PG重导435.05MiB/307.414秒，facts复用36000/ID-basis-facts-history42000稳定，变化零。cgroup含缓存达到512硬限、exit0无OOM，不代实际材料/并发API/v0真健康。间接opentelemetry1.45.1→1.45.2为未改requirements的解析漂移单列，非警告升级，不称完全同环境。六API/PG卷/网络/镜像/快照/.env/raw清理，v0未变，无当前资源或子agent；证据 [公开验证摘要](../../docs/verification.md)（详细原件非公开）。独立R2已判P1代码级/02/05关闭、软件通过；N1/P3待用户决定修复时机，未Gate2。原约定：新Analyze通过、Astra串行C/A并主会话复验后才开始；不能沿用423或任何旧内存数字。仅已批准合成候选测试，不含Gate2/main/NAS部署/真实材料。
- **范围/分工**：主会话操作诊断/记录/清理，不写业务修复；若实际缺陷派回Astra原边界。候选Git快照/新批次标签，512m=memswap构建/API、384m=memswap PG、MemAvailable≥2GB且低峰，无真实材料/v0/认证/正式pgdata绑定、无宿主端口/正式Compose/prune；所有资源/凭据最后删除并核v0状态不变。不改spec/plan/checklist/依赖/限额。
- **完成标准**：AC-012-3/AC-012-4软件资源证据并保持上述所有值/身份/历史。目标Python3.12/PG17.4完整`python -m pytest tests acceptance/test_compare.py`所有新旧db实际执行；原S0/游标/弱引用及JSON/历史/失败路径通过。无hook same2k/6k、varied6k真实prepare/execute两次，记录baseline B、累计RSS R/V（字节）、cgroup/退出/OOM（页缓存另列）及ID/basis/facts/history稳定/事实全复用/变化零，varied独立尺寸和宽度和。小对象容量计量仅辅证，不当RSS、不预扣C。
- **机械放大门槛**：同质`P_same=R2000+(R6000-R2000)/4000*34000`，差异`P_varied=B6000+(V6000-B6000)*6`，R/V固定各点第二次真实PG重导的累计ru_maxrss，B为varied加载前基线；新upscale-guard.json含候选SHA/四输入字节/P值/passed。两者均≤480*1048576才建约36k合成库/容器跑首轮及真实PG重导；不过则停止/清理/报告，不扩其他行族/统一叶池/B流水线/增swap或改门槛。需实际36k完成/不变量/OOM状态，不能仅外推称512达标；实际原材料/v0持续健康/吞吐等仍T26待验。
- **验证/证据命令**：沿T24/T32已批准Git archive候选、512m受限build及一次性PG/API命令；原`T31-pg-scale-probe.py`与`T28-s0-load-probe.py`保持口径，合成文件确认btrfs/磁盘非tmpfs。每候选完整SHA、脚本/结果/归档哈希、所有命令/资源/完整结果与清理存新handoff目录；不提交tar/.env/凭证/private raw/trace。A+C通过资源后独立Claude CodeReview-R2，不以设计全勾/测试绿代审核或Gate2；仍不足先讨论。

### T-37 CodeReview-R2 N1/P3：仅规则依据变化不重置编号持有历史（0.5～1小时，P14实现/真PG完成，独立R3关闭N1）

- **本机结果（2026-10-30）**：P14独立openai/gpt-6-astra，派发private-candidate-060，09:59:27～10:09:41 （原始时刻；时区非公开）、exit0，仅importer（+6/-1、两个函数）/test_import（+178）/test_api（+71/-1）。主会话核全部差异、旧测试AST无修改/其他生产函数AST不变、UTF8LF/3.12 AST/diff通过；完整本机 **389 passed/57 skipped/1原有警告，446项，10.15秒**，指定两文件53通过/42skip。57=54无DB+3Linux，新增1PG/1HTTP均未在本机执行。Astra先红2失败/48通过/28skip；主会话另用private-candidate-060真实旧源码+最终新测试反事实重跑 **2失败/48通过/29skip，exit1，1.43秒**（多1新PG skip），旧since_run1→3/丢id确实复现，外部源码快照已删除。固定新增测试名：test_identifier_basis_upgrade_preserves_tenure_and_s0（2参数）、test_identifier_basis_upgrade_keeps_database_rows_and_history、test_identifier_basis_upgrade_detail_resolve_and_history；原断言保留，PG含xmin证明未变行不UPDATE。证据 [公开验证摘要](../../docs/verification.md)（详细原件非公开）。这只是本机就绪，不代真库/R3/Gate2；本轮未规模测试。
- **发现/许可**：R2软件层通过但新列N1/P3：RULE_VERSION升级、编号/state/source/source_path/is_primary等值不变，_identifier_rows因basis不同不复用旧行，_persist_identifiers把旧current历史化/重插同号current，since_run重置；pending亦删后重插。R1基线已有非本轮回归，原文/真实compute探针在 [公开验证摘要](../../docs/verification.md)（详细原件非公开）（不是新PG证据）。2026-10-30用户回复「同意并继续」，选择Gate2前最小修复、真库复验和独立重审，不是Gate2/部署/真实导入许可。
- **依赖/分工**：冻结spec7/plan10需求与设计不变，支持既有编号起止批次、字段依据与历史契约；独立Analyze16已核对新T37/T38与全部12项Checklist，12通过/无阻断，允许由独立 `openai/gpt-6-astra` 实施。原文/meta/status/哈希在 [公开验证摘要](../../docs/verification.md)（详细原件非公开）。派发纳入compute S0可无id、只UPDATE实际变化basis及红绿留证等建议；不扩设计。主会话负责派发、差异复核、复验与证据；模型不可用即报告，不替换。共享文件串行，不与审核/其他实施同时写入。
- **修改范围**：仅 `catalog/src/dh_catalog/importer.py` 的 `_identifier_rows` / `_persist_identifiers`、`catalog/tests/test_import.py`，必要的HTTP断言只在 `catalog/tests/test_api.py`。值全等仅basis变化时保旧id/since_run/until_run，构造新行/field_basis而不就地改S0，持久化只原地更新变化的field_basis；同版本完全未变仍复用、不无条件UPDATE。约6～10行生产是审核员估计，不是强制行数。不改schema/规则版本/身份算法/JSON结构/事务锁/游标/CompactMap/依赖/配置/v0，不新增状态、恢复机制或通用抽象。
- **完成标准**：满足AC-003-1/AC-004-5/AC-011-2/AC-013-1/AC-013-3。current与pending在值不变、仅规则作者版本变化时保数据库identifier.id及原since_run、until_run；不制造同号historical、不删重插pending。当前依据更新为实际规则作者/本批run/at，旧S0与旧history中的作者/时间/批次完全保留；新history仍记录依据变化。同版本下一次重导不新增history。真正改号仍历史化旧current，撤销pending仍删除当前候选而保过去快照。含NLC目录号/Pressmark/IDP多来源的回归验证原文、来源、主号及resolve/detail语义不变，不把不同source/path/state等值变化误当basis-only。
- **真实测试**：先以新回归在旧代码上证明失败，再最小修复。小型compute用独立S0 builder模拟旧版本依据，保旧S0深值/身份断言；PG用真实文件/prepare/execute/SQL与批次历史，沿既有测试方式设置合成旧部署依据，不mock业务/SQL或复制比较逻辑。补current/pending及多来源/历史/无变化重跑断言；必要时用已有API夹具验证当前详情无伪曾用号、resolve只current及过去history原样。不改旧断言求绿，只有HTTP外边界可用替身。
- **验证命令**：本机指定完整文件 `catalog/.venv/Scripts/python.exe -B -I -X utf8 -m pytest -p no:cacheprovider -c catalog/pytest.ini catalog/tests/test_import.py catalog/tests/test_api.py`，再显式全套 `catalog/tests catalog/acceptance/test_compare.py`；无DB/仅Linux如实skip、不算通过。`git diff --check`、UTF8LF/无BOM、3.12 AST及未授权函数/文件AST不变检查。真库由T38补，不与本机就绪形成循环；实施者不提交/推送/连NAS、不改冻结spec/plan/checklist或状态文档。任何新代码不能沿用442作为新证据。

### T-38 N1新候选隔离目标回归与独立CodeReview-R3（1～2小时，验证/清理与独立R3完成，Gate2未批）

- **R3独立结果**：Anthropic Claude审核员A，实际10:47:51～11:00:57 （原始时刻；时区非公开）、exit0，审private-candidate-064（源码/测试等同private-candidate-063），前后HEAD/工作区固定干净，无NAS操作；桥仍既有接入不可用证据未调用。**软件层面通过，N1修复充分并关闭，无新P0/P1/P2**，旧CR1-01代码级/02/05关闭维持。审核员亲跑本机389通过/57skip/1原有警告（10.14秒），仅核NAS446原件未亲跑；归档 [公开验证摘要](../../docs/verification.md)（详细原件非公开）。依据两个函数差异判断旧T36可支持新候选首轮/同版本无变化重导，不要求本轮重跑36k；不当新候选直接实测，规则升级足规模/真实材料/并发/v0健康/性能仍待验。另记非回归P3边界：同号但来源/路径/主号来源改变仍会同号historical并重置该记录since_run（任务明确保留行为），Handoff写清记录历史不等于编号值曾改变；若要改语义先Clarify，不擅扩修。Gate2风险见review.md，未代用户接受或merge/部署。
- **A2最新结果**：候选private-candidate-063在NAS Python3.12.15/PG17.4 **446 passed/0 failed/0 skipped/1原有警告，73.22秒**，57db全执行，新增PG/HTTP编号历史回归实际通过。API实际512m=memswap、PG384m=memswap，pip check通过、A1/A2完整freeze相同。全部临时库/容器/匿名卷/网络/镜像/隔离快照/raw/env已清理，v0未重启，具体现场状态与可用内存原值非公开保全。证据 [公开验证摘要](../../docs/verification.md)（详细原件非公开），A1失败不覆盖。本轮未新36k/规则升级足规模，不把旧T36变新实测；独立R3已据差异通过（见上），仍未Gate2/merge/部署。
- **A1实际结果/修正入口**：候选private-candidate-061在Python3.12.15/PG17.4完整 **445 passed/1 failed/0 skipped/1原有警告，72.66秒**，57db实际执行；编号/历史新PG回归通过。唯一失败是新HTTP测试最后把请求批次元数据`requested_run`也当旧响应完全相同：API原有`_history_at`返回requested_run=本次请求，实际4!=旧3，其余3项一致。非生产缺陷；交独立Astra P15仅`test_api.py`该新增断言修正期望为新requested_run、仍完整比较run_id/快照/依据，不改API或删内容断言。旧测试AST保持，形成新候选后重跑全套目标测试，不能沿用A1或旧442。A1库/容器/卷/网络/镜像/快照/凭据全清理，v0不变；stop后--rm异步删除初检曾exit1，后续等待确认清理成功留两日志。证据 [公开验证摘要](../../docs/verification.md)（详细原件非公开），R3/Gate2仍待。

- **P15后续（本机就绪）**：openai/gpt-6-astra于10:25:52～10:29:51 （原始时刻；时区非公开）、exit0，仅test_api.py新增测试的一行改为完整响应等于`dict(new_history[q], requested_run=repeated_run)`，所有快照/run_id/basis与旧历史断言仍完整。主会话复验完整389通过/57skip/1原有警告，精确差异/其他生产及旧测试AST/UTF8LF/3.12 AST/diff通过；本机新API仍skip，需A2。P15曾因主会话同期新建A1/commands.txt而未跟踪文件检查失败，该文件是主会话操作记录、子agent未改，非越界修改；原报告保留。证据 [公开验证摘要](../../docs/verification.md)（详细原件非公开）。
- **范围/顺序**：T37本机集成通过并形成完整候选SHA后，主会话按既有T24/T36通道导出 `git archive <SHA> catalog` 到新NAS隔离临时目录，仅构建候选并跑完整真实Python3.12/PostgreSQL17.4 pytest。所有新旧db项实际执行、0跳过；不是正式部署/材料导入，也不自动重跑36k规模。T36旧36k只属private-candidate-056，本轮若未新做规模不得称新候选已足规模实测；用限定差异/回归与独立R3判断原资源证据适用边界。
- **安全/停止**：前检NAS MemAvailable≥2GB且低峰；构建/测试512m=memswap、PG384m=memswap，PG64MB buffers/20连接/work_mem4MB，先inspect验证限额再start；不挂真实材料/v0 cache或.env/正式pgdata、不发布端口、不起正式Compose、不重启v0/生成器、不全局prune。新随机临时凭据只写权限600外部env文件、不打印/入库；测试库只dh_catalog_test_*。预算/连接/模型失败则报告，不扩限/换模型/隐瞒跳过；业务缺陷派回Astra。
- **完成标准**：上述AC在目标环境全部回归并取得候选SHA/快照哈希、完整pytest与exit、资源限制/OOM/依赖解析与pip freeze、v0前后ID/启动/restarts、临时库/容器/匿名卷/网络/镜像/快照/凭据清理证据。保持Starlette/httpx原警告、不升级/屏蔽；依赖漂移如实记录。仅合成软件证据，T25/T26与真实资源/连续健康/性能仍待单独许可。
- **验证/审核**：完整目标命令 `python -m pytest tests acceptance/test_compare.py`，真实连接由外部env-file传入；限定inspect字段不输出Env。清理后冻结新HEAD，由独立Claude审核员A按AGENTS指定实际通道运行CodeReview-R3，核spec/plan/tasks、当时基线 private-candidate-058 与审阅候选之间的 catalog 差异（别名不可直接作为Git参数）及旧R2基线、新测试与原证据，评估N1、旧修复与残余风险。原文/meta/status/哈希归档 [公开验证摘要](../../docs/verification.md)（详细原件非公开）；主会话更新tasks/converge/review/HANDOFF与状态表。R3不能代用户批准Gate2，仍不merge/push nas/部署/真实导入。

### T-39 合并后main隔离目标回归（2026-10-30，验证与清理完成）

- **许可/范围**：PR #1合并后，用户单独批准一次隔离验证：以已合并main `646a29ee64ba` 的 `catalog` 快照（`git archive`）在NAS隔离临时目录受限构建测试镜像，用一次性PostgreSQL/测试容器运行完整目标测试；不挂真实材料、正式pgdata、v0配置或cache，无宿主端口；不推送nas、不部署、不重启v0、不触发导入。目的是补齐public-release-privacy评审列出的4项新增DB回归，并对合并后代码重跑T-24所列数据库/HTTP/镜像内契约测试。
- **安全前检**：低峰、宿主可用内存高于2GB门槛（原值非公开）、临时名称/目录未占用（记录更正：当时“无图块生成器运行”检查的容器名过滤写错，实际未生效；测试容器各有硬限额，测试结论不受影响，T-25 已改用正确名称核查）；构建前以独立探针实证构建内存硬限额生效（cgroup内存与memsw均536870912字节）。
- **A1（2026-10-30T18:47Z～18:49Z，停止，非产品失败）**：候选镜像受限构建成功；一次性PG的 `pg_isready` 在镜像初始化临时服务阶段即返回成功，专用测试库尚不可连接，版本查询失败。按“失败即止”未运行pytest；该批容器/匿名卷/网络/镜像/隔离文件/临时凭据全部清理，v0未变。仅修正仓库外操作脚本的就绪条件为“专用测试库TCP SQL查询成功”；产品代码、测试、镜像内容与限额均未改。
- **A2结果（2026-10-30T18:53Z～18:57Z）**：同一快照、同一限额、全新临时名称。Python 3.12.15 / PostgreSQL 17.4；构建与测试容器512m=memswap、PG 384m=memswap（创建后启动前核验），无宿主绑定与端口。**483 passed / 0 failed / 0 skipped / 1条原有Starlette弃用警告，84.45秒**；61个db项全部实际通过，含新增4项（后台导入使用配置的旧记录前缀的2个参数、PreparedImport传递记录前缀并保留历史、公开事件标签升级追加历史且不改变编号持有）；3个仅Linux协议trace项通过。测试容器exit0，事件中无OOM。pip freeze 29项与T38-A2逐项相同，固定依赖全部匹配。
- **清理**：两批次的临时容器、匿名卷、网络、测试镜像、隔离快照目录与临时凭据均删除，并按标签/名称复核无残留；v0容器标识、启动时间、重启次数与运行状态前后一致；未全局prune、未起正式Compose。原始命令/输出/事件仅非公开保全。
- **边界**：合成软件证据，不是T-25正式部署或T-26真实材料/规模/性能/v0连续健康验收；旧36k不变成新候选实测，规则升级足规模仍未验。隔离测试镜像构建成功不等于正式镜像重建；v0根Dockerfile（仅注释变化）的镜像仍未重建。

CR1-03（扩展名紧邻裸号，未证实）与CR1-04（备份散放，低概率）现在不改代码或冻结编号规则；留T-26按实际材料核查，必要时先澄清/登记。评审范围、全部发现与Gate2待验风险见review.md，原文按哈希归档，不勾改设计checklist。

## 子 agent 实施记录

| 批次 | 任务 | 实际模型 / 通道 | 修改范围 | 执行与主会话复验 |
|---|---|---|---|---|
| P1 | T-13 | GPT 6 Astra / openai（gpt-6-astra） | nlc.py、test_nlc.py | 独立进程，14:23～14:31；子 agent 36 通过，主会话同套件与完整回归复验通过 |
| P1 | T-14 | GPT 6 Astra / openai（gpt-6-astra） | derivation.py、test_derivation.py | 与 T-13 并行且无共享修改文件，14:23～14:33；子 agent 35 通过，主会话同套件与完整回归复验通过 |
| P2 | T-17 → T-18 → T-19 | GPT 6 Astra / openai（gpt-6-astra） | importer.py、test_import.py、__main__.py；conftest.py / test_db.py 只提取共享真实 DB 夹具 | 独立进程，14:48～15:11，依赖串行；指定测试 47 通过 / 30 db 跳过，主会话发现四项集成缺口后派回修复 |
| P2-fix | P2 集成修复 | GPT 6 Astra / openai（gpt-6-astra） | 仅 importer.py、test_import.py | 15:29～15:33，新增四个真实文件回归并修复；指定测试 51 通过 / 30 db 跳过；主会话完整复验 303 通过 / 30 db 跳过 / 1 条原有警告 |
| P3 | T-20 → T-21 | GPT 6 Astra / openai（gpt-6-astra） | api.py、config.py、__main__.py、test_api.py / test_config.py；importer.py / test_import.py 仅补合并建议双端对象关联 | 16:15～16:33 串行完成；子 agent 指定文件 73 通过 / 27 db 跳过；主会话完整复验 311 通过 / 42 db 跳过 / 1 条原有警告，真实 DB 未验 |
| P4 | T-22 | GPT 6 Astra / openai（gpt-6-astra） | catalog/Dockerfile、docker-compose.yml、.env.example、.dockerignore、test_runtime.py、README.md | 16:53:17～17:01:12 自然完成 exit=0，随暂停 WIP 保存；21:26 恢复后主会话复核并完整回归：318 passed / 42 db skipped / 1 条原有警告，其中静态运行契约 7 通过；文档一致性与差异空白检查通过，Compose / 镜像 / 运行仍待验 |
| P5 | T-23 | GPT 6 Astra / openai（gpt-6-astra） | acceptance/baseline-2026-10-27.json、compare.py、test_compare.py、catalog/README.md | 当前安全点 private-candidate-031；独立进程 21:28:27～21:45:32，exit=0，仅写四个分配文件。子 agent 非 DB 回归 360 passed / 42 deselected / 1 warning；主会话同命令复验一致，另跑完整回归 360 passed / 42 db skipped / 1 warning、比较测试独立 42 passed；源码与文档语法/一致性通过，未连接 NAS 或启动服务 |
| P6 | T-24 两处 CLI 测试修复 | GPT 6 Astra / openai（gpt-6-astra） | 仅 test_api.py、test_import.py | 22:26:19～22:28:04，exit=0；各测试显式接收 test_database_url 并传给子进程，共替换 4 行，保留真实 subprocess 与全部断言，不改生产代码或认证。子 agent 两文件 41 passed / 27 db skipped，完整本机 360 passed / 42 db skipped / 1 warning；主会话完整本机复验一致；随后在 T-24 A2 候选 private-candidate-035 真库复验，两处子进程及完整 402 项全部通过、0 跳过 |

P1 主会话完整回归：266 passed / 15 db skipped / 1 条原有依赖弃用警告。P2 集成修复后：303 passed / 30 db skipped / 1 条原有警告（test_import.py 37 通过、15 db 跳过；test_db.py 15 db 跳过）。P4 恢复复验为 318 passed / 42 db skipped；P5 后显式包含 acceptance 的本机完整回归当时为 360 passed / 42 db skipped / 1 条原有警告。本机默认 pytest.ini 的 testpaths 仍只有 tests，验收比较测试须显式加入 acceptance/test_compare.py（README 与 T-24 命令已包含）。上述是 P5/迁移阶段的历史结果，彼时尚未执行真实数据库或 Python 3.12 容器测试；后续已获准的 T-24 A2 最新真实库回归为 402 passed / 0 skipped / 1 条原有警告，首轮失败与两轮清理证据见本任务，不混作 P5 成果。正式 NAS 部署验收仍未执行；早先前置资料仅按名只读抽查三个国图卷的 JSON 和 13 个白名单执行记录，没有遍历 cache。

P7：GPT 6 Astra / openai（gpt-6-astra），派发 HEAD `private-candidate-037`，2026-10-29 00:00:58～00:03:35（meta/status 原始记录），exit=0。只改 scan.py、test_scan.py、test_import.py；一处具体异常处理及两条真实文件回归。子 agent 指定文件56通过/15 db跳过，完整本机362通过/42 db跳过/1原有警告；主会话完整本机复验一致，并在新候选private-candidate-038的NAS/3.12/真库全404项通过、0跳过后关闭C1。未由子agent访问NAS。

P8/P9（2026-10-29，均openai/gpt-6-astra，派发HEAD private-candidate-041）：P8 08:08:58～08:19:49，exit=0，仅importer/rules/test_import/test_rules/test_api，T28/T29共享文件串行；子agent分配测试78通过/28 db跳过/1警告。P9 08:08:58～08:11:09，exit=0，仅identity/test_identity，与P8并行无共享修改；子agent38通过，主会话38通过。主会话集成全套 **369 passed/43 db skipped/1原有警告，412 collected**；这是本机证据。随后主会话以候选private-candidate-042在NAS Python3.12/真PG完整 **412 passed/0 skipped/1原有警告，46.08秒**，并实测2k/6k真实库重导及S0定位；未达成36k资源证明，按停止条件待设计讨论、未发R2。全部NAS资源/临时凭据已清理，P8/P9均自然结束、无子agent访问NAS；旧404保留原候选证据。

P10：openai/gpt-6-astra，派发private-candidate-046，meta/status 12:12:32～12:21:09 （原始时刻；时区非公开）、exit0。仅importer.py/test_import.py，显式contextmanager产cursor、128行命名游标、短读事务/嵌套保存点。四新测试参数化11项，子agent完整369通过/54skip/1原有警告，主会话同全套369/54/1（423项）复验一致；54中51无DB/3Linux trace。原函数AST除loader外未改、3.12 AST/UTF8LF/差异通过；不代PG运行。证据 [公开验证摘要](../../docs/verification.md)（详细原件非公开），未由子agent访问NAS/提交；T32真实证据在T32-A1补齐423 passed/0 skipped/1原有警告，54db全部通过；校准资源有改善但未过36k放大条件，按约定停止，未R2。

P12/T34 C：openai/gpt-6-astra，派发private-candidate-054，2026-10-29 22:13:07～22:18:27 （原始时刻；时区非公开），exit0。仅importer/test_import，生产+26/-12改为weakrefable slots解析器，无自捕获/方法缓存/生产GC；新6个测试包括NLC有无署名/BnF/真实多层派生/memo/读失败/异常traceback释放。主会话完整375 passed/54 skipped/1原有警告（429项，51无DB/3Linux），旧函数AST除_image_rows外不改，UTF8LF/3.12 AST/diff检查通过；真库待T36，P1未关，不代Review。证据 [公开验证摘要](../../docs/verification.md)（详细原件非公开），无子agent/NAS资源，现可串行P13。

P13/T35 A：openai/gpt-6-astra，派发private-candidate-055，22:21:58～22:30:05 （原始时刻；时区非公开）、exit0，仅_compact.py/importer/test_compact/test_import；影像只读映射、64完整形状顺序LRU/值tuple、逐行压紧与全部Jsonb同一dumps。主会话完整387通过/55skip/1原有警告（442项）与子agent一致，原C/编排/游标保持；目标真PG待T36。证据 [公开验证摘要](../../docs/verification.md)（详细原件非公开），不代P1/Review，未由agent连NAS/提交。T36可开始。

## 本机目录迁移（2026-10-28，非功能实施任务）

按用户要求将本机工作副本迁至 `<本机仓库根目录>`。原样复制阶段对含 `.git`、忽略的本地环境在内的 6,049 个文件逐一 SHA-256 校验一致；随后重新生成虚拟环境激活脚本及 17 个命令入口，依赖不重装、不下载/升级，清除可再生旧字节码缓存。实施/审核外部调度脚本及仓库备份的 cwd 已更新，新路径验证成功后移除旧目录。旧目录移除后的完整回归为 **360 passed / 42 db skipped / 1 条原有警告**，pip check、Git fsck、模块 help 与调度脚本语法通过；证据在 [公开验证摘要](../../docs/verification.md)（详细原件非公开）。业务代码、冻结 spec/plan/checklist、v0 与 NAS 部署路径不变，未启动子 agent、容器或服务。迁移当时 T-24 许可尚待确认，其后已单独批准并完成 T-24 两轮实测与清理，详见 T-24；路径/文档更新按已批准约定同步 GitHub 功能分支，不合并 main、不推送 NAS。

## Handoff 文档与当前交付（2026-10-30）

原软件R3/Gate2及隐私R5/本轮Gate2均通过；原公开发布阻塞已解除。origin两分支已按原租约一次原子受保护更新，新取副本全历史/独立语境复扫通过，本机main/功能分支CAS迁移完成，旧私有引用/reflog仅保留恢复且禁止回传。交接与PR #1正常匿名UTC合并已完成，GitHub确认MERGED、合并后新取两ref复扫通过；部署远端未访问/未推送。

按D-018补齐`docs/architecture.md` §12目录服务实际入口、事务、只读/身份与编号记录边界；review.md与状态表同步，旧审核/测试数字和冻结需求保持。最新软件本机489通过/61跳过/1警告；合并后T-39隔离目标回归483通过/0跳过（61个db项含新增4项全部实际通过）。v0根镜像重建与T25/T26真实验收未执行。软件合并不代表全量验收完成，feature仍in-progress。
