# Feature: catalog-foundation 目录底座 实施计划（plan.md）

> Plan 阶段产物：由 spec.md 生成的设计成果，包含具体实施细节。需求本身在 spec.md，此处不复制。
> 状态（2026-10-28）：第 8 版，对应已获 Gate 1 批准并冻结的 spec 第 7 版（按 AGENTS.md §2「工程约束」精简；删去的内容见 spec §5 Q-025）。第 11 轮 Analyze 全部 12 项通过，现进入 Implement；各轮结果见 `checklist.md`。

## 1. 技术方案

- **架构落点**：前后端分离后的第一个后端服务「目录服务」（D-011、D-016、D-018），与 v0 并存、互不依赖；影像查看仍由 v0 提供
- **技术栈**：Python 3.12 + FastAPI + uvicorn（D-018）；PostgreSQL 17.4（NAS 已有镜像 `postgres:17.4-alpine3.21`，D-016），驱动 psycopg 3；影像事实用 tifffile 读 TIFF 标签、Pillow 读 JPEG 信息，PSB 只读文件头 26 字节；测试用 pytest
- **依赖**：`catalog/requirements.txt` 写精确版本（v0 的范围约束保持不动）；与 v0 共有的库取 v0 当前版本（plan.md RK-05）
- **规则数据**：批次层登记、子目录词表、编号号段、疑似编号、谱系、许可默认表、出处线索集中在 `rules.py`；每条规则有名称，整体带版本号（如 `2026-10-28.1`），作为字段依据的「作者」（R-013）
- **校验位置**（AGENTS.md §2 工程约束第 2 条）：外部输入只在入口校验——文件系统（`scan.py`）、国图清单与执行记录（`nlc.py`、`derivation.py`）、登录 cookie 与接口参数（`api.py`）、v0 的响应（`v0.py`）；之后传类型确定的值，内部不重复检查
- **测试数据**：全部合成（目录树、TIFF、PSB 头、JPEG、清单、仿照格式的执行记录），不把 NAS 上的真实日志或文件放进仓库

## 2. 模块设计

```
catalog/
├── README.md                  # 职责、入口、运行与验证
├── Dockerfile                 # python:3.12-slim + requirements.txt（apt / pip 源与 v0 一致）
├── requirements.txt
├── docker-compose.yml         # 项目 dunhuang-catalog：catalog-db、catalog-api
├── .env.example               # POSTGRES_PASSWORD 等（catalog/.env 不入库）
├── migrations/                # 0001_init.sql …，按序执行
├── src/dh_catalog/
│   ├── config.py              # 环境变量与路径
│   ├── db.py                  # 连接池、迁移、事务、咨询锁
│   ├── scan.py                # 只读扫描：文件条目、影像事实、附件、未导入清单
│   ├── units.py               # 写卷单元：批次层、写卷目录、子目录词表、散放文件、备份映射
│   ├── identifiers.py         # 编号解析、规范化、合规判定、疑似编号
│   ├── identity.py            # 影像身份与写卷归并（§4.2.1、§4.2.3）
│   ├── rules.py               # 规则数据与谱系、角色、许可、出处
│   ├── nlc.py                 # 国图清单：Pressmark、IDP 条目 ID、署名、画布对应
│   ├── derivation.py          # 10-21 执行记录 → 派生来源；cache/ 的统一打开函数
│   ├── v0.py                  # v0 索引快照、健康采样、卷 ID 与链接
│   ├── importer.py            # 一次导入：扫描 → 计算 → 单事务写入（含字段依据与历史）→ 报告
│   ├── api.py                 # FastAPI：认证、只读接口、触发导入
│   └── __main__.py            # 命令行：migrate / report / health
├── acceptance/                # NAS 验收：基线 baseline-2026-10-27.json 与对照脚本（§6.3）
└── tests/                     # pytest
```

### 2.1 接口

全部接口都要求登录（AC-011-1）。

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| GET | `/api/v1/items` | 写卷列表；筛选 `system`、`lineage`、`provenance`、`has_anomaly`（按最近一次成功导入的异常清单）、`category`、`batch`（写卷任一影像的位置在其中即命中）；分页 `page`、`page_size`（≤ 200） | 登录 |
| GET | `/api/v1/items/{id}` | 写卷详情：编号（含历史与待确认编号）、影像（事实、谱系、角色、来源目录、派生、IIIF 画布、v0 链接或不给链接的原因）、来源与许可、出处认定及历史、原始记录、路径历史、母号与分件、字段依据 | 登录 |
| GET | `/api/v1/items/{id}/history?run=` | 写卷在指定批次时的取值与字段依据（AC-013-3） | 登录 |
| GET | `/api/v1/resolve?q=` | 按现行编号查（任一写法、不区分大小写，含存疑编号），返回写卷列表（0～n 件）；母号返回母号写卷与全部分件 | 登录 |
| GET | `/api/v1/images/{id}` | 影像详情：事实、许可、路径历史、变化历史、字段依据 | 登录 |
| GET | `/api/v1/images/{id}/history?run=` | 影像在指定批次时的取值与字段依据 | 登录 |
| GET | `/api/v1/attachments/{id}` | 附件原文，原样字节 | 登录 |
| GET | `/api/v1/anomalies` | 异常清单（含「未导入的文件」）；筛选 `run`、`category`；分页 | 登录 |
| GET | `/api/v1/imports`、`/api/v1/imports/{id}` | 导入记录与报告（含 v0 索引快照状态、健康采样、不关联写卷的附件） | 登录 |
| POST | `/api/v1/imports` | 触发一次导入，后台执行，返回 202 与批次 ID；已有导入在跑时返回 409 | 管理员 |

