# Feature: catalog-foundation 任务清单（tasks.md）

> 2026-10-28：用户已在 Gate 1 批准 spec 第 7 版（含第 9 轮建议 1～3、5 的措辞澄清）。依据 plan 第 8 版拆分。
> 状态：第 11 轮 Analyze 已由审核员 A 判定 12 项全部通过，可以进入 Implement；以下任务按依赖实施，NAS 项仍待许可。

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

## 任务

### T-01 服务包、配置与合成测试夹具（1 小时）

- **状态**：本机完成（2026-10-28）；test_config.py 14 项通过（含 CLI 不提供导入入口、不使用数据库默认连接），固定依赖已在独立 venv 安装，pip check 通过；HTTP 503 留 T-15/T-21 验证
- **上下文**：M1；建立本机测试入口与明确的外部配置边界，后续模块使用确定类型的配置值。
- **依赖**：无
- **修改范围**：`catalog/README.md`、`catalog/requirements.txt`、`catalog/pytest.ini`、`catalog/src/dh_catalog/__init__.py`、`config.py`、`catalog/tests/conftest.py`、`test_config.py`。现有 `.gitignore` 的 `.env` / `.venv/` 规则已覆盖子目录，不另建一份。
- **完成标准**：为 AC-005-1、AC-011-1、AC-012-1 提供合成小 TIFF / PSB 头 / JPEG、临时目录和配置；入口只读取环境变量及只读 v0 配置，不包含凭证默认值；缺少 `AUTH_SECRET` 保持不可服务的状态，由 API 返回 503（T-15/T-21）；固定依赖版本，v0 本身不动。
- **验证命令**：`python -I -X utf8 -m pytest -c catalog/pytest.ini catalog/tests/test_config.py`。

### T-02 初始数据模型与迁移（2 小时）

- **状态**：代码与真实 PostgreSQL 测试已写成（2026-10-28），未标完成；本机没有测试库，test_db.py 的 15 项测试跳过，待 T-24 实测 SQL / 迁移 / 约束
- **上下文**：M1；以 plan §3 的表和约束承载稳定 ID、关联、附件、字段依据及历史。
- **依赖**：T-01
- **修改范围**：`catalog/migrations/0001_init.sql`、`db.py`、`__main__.py` 的 migrate、`test_db.py`。
- **完成标准**：为 AC-002-4、AC-003-3、AC-004-5、AC-008-2、AC-009-2、AC-013-3 建表；UUIDv4 与路径解耦；多对多关系、非空 grouping_key 唯一、present 位置唯一、编号索引齐全；迁移重复执行不重复建表，不引入 ORM 或迁移框架。
- **验证命令**：T-24 中执行 `python -m pytest tests/test_db.py`，连接真实临时 PostgreSQL 库；本机只编译 `python -m compileall -q catalog/src`，不能据此宣称数据库验证通过。

### T-03 连接、事务与导入互斥（1 小时）

- **状态**：代码已写成（2026-10-28），未标完成；连接池、事务与会话锁的真实验证随 T-24 执行，不以语法检查代替
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

- **状态**：本机完成（2026-10-28）；test_identifiers.py 45 项通过；写卷最多一个主编号及存疑不归并的端到端保证留 T-10/T-24
- **上下文**：M3；只解析单元规定的编号来源，不解析写卷内部普通文件名。
- **依赖**：T-01
- **修改范围**：`identifiers.py`、`rules.py` 的号段、`test_identifiers.py`。
- **完成标准**：满足 AC-002-5、AC-002-8、AC-004-1、AC-004-2、AC-004-4、AC-004-5；覆盖分件、多号省略前缀、大小写、分享者编号、带开宝藏上下文的帙号，以及疑似四位数的尺寸 / 年份排除；保留逐字原文，存疑不作主编号。
- **验证命令**：`python -I -X utf8 -m pytest -c catalog/pytest.ini catalog/tests/test_identifiers.py`。

