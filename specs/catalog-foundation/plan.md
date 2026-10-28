# Feature: catalog-foundation 目录底座 实施计划（plan.md）

> Plan 阶段产物：由 spec.md 生成的设计成果，包含具体实施细节。需求本身在 spec.md，此处不复制。
> 状态（2026-10-28）：第 7 版，对应 spec 第 6 版（待 Gate 1 再批准）。各轮 Checklist 的结果与修订对照见 `checklist.md`。

## 1. 技术方案

- **架构落点**：前后端分离后的第一个后端服务「目录服务」（D-011、D-016、D-018），与 v0 并存、互不依赖；影像查看仍由 v0 提供
- **技术栈**：
  - Python 3.12 + FastAPI + uvicorn（D-018）
  - PostgreSQL 17.4（NAS 已有镜像 `postgres:17.4-alpine3.21`，D-016），驱动 psycopg 3（连接池）
  - 影像事实：tifffile 读 TIFF 标签，Pillow 读 JPEG 信息，PSB 头自行解析（只读文件头 26 字节）
  - 测试：pytest + httpx
- **依赖锁定**：`catalog/requirements.lock` 精确锁定；与 v0 共有的库取 v0 当前运行版本（plan.md RK-05：fastapi 0.144.0、starlette 1.8.0、uvicorn 0.54.0、pydantic 2.14.1、tifffile 2026.10.15、numpy 2.5.4、Pillow 13.0.0）；psycopg 在 T-01 取当时的稳定版并锁定
- **规则数据**：批次层登记、子目录词表、编号体系与号段、疑似编号判定、谱系、许可默认表、出处线索都集中在 `rules.py`，每条规则有名称，整体带版本号（如 `2026-10-27.3`），写入每条字段依据的「作者」（R-013）；与 spec §1 术语一一对应
- **测试数据**：全部用合成数据（目录树、TIFF、PSB 头、JPEG、清单、仿照格式写的执行记录、文件条目），不把 NAS 上的真实日志或文件放进仓库

## 2. 模块设计

```
catalog/
├── README.md                  # 职责、入口、运行与验证
├── Dockerfile                 # python:3.12-slim + requirements.lock + postgresql-client（apt 阿里云源、pip 清华源，与 v0 一致）
├── requirements.lock
├── docker-compose.yml         # 项目 dunhuang-catalog：catalog-db、catalog-api
├── docker-compose.test.yml    # 测试：tmpfs 上的 PostgreSQL + 测试运行器，跑完即删
├── .env.example               # POSTGRES_PASSWORD 等（catalog/.env 不入库）
├── migrations/                # 0001_init.sql …，按序执行，记入 schema_migrations
├── src/dh_catalog/
│   ├── config.py              # 环境变量与路径
│   ├── db.py                  # 连接池、迁移、事务、咨询锁
│   ├── rules.py               # 规则数据（带名称与版本号）
│   ├── identifiers.py         # 编号解析、规范化、合规判定、疑似编号
│   ├── scan.py                # 只读扫描：目录树、文件条目（含 inode、mtime_ns）、附件、未导入清单
│   ├── facts.py               # 影像事实（有值 / 不适用 / 缺失）、5 段指纹
│   ├── units.py               # 写卷单元的划分（批次层、写卷目录、子目录词表、散放文件、备份映射）
│   ├── identity.py            # 影像身份（§4.2.1）
│   ├── grouping.py            # 写卷的归并与身份（§4.2.3 A～E）、合并建议
│   ├── nlc.py                 # 国图清单：Pressmark、IDP 条目 ID、署名、画布对应
│   ├── derivation.py          # 2026-10-21 执行记录 → 合并长卷的派生来源；cache/ 统一打开函数
│   ├── licensing.py           # D-012 默认规则与继承
│   ├── provenance.py          # 出处认定初值、建议、证据冲突
│   ├── trace.py               # 字段依据（来源、作者、批次、时间、置信度）与历史（R-013）
│   ├── v0.py                  # v0 索引快照、健康采样与让路、卷 ID 与链接
│   ├── importer.py            # 一次导入：暂存 → 计算差异 → 单事务应用 → 报告
│   ├── report.py              # 导入报告、异常清单、基线对照
│   ├── auth.py                # 校验 v0 会话 cookie 与用户表、Origin 校验
│   ├── api.py                 # FastAPI：只读接口 + 管理员触发导入
│   └── __main__.py            # 命令行：migrate / report / health（不提供导入，导入只经接口触发）
├── acceptance/                # NAS 验收脚本 A1–A7（§6.3）与基线 baseline-2026-10-27.json
└── tests/                     # pytest；fixtures/ 生成合成目录树、合成文件与文件条目
```

### 2.1 接口

全部接口都要求登录（AC-011-1）；容器健康检查用命令行 `python -m dh_catalog health`，不走 HTTP。

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| GET | `/api/v1/items` | 写卷列表；筛选 `system`、`lineage`、`provenance`、`has_anomaly`（按最近一次成功导入的异常清单）、`category`、`batch`（写卷任一影像的位置在其中即命中，含缺失的影像）；分页 `page`、`page_size`（≤ 200） | 登录 |
| GET | `/api/v1/items/{id}` | 写卷详情：编号（含历史与待确认编号）、影像（事实、谱系、角色、来源目录、派生、IIIF 画布、v0 链接或不给链接的原因）、来源与许可、出处认定及历史、原始记录、路径历史、母号与分件、字段依据 | 登录 |
| GET | `/api/v1/items/{id}/history?run=` | 写卷在指定导入批次时的取值及其字段依据（AC-013-3） | 登录 |
| GET | `/api/v1/resolve?q=` | 按编号查（任一写法、不区分大小写；查现行编号，含存疑编号；历史编号与待确认编号不参与，在写卷详情中可见），返回写卷列表（0～n 件）；母号返回母号写卷与全部分件 | 登录 |
| GET | `/api/v1/images/{id}` | 影像详情：事实、许可、路径历史、变化历史、字段依据 | 登录 |
| GET | `/api/v1/images/{id}/history?run=` | 影像在指定导入批次时的取值及其字段依据 | 登录 |
| GET | `/api/v1/attachments/{id}` | 附件原文，原样字节 | 登录 |
| GET | `/api/v1/anomalies` | 异常清单（含「未导入的文件」类别）；筛选 `run`、`category`；分页 | 登录 |
| GET | `/api/v1/imports`、`/api/v1/imports/{id}` | 导入记录与报告（含 v0 索引快照状态、v0 健康采样、不关联写卷的附件） | 登录 |
| POST | `/api/v1/imports` | 触发一次导入，后台执行，返回 202 与批次 ID；已有导入在跑时返回 409；登录状态剩余有效期不足 90 分钟时返回 400 并提示重新登录；`Origin` 校验见 §4.7 | 管理员 |

接口文档（OpenAPI）在 `/api/v1/docs`，同样需要登录；管理员可在该页面触发导入。

## 3. 数据与存储

PostgreSQL 数据目录在 `/srv/example/pgdata`，备份目录在 `/srv/example/catalog-backups`，都不在 v0 的部署目录（git 工作区）里。