接口文档（OpenAPI）在 `/api/v1/docs`，同样需要登录；管理员在该页触发导入。容器健康检查用 `python -m dh_catalog health`，不走 HTTP。

## 3. 数据与存储

PostgreSQL 数据目录在 `/srv/example/pgdata`，不在 v0 的部署目录（git 工作区）里。

| 表 | 主要字段 | 说明 |
|---|---|---|
| `import_run` | id、起止时间、状态、触发者账号、规则版本、代码版本、v0 索引快照状态（有效 / 不可用及原因）、v0 健康采样汇总、各类数量、错误 | 每次导入一条（AC-009-4）；触发者只记在这里，不作为字段作者 |
| `item` | id（UUIDv4）、serial（登记顺序）、grouping_key、parent_id、原始位置、展示策略、出处认定（状态、依据、判定者、时间、建议、建议依据）、线索、字段依据 | 写卷；`grouping_key` 只给持有合规馆藏号的写卷（如 `pelliot:2504:1`、`nlc:BD00023a`），非空值唯一；「较早登记」按 serial 比较 |
| `identifier` | item_id、体系、原文、规范写法、母号、分件、出处与出处位置、主编号、合规 / 存疑、状态（现行 / 历史 / 待确认）、起止批次、字段依据 | 编号、编号历史与待确认编号；规范写法与母号建索引（不区分大小写） |
| `image` | id（UUIDv4）、根（data / backup）、相对路径、原始文件名、是否隐藏、种类（tiff / psb / jpg）、大小、mtime_ns、inode、读取是否成功、事实（7 个字段各为有值 / 不适用 / 缺失）、谱系、来源与许可五字段、对外策略、IIIF 画布序号与 ID、状态（present / missing）、首见 / 末见批次、缺失时间、字段依据 | 根与相对路径是影像最后一次被发现时的位置；present 影像的（根，相对路径）唯一 |
| `image_path_history` | image_id、根、相对路径、起止批次 | 路径历史（AC-003-2） |
| `item_image` | item_id、image_id、角色、来源目录、写卷单元、字段依据 | 写卷与影像多对多（AC-002-4、AC-005-5） |
| `attachment`、`item_attachment` | 附件：根、相对路径、种类、原始字节、编码；与写卷多对多 | 不属于任何写卷单元的附件没有关联（AC-001-3、AC-008-2） |
| `derivation` | 派生影像、源影像、方式（拼接 / PSB 转换）、证据（日志文件与行号） | 合并长卷的来源（AC-005-3） |
| `provenance_history` | item_id、状态、依据、判定者（`rule:` 或 `user:`）、时间、批次 | AC-007-4 |
| `history` | 对象种类、对象 ID、批次、快照、字段依据 | 派生字段每次变化记一条，按批次可查任一时刻的取值、来源与作者（AC-009-3、AC-013-3） |
| `anomaly` | 批次、类别、对象、路径、原文、说明 | 异常清单（AC-010-1） |
| `excluded` | 批次、根、相对路径、原因 | 未导入清单（AC-001-4），接口中并入异常清单 |
| `v0_volume` | 批次、v0 卷 ID、相对目录 | 有效的 v0 索引快照（AC-001-1、AC-011-4） |

**字段依据**（R-013）：按字段记录 `{来源, 作者, 批次, 时间, 置信度}`。来源为 文件名解析 / 文件头 / 外部清单 / 执行记录 / 默认规则 / 人工；作者为 `rule:<规则名>@<规则版本>` 或 `user:<账号>`；置信度为 确定 / 推断。

数据量：影像约 3.6 万行、写卷约 6,000 行，导入在内存中计算。

## 4. 关键流程

### 4.1 一次导入

1. 取得咨询锁，没取到返回「已有导入在跑」；写入 `import_run`（running，记触发者账号）
2. **v0 索引快照**：用触发者自己的 `dh_session` 调用 v0 `/api/index`；HTTP 200 且 `status` 为 `ready` 时快照有效，写入 `v0_volume`；否则记「v0 索引不可用」及原因，报告标明「v0 覆盖对照不可验证」，导入照常进行。快照单独提交，不随第 7 步回滚（AC-011-4 以最近一份有效索引为准）。随后开始健康采样（§4.7）
3. **扫描**（只读）：遍历原图目录的各分类与备份目录，跳过以 `@`、`#`、`.` 开头的目录并记入 `excluded`。`.tif` / `.tiff` / `.btf` / `.psb` 为影像，国图 `pages/*.jpg` 为页图，国图 `*_preview.jpg` 为预览图，`.txt` 与国图三种 JSON 为附件；其余文件（`tiles/`、`.npy`、PDF、PNG、下载中的临时文件等）记入 `excluded`。每个文件取得大小、mtime_ns、inode
4. **事实**：（根，相对路径，大小，mtime_ns，inode）与库中一条读取成功的记录相同的，沿用已有事实；否则读取（§4.4）。读不了的记「读不了的文件」，该种文件要记的字段记为缺失，下次导入重读
5. **国图清单与执行记录**：§4.6、§4.5
6. **身份、单元与规则**：§4.2.1 → §4.2.2 → §4.2.3 → §4.4
7. **写入**：结果在一个事务中写入正式表，派生字段有变化的写入 `history`；任何一步失败则整批回滚，`import_run` 记为 failed。`grouping_key` 与影像位置有变化的，先改为临时值再写入新值，编号或位置互换时不违反唯一约束。附件原文读到即写入这个事务，不在内存中整体保留（5,140 份 manifest 与 report 合计约百 MB）；附件内容变化时更新为最新原文
8. 停止健康采样；生成报告与计数，写回 `import_run`；释放锁，丢弃内存中的登录状态。基线对照只由 `acceptance/compare.py` 读取报告完成，不在导入器中重复计算