### T-07 单元划分、附件归属与合并建议（2 小时）

- **状态**：本机完成（2026-10-28）；test_units.py 共 20 项通过，含词表、国图页图、散放文件、附件与只提合并建议；持久化关联留 T-17/T-24
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

- **状态**：本机完成（2026-10-28）；首批影像用例 10 项通过，从扫描开始真实改名 / 移动 / 互换 / 原子覆盖 / 回收站还原；新增写卷计算证据见 T-10/T-11，数据库历史仍待 T-17/T-18/T-24
- **上下文**：M3；在每个根内先匹配文件标识，再按未被认领的位置延续。
- **依赖**：T-05
- **修改范围**：`identity.py`、`test_identity.py`。
- **完成标准**：满足 AC-003-1、AC-003-2、AC-003-3、AC-009-2、AC-009-3、AC-009-5 的影像部分；ID 不复用，改名 / 移动 / 互换随文件，覆盖记变化，缺失只标记，再出现恢复；从真实扫描结果计算，不加入内容指纹或 Q-025 规则。
- **验证命令**：`python -I -X utf8 -m pytest -c catalog/pytest.ini catalog/tests/test_identity.py`。

### T-10 写卷初建、主编号与多影像关联（2 小时）

- **状态**：本机计算完成（2026-10-28）；test_identity.py 共 35 项通过，含同号跨目录、多号共享、分件、无号 / 存疑不合并、新影像归属、整件缺失保留编号 / 线索；preserved_items 给后续导入器保留出处的依据，持久化保证留 T-18/T-24
- **上下文**：M3；实现 plan §4.2.3 D/E 中初建写卷的正常流程。
- **依赖**：T-06、T-08、T-09
- **修改范围**：`identity.py`、`test_identity.py`。
- **完成标准**：满足 AC-002-1、AC-002-4、AC-002-5、AC-002-8、AC-003-1、AC-003-6、AC-005-5；跨谱系同号归并，多编号共享影像，分件记母号，无号分别建卷；新文件归属按已有数量与 serial 判定；全部影像缺失的写卷保留编号、线索与出处。
- **验证命令**：`python -I -X utf8 -m pytest -c catalog/pytest.ini catalog/tests/test_identity.py`。

### T-11 编号变化、同号回退与顺序无关（2 小时）

- **状态**：本机计算完成（2026-10-28）；test_identity.py 共 35 项通过，含五种待确认情形及改回恢复、两件互换 / 三件轮换、增号 / 改号、同号迭代回退、改号后新增目录的归属；数据库端到端互换未验
- **上下文**：M3；已有写卷始终保留 ID，不自动合并 / 拆分。
- **依赖**：T-10
- **修改范围**：`identity.py`、`test_identity.py`。
- **完成标准**：满足 AC-003-4、AC-003-5、AC-003-7、AC-003-8；按导入前 S0 同时计算 A～E；撞号逐步回退，互换 / 三件轮换不撞唯一约束，多编号增号 / 单号改写分别处理；待确认编号不关联到其他持有者；不为备份目录不同步改名增加规则。
- **验证命令**：`python -I -X utf8 -m pytest -c catalog/pytest.ini catalog/tests/test_identity.py`；数据库端到端互换另在 T-17/T-24 验证。

### T-12 谱系、许可与出处规则（2 小时）

- **状态**：本机规则完成（2026-10-28）；test_rules.py 32 项通过，含读失败不误判 BnF、目录混合、严格许可继承、署名来源、出处建议 / 冲突、人工结论保留及不变初值复用；真实数据基线与落库保留尚未验
- **上下文**：M4；规则有名称、版本与依据，不把触发者当作者。
- **依赖**：T-05、T-06、T-08
- **修改范围**：`rules.py`、`test_rules.py`。
- **完成标准**：满足 AC-005-2、AC-006-1、AC-006-2、AC-006-3、AC-007-1、AC-007-2、AC-007-3、AC-007-4；谱系逐文件判、目录只汇总直接 TIFF；读不了的不误判 BnF；本地合成取最严格许可；人工出处不覆盖；非敦煌只给建议。规则作者与确定 / 推断明确，为 AC-013-1、AC-013-2 提供依据。
- **验证命令**：`python -I -X utf8 -m pytest -c catalog/pytest.ini catalog/tests/test_rules.py`。