| 表 | 主要字段 | 说明 |
|---|---|---|
| `import_run` | id、起止时间、状态、触发方式（`api:<账号>`）、规则版本、代码版本、v0 索引快照状态（有效 / 不可用及原因）、v0 健康采样汇总（jsonb）、各类数量（jsonb）、基线对照（jsonb）、错误 | 每次导入一条（AC-009-4）；触发者只记在这里，不作为字段作者 |
| `item` | id（UUIDv4）、serial（登记顺序）、grouping_key、parent_id、原始位置、展示策略、出处认定（状态、依据、判定者、时间、建议、建议依据）、线索（jsonb）、字段依据（jsonb） | 写卷；`grouping_key` 只给持有合规馆藏号的写卷（如 `pelliot:2504:1`、`nlc:BD00023a`），非空值唯一（spec R-003 写卷第 4 条：已有写卷之间不自动合并，同号不会写入）；「较早登记」按 serial 比较 |
| `identifier` | item_id、体系、原文、规范写法、母号、分件、出处、出处位置、主编号、合规 / 存疑、状态（现行 / 历史 / 待确认）、起止批次、字段依据 | 编号、编号历史与待确认的编号（规则要求拆分、同号未生效；AC-003-4～AC-003-6、R-004）；规范写法与母号建索引（不区分大小写） |
| `image` | id（UUIDv4）、根（data / backup）、相对路径、原始文件名、是否隐藏、种类（tiff / psb / jpg）、大小、mtime_ns、inode、指纹、事实（jsonb：7 个字段各为有值 / 不适用 / 缺失）、谱系、来源与许可五字段、对外策略、IIIF 画布序号与 ID、读取状态（成功 / 失败及原因）、状态（present / missing）、首见 / 末见批次、缺失时间、字段依据 | 影像（R-005、R-006）；根与相对路径是影像最后一次被发现时的位置（missing 影像保留）；present 影像的（根，相对路径）唯一 |
| `image_path_history` | image_id、根、相对路径、起止批次 | 路径历史（AC-003-2） |
| `item_image` | item_id、image_id、角色、来源目录（set_key）、写卷单元、字段依据 | 写卷与影像的多对多：多编号单元的影像关联多件（AC-002-4），一件写卷可有多套影像（AC-005-5） |
| `item_attachment` | item_id、attachment_id | 附件与写卷的多对多（AC-001-3） |
| `attachment` | id、根、相对路径、种类（说明 / manifest / report / index）、原始字节、sha256、解码文本、编码 | 原始附件（AC-008-2）；不属于任何写卷单元的附件同样导入，`item_attachment` 中没有它的关联，导入报告列出（AC-001-3） |
| `derivation` | 派生影像、源影像、方式（拼接 / PSB 转换）、证据（日志文件与行号） | 合并长卷的来源（AC-005-3） |
| `provenance_history` | item_id、状态、依据、判定者、时间、批次 | 判定者以 `rule:` 或 `user:` 开头（AC-007-4） |
| `history` | 对象种类、对象 ID、批次、快照（jsonb）、字段依据（jsonb） | 写卷、影像、编号、关系的派生字段每次变化时记一条快照（含字段依据），按批次可查任一时刻的取值及其来源与作者（AC-009-3、AC-013-3）；影像的缺失与重新出现也记入（AC-009-2、AC-009-5） |
| `anomaly` | 批次、类别、对象种类与 ID、路径、原文、说明 | 异常清单（AC-010-1） |
| `excluded` | 批次、根、相对路径、文件或目录、原因 | 未导入清单；接口中作为「未导入的文件」类别并入异常清单（AC-001-4、AC-010-1） |
| `v0_volume` | 批次、v0 卷 ID、相对目录 | 有效的 v0 索引快照（AC-001-1、AC-011-4）；只在快照有效时写入 |
| `stage_file` | 批次、根、相对路径、大小、mtime_ns、inode、是否隐藏、种类、事实（jsonb）、指纹 | 暂存表（UNLOGGED），每次导入前清空 |

**字段依据**（R-013）：jsonb，按字段记录 `{来源, 作者, 批次, 时间, 置信度}`。来源取值为 文件名解析 / 文件头 / 外部清单 / 执行记录 / 默认规则 / 人工；作者为 `rule:<规则名>@<规则版本>`（程序规则）或 `user:<账号>`（人工）；置信度取值为 确定 / 推断。

数据量：影像约 3.6 万行、写卷约 6,000 行，都在 PostgreSQL 的轻量范围内。

## 4. 关键流程

### 4.1 一次导入

1. 取得咨询锁，没取到就返回「已有导入在跑」；写入 `import_run`（running，记触发方式）
2. **v0 索引快照**（§4.7）：用触发者自己的 `dh_session` 调用 v0 `/api/index`；HTTP 200 且 `status` 为 `ready` 时快照有效，写入 `v0_volume`；否则（调用失败、`status` 为 empty / scanning / error）记「v0 索引不可用」异常及原因，报告标明「v0 覆盖对照不可验证」，导入照常进行。随后启动 v0 健康采样（§4.7）
3. **扫描**（只读）：遍历原图目录的各分类（一级子目录）与备份目录，跳过以 `@`、`#`、`.` 开头的目录并记入 `excluded`（`#recycle`、`@eaDir`、国图 `BD00081/.pages` 等）。按种类分类文件：`.tif` / `.tiff` / `.btf` / `.psb` 为影像，国图 `pages/*.jpg` 为页图，国图 `*_preview.jpg` 为预览图（其他分类的 JPG 不导入），`.txt` 与国图三种 JSON 为附件；国图 `tiles/`、`.npy` 及其他文件（PDF、PNG、下载中的临时文件等）记入 `excluded`。每个文件取得 大小、mtime_ns、inode
4. **事实与指纹**：（根，相对路径，大小，mtime_ns，inode）与库中记录相同、且上次读取成功的，沿用已有事实与指纹；否则读取事实（§4.4），计算指纹 = 文件大小 + sha256（头、25%、50%、75%、尾 5 段各 64 KiB）。读不了的记「读不了的文件」，仍建影像记录：按种类不记的字段为不适用，其余为缺失，读取状态记为失败；打不开或读不出字节的没有指纹，字节能读、只是解析事实失败的仍计算指纹（可参与 §4.2.1 第 2 行）；失败的结果不沿用，下次导入即使大小、mtime_ns、inode 都未变也重读，读成功后更新事实、不再记该异常（spec AC-005-1）。继续下一个。结果流式写入 `stage_file`
5. **国图清单与 10-21 执行记录**：解析 `manifest.json` / `report.json` / `index.json`（§4.6），解析白名单内的执行记录（§4.5）
6. **影像身份**（§4.2.1）、**写卷单元**（§4.2.2）、**归并与写卷身份**（§4.2.3）、**规则**（§4.4）：写卷、编号、影像关系、谱系、许可、出处认定初值、合并建议、异常
7. **应用**：以上结果在一个事务中写入正式表，派生字段有变化的写入 `history`；任何一步失败则整批回滚，`import_run` 记为 failed，正式表保持上一次的状态。写卷的 grouping_key、影像的（根，相对路径）有变化的，先在同一事务中改为临时值（grouping_key 置空，影像位置加临时前缀），再写入新值，编号或位置互换时不违反唯一约束（AC-003-9）
8. 停止健康采样；生成报告与基线对照（`report.py`），写回 `import_run`；成功后执行 `pg_dump` 备份；释放锁，丢弃内存中的登录状态

### 4.2 身份与归并（R-002、R-003）

**4.2.1 影像身份**（spec R-003 影像第 1～4 条；AC-003-1、AC-003-2、AC-003-7、AC-003-9、AC-009-2、AC-009-3、AC-009-5）