### 4.2 身份与归并（R-002、R-003）

**4.2.1 影像身份**（spec R-003 影像第 1～4 条；AC-003-2、AC-009-2、AC-009-3、AC-009-5）

在每个根内进行。库中每条影像（present 或 missing）的位置是它最后一次被发现时的（根，相对路径）。按顺序认领：

| 顺序 | 情形 | 判定 |
|---|---|---|
| 1 | 文件标识（inode、大小、mtime_ns）与一条影像的记录相同 | 同一影像；位置变了写路径历史 |
| 2 | 其余文件：所在位置上最近一次被发现的影像没有被第 1 行认领 | 同一影像，内容变化：重读事实，写变化历史 |
| 3 | 其余文件 | 新影像 |

未被认领的 present 影像标为 missing，记缺失时间，不删除；被认领的 missing 影像恢复为 present，记「重新出现」。

依据：2026-10-27 核查两个根目录的 `st_dev` 不同（btrfs 的不同子卷，inode 各自独立），故只在同根内比较；btrfs 按设计不复用已删除的 inode，同一子卷内改名或移动保留 inode 与 mtime_ns（设计说明，未实测）。拼接工作台以临时文件 + 原子替换覆盖 `合并长卷.tif`，新文件的 inode 不同，落到第 2 行（AC-009-3）。

**4.2.2 写卷单元**（spec §1 术语；AC-001-3、AC-002-2、AC-002-3、AC-002-6、AC-002-7）

1. 批次层按 `rules.py` 的登记表判定；未登记的分类按没有批次层处理，并在报告中提示
2. 写卷目录 = 批次目录（没有批次层时为分类目录）下的一级子目录。不在任何写卷目录中的影像文件各成一个单元，编号取自文件名；直接放在分类或批次目录中的附件不关联写卷；直接放在原图根目录的文件记入 `excluded`
3. 写卷目录之下逐层判定子目录（名称精确匹配词表）：分段类、版本类、国图 `pages/` 并入所在单元，沿用该单元的编号；词表外且含可导入影像的自成单元，编号取自它自己的名称，记「词表外子目录」；不含可导入影像的记入 `excluded`，其中的附件归入所在单元（没有所在单元时不关联写卷）
4. 写卷目录（连同词表内子目录）没有可导入影像、只有附件时：不建单元，附件不关联写卷，记「缺少影像」
5. 一个目录中同时有隐藏与非隐藏影像时，对每个隐藏影像记「隐藏文件与非隐藏影像同目录（待确认）」
6. 备份目录：把相对路径映射为原图目录中的同一路径，按第 1～3 条确定所属单元（映射路径上已不存在的子目录按名称照常判定，706 个分片属于这种情况），角色「已迁出的分片」，记录原位置；写卷目录在原图目录中也不存在时，按备份目录中的写卷目录自成单元，并记「备份分片对不上」
7. 每个单元按 §4.3 解析编号，得到合规馆藏号集合 K(U) 与其余编号；国图另取清单 Pressmark。K(U) 为空的单元记「无馆藏号的写卷单元」，并参与合并建议：名称只差「上部 / 下部」「上卷 / 下卷」「紙背」、使用同一分享者自编号、使用同一《开宝藏》帙号的单元，成对记「合并建议」

**4.2.3 归并与写卷身份**（spec R-002，R-003 写卷第 1～6 条；AC-002-1、AC-002-4、AC-002-5、AC-003-4～AC-003-8）

记号：S0 = 导入前的状态（写卷的 grouping_key 记为 key0，以及影像与写卷的关联）；K(U) 见 §4.2.2；P(U) = U 中本次仍在的已有影像在 S0 中关联的写卷。A～D 只读 S0 与本次的单元，算出全部结果后在 §4.1 第 7 步一次写入，与单元的处理顺序无关。