### T-13 国图清单与画布（1.5 小时）

- **状态**：本机完成（2026-10-28，Astra 子 agent P1）；test_nlc.py 36 项通过，主会话已复验；只读抽查确认画布从 0 起、strips 列表 / 整数两种结构。Pressmark 来源、大小写与异常、署名、TIFF / pages 画布映射均已覆盖；原附件落库与 NAS 全量对应率留 T-17/T-26
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

- **状态**：本机完成（2026-10-28）；test_auth.py 14 项通过，含真实签名协议、过期 / 非法 cookie、删用户、管理员位、secret 缺失全请求 503、文档页与 OpenAPI 登录墙；只建认证框架，无正式查询或导入路由
- **上下文**：M6；只验证 v0 会话，不创建账号或签发 cookie。
- **依赖**：T-01
- **修改范围**：`api.py` 的认证入口、`test_auth.py`。
- **完成标准**：满足 AC-011-1 的认证部分；正确验证 v0 的签名、过期时间、用户存在与管理员位；缺 secret 拒绝服务；用户表只在请求校验读取，不进入导入器；测试按 app.py 的签名协议生成外部 cookie，调用真实认证函数，不另写被测实现。v0 .env 的 secret 按 env_file 的常见写法读取首尾空白与成对引号，测试含带引号的配置。
- **验证命令**：`python -I -X utf8 -m pytest -c catalog/pytest.ini catalog/tests/test_auth.py`。HTTP 路由权限另由 T-21 验证。

### T-16 v0 快照、健康采样与链接（1.5 小时）

- **状态**：本机完成（2026-10-28）；test_v0.py 19 项通过，HTTP 边界用 MockTransport，验证索引有效 / 未就绪 / 失败 / 有效空快照、原会话传递与释放、健康采样 / 2 秒指标、链接与不给链接原因；未访问实际 v0，快照落库及完整覆盖报告留 T-17/T-19
- **上下文**：M4；v0 是外部 HTTP 边界，导入使用触发者原会话，结束丢弃。
- **依赖**：T-04、T-15
- **修改范围**：`v0.py`、`test_v0.py`。
- **完成标准**：满足 AC-001-1、AC-011-4，并支持 AC-012-3；索引失败 / 未 ready 不阻断；快照取最近有效的一份；链接只给快照内且仍在的 TIFF 目录，其他给原因；健康采样每 5 秒，超时 2 秒，输出次数 / 失败数 / 最大耗时；不恢复暂停 / 中止或会话剩余时长规则。
- **验证命令**：`python -I -X utf8 -m pytest -c catalog/pytest.ini catalog/tests/test_v0.py`（仅此 HTTP 边界用替身；链接编码与磁盘检查运行真实实现）。

### T-17 导入主流程与事务写入（2 小时）

- **状态**：未开始
- **上下文**：M5；主函数只串正常流程，调用前面各模块，不重新实现规则。
- **依赖**：T-03、T-11、T-12、T-13、T-14、T-16
- **修改范围**：`importer.py`、`test_import.py`。
- **完成标准**：满足 AC-001-3、AC-003-1、AC-003-7、AC-008-1、AC-008-2、AC-009-1；后台线程内持锁，快照单独提交，正式数据单事务；编号与路径互换先用临时值避开唯一约束；附件边读边写，保存最新原文；真实数据库验证失败回滚与成功保留；不加暂存表 / 后备份 / 任务队列。
- **验证命令**：T-24 中执行 `python -m pytest tests/test_import.py`。