在每个根内分别进行。库中每条影像（present 或 missing）都有位置：最后一次被发现时的（根，相对路径）。按下表顺序认领，被认领的影像与文件不再参与后面的行：

| 顺序 | 情形 | 判定 |
|---|---|---|
| 1 | 文件所在（根，相对路径）上有一条影像，大小、mtime_ns、inode 都与文件相同（有几条时取末见批次最新者） | 同一影像，位置不变；上次读取成功的沿用已有事实与指纹，失败的重读（§4.1 第 4 步） |
| 2 | 其余文件。候选 = 同根、未被认领的影像中，inode、大小、mtime_ns、指纹都与文件相同者；文件恰有一个候选，且该候选恰对应这一个文件 | 同一影像（改名、移动或互换位置），写路径历史 |
| 3 | 其余文件：所在（根，相对路径）上末见批次最新的那条影像未被认领 | 同一影像，内容变化：重读事实与指纹，写变化历史 |
| 4 | 其余文件 | 新影像；存在部分相符（同根同 inode、任一根下大小与指纹相同、或第 2 行的候选不唯一，含硬链接）时记「身份待确认」，注明疑似的原影像 |
| — | 未被认领的 present 影像 | 标为 missing，记缺失时间，不删除；已是 missing 的保持不变 |

第 1～3 行认领到 missing 影像时，状态改为 present，记「重新出现」（spec 第 4 条）。

与 spec 的对应：第 1、2 行即 spec 的「可确认是同一文件」，合起来是 spec 第 1 条：第 1 行是第一步（按位置认定，视为内容未变，沿用已有事实与指纹，spec §5 Q-047），第 2 行是第二步（在未被认领的文件与影像之间判定一一对应）；一对已登记的硬链接只改名其一时，不动的一个在第 1 行认领，改名的一个在第 2 行认到另一条影像。没有指纹的文件（打不开或读不出字节）不参与第 2 行。一个位置上可能同时有一条 present 与几条 missing 的记录（另一条影像移入、覆盖了原文件时），第 1 行在其中取末见批次最新者，这是 spec 第 1 条在该极端情形下的实现选择。第 3 行即 spec 第 2 条：位置上原有的影像已被第 1、2 行认到别处（移走了）时，该位置上的文件按第 4 行作新影像。拼接工作台以临时文件 + 原子替换覆盖 `合并长卷.tif`，新文件的 inode 与指纹对不上任何影像，落到第 3 行（AC-009-3）。两个目录整名互换时，同名文件在第 2 行各自认到对方原来的影像（AC-003-9）。

依据：

- 2026-10-27 核查：原图目录与备份目录所在文件系统为 btrfs，两个根目录的 `st_dev` 不同（在 btrfs 上即不同子卷，inode 号各自独立），故只在同根内比较
- 设计说明（未在 NAS 上实测）：btrfs 按递增分配 inode 号、不复用已删除的号（只有重新挂载后，最近删除的最高号可能被再用）；同一子卷内改名或移动保留 inode 与 mtime_ns（POSIX rename）
- 复用 inode 的新文件通常 mtime_ns 不同；以保留时间戳的方式复制时可能相同，这时仍要求大小与 5 段指纹都相同才延续
- 大小、mtime_ns 与 5 段内容都相同、只有未采样部分不同的替换文件无法区分，按 spec §5 Q-030 接受
- 第 1 行不重读内容：原地改写而大小不变、mtime_ns 又被还原的文件不会被发现，按 spec §5 Q-047 接受

**4.2.2 写卷单元**（spec §1 术语；AC-001-3、AC-002-2、AC-002-3、AC-002-7）

1. 批次层按 `rules.py` 的登记表判定；未登记的分类按「没有批次层」处理；有批次层的分类中出现登记表以外的批次目录时，照常作批次目录处理；两种情况都在报告中提示
2. 写卷目录 = 批次目录（没有批次层时为分类目录）下的一级子目录。不在任何写卷目录中的影像文件（直接放在批次目录或分类目录里）各成一个单元，编号取自文件名（2026-10-27：`2018年` 中 7 个 TIFF、1 个 PSB）；直接放在原图根目录的文件记入 `excluded`；直接放在分类或批次目录中的附件作为不关联写卷的附件导入（2026-10-27 晚出现 1 个：`A077-敦煌文献目录/目录.txt`）
3. 写卷目录之下逐层判定子目录（名称精确匹配词表）：
   - 分段类、版本类、国图 `pages/`：并入所在单元，沿用该单元的编号；其下的子目录继续按本条判定
   - 词表外且含可导入影像（直接或更深层）：自成单元，编号取自它自己的名称（不继承父目录）；记「词表外子目录」；其下的子目录相对于它继续按本条判定
   - 不含可导入影像：整体记入 `excluded`（原因「不含影像」，如国图 `tiles/`）；其中的附件归入所在单元，没有所在单元时作为不关联写卷的附件导入
4. 写卷目录（连同词表内子目录）没有可导入影像、只有附件时：不建单元，附件作为不关联写卷的附件导入，记「缺少影像」；没有附件时整个目录记入 `excluded`，其中的文件逐一列出原因
5. 隐藏影像照常归入所在单元；一个目录中同时有隐藏与非隐藏影像时，对每个隐藏影像记「隐藏文件与非隐藏影像同目录（待确认）」（2026-10-27 为 10 个）
6. 备份目录：把相对路径映射为原图目录中的同一路径，按第 1～3 条确定所属单元（映射路径上已不存在的子目录按名称照常判定，706 个分片属于这种情况），角色「已迁出的分片」，记录原位置；写卷目录在原图目录中也不存在时，按备份目录中的写卷目录自成单元，并记「备份分片对不上」。原图目录中的写卷目录改名后，按旧名映射的分片落到这一分支，该写卷可能因几个单元结果不同而记「规则要求拆分」（spec R-002 规则 7）
7. 每个单元按 §4.3 解析编号，得到合规馆藏号集合 K(U) 与其余编号；国图另取清单 Pressmark（§4.6）。K(U) 为空的单元记「无馆藏号的写卷单元」，并参与合并建议：名称只差「上部 / 下部」「上卷 / 下卷」「紙背」、使用同一分享者自编号、使用同一《开宝藏》帙号的单元，成对记「合并建议」（AC-002-6）

**4.2.3 归并与写卷身份**（spec R-002，R-003 写卷第 1～7 条；AC-002-1、AC-002-4～AC-002-6、AC-002-8、AC-003-4～AC-003-6、AC-003-8～AC-003-11）

记号：S0 = 导入前的状态（写卷的 grouping_key 记为 key0，以及影像与写卷的关联）；本次每个单元 U 有影像（已有 / 新）与 K(U)；P(U) = U 中本次在磁盘上的已有影像（含重新出现的，§4.2.1）在 S0 中关联的写卷，即 spec 的「单元中的写卷」。A～D 只读 S0 与本次的单元，算出全部结果后在 §4.1 第 7 步一次写入，与单元的处理顺序无关。