- **A. 单元判定**（对 P(U) 非空的单元）：P(U) 中 key0 属于 K(U) 的写卷为「保持」；H(U) = K(U) 中没有被 P(U) 中的写卷持有的编号，L(U) = P(U) 中不持有 K(U) 任何编号的写卷。H(U) 与 L(U) 各恰有一个 → 该写卷「改用 h」；L(U) 为空 → H(U) 是新增编号，留到 D；K(U) 为空 → P(U) 中有主编号的写卷为「待确认」，没有主编号的为「保持」；其余情况，L(U) 中每件写卷为「待确认」
- **B. 写卷判定**（S0 中每件写卷 X）：本次没有仍在的影像 → key1 = key0，编号、线索与出处认定都不重算；所在全部单元的结果相同 → 采用（保持 / 改用 h）；否则（有「待确认」或各单元结果不同）→ key1 = key0，记「身份待确认」并注明原因
- **C. 同号**：只看非空的 key1；重复执行直到没有同号：同号组中 key1 ≠ key0 的写卷退回 key0，记「身份待确认」并注明同号的写卷。S0 中非空的 key0 互不相同，每组至少有一件可退回，所以必然结束
- 含有被记「身份待确认」的写卷的单元为待确认单元，其余为正常单元
- **D. 关联与新建**（owner(k) = C 之后持有 k 的写卷）：
  - P(U) 为空的单元：K(U) 中每个 k，owner(k) 存在则关联 U 的全部影像，否则新建写卷（key = k）再关联；K(U) 为空时新建一件没有主编号的写卷
  - 正常单元：新影像关联到 K(U) 中每个编号的 owner；H(U) 中的新增编号按上一条处理，关联 U 的全部影像
  - 没有编号的单元与待确认单元：新影像归入 P(U) 中在 U 内已有影像最多的写卷，并列取 serial 最小者；待确认单元的 H(U) 本次不处理
  - 同一个新 key 只新建一件；新写卷的 serial 按 key 排序依次分配（没有 key 的按单元相对路径排序）
- **E. 收尾**：按 key 重算分件的 parent_id（`pelliot:2504:1` 的母号为 `pelliot:2504`；母号没有写卷时为空）；多编号单元的写卷记「名称所示的合装或缀合」线索；写卷的其余编号与线索取自它本次所在的单元（B 中不重算的写卷除外）；待确认写卷所在单元中它不持有的合规馆藏号，记为它的「待确认」编号

### 4.3 编号解析与合规判定（R-004）

只解析单元的编号来源（写卷目录名、散放文件名、词表外子目录名、国图 Pressmark）；写卷目录内的文件名（如 `2660-1.tif`）不解析编号。

| 体系 | 识别的写法（例） | 规范写法 | 合规判定与用途 |
|---|---|---|---|
| 伯希和汉文写卷号 | `P2602`、`P.2033`、`P. 0901`、`p.2731`、`Pelliot chinois 2002` | `P.2602` | 号段内为合规，作主编号与归并依据；号段外为存疑：可检索，不作主编号、不作归并依据，记「编号存疑」 |
| 伯希和分件 | `-1`、`-1Pièce`、`-P2`、`A` / `B` / `a` | `P.2504-1`、`P.2842-2`、`P.2222A`（字母取大写） | 母号 = 不带分件的号；合规性随母号 |
| 多号 | `P3012+5564`、`P2661(+3735)` | 各成一号 | 第二个号省略「P」也识别 |
| 国图 BD 号 | 清单 Pressmark；目录名 `BD00001`、`BD00023a` | 以 Pressmark 的写法为准 | 有清单：Pressmark 为馆藏号，目录名与之不一致（不区分大小写比较）时目录名记为存疑并记「编号与清单不一致」；Pressmark 本身写法不合规时两者都记为存疑并记该异常；无清单：目录名写法合规（BD + 5 位数字 + 可选字母）即用，并记「缺少清单」 |
| 分享者自编号 | `WB 15`、`WB15`、`WA9` | `WB 15`、`WA 9` | 不作主编号、不作归并依据，只提合并建议 |
| 《开宝藏》帙号 | 「令字」「存字」「李字」等 | `令` 等 | 只在目录名或同目录 PSB 文件名含「開寶藏 / 开宝藏」，或目录名以「敦煌藏經洞 + 序号」开头时识别（避免把「小字法华经」的「小字」误认作帙号）；不作主编号与归并依据 |
| IDP 条目 ID | 清单 `id` 末段 | 原样 | 外部编号 |
| 疑似编号 | 独立的 4 位数字：前后不紧邻数字、字母、`.`、`,`、`×`、`x`、`*`，后面不接 `cm`、`mm`、`年`、`×`、`x`（中间可隔空格），不是多号写法中的后一个号，且落在汉文号段内 | — | 不解析，记「疑似编号」；2026-10-27 命中 2 处：`4518(35)`、散放 PSB 名中的 `2178` |

主编号：每件写卷最多一个，只取合规馆藏号；母号与分件各自为主编号。查询时编号比较不区分大小写。

### 4.4 规则表（`rules.py`）

**事实字段**（AC-005-1）：

| 种类 | 有值或缺失 | 不适用 |
|---|---|---|
| TIFF | 像素尺寸、通道数（SamplesPerPixel）、色彩模式（Photometric）、位深（BitsPerSample）、分辨率（X/YResolution 与单位）、压缩方式（Compression）、软件标签（Software） | — |
| PSB | 像素尺寸、通道数、色彩模式、位深（取自文件头） | 分辨率、压缩方式、软件标签 |
| JPG | 像素尺寸、通道数、色彩模式、位深（取自 SOF 段）；分辨率（文件内有 JFIF / EXIF 分辨率时有值，否则缺失） | 压缩方式、软件标签 |

**角色**（按顺序取第一条命中；文件名比较时去掉开头的点）：