### T-18 变化、字段依据与批次历史（2 小时）

- **状态**：未开始
- **上下文**：M5；变化历史与 import_run 分开，能够按批次还原对象。
- **依赖**：T-17
- **修改范围**：`importer.py`、`test_import.py`。
- **完成标准**：满足 AC-007-4、AC-009-2、AC-009-3、AC-009-5、AC-013-1、AC-013-2、AC-013-3；保留人工认定，缺失不删写卷或编号，整件缺失不清空线索 / 出处；改文件与改规则产生可追溯快照，按任一批次取值及来源作者；不把修改和移动混在同一内容变化测试中。
- **验证命令**：T-24 中执行 `python -m pytest tests/test_import.py`。

### T-19 导入记录、报告与异常（1.5 小时）

- **状态**：未开始
- **上下文**：M5；报告引用各模块产生的事实与异常，不另做一套判断。
- **依赖**：T-18
- **修改范围**：`importer.py`、`__main__.py` 的 report、`test_import.py`。
- **完成标准**：满足 AC-001-1、AC-001-4、AC-009-4、AC-010-1，并支持 AC-010-2；含统计、变更、异常、无关联附件、有效快照状态、健康采样及 derivation 统一打开函数实际访问的 cache 路径记录；18 类异常均能由合成数据触发；导入期间 cache 访问只有白名单、不含 users.json（AC-012-2）；report 只读导出已保存结果，无 CLI 导入入口。
- **验证命令**：T-24 中执行 `python -m pytest tests/test_import.py`，一次覆盖全部导入行为。

### T-20 只读查询与按批次历史（2 小时）

- **状态**：未开始
- **上下文**：M6；公开路径按 plan §2.1，统一认证与参数校验后查询数据库。
- **依赖**：T-15、T-19
- **修改范围**：`api.py`、`test_api.py`。
- **完成标准**：满足 AC-011-2、AC-011-3、AC-011-4、AC-011-5、AC-013-3；编号任一写法、不区分大小写，历史 / 待确认编号不查，母号加分件；筛选分页覆盖多影像目录；详情返回依据、关系、原文与路径；附件原字节取回；无目录修改接口。P95 留 T-26 测真实 NAS。
- **验证命令**：T-24 中执行 `python -m pytest tests/test_api.py`，TestClient 调真实路由和临时 PostgreSQL。

### T-21 管理员触发、导入状态与 OpenAPI（1 小时）

- **状态**：未开始
- **上下文**：M6；使用已实现的后台导入与咨询锁，不引入任务系统。
- **依赖**：T-20
- **修改范围**：`api.py`、`__main__.py` 的 health、`test_api.py`。
- **完成标准**：满足 AC-011-1、AC-011-5，并支持 AC-009-4；管理员 POST 返回 202 / 运行中 409，普通用户仅可查询，匿名 / secret 缺失分别拒绝；导入记录与文档页受认证保护；health 为容器内命令，不借签发 cookie 绕过登录。
- **验证命令**：T-24 中执行 `python -m pytest tests/test_api.py`；CLI 健康命令由 T-25 验证。

### T-22 镜像与独立 compose 配置（1 小时）

- **状态**：未开始
- **上下文**：M7；只写新服务运行文件，不操作 NAS 或 v0 compose。
- **依赖**：T-03、T-21
- **修改范围**：`catalog/Dockerfile`、`catalog/docker-compose.yml`、`catalog/.env.example`、`catalog/README.md`。
- **完成标准**：落实 AC-011-1、AC-012-1、AC-012-3 的部署前提与 D-018：Python 3.12；384m / 512m 硬上限且 memswap 相等；三数据根与 v0 .env 只读，pgdata 在工作区外；数据库无宿主端口，API 8504，文档注明不接入公网；.env.example 不含真实口令；镜像含 tests/、acceptance/、pytest.ini 与 pytest，供一次性测试容器直接执行。构建验证留 T-24，运行验证留 T-25。
- **验证命令**：本机 `git diff --check`；经许可后 T-24 以 `docker build` 构建候选快照（不需要正式 .env），不初始化正式 pgdata；compose 的配置校验留 T-25（正式 .env 就位后执行 `docker-compose -p dunhuang-catalog config -q`，不打印展开凭证）。

