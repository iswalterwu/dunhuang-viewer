# public-release-privacy 任务清单

> 7R/25AC已获用户Gate1批准。独立Tasks后Analyze第2轮12项全通过、无阻断，设计层关闭B-1，允许仅PRIV-01～07按依赖实施（Anthropic/claude-fable-5-1，2026-10-30T09:04:56Z～09:13:40Z，exit0）。Plan/Checklist/本任务范围在实施中冻结；原始派发/输出私下保全，公开仅脱敏摘要。

## 当前实施与集成结果

PRIV-01～04已由4个独立openai/gpt-6-astra会话按边界实施，全部exit0，未提交/推送/操作私人服务。主会话分别复跑配置/认证、48项主机脚本验收、19项真实合成Git验收，再完整集成 **489 passed/61 skipped/1原有警告（550项，42.67秒）**；61=58缺DB+3仅Linux，不算通过。起点112文件的index+worktree224文本实例机密/通用规则0命中，后续新增状态文件须再扫。41份Python3.12 AST/内存编译、编码/文档/链接/脚本语法通过；不是新目标PG/容器实测。

PRIV-03私下保全404原件并移出旧归档360文件；155初始候选逐项处置，13R58AC、原勾选与518处结果标记保持。详细原件/规则/别名/租约/输出仅非公开保全。实际A1/A2原阻断保留；P21补私有数据/根构建两注释并作真实A3，独立R5复审通过、P1-1关闭，无P0/P1/P2。代码最新489/61/1（43.08秒），A3全历史和独立语境0未处置；审后A4最终72提交/483blob/699文本及独立555记录复扫通过；用户现确认本轮Gate2，origin两分支已依原租约一次原子受保护更新、全新远端复扫及本机分支迁移完成。现交接/PR #1及正常匿名UTC合并完成，GitHub确认MERGED、合并后两ref复扫通过，不动部署远端或把旧副本说成已撤回。详见本feature的converge.md与review.md。

完整本机验收包含需要Git/Bash及完整源码树的host-only acceptance；未来若另获目标数据库镜像验证许可，使用镜像支持的tests及acceptance/test_compare.py，DB项须实际执行，不把镜像不具备的主机发布工具条件混作DB证据；当前未运行该目标验证。

## R4闭环修复批次（PRIV-06/P21，原范围内）

- 独立R4（anthropic/claude-fable-5-1，2026-10-30T11:18Z～11:40Z，exit0）运行/工具差异通过，真实A2机械验证通过，但初始独立类别与人工语境检查发现历史位置/账户窗口、网关/设备/账号数量和接收日期残留，main tip亦有，P1-1阻断。详见review.md；不默认接受残留，不索取重复历史授权。
- P21仍由独立openai/gpt-6-astra实施：仅在仓库外按实际原文修私有规则/分类/验证数据，并补根Dockerfile两处隐私注释遗漏（PRIV-02原隐私目的的注释补漏，不改任何构建指令/环境/依赖/镜像行为）。公开工具、业务实现、冻结7R/25AC不变；实际重建未运行，后续部署仍须重建。
- 补全部初始盘点类别与人工语境覆盖，分类保留学术/合成/通用产品/容器硬限额及测试事实；禁止用同一规则的0命中自证完备。新规则不带入公开程序/fixture，原A1/A2与R4失败保留。最终工作树先stage/复扫/形成干净候选后再新目录真实演练、独立Claude复审及必要Gate2。
- **闭环结果**：P21为openai/gpt-6-astra/exit0，原125规则保留+171完整行=296；618唯一候选人工分类、初始全部类别对账与独立负控。真实A3为71提交/477blob/690文本，机械及独立语境0未处置，R5独立复现并关闭阻断，可请求Gate2。4新增DB、重建/目标/真实材料仍未验；3项非阻断限制见review.md，未代用户接受。R5后治理状态须再复扫/精确人工分类，不改原模式或业务。
- 自本批起，全部本机Git提交及merge显式`TZ=UTC`并使用已设非个人贡献者身份；执行发布plan前逐项比对new_oids等于最终已审演练两输出ref。不加新机制、不改全局设置/其他远端。

