# Feature: catalog-foundation 目录底座 实施计划（plan.md）

> Plan 阶段产物：由 spec.md 生成的设计成果，包含具体实施细节。需求本身在 spec.md，此处不复制。
> 状态（2026-10-27）：第 2 版，对应 spec 第 2 版（待 Gate 1 再批准）。第 1 版的 Checklist 结果与本版的修订对照见 `checklist.md`。

## 1. 技术方案

- **架构落点**：前后端分离后的第一个后端服务「目录服务」（D-011、D-016、D-018），与 v0 并存、互不依赖；影像查看仍由 v0 提供
- **技术栈**：
  - Python 3.12 + FastAPI + uvicorn（D-018）
  - PostgreSQL 17.4（NAS 已有镜像 `postgres:17.4-alpine3.21`，D-016），驱动 psycopg 3（连接池）
  - 影像事实：tifffile 读 TIFF 标签，Pillow 读 JPEG 信息，PSB 头自行解析（只读文件头 26 字节）
  - 测试：pytest + httpx
- **依赖锁定**：`catalog/requirements.lock` 精确锁定；与 v0 共有的库取 v0 当前运行版本（plan.md RK-05：fastapi 0.144.0、starlette 1.8.0、uvicorn 0.54.0、pydantic 2.14.1、tifffile 2026.10.15、numpy 2.5.4、Pillow 13.0.0）；psycopg 在 T-01 取当时的稳定版并锁定
- **规则数据**：批次层登记、子目录词表、编号体系与号段、谱系、许可默认表、出处线索都集中在 `rules.py`，带版本号（如 `2026-10-27.2`），写入每条依据（R-013）；与 spec §1 术语一一对应
- **测试数据**：全部用合成数据（目录树、TIFF、PSB 头、JPEG、清单、仿照格式写的执行记录），不把 NAS 上的真实日志或文件放进仓库

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
│   ├── rules.py               # 规则数据（带版本号）
│   ├── identifiers.py         # 编号解析、规范化、合规判定
│   ├── scan.py                # 只读扫描：目录树、文件条目（含 inode）、附件、未导入清单
│   ├── facts.py               # 影像事实（有值 / 不适用 / 缺失）、多段指纹
│   ├── units.py               # 写卷单元的划分（批次层、写卷目录、子目录词表、散放文件、备份映射）
│   ├── identity.py            # 影像身份延续、写卷身份延续、合并与拆分检测
│   ├── grouping.py            # 写卷单元 → 写卷（R-002）、合并建议
│   ├── nlc.py                 # 国图清单：Pressmark、IDP 条目 ID、署名、画布对应
│   ├── derivation.py          # 2026-10-21 执行记录 → 合并长卷的派生来源
│   ├── licensing.py           # D-012 默认规则与继承
│   ├── provenance.py          # 出处认定初值、建议、证据冲突
│   ├── trace.py               # 字段依据与历史（R-013）
│   ├── v0.py                  # v0 会话签名、`/api/index` 快照、卷 ID 与链接
│   ├── importer.py            # 一次导入：暂存 → 计算差异 → 单事务应用 → 报告
│   ├── report.py              # 导入报告、异常清单、基线对照
│   ├── auth.py                # 校验 v0 会话 cookie 与用户表
│   ├── api.py                 # FastAPI：只读接口 + 管理员触发导入
│   └── __main__.py            # 命令行：migrate / import / report / health
├── acceptance/                # NAS 验收脚本 A1–A7（§6.3）与基线 baseline-2026-10-27.json
└── tests/                     # pytest；fixtures/ 生成合成目录树与合成文件条目
```

### 2.1 接口

全部接口都要求登录（AC-011-1）；容器健康检查用命令行 `python -m dh_catalog health`，不走 HTTP。

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| GET | `/api/v1/items` | 写卷列表；筛选 `system`、`lineage`、`provenance`、`has_anomaly`、`category`、`batch`；分页 `page`、`page_size`（≤ 200） | 登录 |
| GET | `/api/v1/items/{id}` | 写卷详情：编号（含历史）、影像（事实、谱系、角色、来源目录、派生、IIIF 画布、v0 链接或不给链接的原因）、来源与许可、出处认定及历史、原始记录、路径历史、母号与分件、字段依据；旧 ID 已并入时返回保留的写卷，并带 `merged_from` 说明 | 登录 |
| GET | `/api/v1/items/{id}/history?run=` | 写卷在指定导入批次时的取值（AC-013-3） | 登录 |
| GET | `/api/v1/resolve?q=` | 按编号查（任一写法、不区分大小写，含存疑编号），返回写卷列表（0～n 件）；母号返回母号写卷与全部分件 | 登录 |
| GET | `/api/v1/images/{id}` | 影像详情：事实、许可、路径历史、变化历史、字段依据 | 登录 |
| GET | `/api/v1/images/{id}/history?run=` | 影像在指定导入批次时的取值 | 登录 |
| GET | `/api/v1/attachments/{id}` | 附件原文，原样字节 | 登录 |
| GET | `/api/v1/anomalies` | 异常清单（含「未导入的文件」类别）；筛选 `run`、`category`；分页 | 登录 |
| GET | `/api/v1/imports`、`/api/v1/imports/{id}` | 导入记录与报告 | 登录 |
| POST | `/api/v1/imports` | 触发一次导入，后台执行；已有导入在跑时返回 409 | 管理员 |

接口文档（OpenAPI）在 `/api/v1/docs`，同样需要登录。

## 3. 数据与存储

PostgreSQL 数据目录在 `/srv/example/pgdata`，备份目录在 `/srv/example/catalog-backups`，都不在 v0 的部署目录（git 工作区）里。

| 表 | 主要字段 | 说明 |
|---|---|---|
| `import_run` | id、起止时间、状态、触发方式与人、规则版本、代码版本、v0 索引快照摘要、各类数量（jsonb）、基线对照（jsonb）、错误 | 每次导入一条（AC-009-4） |
| `item` | id（UUIDv4）、serial（登记顺序，自增）、grouping_key、parent_id、状态（active / merged）、merged_into、原始位置、展示策略、出处认定（状态、依据、判定者、时间、建议、建议依据）、线索（jsonb）、字段依据（jsonb） | 写卷；`grouping_key` 只给有合规馆藏号的写卷（如 `pelliot:2504:1`、`nlc:BD00023a`），在 active 写卷中唯一；「较早登记」按 serial 比较 |
| `identifier` | item_id、体系、原文、规范写法、母号、分件、出处、出处位置、主编号、合规 / 存疑、起止批次、字段依据 | 编号与编号历史（AC-003-4、R-004）；规范写法与母号建索引（不区分大小写） |
| `image` | id（UUIDv4）、根（data / backup）、相对路径、原始文件名、是否隐藏、种类（tiff / psb / jpg）、大小、mtime_ns、inode、指纹、事实（jsonb：每个字段为有值 / 不适用 / 缺失）、谱系、来源与许可五字段、对外策略、IIIF 画布序号与 ID、状态（present / missing）、首见 / 末见批次、缺失时间、字段依据 | 影像（R-005、R-006）；present 影像的（根，相对路径）唯一 |
| `image_path_history` | image_id、根、相对路径、起止批次 | 路径历史（AC-003-2） |
| `item_image` | item_id、image_id、角色、来源目录（set_key）、写卷单元、字段依据 | 写卷与影像的多对多：多编号单元的影像关联多件（AC-002-4），一件写卷可有多套影像（AC-005-5） |
| `item_attachment` | item_id、attachment_id | 附件与写卷的多对多（AC-001-3） |
| `attachment` | id、根、相对路径、种类（说明 / manifest / report / index）、原始字节、sha256、解码文本、编码 | 原始附件（AC-008-2） |
| `derivation` | 派生影像、源影像、方式（拼接 / PSB 转换）、证据（日志文件与行号） | 合并长卷的来源（AC-005-3） |
| `provenance_history` | item_id、状态、依据、判定者、时间、批次 | 判定者以 `rule:` 或 `user:` 开头（AC-007-4、AC-003-5） |
| `history` | 对象种类、对象 ID、批次、快照（jsonb）、字段依据（jsonb） | 写卷、影像、编号、关系的派生字段每次变化时记一条快照，按批次可查任一时刻的取值（AC-009-3、AC-013-3） |
| `anomaly` | 批次、类别、对象种类与 ID、路径、原文、说明 | 异常清单（AC-010-1） |
| `excluded` | 批次、根、相对路径、文件或目录、原因 | 未导入清单；接口中作为「未导入的文件」类别并入异常清单（AC-001-4、AC-010-1） |
| `v0_volume` | 批次、v0 卷 ID、相对目录 | 导入时刻的 v0 索引快照（AC-001-1、AC-011-4） |
| `stage_file` | 批次、根、相对路径、大小、mtime_ns、inode、是否隐藏、种类、事实（jsonb）、指纹 | 暂存表（UNLOGGED），每次导入前清空 |

**字段依据**（R-013）：jsonb，按字段记录 `{来源, 规则版本, 批次, 时间, 置信度}`；来源取值为 文件名解析 / 文件头 / 外部清单 / 执行记录 / 默认规则 / 人工，置信度取值为 确定 / 推断。

数据量：影像约 3.6 万行、写卷约 6,000 行，都在 PostgreSQL 的轻量范围内。

## 4. 关键流程

### 4.1 一次导入

1. 取得咨询锁，没取到就返回「已有导入在跑」；写入 `import_run`（running）
2. **v0 索引快照**：以 `users.json` 中第一个管理员的身份，用 `AUTH_SECRET` 签发一次性会话，调用 v0 `/api/index`，结果写入 `v0_volume`；调用失败时记「v0 索引不可用」异常，本次导入照常进行
3. **扫描**（只读）：遍历原图目录的 5 个分类与备份目录，跳过以 `@`、`#`、`.` 开头的目录并记入 `excluded`（`#recycle`、`@eaDir`、国图 `BD00081/.pages` 等）。按种类分类文件：`.tif` / `.tiff` / `.btf` / `.psb` 为影像，国图 `pages/*.jpg` 为页图，`*_preview.jpg` 为预览图，`.txt` 与国图三种 JSON 为附件；国图 `tiles/`、`.npy` 及其他文件记入 `excluded`。每个文件取得 大小、mtime_ns、inode
4. **事实与指纹**：（根，相对路径，大小，mtime_ns，inode）与库中记录相同的，沿用已有事实与指纹；否则读取事实（§4.4），计算指纹 = 文件大小 + sha256（头、25%、50%、75%、尾 5 段各 64 KiB）。读不了的记入异常，继续下一个。结果流式写入 `stage_file`
5. **国图清单与 10-21 执行记录**：解析 `manifest.json` / `report.json` / `index.json`（§4.6），解析白名单内的执行记录（§4.5）
6. **影像身份**（§4.2.1）与**写卷单元**（§4.2.2）、**归并与写卷身份**（§4.2.3）、**规则**（§4.4）：写卷、编号、影像关系、谱系、许可、出处认定初值、合并建议、异常
7. **应用**：以上结果在一个事务中写入正式表，派生字段有变化的写入 `history`；任何一步失败则整批回滚，`import_run` 记为 failed，正式表保持上一次的状态
8. 生成报告与基线对照（`report.py`），写回 `import_run`；成功后执行 `pg_dump` 备份；释放锁