### T-23 基线对照、验收入口与本机回归（1.5 小时）

- **状态**：未开始
- **上下文**：M7；用一份基线与现有 CLI 承载验收，避免多份统计规则和重复命令。
- **依赖**：T-19、T-22
- **修改范围**：`catalog/acceptance/baseline-2026-10-27.json`、`catalog/acceptance/compare.py`、`catalog/acceptance/test_compare.py`、`catalog/README.md`、`specs/catalog-foundation/tasks.md`。
- **完成标准**：为 AC-010-2、AC-011-3、AC-012-1、AC-012-2、AC-012-3、AC-012-4 提供 A1～A7 的可执行步骤与输出位置；基线包含全部核查数，Q-024 的新增附件不改旧基线；compare 只比较导入报告，不再扫描一遍计算业务结果；明确 NAS 许可、低峰与 >=2GB 可用内存的前提。跑一次全部本机测试，未执行的数据库 / NAS 项列待验。
- **验证命令**：`python -I -X utf8 -m pytest -c catalog/pytest.ini -m 'not db' catalog/tests catalog/acceptance/test_compare.py`；`python -m py_compile app.py pyramid_worker.py stitch_apply.py`；`git diff --check`。

### T-24 NAS 临时数据库与完整自动化测试（2 小时；需另获许可）

- **状态**：待用户许可，未开始
- **上下文**：M7；本机没有 PostgreSQL / Docker，在目标 Python 3.12 环境验证所有数据库与 HTTP 行为。
- **依赖**：T-23、用户测试许可；正式部署仍在 Review / Gate 2 / merge 后。测试前明确候选提交与 NAS 临时目录，以 `git archive <候选提交> catalog` 传入隔离位置；不推送 nas main、不启动正式 compose。
- **修改范围**：代码修复只在本机 `catalog/`；NAS 只接收候选快照并运行 plan §6.2 的一次性测试容器，不挂真实材料、正式 pgdata 或 v0 配置。数据库 `--rm`、384m = memswap；测试 API 容器 `--rm`、512m = memswap；无宿主数据库端口，共用临时 Docker 网络。
- **完成标准**：补齐 T-02、T-03、T-17～T-22 的数据库和镜像证据，验证 AC-003-7、AC-007-4、AC-008-2、AC-009-1、AC-009-2、AC-009-3、AC-009-4、AC-009-5、AC-011-1、AC-011-2、AC-011-3、AC-011-4、AC-011-5、AC-013-1、AC-013-2、AC-013-3；数据库来自一次性 PostgreSQL 容器，不使用正式 `catalog-db`；在其中建独立测试前缀的临时库，设置测试连接，跑完删库并删除容器 / 网络 / 快照。不得因缺测试库静默跳过 db 项后声称全通过。
- **验证命令**：获准后以 `/usr/local/bin/docker build -t dh-catalog-test <隔离目录>/catalog` 构建候选镜像；按 plan §6.2 启动一次性 PostgreSQL（随机测试口令、不挂宿主卷），就绪后在同网络的一次性测试容器内设置临时库 URL，执行 `python -m pytest tests acceptance/test_compare.py`（db 项 0 跳过）。测试不依赖正式 .env，不在此执行 compose `up`。把实际候选提交、容器与清理命令、通过数及输出摘要写回本任务。

### T-25 正式部署与只读冒烟（1 小时；需另获许可）