1. `.psb` → PSB 源文件
2. 文件名以「合并长卷」开头的 TIFF → 合并长卷
3. 备份目录中的影像 → 已迁出的分片
4. 国图 `pages/*.jpg` → 页图
5. 国图 `*_preview.jpg`、版本类子目录中的影像 → 另一版本
6. 分段类子目录中的影像 → 分段
7. 单元中其余的 TIFF：只有一个 → 单幅整卷，多于一个 → 各为分段（PSB、JPG、合并长卷与备份分片不计入个数）

**谱系**（逐个文件，按顺序；AC-005-2）：

| 条件 | 谱系 |
|---|---|
| 属于国图分类（含页图、预览图） | 国图 IDP 下载 |
| `.psb` | 第三方加工图（分享者的工作文件，plan.md §1.3） |
| TIFF 文件名以「合并长卷」开头，或出现在 10-21 执行记录的输出中 | 本地合成 |
| 其余 TIFF 中读不了的 | 未判定（已记「读不了的文件」，不另记「谱系未判定」；读成功后重判） |
| 文件名为 `native.tif` / `native(n).tif`，且软件标签缺失 | BnF 原图 |
| 软件标签有值（Photoshop 等） | 第三方加工图 |
| 其他 | 未判定（记「谱系未判定」） |

目录级汇总（报告用）：只计影像目录直接包含的 TIFF / BTF；谱系一致时取该谱系，不一致时记「混合」。

**来源与许可**（D-012，AC-006-1～3）：

| 谱系 | 收藏机构 | 获取渠道 | 许可 | 署名 | 展示策略 | 对外策略 |
|---|---|---|---|---|---|---|
| 国图 IDP 下载 | 中国国家图书馆 | IDP IIIF 下载（2026-10-21 起） | IDP：个人或非商业复用 | 清单 requiredStatement（The National Library of China）；没有清单时取 D-012 的默认署名 | 登录墙内可展示 | 链接 IDP |
| BnF 原图 | 法国国家图书馆 | 第三方资料接收（接收事件 A） | Gallica：非商业免费复用，注明出处 | Source gallica.bnf.fr / BnF | 登录墙内可展示 | 链接 Gallica / IDP |
| 第三方加工图 | 有合规伯希和号时推断为法国国家图书馆（置信度「推断」），否则未知 | 第三方资料接收（接收事件 A） | 未知（第三方衍生） | 无 | 仅供研究使用 | 不对外 |
| 本地合成 | 继承源影像 | 本地生成（2026-10-21 脚本或拼接工作台） | 继承源影像中最严格的一项；来源不明时为未知 | 同源影像 | 同源影像中最严格的一项 | 同左 |
| 未判定 | 未知 | 按所在根目录与分类推断（转存或下载） | 未知 | 无 | 仅供研究使用 | 不对外 |

严格程度：许可 未知 > IDP（个人或非商业）> Gallica（非商业）；展示策略 仅供研究使用 > 登录墙内可展示。写卷的展示策略取其全部影像中最严格的一项（AC-006-2）。

**出处认定**（AC-007-1～4）：

1. 已有判定者为 `user:` 的结论 → 保留不动
2. 收集证据：合规伯希和号或 BD 号；非敦煌线索——目录名或同目录 PSB 名含「開寶藏 / 开宝藏」或以「敦煌藏經洞 + 序号」开头、识别出《开宝藏》帙号、题名含「清光绪 / 清光緒」「尖山刻经 / 尖山刻經」「室町」「竹生島経 / 竹生岛经」「紫紙金字 / 紫纸金字」「大橋家来翰集」
3. 只有合规馆藏号 →「已确认」；有非敦煌线索 →「待核」并附「建议：非敦煌」；两者都有 →「待核」，依据中同时列出，并记「出处证据冲突」；两者都没有 →「待核」
4. 规则永远不直接给出「非敦煌」

### 4.5 合并长卷的派生来源（AC-005-3、AC-012-2）

只按名字直接打开 v0 `cache/` 根目录下的这些文件，不列目录、不递归：`merge_all.log`、`merge_smart_all.log`、`merge_extra.log`、`psb_convert.log`、`psb_convert_all.log`、`psb_convert_7.log`、`psb_conv_wb5back.log`、`seg_move_log.txt`、`samefolder_move_log.txt`、`extra_move_log.txt`、`seg_move_plan.json`、`samefolder_plan.json`、`validated_moves.json`（2026-10-27 按名核查，13 个都在）。对 `/v0cache` 的访问只经过 `derivation.py` 的统一打开函数，实际访问路径写入导入报告，供 AC-012-2 验收核对。

- 拼接日志：「开始: <相对目录>」之后列出的分片名 → 源分片（迁出后在备份目录的镜像位置），「完成: …/合并长卷.tif」→ 派生影像
- PSB 转换日志：「转换: <相对目录>」与「PSBNAME」→ 源 PSB，「已替换合并长卷.tif」→ 覆盖之前的拼接结果
- 同一个合并长卷以时间上最后一次成功的操作为准；证据记录日志文件名与行号
- 对不上的、白名单文件不存在或读不了的，记「派生来源不明」（注明原因），导入不因此失败；不在 10-21 记录中的合并长卷（如拼接工作台之后生成的）原因写「不在 2026-10-21 执行记录中」

### 4.6 国图清单（AC-004-3、AC-005-4）