- **A. 单元判定**（第 1、2 条），对每个 P(U) 非空的单元：
  - 持有：held(U) = P(U) 中 key0 属于 K(U) 的写卷，结果为「保持」
  - H(U) = K(U) 中不被 held(U) 持有的编号；L(U) = P(U) 中不持有 K(U) 任何编号的写卷
  - K(U) 为空：P(U) 只有一件时，结果为「去掉主编号」；有几件时，其中有主编号的结果为「待确认」，没有主编号的为「保持」（spec 写卷第 2 条）
  - H(U) 与 L(U) 各恰有一个：该写卷结果为「改用 h」
  - L(U) 为空：H(U) 是新增编号，留到 D
  - 其余：L(U) 中每件结果为「待确认」
- **B. 写卷判定**（第 3 条），对 S0 中每件写卷 X：
  - 本次没有在磁盘上的影像：key1 = key0（AC-009-2）
  - 有单元给出「待确认」：key1 = key0，记「身份待确认」；各单元的结果不止一种时，同时记「规则要求拆分」（spec 写卷第 3 条）
  - 否则，X 所在全部单元的结果给出同一个 key：采用为 key1（「保持」「改用 h」「去掉主编号」）
  - 否则（结果不同）：key1 = key0，记「规则要求拆分」，各单元给出的编号作为待确认编号记在 X 上（AC-003-6）
- **C. 同号处理**（第 4 条，不合并；AC-003-5）：只看非空的 key1，没有主编号的写卷不参与。重复执行，直到没有两件写卷的 key1 相同：找出 key1 相同的各组，组内凡是 key1 ≠ key0（本次改用了编号）的写卷都退回 key1 = key0，记「身份待确认」并注明同号的写卷，被拒的编号作为待确认编号记在该写卷上。S0 中非空的 key0 互不相同，所以每组至少有一件可退回，退回的写卷不再变化；每轮按组整体处理，结果与顺序无关，至多执行写卷件数轮。C 结束后 key1 即最终的主编号，改用生效的写卷把旧编号转入编号历史（AC-003-4）
- 含有被记「身份待确认」或「规则要求拆分」的写卷（含 C 退回的）的单元都是待确认单元，其余为正常单元
- **D. 关联与新建**（第 5～7 条），owner(k) = C 之后持有 k 的写卷：
  - P(U) 为空的单元（首次导入、新目录，或已有影像都不在磁盘上）：K(U) 中每个 k，owner(k) 存在则关联 U 的全部影像，否则新建写卷（key = k）再关联（R-002 规则 1、4）；K(U) 为空时新建一件没有主编号的写卷（规则 6）
  - 正常单元：新影像关联到 K(U) 中每个编号的 owner；H(U) 中的新增编号按上一条处理，关联 U 的全部影像（第 6 条）
  - 名称中没有合规馆藏号的单元与待确认单元：已有影像保持原关联；新影像归入 P(U) 中在 U 内已有影像最多的写卷，并列取 serial 最小者；待确认单元的 H(U) 本次不处理
  - 同一个新 key 只新建一件写卷，几个单元共用同一个新 key 时都关联到它
  - 已有影像与写卷的关联只在 D 的新增编号中增加，不移除（第 7 条）
  - 本次新建写卷的 serial 按 key 排序依次分配（没有 key 的按单元相对路径排序），与遍历顺序无关
- **E. 收尾**：按 key 重算分件的 parent_id（`pelliot:2504:1` 的母号为 `pelliot:2504`；母号没有写卷时为空，AC-002-5）；多编号单元的写卷记「名称所示的合装或缀合」线索（AC-002-4）；每件写卷的其余编号（分享者自编号、帙号、存疑编号、IDP 条目 ID）取它的影像所在单元的其余编号，每次导入按单元当前名称与清单重新解析，变化的旧值转入编号历史（spec R-004、R-013）

### 4.3 编号解析与合规判定（R-004）

只解析单元的编号来源（§4.2.2 第 2、3、7 条：写卷目录名、散放文件名、词表外子目录名、国图 Pressmark）；写卷目录内的文件名（如 `2660-1.tif`）不解析编号。

| 体系 | 识别的写法（例） | 规范写法 | 合规判定与用途 |
|---|---|---|---|
| 伯希和汉文写卷号 | `P2602`、`P.2033`、`P. 0901`、`p.2731`、`Pelliot chinois 2002` | `P.2602` | 号段内为合规，作主编号与归并依据；号段外为存疑：可检索，不作主编号、不作归并依据，记「编号存疑」 |
| 伯希和分件 | `-1`、`-1Pièce`、`-P2`、`A` / `B` / `a` | `P.2504-1`、`P.2842-2`、`P.2222A`（字母取大写；比较与查询不区分大小写） | 母号 = 不带分件的号；合规性随母号 |
| 多号 | `P3012+5564`、`P2661(+3735)` | 各成一号 | 第二个号省略「P」也识别 |
| 国图 BD 号 | 清单 Pressmark；目录名 `BD00001`、`BD00023a` | 以 Pressmark 的写法为准 | 有清单：Pressmark 为馆藏号，目录名与之不一致（比较时不区分大小写）时目录名记为存疑并记「编号与清单不一致」；Pressmark 本身写法不合规时两者都记为存疑并记该异常；无清单：目录名写法合规（BD + 5 位数字 + 可选字母）即用，并记「缺少清单」；查询不区分大小写 |
| 分享者自编号 | `WB 15`、`WB15`、`WA9` | `WB 15`、`WA 9` | 不作主编号、不作归并依据，只提合并建议 |
| 《开宝藏》帙号 | 「令字」「存字」「李字」等 | `令` 等 | 只在目录名或同目录 PSB 文件名含「開寶藏 / 开宝藏」，或目录名以「敦煌藏經洞 + 序号」开头时识别（避免把「小字法华经」的「小字」误认作帙号）；不作主编号与归并依据 |
| IDP 条目 ID | 清单 `id` 末段 | 原样 | 外部编号 |
| 疑似编号 | 独立的 4 位数字：前后不紧邻数字、字母、`.`、`,`、`×`、`x`、`*`，后面不接 `cm`、`mm`、`年`、`×`、`x`（中间可隔空格），不是多号写法中的后一个号，且落在汉文号段内 | — | 不解析，记「疑似编号」；2026-10-27 命中 2 处：`4518(35)`、散放 PSB 名中的 `2178` |

主编号：每件写卷最多一个，只取合规馆藏号；母号与分件各自为主编号（AC-004-5）。

### 4.4 规则表（`rules.py`）

**事实字段**（AC-005-1）：

| 种类 | 有值或缺失 | 不适用 |
|---|---|---|
| TIFF | 像素尺寸、通道数（SamplesPerPixel）、色彩模式（Photometric）、位深（BitsPerSample）、分辨率（X/YResolution 与单位）、压缩方式（Compression）、软件标签（Software） | — |
| PSB | 像素尺寸、通道数、色彩模式、位深（取自文件头） | 分辨率、压缩方式、软件标签 |
| JPG | 像素尺寸、通道数、色彩模式、位深（取自 SOF 段）；分辨率（文件内有 JFIF / EXIF 分辨率时有值，否则缺失） | 压缩方式、软件标签 |

**角色**（按顺序取第一条命中；文件名比较时去掉开头的点，AC-002-2、spec R-001；文件种类先于文件名，`合并长卷.psb` 仍是 PSB 源文件）：

1. `.psb` → PSB 源文件
2. 文件名以「合并长卷」开头的 TIFF → 合并长卷
3. 备份目录中的影像 → 已迁出的分片
4. 国图 `pages/*.jpg` → 页图
5. `*_preview.jpg`、版本类子目录中的影像 → 另一版本
6. 分段类子目录中的影像 → 分段
7. 单元中其余的 TIFF：只有一个 → 单幅整卷，多于一个 → 各为分段（PSB、JPG、合并长卷与备份分片不计入个数）