- **状态**：待用户许可，未开始
- **上下文**：M7；正式部署前必须通过独立 Review、Gate 2，并 merge 到 main；这是运行验收，不提前绕过交付闸门。
- **依赖**：T-24、Review / Gate 2 / merge、用户部署许可、NAS 可用内存 >=2GB
- **修改范围**：不改 v0；仅部署已合并的目录服务。若需修代码，回本机任务并重新评审，不在 NAS 工作区编辑。
- **完成标准**：核实 AC-011-1、AC-011-5、AC-012-1 的运行前提：项目独立、只读挂载、硬内存限额、数据库无宿主端口，未登录请求拒绝、普通用户不能 POST、管理员 GET 通过；不重建或重启 v0。secret 缺失拒绝服务与合成导入以 T-24 的测试结果为证，不在正式服务删 secret 或触发导入；正式首次导入留 T-26。
- **验证命令**：按 `catalog/README.md` 的获准部署步骤，`git push origin main` 后再 `git push nas main`；只启动 `dunhuang-catalog`。`python -m dh_catalog health`、`docker inspect` 核对挂载与限额；只读核验权限与导入记录接口，不执行管理员 POST 导入。

### T-26 全量导入与 A1～A7 验收（2 小时；需另获许可）

- **状态**：待用户许可，未开始
- **上下文**：M7；真实材料、性能与 v0 连续健康只能在部署后证明。用户触发正式导入，不由 agent 代签会话。
- **依赖**：T-25、用户验收许可与低峰时段
- **修改范围**：`specs/catalog-foundation/tasks.md` 的证据；缺口先记任务，不改基线凑数。
- **完成标准**：满足 AC-001-1、AC-001-2、AC-002-1、AC-002-2、AC-002-3、AC-002-4、AC-002-5、AC-002-7、AC-002-8、AC-005-2、AC-005-3、AC-005-4、AC-006-3、AC-007-3、AC-010-2、AC-011-2、AC-011-3、AC-011-4、AC-012-1、AC-012-2、AC-012-3、AC-012-4；按 plan §6.3 A1～A7 执行，差异逐项解释；全量 <=1小时，无变化重跑 <=10分钟，API 各100次 P95 <=1秒；原图 / 备份变化归因，cache 只核对访问记录和只读挂载，不遍历缓存；20个链接抽查无错卷。
- **验证命令**：按 `catalog/README.md` 的 A1～A7，用户在 OpenAPI 触发全量和重跑；agent 只读取导入报告、基线对照、只读挂载与资源采样、性能与链接检查结果。把每项实际输出摘要写回本任务，异常不掩盖；任何代码修复都须新提交并重新 Converge / Review → Gate 2 → merge → 部署，不在 NAS 直接修代码。

## 子 agent 实施记录

| 批次 | 任务 | 实际模型 / 通道 | 修改范围 | 执行与主会话复验 |
|---|---|---|---|---|
| P1 | T-13 | GPT 6 Astra / openai（gpt-6-astra） | nlc.py、test_nlc.py | 独立进程，14:23～14:31；子 agent 36 通过，主会话同套件与完整回归复验通过 |
| P1 | T-14 | GPT 6 Astra / openai（gpt-6-astra） | derivation.py、test_derivation.py | 与 T-13 并行且无共享修改文件，14:23～14:33；子 agent 35 通过，主会话同套件与完整回归复验通过 |

P1 主会话完整回归：266 passed / 15 db skipped / 1 条原有依赖弃用警告；未执行数据库或 NAS 部署验收。前置资料仅按名只读抽查三个国图卷的 JSON 和 13 个白名单执行记录，没有遍历 cache。

## Handoff 文档（实施与评审完成后）

除 AGENTS.md 的 review.md 与状态表要求外，按 D-018 在 `docs/architecture.md` 补入目录服务的实际架构。待验的 NAS 项继续明列，不把软件合并或清单通过写成全量验收完成。