### 4.2 身份与归并（R-002、R-003）

**4.2.1 影像身份**（按顺序判定，AC-003-1、AC-003-2、AC-003-7、AC-009-3）

| 情形 | 判定 |
|---|---|
| （根，相对路径）与库中一条 present 影像相同 | 同一影像；大小、mtime 或 inode 变化时更新事实，写变化历史 |
| 新路径，与库中本次未出现的某影像同根、同 inode、同指纹 | 同一影像（同根内改名或移动），写路径历史 |
| 新路径，与某影像同根、同 inode，但指纹不同 | 新影像（文件编号被复用），记「身份待确认」 |
| 新路径，与某影像指纹相同（不同根、不同 inode，或该影像仍存在） | 新影像（跨根移动或重复副本），记「身份待确认」并注明疑似的原影像 |
| 其他 | 新影像 |

**4.2.2 写卷单元**（spec §1 术语）

1. 批次层按 `rules.py` 的登记表判定；未登记的分类按「没有批次层」处理，并在报告中提示
2. 写卷目录 = 批次目录（或分类目录）下的一级子目录；直接放在批次目录里的影像，每个文件自成单元（AC-002-3）
3. 写卷目录下更深的目录按子目录词表精确匹配：分段类、版本类、国图 `pages/` 并入该写卷目录的单元；词表外的子目录自成单元，记「词表外子目录」异常（AC-002-2）
4. 备份目录中的相对路径映射回原图目录，归入对应单元，角色「已迁出的分片」，记录原位置；映射不到的记「备份分片对不上」（AC-002-7）
5. 每个单元从写卷目录名（散放文件取文件名；国图另取清单 Pressmark）解析编号（§4.3）；单元的合规馆藏号决定其目标 grouping_key（可以有多个：多编号单元）