- `manifest.json`：Pressmark → 馆藏号；`id` 末段 → IDP 条目 ID；`requiredStatement` → 署名；`items[n].id` → 画布 ID
- `report.json`：`strips[i].file` → 本地 TIFF 与画布序号 `strips[i].index`；`strips` 不是列表（如 0）时，按本地 TIFF 文件名中的序号（`BDxxxxx_NNNN_n.tif` 的 NNNN）对应，仍对不上的记「画布对不上」
- `pages/NNNN_WxH.jpg`：文件名前缀 NNNN → 画布序号
- 三份 JSON 都原样存为附件

### 4.7 认证与 v0 接触（AC-001-1、AC-011-1、AC-011-4、AC-012-2、AC-012-3）

- **`AUTH_SECRET`**：从只读挂载的 v0 `.env` 中只读取这一项；缺失时所有请求返回 503（fail-closed）
- **请求校验**：cookie `dh_session` 按 v0 的格式验证——base64url(`用户|过期时间|HMAC-SHA256(AUTH_SECRET, "用户|过期时间")`)，未过期，且用户在 `users.json` 中（architecture.md §7）；管理员 = `admin: true`。`users.json` 只由请求校验读取，导入过程不打开它。cookie 不区分端口，在 8503 登录 v0 后即可访问 8504；v0 的 cookie 为 `SameSite=Lax`，跨站请求不会带上它
- **调用 v0**（局域网地址，配置项 `DH_V0_URL`，默认 `http://192.0.2.10:8503`）：导入只经接口触发，使用该请求自带的 `dh_session`，只保存在导入线程的内存中，导入结束即丢弃；目录服务不签发会话
  - 索引快照：`GET /api/index`，有效条件见 §4.1 第 2 步
  - 健康采样：导入期间每 5 秒 `GET /api/health`，2 秒内返回 200 且 `ok` 为 true 记为正常；采样汇总（次数、失败数、最大耗时）写入 `import_run`
- **v0 链接**（AC-011-4）：取最近一份有效快照（`v0_volume`），只为其中有、且本次导入时磁盘上仍存在的影像目录中的 TIFF 影像生成 `<DH_V0_PUBLIC_URL>/view/<base64url(相对目录)>`；散放文件附带 `?file=<文件名>`（v0 忽略该参数，仅供人看）；其余写明不给链接的原因（备份分片、JPG、PSB、不在 v0 索引中、从未取得有效索引）。`DH_V0_PUBLIC_URL` 默认同 `DH_V0_URL`

### 4.8 部署与运行（D-018）

| 服务（容器） | 镜像 | 内存（= memswap） | 挂载 | 其他 |
|---|---|---|---|---|
| `catalog-db` | `postgres:17.4-alpine3.21` | 384m | pgdata → `/srv/example/pgdata` | 不对外暴露端口；`shared_buffers=64MB`、`max_connections=20`、`work_mem=4MB`；healthcheck `pg_isready` |
| `catalog-api` | 本仓库 `catalog/Dockerfile` | 512m | `/srv/example/data:/data:ro`、`/srv/example/backup:/backup:ro`、`/srv/example/cache:/v0cache:ro`、`/srv/example/viewer/.env:/run/v0.env:ro` | 端口 8504→8000；`env_file: ./.env`（数据库密码等）；以 root 运行（`users.json` 为 root 600）；导入在本容器的后台线程中执行，受 512m 上限约束 |

- 启动：`cd /srv/example/viewer/catalog && /usr/local/bin/docker-compose -p dunhuang-catalog up -d --build`（只作用于本项目，不影响 v0）
- 首次导入：管理员登录 v0 后打开 `http://192.0.2.10:8504/api/v1/docs`，执行 `POST /api/v1/imports`
- 上线前置：NAS `MemAvailable` ≥ 2 GB；首次全量导入放在低峰时段

## 5. 验收对应