## 执行约定

- AC编号均指本feature spec。业务/脚本/工具实现与修复仅由独立openai/gpt-6-astra负责；主会话编写设计/派发/协调、复核与复跑、状态、实际Git操作。独立审核员A按既定Claude渠道规则，不以Astra自报代审核。
- 初次仅可并行PRIV-01/02/03/04，文件集合互不相交；各模型不改其他任务文件、冻结本feature spec/plan/checklist/tasks或做提交/推送/历史操作。共享接口名按下文约定，不覆盖其他模型变化；集成由主会话串行。
- 不连接私人服务/目标PG，不执行Docker、真实文件搬运、部署或真实导入；脚本测试只在临时材料和外部CLI替身上运行。本机缺DB/仅Linux的skip如实记录；旧446/36k不是新证据。
- 全套命令为现有虚拟环境`python -B -I -X utf8 -m pytest -p no:cacheprovider -c catalog/pytest.ini catalog/tests catalog/acceptance`。每任务先完整分配文件，全部模型结束后主会话独立全套，不在并发修改时据全套数字宣称最终集成通过。
- 完整原件、真实禁止值、旧新OID、租约、个人身份、原始命令/报告均仅仓库外，不把新的私有扫描清单或模型提示词提交。新公开fixture仅合成值。
- 本机所有新提交及merge显式`TZ=UTC`，用非个人贡献者身份与example.invalid邮箱；原身份设置私下备份，不改其他项目/全局配置。远端租约早已记录，发布前不得刷新为新值来绕过冲突。

## PRIV-01 catalog配置、旧日志前缀和接收标签（1.5～2小时，Astra）

- **依赖/状态**：独立Analyze已全项通过；准备派发。支持AC-003-1/003-2/003-3、AC-004-1/004-2/004-3/004-4、AC-007-3。
- **唯一写范围**：catalog/src/dh_catalog/{config,api,importer,derivation,rules}.py，catalog/docker-compose.yml、catalog/.env.example，catalog/tests/test_{config,api,import,derivation,rules,runtime}.py。不改schema、其他算法/模块、README/其他文档或其他任务文件。
- **接口/固定值**：Settings新增`record_roots`字符串POSIX映射（默认空，现有构造/replace调用兼容），load_settings只在入口读取DH_RECORD_DATA_ROOT/DH_RECORD_BACKUP_ROOT、去空白、绝对且非单根、补尾斜杠；不用Path值、不加前缀重叠机制。沿API后台→PreparedImport.execute→compute_import→resolve_derivations→读/解析函数传递同名可选record_roots；默认空仍支持/data/、/backup/及相对记录，不硬编码私人前缀，不读日志所指宿主文件。
- **部署/标签**：正式Compose的DH_V0_URL、两项CATALOG_LAN_IP/CATALOG_TAILSCALE_IP及DH_HOST_DATA_DIR/BACKUP_DIR/CACHE_DIR/V0_ENV_FILE/PGDATA_DIR均显式配置（:?），不再私人默认值；DH_V0_PUBLIC_URL可复用显式DH_V0_URL。load_settings开发后备仅http://localhost:8503，明确不是生产入口。env example敏感角色参数为空占位；挂载ro/外部PG/无DB端口/限额/启动/健康策略不变。TRANSFER_EVENT固定为`第三方资料接收（接收事件 A）`，不含原私人事件日期；RULE_VERSION=2026-10-30.1，其余下载/本地派生标签、许可/谱系/机构/严格度不改。
- **完成标准/证明**：真实中性合成日志的host data/backup配置产生正确派生/许可，未配置绝对路径显式异常，容器/相对/失败回归不减；配置入口与API/Prepared链真实测试，DB依赖项如实skip，不能mock业务/SQL求绿。只调整确属隐私默认值的旧fixture/期望，其余断言保持。持久化SQL、事务锁、身份、CompactMap/游标算法不改，来源值变化正常记录版本，不改旧DB。
- **命令**：分配的6个完整测试文件（test_config/api/import/derivation/rules/runtime），UTF8LF/无BOM、Python3.12 AST、限定diff；主会话集成后全套。正常DTO/JSON字段之外不加接口，不启服务。