**4.2.3 归并与写卷身份**（AC-002-1、AC-002-4～AC-002-6、AC-002-8、AC-003-4～AC-003-6）

1. 对每件已有的 active 写卷 X，找出「多数影像属于 X」的单元。若这些单元的非空目标 key 有两个以上不同值 → **需要拆分**：X 保持原样（单元仍归 X），新出现的编号作为待确认编号记在 X 上，记「规则要求拆分」异常
2. 否则，设这些单元的共同目标 key 为 k：
   - X 的 grouping_key 已是 k，或 k 为空 → 不变
   - 没有其他 active 写卷使用 k → X 改用 k，旧编号写入编号历史（AC-003-4）
   - 写卷 Y 已使用 k → X 与 Y 合并：保留 serial 较小者，另一件标 merged 并指向保留者；人工出处结论不冲突时合并保留，冲突时保留方不变，另一方写入历史并记「人工结论冲突」（AC-003-5）
3. 影像不属于任何已有写卷的单元：有目标 key 的按 key 找到或新建写卷（多编号单元关联每一件，写卷上记合装 / 缀合线索；分件写卷的 parent_id 指向母号写卷，如果有）；没有 key 的新建写卷
4. 平局（单元的影像平均分属两件写卷）取 serial 较小者
5. **合并建议**（不自动合并）：没有合规馆藏号的单元之间，名称只差「上部 / 下部」「上卷 / 下卷」「紙背」、使用同一分享者自编号、使用同一《开宝藏》帙号的，成对记「合并建议」（AC-002-6）