**谱系**（逐个文件，文件名比较时去掉开头的点，AC-005-2）：

| 条件（按顺序） | 谱系 |
|---|---|
| 属于国图分类（含页图、预览图） | 国图 IDP 下载 |
| `.psb` | 第三方加工图（分享者的工作文件，plan.md §1.3；文件名以「合并长卷」开头的 PSB 也是） |
| TIFF 文件名以「合并长卷」开头，或出现在 10-21 执行记录的输出中 | 本地合成 |
| 其余 TIFF 中读取失败的（文件名之外的依据无从核实） | 未判定（已记「读不了的文件」，不另记「谱系未判定」；读成功后按下面两行重判，变化记入 `history`） |
| 文件名为 `native.tif` / `native(n).tif`，且软件标签缺失 | BnF 原图 |
| 软件标签有值（Photoshop 等） | 第三方加工图 |
| 其他 | 未判定（记「谱系未判定」） |

目录级汇总（报告用）：只计影像目录直接包含的 TIFF / BTF；谱系一致时取该谱系，不一致时记「混合」。

拼接工作台中断后残留的临时文件（`.合并长卷_building_<时间戳>.tif`，`app.py` 拼接输出）按普通的隐藏 TIFF 导入：角色合并长卷、谱系本地合成，并记「派生来源不明」与「隐藏文件与非隐藏影像同目录」，由人工清理；这是预期行为。

**来源与许可**（D-012，AC-006-1～3）：

| 谱系 | 收藏机构 | 获取渠道 | 许可 | 署名 | 展示策略 | 对外策略 |
|---|---|---|---|---|---|---|
| 国图 IDP 下载 | 中国国家图书馆 | IDP IIIF 下载（2026-10-21 起） | IDP：个人或非商业复用 | 清单 requiredStatement（The National Library of China）；没有清单时取 D-012 的默认署名，依据记为默认规则 | 登录墙内可展示 | 链接 IDP |
| BnF 原图 | 法国国家图书馆 | 第三方资料接收（接收事件 A） | Gallica：非商业免费复用，注明出处 | Source gallica.bnf.fr / BnF | 登录墙内可展示 | 链接 Gallica / IDP |
| 第三方加工图 | 有合规伯希和号时推断为法国国家图书馆（字段依据的置信度为「推断」，spec AC-006-1），否则未知 | 第三方资料接收（接收事件 A） | 未知（第三方衍生） | 无 | 仅供研究使用 | 不对外 |
| 本地合成 | 继承源影像 | 本地生成（2026-10-21 脚本或拼接工作台） | 继承源影像中最严格的一项；来源不明时为未知 | 同源影像 | 同源影像中最严格的一项 | 同左 |
| 未判定 | 未知 | 按所在根目录与分类推断（转存或下载） | 未知 | 无 | 仅供研究使用 | 不对外 |

严格程度：许可 未知 > IDP（个人或非商业）> Gallica（非商业）；展示策略 仅供研究使用 > 登录墙内可展示。写卷的展示策略取其全部影像中最严格的一项（AC-006-2）。

**出处认定**（AC-007-1～4）：

1. 已有判定者为 `user:` 的结论 → 保留不动
2. 收集证据：合规伯希和号或 BD 号；非敦煌线索——目录名或同目录 PSB 名含「開寶藏 / 开宝藏」或以「敦煌藏經洞 + 序号」开头、识别出《开宝藏》帙号、题名含「清光绪 / 清光緒」「尖山刻经 / 尖山刻經」「室町」「竹生島経 / 竹生岛经」「紫紙金字 / 紫纸金字」「大橋家来翰集」
3. 只有合规馆藏号 →「已确认」；有非敦煌线索 →「待核」并附「建议：非敦煌」；两者都有 →「待核」，依据中同时列出，并记「出处证据冲突」；两者都没有 →「待核」
4. 规则永远不直接给出「非敦煌」

### 4.5 合并长卷的派生来源（AC-005-3、AC-012-2）

只按名字直接打开 v0 `cache/` 根目录下的这些文件，不列目录、不递归：`merge_all.log`、`merge_smart_all.log`、`merge_extra.log`、`psb_convert.log`、`psb_convert_all.log`、`psb_convert_7.log`、`psb_conv_wb5back.log`、`seg_move_log.txt`、`samefolder_move_log.txt`、`extra_move_log.txt`、`seg_move_plan.json`、`samefolder_plan.json`、`validated_moves.json`（2026-10-27 按名核查，13 个都在）。对 `/v0cache` 的访问只经过 `derivation.py` 的统一打开函数，测试中记录导入期间全部被打开的路径（AC-012-2）。

- 拼接日志：「开始: <相对目录>」之后列出的分片名 → 源分片（迁出后在备份目录的镜像位置），「完成: …/合并长卷.tif」→ 派生影像
- PSB 转换日志：「转换: <相对目录>」与「PSBNAME」→ 源 PSB，「已替换合并长卷.tif」→ 覆盖之前的拼接结果
- 同一个合并长卷以时间上最后一次成功的操作为准；证据记录日志文件名与行号
- 对不上的、白名单文件不存在或读不了的，记「派生来源不明」（注明原因），导入不因此失败

### 4.6 国图清单（AC-004-3、AC-005-4）

- `manifest.json`：Pressmark → 馆藏号；`id` 末段 → IDP 条目 ID；`requiredStatement` → 署名；`items[n].id` → 画布 ID
- `report.json`：`strips[i].file` → 本地 TIFF 与画布序号 `strips[i].index`；`strips` 不是列表（如 0）时，按本地 TIFF 文件名中的序号（`BDxxxxx_NNNN_n.tif` 的 NNNN）对应，仍对不上的记「画布对不上」
- `pages/NNNN_WxH.jpg`：文件名前缀 NNNN → 画布序号
- 三份 JSON 都原样存为附件（2026-10-27：`manifest.json` 与 `report.json` 各 5,140 个，`index.json` 66 个）

### 4.7 认证与 v0 接触（AC-001-1、AC-011-1、AC-011-4、AC-012-2、AC-012-3）