## PRIV-02 v0部署与辅助脚本（1～1.5小时，Astra）

- **依赖/状态**：Analyze后，可与01并行。支持AC-002-2/002-3、AC-004-1/004-2/004-3/004-4、AC-007-3。
- **唯一写范围**：根docker-compose.yml、auto_huge.sh、auto_huge_boot.sh、auto_huge_daemon.sh、stitch_apply.py；新增根.env.example、catalog/acceptance/test_public_runtime.py。app.py与pyramid_worker.py仅含个人硬件/部署说明的注释可脱敏，AST必须逐函数不变。其他文件不写。
- **约定**：根Compose沿用DH_HOST_DATA_DIR/CACHE_DIR/STATIC_DIR，去私人布局/设备实例/入口注释；static可用明确相对项目示例，数据与cache显式输入，原服务/命令/limits/ro-rw/线程/守卫不动。3个shell脚本显式要求DH_DEPLOY_DIR；boot不能按脚本所在位置猜部署根，缺设置时任何动作前明确报错并非0退出。需访问data/cache的主机脚本还须显式DH_HOST_DATA_DIR/DH_HOST_CACHE_DIR，传给stitch_apply.py的DATA_DIR/CACHE_DIR；缺设置不搬运或启动服务，不把私人路径作后备。stitch_apply.py仅配置边界改动，ID/base64url/sha1/cache键及队列写入算法逐字不变。
- **完成标准**：公开模板无真实入口/宿主布局，升级参数清单明确；真实临时队列/文件运行脚本可证明路径选择和复制结果，Docker/Compose仅外部替身，绝不调用真实服务。缺设置子进程非0且没有动作；Bash/sh语法、编码与原有映射/算法差异核对，不修旧拼接/守护循环其他问题。
- **命令**：完整catalog/acceptance/test_public_runtime.py，bash -n三个脚本；Python3.12 AST/本机编译根3个Python文件，编码/diff；主会话完整集成回归。不得执行旧脚本真实硬编码部署入口。

## PRIV-03 公开文档、归档保全与验证摘要（1.5～2小时，Astra）