### 4.3 编号解析与合规判定（R-004）

| 体系 | 识别的写法（例） | 规范写法 | 合规判定与用途 |
|---|---|---|---|
| 伯希和汉文写卷号 | `P2602`、`P.2033`、`P. 0901`、`p.2731`、`Pelliot chinois 2002` | `P.2602` | 号段内为合规，可作主编号与归并依据；号段外为存疑：可检索，不作主编号、不作归并依据，记异常 |
| 伯希和分件 | `-1`、`-1Pièce`、`-P2`、`A` / `B` / `a` | `P.2504-1`、`P.2842-2`、`P.2222A` | 母号 = 不带分件的号；合规性随母号 |
| 多号 | `P3012+5564`、`P2661(+3735)` | 各成一号 | 第二个号省略「P」也识别 |
| 国图 BD 号 | 清单 Pressmark；目录名 `BD00001`、`BD00023a` | 以 Pressmark 的写法为准 | 有清单：以 Pressmark 为馆藏号，目录名与之不一致时记为存疑并记异常；无清单：目录名写法合规（BD + 5 位数字 + 可选字母）即用，并记「缺少清单」；查询不区分大小写 |
| 分享者自编号 | `WB 15`、`WB15`、`WA9` | `WB 15`、`WA 9` | 不作主编号、不作归并依据，只提合并建议 |
| 《开宝藏》帙号 | 「令字」「存字」「李字」等 | `令` 等 | 只在目录名或同目录 PSB 文件名含「開寶藏 / 开宝藏」，或目录名以「敦煌藏經洞 + 序号」开头时识别（避免把「小字法华经」的「小字」误认作帙号）；不作主编号与归并依据 |
| IDP 条目 ID | 清单 `id` 末段 | 原样 | 外部编号 |
| 疑似编号 | 没有前缀的数字，如 `4518(35)` | — | 不解析，记「疑似编号」异常 |

主编号：每件写卷最多一个，只取合规馆藏号；母号与分件各自为主编号（AC-004-5）。

### 4.4 规则表（`rules.py`）

**事实字段**（AC-005-1）：

| 种类 | 有值或缺失 | 不适用 |
|---|---|---|
| TIFF | 像素尺寸、色彩模式、位深、分辨率、压缩方式、软件标签 | — |
| PSB | 像素尺寸、通道数、位深、色彩模式（取自文件头） | 分辨率、压缩方式、软件标签 |
| JPG | 像素尺寸、色彩模式；分辨率（文件内有 JFIF / EXIF 分辨率时有值，否则缺失） | 压缩方式、软件标签 |

**角色**（按顺序取第一条命中，AC-002-2、spec R-001）：

1. 文件名以「合并长卷」开头 → 合并长卷
2. `.psb` → PSB 源文件
3. 备份目录中的影像 → 已迁出的分片
4. 国图 `pages/*.jpg` → 页图
5. `*_preview.jpg`、版本类子目录中的影像 → 另一版本
6. 分段类子目录中的影像 → 分段
7. 单元中其余的 TIFF：只有一个 → 单幅整卷，多于一个 → 各为分段（PSB、JPG 不计入个数）