- **`AUTH_SECRET`**：从只读挂载的 v0 `.env` 中只读取这一项（不把 `AUTH_USER` / `AUTH_PASS` 注入目录服务）；缺失时所有请求返回 503（fail-closed）
- **请求校验**：cookie `dh_session` 按 v0 的格式验证——base64url(`用户|过期时间|HMAC-SHA256(AUTH_SECRET, "用户|过期时间")`)，未过期，且用户在 `users.json` 中（architecture.md §7）；管理员 = `admin: true`。`users.json` 只由请求校验读取（按修改时间缓存），导入过程不打开它
- cookie 不区分端口，在 8503 登录 v0 后即可访问 8504
- **防跨站请求**：v0 的 cookie 为 `SameSite=Lax`，跨站的 POST 不会带上它；`POST /api/v1/imports` 另校验请求头 `Origin`：存在时必须属于 `DH_ALLOWED_ORIGINS`（默认 `http://192.0.2.10:8504`、`http://192.0.2.20:8504`），否则 403；服务不返回任何 CORS 头
- **调用 v0**（经 NAS 局域网地址，配置项 `DH_V0_URL`，默认 `http://192.0.2.10:8503`）：
  - 导入只经接口触发，使用该请求自带的 `dh_session`（即触发者自己的登录状态），只保存在导入线程的内存中，不写日志、不落库，导入结束即丢弃；目录服务不签发会话，也不提供命令行导入（没有登录状态就无法按 AC-012-3 判定 v0 健康）
  - 触发前检查登录状态的剩余有效期（cookie 中的过期时间）不少于 90 分钟（全量导入上限 1 小时 + 让路上限 10 分钟 + 余量），不足时拒绝并提示重新登录；导入中健康采样返回 401（如账号被删）按失败计
  - 索引快照：`GET /api/index`，有效条件见 §4.1 第 2 步
  - 健康采样：导入期间每 5 秒 `GET /api/health`，2 秒内返回 200 且 `ok` 为 true 记为正常；采样汇总（次数、失败数、最大耗时）写入 `import_run`（AC-012-3）
  - 让路（spec AC-012-3）：连续 3 次采样失败即暂停读文件，连续 3 次正常后继续；暂停累计超过 10 分钟则中止导入（failed，回滚，正式表保持上一次的状态）
- **v0 链接**（AC-011-4）：取最近一次成功、且快照有效的导入的 `v0_volume`（失败或中止的导入留下的快照不用），只为其中有、且本次导入时磁盘上仍存在的影像目录中的 TIFF 影像生成 `<DH_V0_PUBLIC_URL>/view/<base64url(相对目录)>`；散放文件附带 `?file=<文件名>`（v0 忽略该参数，仅供人看）；其余写明不给链接的原因（备份分片、JPG、PSB、不在 v0 索引中、从未取得有效索引）。`DH_V0_PUBLIC_URL` 默认同 `DH_V0_URL`

### 4.8 部署与运行（D-018）

| 服务（容器） | 镜像 | 内存（= memswap） | 挂载 | 其他 |
|---|---|---|---|---|
| `catalog-db` | `postgres:17.4-alpine3.21` | 384m | pgdata → `/srv/example/pgdata` | 不对外暴露端口；`shared_buffers=64MB`、`max_connections=20`、`work_mem=4MB`；healthcheck `pg_isready` |
| `catalog-api` | 本仓库 `catalog/Dockerfile` | 512m | `/srv/example/data:/data:ro`、`/srv/example/backup:/backup:ro`、`/srv/example/cache:/v0cache:ro`、`/srv/example/viewer/.env:/run/v0.env:ro`、`/srv/example/catalog-backups:/backups` | 端口 8504→8000；`env_file: ./.env`（数据库密码、`DH_ALLOWED_ORIGINS` 等）；以 root 运行（`users.json` 为 root 600）；导入在本容器的后台线程中执行，受 512m 上限约束；`pg_dump` 用镜像内的 postgresql-client |

- 启动：`cd /srv/example/viewer/catalog && /usr/local/bin/docker-compose -p dunhuang-catalog up -d --build`（只作用于本项目，不影响 v0）
- 首次导入：管理员登录 v0 后打开 `http://192.0.2.10:8504/api/v1/docs`，执行 `POST /api/v1/imports`；导入只经接口触发（也可用带管理员 cookie 的 HTTP 请求调用）
- 备份：每次导入成功后 `pg_dump` 到 `/backups`，保留最近 7 份
- 上线前置：NAS `MemAvailable` ≥ 2 GB；首次全量导入放在低峰时段

## 5. 验收对应