- **依赖/状态**：Analyze后可并行；只按上述固定参数/标签写升级说明，最终差异由主会话整合。支持AC-001-1/001-2/001-3、AC-002-1/002-2/002-3、AC-003-1/003-2/003-3、AC-005-1/005-2/005-3/005-4、AC-007-2。
- **唯一写范围**：所有既有公开Markdown、.gitattributes的部署实例注释；但本feature的spec/plan/tasks/checklist/audit-summary由主会话维护，只可报告其中需脱敏项，不自行修改。可移除旧handoff/**（必须先私下完整保存，豁免新handoff/README.md），新增docs/verification.md、迁移tools/check_docs.py。不得写源码/运行文件、PRIV-04工具/测试、.git、分支或提交。
- **原件/摘要**：实施前将旧handoff原件与即将改的文档私下保全，和最新Git/工作区备份相核；公开文档明确为隐私发布修订。原checklist/review只改私人词语/链接与脱敏标识，原测试通过/失败/skip、数据规模/容器限额/耗时和审核结论保持，不能自勾项。设备实例、账号数量、现场主机资源等私人运行细节可移入非公开原件，不填造新的测量值；不能以此删除软件资源红线或失败事实。D-009状态注明可见性被D-019取代，旧部署决策意义保留。现行AGENTS工作流/模型/闸门、安全与部署许可不放宽。
- **来源/入口**：个人接收渠道统一中性事件A，不捏造机构直接获取或授权；保留学术机构/原始材料名称、编号、谱系、未知许可和引用。实际私网/网关/个人账户/工作站宿主路径、设备实例/额度/位置不出现在公开说明；使用角色环境变量、相对项目操作和中性示例。个人仓库账户文字改为origin/相对链接，不改平台本身的公开归属。
- **候选/证明**：旧私有候选以独立别名呈现，不含其旧SHA前缀；对应映射仅私下。verification阶段表逐行核对原件的模型/范围/版本/通过失败skip/资源/退出/未验边界，保存私下对照。公开摘要不当原文、不把旧446或36k当新代码实测。公开产物如有校验清单，按实际新文件生成，不能挪用原件哈希。
- **清单/链接**：初始155个候选文件的逐项处置与全部待发布文本覆盖表保存于仓库外；公开仅分类/相对文件或非敏感别名/原因及汇总，不带原值。更新所有handoff链接和工具入口，保留被引用的领域文档锚点，私人材料不设假公开链接。check_docs从现有实现迁移后仅输出类别/路径/计数，绝不打印命中地址。
- **命令/完成标准**：tools/check_docs.py .、链接/Markdown结构和25AC/原catalog需求ID检查、人工摘要逐行核对；无源文件功能变化。完整隐私复扫由04/05执行，不能自行宣称已全树无残留。

## PRIV-04 通用发布检查与历史过滤工具（1.5～2小时，Astra）

- **依赖/状态**：Analyze后可并行；不对真实源仓库执行改写。支持AC-001-2/001-3、AC-002-1/002-2/002-4、AC-005-3、AC-006-1/006-2/006-3、AC-007-1/007-3。
- **唯一写范围**：新增tools/check_public_release.py、tools/rewrite_public_history.py、catalog/acceptance/test_public_release.py；仓库外本轮专用public-privacy/operator工具/规则/测试资产。不得写其他源码/文档，不改真实Git引用，不推送或访问部署远端/服务。
- **规则/输出**：公开工具不含真实禁止值；机密规则与私有映射输入来自仓库外初始audit和Git元数据，禁止原样写公开fixture或错误消息。scan默认全树，能显式扫描指定两个ref的全部可达blob/message/identity，报告只类别/相对路径/计数，不回显值或上下文。公开学术作者/机构/保留示例与合成值不机械误删。
- **过滤**：现有Git原生filter-branch index/env/message机制+标准库，独立副本，不手写fast-import parser，不安装新应用依赖；仅两个明确分支。原件与私有mapping保全，旧handoff/**仅豁免公开README；保留根与分支拓扑、100644/100755，NUL文件/index接口支持非ASCII路径。历史源码只做对应中性替换且保语法，不将tip新实现灌入早期版本；新feature tip必须与已验收树相同。旧SHA片段从公开候选描述/消息移为不含原SHA的别名。
- **身份/发布边界**：author/committer用非个人贡献者身份和example.invalid邮箱，Unix时间保留/统一UTC；private actor原值不打印。工具只输出受保护发布所需本机计划，不执行真实远端push。main/feature精确旧OID租约、一次原子两ref更新与失败停止契约需可测试；不得裸force/mirror/all，不能更改保护规则或租约。
- **真实合成演练**：临时Git仓库包含实际相关的根/两分支共祖先/重复blob/mode100644与100755/非ASCII文件名/消息与身份。验证覆盖全部历史而不只tip、原仓库不变、输出当前树一致、旧归档README豁免、实际文件路径不误转义；本地bare模拟远端证明租约不匹配拒绝且两ref原子不部分更新。public测试不包含真实敏感值，规则数据用假身份/保留示例。
- **命令**：完整catalog/acceptance/test_public_release.py，两个新工具--help与自测、AST/UTF8LF/diff；不在此任务执行真实改写/发布，不以自己的扫结果代最终Review。

## PRIV-05 主会话集成、原件与新候选验证（1小时，主会话）

- **依赖**：01～04全部结束；无运行实施者。覆盖上述AC及AC-004-4、AC-007-1/007-2/007-3。
- **步骤**：只读复核完整差异、模型/通道/测试；共享参数名与新增前缀调用链逐层核对。主会话不自行改业务/工具，缺陷交Astra原任务边界修复。刷新仓库外bundle/工作区/原件清单并恢复验证，不能拿旧备份称新起点。
- **证明**：完整catalog/tests+catalog/acceptance；Python3.12 AST/UTF8LF/无BOM、根编译/shell语法、文档检查、机密规则全树扫描和逐项处置。公开verification表与私下原件逐项核对，审核员产物数字/结论逐项保持。私有规则和详细原命令不入库。
- **命令**：现有venv完整pytest；tools/check_docs.py .；tools/check_public_release.py --help所声明全树机密规则命令；保存每个exit与全部适用检查数。目标PG尚未授权时明确skip/未验，若需补必须先申请，不冒用旧446/36k。

## PRIV-06 真实历史的独立本机演练与复扫（1～2小时，主会话操作）

- **依赖**：05通过并形成固定新候选。支持AC-001-2/001-3、AC-005-3、AC-006-1/006-2/006-3、AC-007-1/007-3。
- **操作范围**：只在仓库外新副本执行已审工具，备份最新源历史/工作区并核恢复；保留私有旧新OID/租约，不改原工作副本/部署远端或真实GitHub引用。
- **验证**：两ref的全部可达blob、提交消息、author/committer复扫；Unix时间/拓扑/mode、当前feature树与05验收树逐项一致；原引用仍可恢复。重写main旧tip做适用静态编译/隐私检查，feature做完整集成；任何源码意外变化或泄漏即停止交Astra修复。
- **证据**：公开仅覆盖/通过状态与限制，完整mapping/树和ref原值私下。不得把未发布演练称远端完成。冻结差异交独立PrivacyReview，再必要Gate2。

## PRIV-07 独立评审、受保护发布与交接（1～2小时，主会话协调/操作）

- **实际进展**：R5与用户Gate2通过；原精确租约与实时origin相符，A4的plan/new_oids逐项核对后一次atomic+两条lease成功。全新bare从GitHub新取两ref，实际OID/tree与批准候选一致，72提交/483blob/699文本规则0、独立555记录0未处置；其他公开引用未变。本机先detach到同树新候选，再原子CAS更新main/功能分支，工作树相同干净；旧私有refs/reflog盘点完成禁止回传，部署远端配置/引用未变。交接/PR #1/正常匿名UTC合并及合并后新取远端复扫完成；仅正常追加完成记录并持续复扫，未执行部署/新目标PG/材料。

- **依赖**：05/06，独立Claude实际Review通过并取得必要Gate2；用户历史授权不被撤回，精确租约仍匹配。覆盖AC-006-2/006-3、AC-007-4及全部未验风险说明。
- **审核**：核spec/plan/tasks、实际源码/文档/归档/工具/历史差异，查bug、隐私残留、测试缺口与许可/安全对齐；原报告非公开，公开摘要标明范围和局限。新目标PG未验、旧证据支持边界不可隐瞒。
- **发布**：重新只读核origin两完整OID仍等于私下旧租约；一次`--atomic`+两个精确`--force-with-lease`及显式main/feature refspec，不裸force、不改保护、不更新其他引用。拒绝即停，不刷新租约覆盖并发。新取远端两ref完整复扫且核新OID，才报告已发布。
- **本机切换（B-1）**：远端验证通过后，先保存此时未提交变化，再fetch并切换本机main/feature到已验收新OID；核工作树。完成前禁止从旧历史开/推新分支。for-each-ref与reflog私下盘点仍旧历史引用（含部署跟踪引用/备份），公开说明范围且不得回传origin；不动部署远端本身。
- **交接**：补架构目录服务章与编号记录边界、更新review/状态，使用脱敏PR正文；涉及语义冲突回Analyze/Converge。为不重引提交者信息，合并也用本机非个人身份/UTC创建正常no-ff merge，再仅fast-forward推main并核GitHub PR状态，不用托管默认个人提交身份，不放宽保护。新merge及远端两ref须再隐私复扫。部署/正式导入仍另获许可，不将代码合并写成feature真实材料验收完成。