**谱系**（逐个文件，AC-005-2）：

| 条件（按顺序） | 谱系 |
|---|---|
| 属于国图分类 | 国图 IDP 下载 |
| 文件名以「合并长卷」开头，或出现在 10-21 执行记录的输出中 | 本地合成 |
| 文件名为 `native.tif` / `native(n).tif`，且没有软件标签 | BnF 原图 |
| 有软件标签（Photoshop 等） | 第三方加工图 |
| 其他 | 未判定（记异常） |

目录级汇总（报告用）：影像目录内源影像谱系一致时取该谱系，不一致时记「混合」。

**来源与许可**（D-012，AC-006-1～3）：

| 谱系 | 收藏机构 | 获取渠道 | 许可 | 署名 | 展示策略 | 对外策略 |
|---|---|---|---|---|---|---|
| 国图 IDP 下载 | 中国国家图书馆 | IDP IIIF 下载（2026-10-21 起） | IDP：个人或非商业复用 | 清单 requiredStatement（The National Library of China） | 登录墙内可展示 | 链接 IDP |
| BnF 原图 | 法国国家图书馆 | 第三方资料接收（接收事件 A） | Gallica：非商业免费复用，注明出处 | Source gallica.bnf.fr / BnF | 登录墙内可展示 | 链接 Gallica / IDP |
| 第三方加工图 | 有合规伯希和号时为「法国国家图书馆（第三方加工）」，否则未知 | 第三方资料接收（接收事件 A） | 未知（第三方衍生） | 无 | 仅供研究使用 | 不对外 |
| 本地合成 | 继承源影像 | 本地生成（2026-10-21 脚本或拼接工作台） | 继承源影像中最严格的一项；来源不明时为未知 | 同源影像 | 同源影像中最严格的一项 | 同左 |
| 未判定 | 未知 | 按所在根目录与分类推断（转存或下载） | 未知 | 无 | 仅供研究使用 | 不对外 |

严格程度：许可 未知 > IDP（个人或非商业）> Gallica（非商业）；展示策略 仅供研究使用 > 登录墙内可展示。写卷的展示策略取其全部影像中最严格的一项（AC-006-2）。

**出处认定**（AC-007-1～4）：

1. 已有判定者为 `user:` 的结论 → 保留不动
2. 收集证据：合规伯希和号或 BD 号；非敦煌线索——目录名或同目录 PSB 名含「開寶藏 / 开宝藏」或以「敦煌藏經洞 + 序号」开头、识别出《开宝藏》帙号、题名含「清光绪 / 清光緒」「尖山刻经 / 尖山刻經」「室町」「竹生島経 / 竹生岛经」「紫紙金字 / 紫纸金字」「大橋家来翰集」
3. 只有合规馆藏号 →「已确认」；有非敦煌线索 →「待核」并附「建议：非敦煌」；两者都有 →「待核」，依据中同时列出，并记「出处证据冲突」异常；两者都没有 →「待核」
4. 规则永远不直接给出「非敦煌」

### 4.5 合并长卷的派生来源（AC-005-3、AC-012-2）

只按名字直接打开 v0 `cache/` 根目录下的这些文件，不列目录、不递归：`merge_all.log`、`merge_smart_all.log`、`merge_extra.log`、`psb_convert.log`、`psb_convert_all.log`、`psb_convert_7.log`、`psb_conv_wb5back.log`、`seg_move_log.txt`、`samefolder_move_log.txt`、`extra_move_log.txt`、`seg_move_plan.json`、`samefolder_plan.json`、`validated_moves.json`。文件访问经过一个统一的打开函数，测试中记录全部被打开的路径（AC-012-2）。

- 拼接日志：「开始: <相对目录>」之后列出的分片名 → 源分片（迁出后在备份目录的镜像位置），「完成: …/合并长卷.tif」→ 派生影像
- PSB 转换日志：「转换: <相对目录>」与「PSBNAME」→ 源 PSB，「已替换合并长卷.tif」→ 覆盖之前的拼接结果
- 同一个合并长卷以时间上最后一次成功的操作为准；证据记录日志文件名与行号；对不上的记「派生来源不明」

### 4.6 国图清单（AC-004-3、AC-005-4）