| AC | 实现位置 | 验证方式 |
|---|---|---|
| AC-001-1 | `v0.py` 索引快照、`report.py` | `tests/test_import.py::test_v0_index_coverage`（模拟 v0：索引落后于磁盘、索引中有已删除目录）、`test_import.py::test_v0_index_unavailable`（调用失败、`status` 不是 ready）；NAS A1 |
| AC-001-2 | `scan.py`、`importer.py` | `test_scan.py::test_image_inventory_complete`；NAS A2 |
| AC-001-3 | `scan.py`、`units.py` §4.2.2 第 3、4 条、`nlc.py`、`item_attachment` | `test_import.py::test_attachments_imported_and_shared`（含子目录中的附件；只有附件的写卷目录中的附件、直接放在分类目录中的说明作为不关联写卷的附件导入，导入报告列出） |
| AC-001-4 | `scan.py`、`units.py`、`excluded` | `test_scan.py::test_excluded_listed_with_reason`（含 PDF、PNG 与下载中的临时文件） |
| AC-002-1 | `grouping.py` §4.2.3 D | `test_grouping.py::test_catalog_number_merged_across_lineages`；NAS A2（P.2002 的两套影像） |
| AC-002-2 | `units.py` §4.2.2 第 3 条、角色规则 | `test_units.py::test_subdir_vocabulary_and_unknown_subdir`（含父 P.2002 / 子 P.2003、`tiles/`）；NAS A2 |
| AC-002-3 | `units.py` §4.2.2 第 2 条 | `test_units.py::test_loose_files_are_units`；NAS A2（8 个） |
| AC-002-4 | `identifiers.py`、`grouping.py` §4.2.3 D、E | `test_grouping.py::test_multi_number_units_share_images`；NAS A2 |
| AC-002-5 | `identifiers.py`、`grouping.py` §4.2.3 E | `test_grouping.py::test_parts_and_parent`；NAS A2（P.2504 母号与 4 个分件） |
| AC-002-6 | `units.py` §4.2.2 第 7 条、`grouping.py` §4.2.3 C | `test_grouping.py::test_suggestions_only_for_non_catalog_units`；`test_grouping_identity.py::test_unnumbered_items_never_grouped`（无号单元、存疑号单元连续导入两次仍各自一件；两件写卷同时去掉主编号后仍是两件） |
| AC-002-7 | `units.py` §4.2.2 第 6 条 | `test_units.py::test_backup_fragments_mapped`（含只改原图目录 → 记「规则要求拆分」→ 再同步备份目录 → 编号更新）；NAS A2 |
| AC-002-8 | `identifiers.py`、`grouping.py` | `test_grouping.py::test_doubtful_numbers_not_merged`（含连续导入两次）；NAS A2（P.0901 的 3 个目录） |
| AC-003-1 | `identity.py`、`grouping.py`、`importer.py` | `test_identity.py::test_reimport_keeps_ids` |
| AC-003-2 | `identity.py` §4.2.1 第 2 行 | `test_identity.py::test_rename_and_move_within_root_keep_ids`（在临时目录中真实改名、移动，保留 inode 与 mtime_ns） |
| AC-003-3 | UUIDv4 生成 | `test_identity.py::test_ids_not_path_derived` |
| AC-003-4 | `grouping.py` §4.2.3 A、B | `test_grouping_identity.py::test_number_change_keeps_item_id` |
| AC-003-5 | `grouping.py` §4.2.3 C | `test_grouping_identity.py::test_number_collision_not_merged`（改名为另一件写卷持有的编号、两件同时改用同一个新编号、退回引起的连锁同号：ID 与主编号不变，记「身份待确认」并注明同号的写卷；目录名改回后下一次导入不再列入） |
| AC-003-6 | `grouping.py` §4.2.3 B | `test_grouping_identity.py::test_split_not_automatic`（一件写卷两个目录中的一个改名为别的编号；部分影像移入另一个有编号的目录：目录原有影像仍在时两类都记，已全部删除时只记「规则要求拆分」） |
| AC-003-7 | `identity.py` §4.2.1、`facts.py` 指纹 | `test_identity.py::test_uncertain_identity_not_continued`：用真实文件算真实指纹（同大小、5 段相同、未采样部分不同的两个文件），再与文件条目组合出 inode 复用且 mtime_ns 不同、重复副本、跨根同内容、一对多与多对一、新建的硬链接（文件都放在没有影像记录的位置）；另测一对已登记的硬链接一个不动、一个改名：不动的按位置认定，改名的延续另一条影像（spec Q-047）；另测两条已登记的硬链接都缺失后只恢复一条到没有影像记录的新位置：对应不唯一，作新影像并记「身份待确认」 |
| AC-003-8 | `grouping.py` §4.2.3 D | `test_grouping_identity.py::test_new_images_assignment` |
| AC-003-9 | `identity.py` §4.2.1、`grouping.py` §4.2.3（A～D 只读 S0）、`importer.py` §4.1 第 7 步 | `test_grouping_identity.py::test_swap_and_chain_order_independent`（纯函数：同一输入打乱单元顺序 20 次，结果含 serial 完全相同）；`test_identity.py::test_whole_name_swap_follows_files`（临时目录中经中转名真实互换两个目录的整个名称，目录中的 TIFF 同名；互换过程中导入与不导入，结果相同）；`test_import.py::test_number_swap_end_to_end`（数据库上从扫描起完整导入，不预先给出影像 ID：名称其余部分不同的互换、整名互换、三目录编号轮换、整体顺移到没有被持有的编号；不违反写卷编号与影像位置的唯一约束，写卷 ID 不变、编号分别更新） |
| AC-003-10 | `grouping.py` §4.2.3 A、D | `test_grouping_identity.py::test_multi_number_stable_add_and_rewrite` |
| AC-003-11 | `grouping.py` §4.2.3 A～D | `test_grouping_identity.py::test_unmatched_cases_kept_pending`（多编号单元两号同改；另一件写卷的全部影像移入有编号的目录，目录原有影像仍在、已全部删除两种；有编号写卷的全部影像移入已有其他写卷影像的无号目录） |
| AC-004-1 | `identifiers.py` | `test_identifiers.py::test_pelliot_variants_and_doubtful_numbers`（含 2026-10-27 的 2 处命中、尺寸与年份（含数字后隔空格接 `cm`）、多号写法，以及不解析的 `2660-1.tif`） |
| AC-004-2 | `identifiers.py`、`rules.py` 号段 | `test_identifiers.py::test_pelliot_ranges_and_doubtful_usage` |
| AC-004-3 | `nlc.py`、`identifiers.py` | `test_nlc.py::test_pressmark_authority_and_missing_manifest`（含 Pressmark 写法不合规、与目录名只差大小写） |
| AC-004-4 | `identifiers.py` | `test_identifiers.py::test_sharer_and_zhihao_systems` |
| AC-004-5 | `identifiers.py`、`grouping.py` | `test_identifiers.py::test_primary_only_compliant_catalog_numbers` |
| AC-005-1 | `facts.py`、事实字段表 | `test_facts.py::test_facts_by_kind_and_states`（合成 TIFF、PSB、JPG 的有值 / 不适用 / 缺失）、`test_facts.py::test_unreadable_file_anomaly`（读不了的 PSB、JPG 的不适用字段不变；字节能读而解析失败的仍有指纹；第一次读取失败、第二次读取成功而大小、mtime_ns、inode 都未变时，事实被更新、异常消除；读不了的 `native(n).tif` 第一次谱系为未判定、许可为未知，第二次读成功后变为 BnF 原图与 Gallica 条款，并写入 `history`） |
| AC-005-2 | `rules.py` 谱系、`report.py` 目录级汇总 | `test_lineage.py::test_lineage_rules_psb_and_mixed_summary`（含同目录的 `合并长卷.psb`、`.合并长卷.psb` 与 `合并长卷.tif`：分别验证谱系、角色与来源许可默认值；读不了的 TIFF 谱系为未判定）；NAS A3 |
| AC-005-3 | `derivation.py` | `test_derivation.py::test_stitch_and_psb_logs`（仿照格式的合成日志，含白名单文件缺失）；NAS A2（12 个合并长卷） |
| AC-005-4 | `nlc.py` | `test_nlc.py::test_canvas_mapping_with_and_without_strips`；NAS A4 |
| AC-005-5 | `item_image.set_key` | `test_grouping.py::test_image_sets_distinguishable` |
| AC-006-1 | `licensing.py` | `test_licensing.py::test_default_rules_table_explicit_values`（含第三方加工图收藏机构的推断与「推断」标记） |
| AC-006-2 | `licensing.py` | `test_licensing.py::test_item_policy_most_restrictive` |
| AC-006-3 | `licensing.py` | `test_licensing.py::test_channel_is_specific_event` |
| AC-007-1 | `provenance.py` | `test_provenance.py::test_every_item_has_provenance` |
| AC-007-2 | `provenance.py` 第 3 条 | `test_provenance.py::test_confirmed_only_without_counter_evidence` |
| AC-007-3 | `provenance.py`、`rules.py` 线索 | `test_provenance.py::test_non_dunhuang_suggestions_and_conflicts`；NAS A2（18 + 6 个目录） |
| AC-007-4 | `provenance.py` 第 1 条 | `test_provenance.py::test_human_conclusion_survives_reimport` |
| AC-008-1 | `scan.py`（原样保存名称） | `test_import.py::test_raw_names_verbatim` |
| AC-008-2 | `attachment` | `test_import.py::test_attachment_raw_roundtrip`（含不关联写卷的附件） |
| AC-009-1 | `importer.py` | `test_changes.py::test_new_files_appear` |
| AC-009-2 | `identity.py` §4.2.1 最后一行 | `test_changes.py::test_missing_marked_not_deleted` |
| AC-009-3 | `identity.py` §4.2.1 第 3 行、`history` | `test_changes.py::test_changed_file_history`；另测原地改写并还原 mtime_ns：按 spec Q-047 不发现变化（接受的限制） |
| AC-009-4 | `importer.py`、`import_run` | `test_changes.py::test_import_run_record`（含重新出现数） |
| AC-009-5 | `identity.py` §4.2.1 第 1～3 行 | `test_changes.py::test_reappearance_keeps_ids`（三次导入，删除用移入以 `#` 开头的回收站目录模拟：还原到原位置、原位置换成不属于任何已登记影像的新文件、还原后移到同一写卷单元中的另一位置；影像 ID 与写卷关联不变，记「重新出现」，不记「身份待确认」。另测：复制出的副本放到没有影像记录的位置 → 新影像并记「身份待确认」；原位置放入另一条已登记影像的文件 → 随文件延续那条影像，原影像仍缺失；真实硬链接 x、y，x 移入回收站并导入后把 y 改名为 x → 按位置认定为 Ix，Iy 缺失） |
| AC-010-1 | `report.py`；产生点：§4.1（v0 索引不可用、读不了的文件、未导入的文件）、§4.2.1（身份待确认）、§4.2.2（词表外子目录、缺少影像、隐藏文件与非隐藏影像同目录、备份分片对不上、无馆藏号的写卷单元、合并建议）、§4.2.3（身份待确认、规则要求拆分）、§4.3（编号存疑、疑似编号、编号与清单不一致、缺少清单）、§4.4（谱系未判定、出处证据冲突）、§4.5（派生来源不明）、§4.6（画布对不上） | `test_report.py::test_anomaly_categories_complete`（每个类别用一份合成数据触发，逐一断言） |
| AC-010-2 | `report.py`、`acceptance/baseline-2026-10-27.json` | NAS A2（基线全部条目对照，差异逐项说明写入 review.md） |
| AC-011-1 | `auth.py`、`api.py` | `test_api.py::test_auth_required_and_admin_import`（含 `Origin` 校验） |
| AC-011-2 | `api.py` `/resolve`、`identifiers.py` | `test_api.py::test_resolve_returns_all_matches`（编号历史与待确认编号不返回）；NAS A2（`P.2504` → 5 件） |
| AC-011-3 | `api.py`、索引 | `test_api.py::test_filters_and_pagination`；NAS A6（列表与详情分别统计 P95） |
| AC-011-4 | `v0.py` 链接 | `test_api.py::test_v0_links_from_latest_valid_snapshot`；NAS A7 |
| AC-011-5 | `api.py` | `test_api.py::test_no_mutating_routes`（检查路由表） |
| AC-012-1 | 只读挂载、`scan.py` | NAS A5：三个挂载均为只读（`docker inspect`）；原图与备份目录前后快照，变化逐项归因 |
| AC-012-2 | `derivation.py` 统一打开函数、`auth.py` | `test_scan.py::test_v0_cache_only_whitelist_opened`（记录导入期间全部被打开的路径：只有白名单文件，没有 `users.json`，没有列目录） |
| AC-012-3 | 容器 512m 上限、流式处理、`v0.py` 健康采样与让路（§4.7） | `test_v0.py::test_yield_pause_resume_abort`（模拟健康检查连续失败：暂停读文件、恢复后继续；累计超过时限即中止，正式表保持上一次的状态，导入记录为 failed）；`test_v0.py::test_session_lifetime_and_401`（剩余有效期不足 90 分钟时拒绝触发；导入中返回 401 按失败计）；`test_api.py::test_no_cli_import`（命令行不提供导入）；NAS A5：经接口触发的全量导入完成，容器未被 OOM 终止；导入记录中的 v0 健康采样全部正常 |
| AC-012-4 | 增量事实与指纹 | NAS A5：全量 ≤ 1 小时、无变化重跑 ≤ 10 分钟 |
| AC-013-1 | `trace.py`、各表的字段依据 | `test_trace.py::test_every_field_has_basis_and_author`（规则字段的作者为规则名与版本，不是触发者） |
| AC-013-2 | `trace.py` | `test_trace.py::test_confidence_labels` |
| AC-013-3 | `trace.py`、`history`、`/history` 接口 | `test_trace.py::test_value_at_any_run`（两次导入之间修改规则版本与文件，取回各批次的取值、来源与作者） |