| AC | 实现位置 | 验证方式 |
|---|---|---|
| AC-001-1 | `v0.py` 索引快照、`importer.py` 报告 | `test_import.py::test_v0_index_coverage`（v0 替身：索引落后于磁盘、索引中有已删除目录、调用失败、未就绪）；NAS A1 |
| AC-001-2 | `scan.py` | `test_scan.py::test_image_inventory_complete`；NAS A2 |
| AC-001-3 | `scan.py`、`units.py` §4.2.2 第 2～4 条 | `test_import.py::test_attachments`（子目录中的附件、只有附件的写卷目录、分类目录中的说明） |
| AC-001-4 | `scan.py` | `test_scan.py::test_excluded_listed_with_reason` |
| AC-002-1 | `identity.py` §4.2.3 D | `test_identity.py::test_same_number_merged_across_lineages`；NAS A2（P.2002 的两套影像） |
| AC-002-2 | `units.py` §4.2.2 第 3 条、`rules.py` 角色 | `test_units.py::test_subdirs`（含父 P.2002 / 子 P.2003、`tiles/`）；NAS A2 |
| AC-002-3 | `units.py` §4.2.2 第 2 条 | `test_units.py::test_loose_files`；NAS A2 |
| AC-002-4 | `identifiers.py`、`identity.py` §4.2.3 D、E | `test_identity.py::test_multi_number_units_share_images`；NAS A2 |
| AC-002-5 | `identifiers.py`、`identity.py` §4.2.3 E | `test_identity.py::test_parts_and_parent`；NAS A2 |
| AC-002-6 | `units.py` §4.2.2 第 7 条 | `test_units.py::test_merge_suggestions_only` |
| AC-002-7 | `units.py` §4.2.2 第 6 条 | `test_units.py::test_backup_fragments_mapped`；NAS A2 |
| AC-002-8 | `identifiers.py` | `test_identity.py::test_doubtful_numbers_not_merged`；NAS A2 |
| AC-003-1 | `identity.py`、`importer.py` | `test_identity.py::test_reimport_keeps_ids` |
| AC-003-2 | `identity.py` §4.2.1 第 1 行 | `test_identity.py::test_rename_move_and_swap`（临时目录中真实改名、移动、互换） |
| AC-003-3 | UUIDv4 | `test_identity.py::test_ids_not_path_derived` |
| AC-003-4 | `identity.py` §4.2.3 A、B | `test_identity.py::test_number_change_keeps_id` |
| AC-003-5 | `identity.py` §4.2.3 A～C | `test_identity.py::test_unmatched_cases_kept_pending`（spec 所列五种情形；名称改回后不再列入） |
| AC-003-6 | `identity.py` §4.2.3 D | `test_identity.py::test_new_images_assignment` |
| AC-003-7 | `identity.py` §4.2.3、`importer.py` §4.1 第 7 步 | `test_identity.py::test_swap_and_rotation_order_independent`（打乱单元顺序，结果相同）；`test_import.py::test_number_swap_end_to_end`（数据库上完整导入，不违反唯一约束） |
| AC-003-8 | `identity.py` §4.2.3 A、D | `test_identity.py::test_multi_number_add_and_rewrite` |
| AC-004-1 | `identifiers.py` | `test_identifiers.py::test_pelliot_variants_and_suspected`（含 2026-10-27 的 2 处命中、尺寸与年份、多号写法、不解析的 `2660-1.tif`） |
| AC-004-2 | `identifiers.py`、`rules.py` 号段 | `test_identifiers.py::test_ranges_and_doubtful` |
| AC-004-3 | `nlc.py`、`identifiers.py` | `test_nlc.py::test_pressmark_authority`（含只差大小写、写法不合规、没有清单） |
| AC-004-4 | `identifiers.py` | `test_identifiers.py::test_sharer_and_zhihao_systems` |
| AC-004-5 | `identifiers.py`、`identity.py` | `test_identifiers.py::test_primary_only_compliant` |
| AC-005-1 | `scan.py`、事实字段表 | `test_scan.py::test_facts_by_kind`（有值 / 不适用 / 缺失；读不了的文件下次导入重读） |
| AC-005-2 | `rules.py` 谱系、`importer.py` 目录级汇总 | `test_rules.py::test_lineage`（含 `合并长卷.psb`、读不了的 TIFF、混合目录）；NAS A3 |
| AC-005-3 | `derivation.py` | `test_derivation.py::test_stitch_and_psb_logs`（仿照格式的合成日志，含白名单文件缺失）；NAS A2 |
| AC-005-4 | `nlc.py` | `test_nlc.py::test_canvas_mapping`（`strips` 是列表与不是列表）；NAS A4 |
| AC-005-5 | `item_image` 来源目录 | `test_identity.py::test_image_sets_distinguishable` |
| AC-006-1 | `rules.py` 许可 | `test_rules.py::test_license_defaults` |
| AC-006-2 | `rules.py` | `test_rules.py::test_item_policy_most_restrictive` |
| AC-006-3 | `rules.py` | `test_rules.py::test_channel_is_specific_event` |
| AC-007-1 | `rules.py` 出处 | `test_rules.py::test_every_item_has_provenance` |
| AC-007-2 | `rules.py` | `test_rules.py::test_confirmed_only_without_counter_evidence` |
| AC-007-3 | `rules.py` 出处线索 | `test_rules.py::test_non_dunhuang_suggestions_and_conflicts`；NAS A2（18 + 6 个目录） |
| AC-007-4 | `rules.py`、`importer.py` | `test_import.py::test_human_conclusion_survives_reimport` |
| AC-008-1 | `scan.py` | `test_import.py::test_raw_names_verbatim` |
| AC-008-2 | `attachment` | `test_import.py::test_attachment_raw_roundtrip` |
| AC-009-1 | `importer.py` | `test_import.py::test_new_files_appear` |
| AC-009-2 | `identity.py` §4.2.1 | `test_import.py::test_missing_marked_not_deleted` |
| AC-009-3 | `identity.py` §4.2.1 第 2 行、`history` | `test_import.py::test_changed_file_history` |
| AC-009-4 | `importer.py`、`import_run` | `test_import.py::test_import_run_record` |
| AC-009-5 | `identity.py` §4.2.1 第 1 行 | `test_import.py::test_reappearance`（移入以 `#` 开头的目录 → 导入 → 移回原处或同根别处 → 导入） |
| AC-010-1 | `importer.py`；各类异常的产生点见 §4.1～§4.6 | `test_import.py::test_anomaly_categories`（每个类别用一份合成数据触发） |
| AC-010-2 | `importer.py`、`acceptance/baseline-2026-10-27.json` | NAS A2 |
| AC-011-1 | `api.py` | `test_api.py::test_auth_and_admin_import` |
| AC-011-2 | `api.py` `/resolve`、`identifiers.py` | `test_api.py::test_resolve`；NAS A2（`P.2504` → 5 件） |
| AC-011-3 | `api.py`、索引 | `test_api.py::test_filters_and_pagination`；NAS A6 |
| AC-011-4 | `v0.py` 链接 | `test_api.py::test_v0_links`；NAS A7 |
| AC-011-5 | `api.py` | `test_api.py::test_no_mutating_routes`（检查路由表） |
| AC-012-1 | 只读挂载 | NAS A5 |
| AC-012-2 | `derivation.py` 统一打开函数、`api.py` | `test_import.py::test_v0_cache_access`（记录导入期间打开的全部路径：只有白名单文件，没有 `users.json`，没有列目录） |
| AC-012-3 | 512m 上限、`v0.py` 健康采样 | NAS A5 |
| AC-012-4 | 沿用未变文件的事实 | NAS A5 |
| AC-013-1 | `importer.py` 字段依据 | `test_import.py::test_field_basis_and_author`（规则字段的作者是规则名与版本，不是触发者） |
| AC-013-2 | `importer.py` | `test_import.py::test_confidence_labels` |
| AC-013-3 | `importer.py`、`history`、`/history` 接口 | `test_import.py::test_value_at_any_run`（两次导入之间修改规则版本与文件） |