- `manifest.json`：Pressmark → 馆藏号；`id` 末段 → IDP 条目 ID；`requiredStatement` → 署名；`items[n].id` → 画布 ID
- `report.json`：`strips[i].file` → 本地 TIFF 与画布序号 `strips[i].index`；`strips` 不是列表（如 0）时，按本地 TIFF 文件名中的序号（`BDxxxxx_NNNN_n.tif` 的 NNNN）对应，仍对不上的记「画布对不上」
- `pages/NNNN_WxH.jpg`：文件名前缀 NNNN → 画布序号
- 三份 JSON 都原样存为附件

### 4.7 认证与 v0 接触（AC-011-1、AC-011-4）

- `AUTH_SECRET`：从只读挂载的 v0 `.env` 中只读取这一项（不把 `AUTH_USER` / `AUTH_PASS` 注入目录服务）；缺失时所有请求返回 503（fail-closed）
- 请求校验：cookie `dh_session` 按 v0 的格式验证——base64url(`用户|过期时间|HMAC-SHA256(AUTH_SECRET, "用户|过期时间")`)，未过期，且用户在 `users.json` 中（architecture.md §7）；管理员 = `admin: true`；`users.json` 按修改时间缓存
- cookie 不区分端口，在 8503 登录 v0 后即可访问 8504
- 容器内经 NAS 局域网地址访问 v0（配置项 `DH_V0_URL`，默认 `http://192.0.2.10:8503`）；链接中给用户的地址另设 `DH_V0_PUBLIC_URL`
- v0 链接：只为最近一次导入的 v0 索引快照中存在的卷生成 `/view/<base64url(相对目录)>`；散放文件附带文件名；其余写明不给链接的原因（备份目录、不在 v0 索引中）

### 4.8 部署与运行（D-018）

| 服务（容器） | 镜像 | 内存（= memswap） | 挂载 | 其他 |
|---|---|---|---|---|
| `catalog-db` | `postgres:17.4-alpine3.21` | 384m | pgdata → `/srv/example/pgdata` | 不对外暴露端口；`shared_buffers=64MB`、`max_connections=20`、`work_mem=4MB`；healthcheck `pg_isready` |
| `catalog-api` | 本仓库 `catalog/Dockerfile` | 512m | `/srv/example/data:/data:ro`、`/srv/example/backup:/backup:ro`、`/srv/example/cache:/v0cache:ro`、`/srv/example/viewer/.env:/run/v0.env:ro`、`/srv/example/catalog-backups:/backups` | 端口 8504→8000；`env_file: ./.env`（数据库密码）；以 root 运行（`users.json` 为 root 600）；导入在本容器的后台线程中执行，受 512m 上限约束；`pg_dump` 用镜像内的 postgresql-client |

- 启动：`cd /srv/example/viewer/catalog && /usr/local/bin/docker-compose -p dunhuang-catalog up -d --build`（只作用于本项目，不影响 v0）
- 首次导入：管理员 `POST /api/v1/imports`，或 `docker-compose -p dunhuang-catalog exec catalog-api python -m dh_catalog import`
- 备份：每次导入成功后 `pg_dump` 到 `/backups`，保留最近 7 份
- 上线前置：NAS `MemAvailable` ≥ 2 GB；首次全量导入放在低峰时段

## 5. 验收对应