## 6. 测试与验证

### 6.1 本机（Windows，Python 3.14）

不依赖数据库的单元测试：编号、规则、写卷单元、影像事实、影像身份、归并与写卷身份（纯函数：输入 S0 与单元，输出结果）、派生解析、许可、出处、认证签名。影像身份的测试在临时目录中真实地改名、移动、互换、删除与还原文件，从扫描开始计算，不预先给出影像 ID。用于快速反馈；运行时以容器内的 Python 3.12 为准。

### 6.2 NAS 临时测试环境（需你许可后才运行）

`docker-compose.test.yml`：tmpfs 上的 PostgreSQL（256m）+ 测试运行器（512m），运行完整的 pytest（含数据库与接口测试，以及 AC-003-9 在唯一约束下的完整导入测试），结束后 `down -v` 删除。不挂载原图目录，只用合成数据。

### 6.3 NAS 验收（部署后，需你许可；导入由你在接口文档页触发）

| 编号 | 内容 |
|---|---|
| A1 | 以快照有效的导入为准：v0 索引中、磁盘上仍存在的卷未对应到写卷的数量（须为 0）；分别列出 v0 尚未收录的影像目录与 v0 索引中已不存在的目录 |
| A2 | 基线对照：`baseline-2026-10-27.json` 包含 spec AC-010-2 列出的全部数字，逐项比较 |
| A3 | 谱系目录级汇总与 447 / 499 / 12 及国图 5,138 比较 |
| A4 | 国图 TIFF → 画布的对应率 |
| A5 | 安全与资源：三个挂载为只读；原图与备份目录前后快照（路径、大小、mtime），变化逐项归因于其他写入方；导入期间宿主机每 5 秒采样 `docker stats`；容器未被 OOM 终止；导入记录中的 v0 健康采样全部正常；全量与无变化重跑的耗时 |
| A6 | 列表查询与详情查询各 100 次（先预热 10 次，单并发顺序执行），分别统计 P95；任何错误计为不通过 |
| A7 | 随机抽 20 个 v0 链接，确认 v0 返回对应的卷 |

## 7. 风险与回滚

| 风险 | 应对 |
|---|---|
| NAS 内存紧张（plan.md RK-01） | 两个容器硬上限合计 896m；上线前确认可用内存 ≥ 2 GB；必要时下调 `shared_buffers` |
| 首次全量导入与 v0 争用磁盘 | 指纹只读 5 段各 64 KiB；增量跳过未变文件；健康采样失败即暂停读文件（§4.7） |
| 2026-10-21 执行记录格式不规整 | 解析不到的记异常（AC-005-3 允许），不臆测 |
| v0 会话格式变化导致认证失效 | 测试锁定 v0 的签名格式；v0 修改 cookie 时同步（D-018） |
| 导入期间持有管理员的登录状态 | 只用触发者自己的会话调用 v0 的两个只读接口；只在内存中、导入结束即丢弃；不签发会话；不提供命令行导入 |
| 跨站请求触发导入 | `SameSite=Lax` + `Origin` 校验 + 不返回 CORS 头（§4.7） |
| 规则误判（谱系、出处、归并） | 规则带名称与版本写入依据；人工结论不被覆盖；对不上的保持原样并列异常；已有写卷之间不自动拆分，也不自动合并 |
| 影像身份的残余误判（spec §5 Q-030） | 按文件延续只在同根、inode、大小、mtime_ns、5 段指纹全部相同且一一对应时成立；其余按位置延续或作新影像（§4.2.1） |
| 数据库损坏或丢失 | 目录可由原始材料重新导入；每次导入后 `pg_dump`，保留 7 份 |
| 回滚 | `docker-compose -p dunhuang-catalog down`；删除 `pgdata` 即完全移除；v0 没有任何改动 |

## 8. 实施里程碑（供 Tasks 拆分）

| 里程碑 | 内容 |
|---|---|
| M1 骨架 | 目录与锁定依赖、配置、数据库连接与迁移、测试夹具生成器 |
| M2 扫描、事实与单元 | `scan.py`、`facts.py`、`units.py`、暂存 |
| M3 编号、身份与归并 | `identifiers.py`、`identity.py`、`grouping.py` |
| M4 规则与外部记录 | `nlc.py`、`derivation.py`、`licensing.py`、`provenance.py`、`trace.py`、`v0.py` |
| M5 导入与报告 | `importer.py`、`report.py`、异常与基线对照 |
| M6 接口 | `auth.py`、`api.py` |
| M7 部署与验收 | compose、NAS 测试、部署、A1–A7、备份 |