## 6. 测试与验证

### 6.1 本机（Windows，Python 3.14）

不依赖数据库的测试：编号、规则、写卷单元、影像身份与归并（输入导入前状态与本次单元，输出结果）、派生解析、认证签名。影像身份在临时目录中真实地改名、移动、互换、删除与还原文件，从扫描开始计算。运行时以容器内的 Python 3.12 为准。

### 6.2 NAS（需你许可后才运行）

数据库与接口测试用候选提交快照构建的测试镜像和一次性 PostgreSQL 容器运行，**不启动正式 compose、不访问正式 pgdata、不挂真实材料或 v0 文件**。经许可后以 `git archive` 把候选提交送到 NAS 隔离临时目录，`docker build -t dh-catalog-test <隔离目录>/catalog`；一次性数据库使用 `postgres:17.4-alpine3.21`，`--rm --memory 384m --memory-swap 384m`，无宿主数据卷、无宿主端口，在临时 Docker 网络内连通；测试容器同样 `--rm`，内存与 memswap 均为 512m，只用合成数据与合成认证文件。设置临时库 URL 后执行 pytest，结束删除测试容器、网络与隔离快照。它们是测试，不是正式服务部署；正式 compose 仍须 Gate 2 / merge 后另获许可才启动。

### 6.3 NAS 验收（部署后，需你许可；导入由你在接口文档页触发）

| 编号 | 内容 |
|---|---|
| A1 | 以快照有效的导入为准：v0 索引中、磁盘上仍存在的卷未对应到写卷的数量（须为 0）；分别列出 v0 尚未收录与 v0 索引中已不存在的目录 |
| A2 | 基线对照：`baseline-2026-10-27.json` 包含 spec AC-010-2 列出的全部数字；`acceptance/compare.py` 只读导入报告计数逐项比较，差异写明原因 |
| A3 | 谱系目录级汇总与 447 / 499 / 12 及国图 5,138 比较 |
| A4 | 国图 TIFF → 画布的对应率 |
| A5 | 三个挂载为只读；原图与备份目录前后快照（路径、大小、mtime），变化逐项归因于其他写入方；导入期间宿主机每 5 秒采样 `docker stats`，容器未被 OOM 终止；导入记录中的 v0 健康采样全部正常；全量与无变化重跑的耗时 |
| A6 | 列表查询与详情查询各 100 次（先预热 10 次，单并发顺序执行），分别统计 P95 |
| A7 | 随机抽 20 个 v0 链接，确认 v0 返回对应的卷 |

## 7. 风险与回滚

| 风险 | 应对 |
|---|---|
| NAS 内存紧张（plan.md RK-01） | 两个容器硬上限合计 896m；上线前确认可用内存 ≥ 2 GB |
| 首次全量导入与 v0 争用磁盘 | 只读文件头；未变文件沿用事实；放在低峰时段；导入期间采样 v0 健康并写入导入记录 |
| 10-21 执行记录格式不规整 | 解析不到的记异常（AC-005-3 允许），不臆测 |
| v0 会话格式变化导致认证失效 | 测试锁定 v0 的签名格式；v0 修改 cookie 时同步（D-018） |
| 规则误判（谱系、出处、归并） | 规则带名称与版本写入依据；人工结论不被覆盖；对不上的保持原样并列异常；不自动合并、不自动拆分 |
| 数据库损坏或丢失 | 本 feature 的数据都可由原始材料重新导入；人工数据在 `annotation-workbench` 之后才出现，届时再定备份 |
| 回滚 | `docker-compose -p dunhuang-catalog down`；删除 `pgdata` 即完全移除；v0 没有改动 |

## 8. 实施里程碑（供 Tasks 拆分）

| 里程碑 | 内容 |
|---|---|
| M1 骨架 | 目录与依赖、配置、数据库连接与迁移、测试夹具生成器 |
| M2 扫描与单元 | `scan.py`（含事实）、`units.py` |
| M3 编号与身份 | `identifiers.py`、`identity.py` |
| M4 规则与外部记录 | `rules.py`、`nlc.py`、`derivation.py`、`v0.py` |
| M5 导入与报告 | `importer.py`（写入、字段依据、历史、报告） |
| M6 接口 | `api.py` |
| M7 部署与验收 | compose、NAS 测试、部署、A1–A7 |