| AC | 实现位置 | 验证方式 |
|---|---|---|
| AC-001-1 | `v0.py` 索引快照、`report.py` | `tests/test_import.py::test_v0_index_coverage`（模拟 v0 接口，含索引落后于磁盘的情形）；NAS A1 |
| AC-001-2 | `scan.py`、`importer.py` | `test_scan.py::test_image_inventory_complete`；NAS A2 |
| AC-001-3 | `scan.py`、`nlc.py`、`item_attachment` | `test_import.py::test_attachments_imported_and_shared` |
| AC-001-4 | `scan.py`、`excluded` | `test_scan.py::test_excluded_listed_with_reason` |
| AC-002-1 | `grouping.py` §4.2.3 | `test_grouping.py::test_catalog_number_merged_across_lineages` |
| AC-002-2 | `units.py` §4.2.2、角色规则 | `test_units.py::test_subdir_vocabulary_and_unknown_subdir`；NAS A2 |
| AC-002-3 | `units.py` | `test_units.py::test_loose_files_are_units`；NAS A2 |
| AC-002-4 | `identifiers.py`、`grouping.py` | `test_grouping.py::test_multi_number_units_share_images`；NAS A2 |
| AC-002-5 | `identifiers.py`、`grouping.py` | `test_grouping.py::test_parts_and_parent`；NAS A2（P.2504 的 4 个分件） |
| AC-002-6 | `grouping.py` §4.2.3 第 5 条 | `test_grouping.py::test_suggestions_only_for_non_catalog_units` |
| AC-002-7 | `units.py` §4.2.2 第 4 条 | `test_units.py::test_backup_fragments_mapped`；NAS A2 |
| AC-002-8 | `identifiers.py`、`grouping.py` | `test_grouping.py::test_doubtful_numbers_not_merged`；NAS A2（P.0901 的 3 个目录） |
| AC-003-1 | `identity.py`、`importer.py` | `test_identity.py::test_reimport_keeps_ids` |
| AC-003-2 | `identity.py` §4.2.1 | `test_identity.py::test_rename_and_move_within_root_keep_ids` |
| AC-003-3 | UUIDv4 生成 | `test_identity.py::test_ids_not_path_derived` |
| AC-003-4 | `identity.py` §4.2.3 第 2 条 | `test_identity.py::test_number_change_keeps_item_id` |
| AC-003-5 | `identity.py` §4.2.3 第 2 条 | `test_identity.py::test_merge_keeps_earlier_id` |
| AC-003-6 | `identity.py` §4.2.3 第 1 条 | `test_identity.py::test_split_not_automatic` |
| AC-003-7 | `identity.py` §4.2.1 | `test_identity.py::test_uncertain_identity_not_continued`（合成文件条目：重复副本、跨根同名同大小、inode 复用） |
| AC-004-1 | `identifiers.py` | `test_identifiers.py::test_pelliot_variants_and_unprefixed_numbers` |
| AC-004-2 | `identifiers.py`、`rules.py` 号段 | `test_identifiers.py::test_pelliot_ranges_and_doubtful_usage` |
| AC-004-3 | `nlc.py`、`identifiers.py` | `test_nlc.py::test_pressmark_authority_and_missing_manifest` |
| AC-004-4 | `identifiers.py` | `test_identifiers.py::test_sharer_and_zhihao_systems` |
| AC-004-5 | `identifiers.py` | `test_identifiers.py::test_primary_only_compliant_catalog_numbers` |
| AC-005-1 | `facts.py`、事实字段表 | `test_facts.py::test_facts_by_kind_and_states`、`test_facts.py::test_unreadable_file_anomaly` |
| AC-005-2 | `rules.py` 谱系、`report.py` 目录级汇总 | `test_lineage.py::test_lineage_rules_and_mixed_summary`；NAS A3 |
| AC-005-3 | `derivation.py` | `test_derivation.py::test_stitch_and_psb_logs`（仿照格式的合成日志）；NAS A2（12 个合并长卷） |
| AC-005-4 | `nlc.py` | `test_nlc.py::test_canvas_mapping_with_and_without_strips`；NAS A4 |
| AC-005-5 | `item_image.set_key` | `test_grouping.py::test_image_sets_distinguishable` |
| AC-006-1 | `licensing.py` | `test_licensing.py::test_default_rules_table_explicit_values` |
| AC-006-2 | `licensing.py` | `test_licensing.py::test_item_policy_most_restrictive` |
| AC-006-3 | `licensing.py` | `test_licensing.py::test_channel_is_specific_event` |
| AC-007-1 | `provenance.py` | `test_provenance.py::test_every_item_has_provenance` |
| AC-007-2 | `provenance.py` 第 3 条 | `test_provenance.py::test_confirmed_only_without_counter_evidence` |
| AC-007-3 | `provenance.py`、`rules.py` 线索 | `test_provenance.py::test_non_dunhuang_suggestions_and_conflicts`；NAS A2（18 + 6 个目录） |
| AC-007-4 | `provenance.py` 第 1 条 | `test_provenance.py::test_human_conclusion_survives_reimport` |
| AC-008-1 | `scan.py`（原样保存名称） | `test_import.py::test_raw_names_verbatim` |
| AC-008-2 | `attachment` | `test_import.py::test_attachment_raw_roundtrip` |
| AC-009-1 | `importer.py` | `test_changes.py::test_new_files_appear` |
| AC-009-2 | `importer.py` | `test_changes.py::test_missing_marked_not_deleted` |
| AC-009-3 | `identity.py` §4.2.1、`history` | `test_changes.py::test_changed_file_history` |
| AC-009-4 | `importer.py`、`import_run` | `test_changes.py::test_import_run_record` |
| AC-010-1 | `report.py`、`anomaly` 与 `excluded` | `test_report.py::test_anomaly_categories_complete` |
| AC-010-2 | `report.py`、`acceptance/baseline-2026-10-27.json` | NAS A2（基线全部条目对照，差异逐项说明写入 review.md） |
| AC-011-1 | `auth.py`、`api.py` | `test_api.py::test_auth_required_and_admin_import` |
| AC-011-2 | `api.py` `/resolve`、`identifiers.py` | `test_api.py::test_resolve_returns_all_matches` |
| AC-011-3 | `api.py`、索引 | `test_api.py::test_filters_and_pagination`；NAS A6（列表与详情分别统计 P95） |
| AC-011-4 | `v0.py` 链接 | `test_api.py::test_v0_links_only_for_indexed_volumes`；NAS A7 |
| AC-011-5 | `api.py` | `test_api.py::test_no_mutating_routes`（检查路由表） |
| AC-012-1 | 只读挂载、`scan.py` | NAS A5：三个挂载均为只读（`docker inspect`）；原图与备份目录前后快照，变化逐项归因 |
| AC-012-2 | `derivation.py` 统一打开函数 | `test_scan.py::test_v0_cache_only_whitelist_opened`（记录全部被打开的路径，确认没有列目录、没有打开白名单外的文件） |
| AC-012-3 | 容器 512m 上限、流式处理 | NAS A5：导入完成且内存峰值 ≤ 512 MiB；期间 v0 `/api/health` 全部正常 |
| AC-012-4 | 增量事实与指纹 | NAS A5：全量 ≤ 1 小时、无变化重跑 ≤ 10 分钟 |
| AC-013-1 | `trace.py`、各表的字段依据 | `test_trace.py::test_every_field_has_basis` |
| AC-013-2 | `trace.py` | `test_trace.py::test_confidence_labels` |
| AC-013-3 | `trace.py`、`history`、`/history` 接口 | `test_trace.py::test_value_at_any_run`（两次导入之间修改规则版本与文件） |

## 6. 测试与验证

### 6.1 本机（Windows，Python 3.14）

不依赖数据库的单元测试：编号、规则、写卷单元、影像事实、身份判定（合成文件条目）、派生解析、许可、出处、认证签名。用于快速反馈；运行时以容器内的 Python 3.12 为准。

### 6.2 NAS 临时测试环境（需你许可后才运行）

`docker-compose.test.yml`：tmpfs 上的 PostgreSQL（256m）+ 测试运行器（512m），运行完整的 pytest（含数据库与接口测试），结束后 `down -v` 删除。不挂载原图目录，只用合成数据。

### 6.3 NAS 验收（部署后，需你许可）

| 编号 | 内容 |
|---|---|
| A1 | 以导入时刻的 v0 `/api/index` 快照为准，统计未对应到写卷的卷（须为 0），并列出 v0 尚未收录的影像目录 |
| A2 | 基线对照：`baseline-2026-10-27.json` 包含 spec AC-010-2 列出的全部数字（含词表外子目录、P.2504 分件、12 个合并长卷、18 + 6 个线索目录、P.0901 的 3 个目录），逐项比较 |
| A3 | 谱系目录级汇总与 447 / 499 / 12 比较 |
| A4 | 国图 TIFF → 画布的对应率 |
| A5 | 安全与资源：三个挂载为只读；原图与备份目录前后快照（路径、大小、mtime），变化逐项归因于其他写入方；导入期间每 5 秒采样内存与 v0 健康；导入耗时 |
| A6 | 列表查询与详情查询各 100 次（先预热 10 次，单并发顺序执行），分别统计 P95；任何错误计为不通过 |
| A7 | 随机抽 20 个 v0 链接，确认 v0 返回对应的卷 |

## 7. 风险与回滚

| 风险 | 应对 |
|---|---|
| NAS 内存紧张（plan.md RK-01） | 两个容器硬上限合计 896m；上线前确认可用内存 ≥ 2 GB；必要时下调 `shared_buffers` |
| 首次全量导入与 v0 争用磁盘 | 指纹只读 5 段各 64 KiB；增量跳过未变文件；导入期间轮询 v0 健康，连续失败即暂停导入 |
| 2026-10-21 执行记录格式不规整 | 解析不到的记异常（AC-005-3 允许），不臆测 |
| v0 会话格式变化导致认证失效 | 测试锁定 v0 的签名格式；v0 修改 cookie 时同步（D-018） |
| 以管理员身份签发会话调用 v0 | 只在导入时调用只读的 `/api/index`，会话一次性、不落盘 |
| 规则误判（谱系、出处、归并） | 规则带版本号写入依据；人工结论不被覆盖；异常与合并建议交人工复核；不自动拆分 |
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
