# catalog-foundation — Converge 实现核对

> 2026-10-29，主会话对照已批准spec7、原plan8及本轮独立核对后的plan9、tasks、实际源码/测试与T24/T32证据进行核对。起点 `private-candidate-036`。这是实施收敛记录，**不是独立审核员 A 的 Review、不是 Gate 2，也不宣称真实全量验收通过**。
> 当前结论：plan9经独立Checklist12→Tasks→Analyze13（12项全通过）后P10仅两文件实现，候选private-candidate-047在NAS **423 passed/0 skipped/1原有警告，59.66秒**，54db项全执行。**P1仍开：6k真库重导153.01MiB（旧175.71）、差异160.58，两种36k趋势532.82/586.54MiB未过事前480操作门槛，按约定停止/清理，未36k/未OOM/未R2。** Converge不收敛/不进Gate2，T33已获准并完成受限归因，报告memory-diagnosis.md推荐A为主/C小任务辅选，用户现同意Plan10独立核对后实施，Checklist14/Tasks后Analyze15现全12项通过允许C/A串行，P12/P13已C/A串行本机就绪（442项387通过/55skip/1原有警告），新目标真PG/资源T36待验；spec、plan9/checklist及硬限额未再改。

## 1. 范围与证据边界

已完整核对 catalog 的配置/CLI、扫描事实、单元、编号、影像/写卷身份、规则、国图、派生、v0 边界、导入/持久化/报告、API、迁移与运行配置，并核对对应测试的实际断言。v0 源码及根镜像/compose/依赖与 main 无差异；未接入公网、未新增目录写接口、取消/回滚 API 或 CLI 导入。

- 旧候选 `private-candidate-035`：T-24 A2 真库/Python 3.12.15 为 402 passed / 0 skipped / 1 原有警告，证据在 T24-A2（非公开历史记录）。该结果不覆盖本次新增 C1 回归。
- P7 修复后主会话本机：362 passed / 42 db skipped / 1 原有警告（404 collected）；本机 Python 3.14.2，不能冒充 Python 3.12/SQL 新证据。源输出归档随 P7 记录。
- 新候选 A3：private-candidate-038 的404项全部通过、0跳过，含两条新增C1回归与全部42个db项；API实际cgroup memory=memsw=536870912、DB384m；Compose合成config -q通过；证据 T24-A3（非公开历史记录），临时库/容器/卷/网络/镜像/快照/凭据均已清理，v0未改动或重启。
- 新候选A4：private-candidate-042的 **412 passed/0 skipped/1原有警告，46.08秒**，43个db项实际执行。2k/6k真实PG二次加载/重导等价通过，但资源目标尚未完成；无36k实测。源码/探针/结果/清理见 T28-scale-A4（非公开历史记录），先读README。所有临时资源/凭据已清理、v0 ID/启动/restarts未变。
- 最新T32-A1：候选private-candidate-047在NAS **423 passed/0 skipped/1警告，59.66秒**，54db全执行；游标/外事务/两异常路径的新11项实际通过。2k/6k/差异6k真库等价与S0定位通过，但未满足放大条件，未36k；资源全清理，v0不变。证据 T32-A1（非公开历史记录）。
- 表中 **S**：源码与真实合成文件/数据库测试具有实现、断言及可复现路径，新版本已由T32-A1全套复验；**S+N**：软件路径已核对，但真实材料/服务/性能还须 T-25/T-26；**N**：AC 核心结论仅部署后可证明。
- S 不表示学术认定、生产配置或全部 AC 已验收。T-25/T-26 未获许可；没有因此启动正式服务或扫描真实材料。

P10仅改loader读法及真实PG测试，plan9按顺序核对后才实施；本机369通过/54skip与T32目标423全通过分开记录。下表软件路径现经T32完整复验，但P1资源目标仍未关闭，不能将S或设计核对当独立实现Review/规模收敛。

## 2. 58 条 AC 的实际映射

测试路径均相对 `catalog/tests/`；函数名取自当前真实实现，不仅核对 plan 中的预期名称。合成数据与 HTTP 边界替身不当作 NAS 实际覆盖/性能证据。

| AC | 实际实现与测试核对 | 结论与后续 |
|---|---|---|
| AC-001-1 | importer._coverage / v0.fetch_index；test_import::test_v0_index_coverage；valid/未就绪/索引落后/已删除目录分别断言 | S+N；A1 需本批有效真实索引，旧快照不替代覆盖 |
| AC-001-2 | scan._scan_root/_classify；test_scan::test_image_inventory_complete；每文件一个清单条目，隐藏文件不丢 | S+N；A2 对照实际 TIFF/PSB/页图/备份数量 |
| AC-001-3 | units._walk_unit/_finish_units、importer._read_attachments/_save_attachment；test_import::test_attachments、test_attachment_raw_roundtrip | S+N；A2 核对真实附件/无关联位置，原字节已测 |
| AC-001-4 | Inventory.excluded/UnitsResult.excluded 汇入报告与 anomaly；test_scan::test_excluded_listed_with_reason | S+N；A2 逐项说明真实排除路径/原因 |
| AC-002-1 | identity.resolve_items / _assign_item_images；test_identity::test_same_number_merged_across_lineages | S+N；A2 实际 P.2002 两套影像 |
| AC-002-2 | units._subdir_context/_walk_unit 与 rules.image_role；test_units::test_subdirs、test_segment_vocabulary、test_nlc_pages_preview_and_tiles | S+N；A2 词表外目录及页图对象核查 |
| AC-002-3 | units._loose_files；test_units::test_loose_files；真实临时文件与单元编号来源 | S+N；A2 原基线8个散放文件 |
| AC-002-4 | identifiers 多号、identity 共享关联；test_identity::test_multi_number_units_share_images | S+N；A2 实际7个多号目录/合装线索 |
| AC-002-5 | Identifier.parent/part、identity._parent_key/_finish_items；test_identity::test_parts_and_parent；test_api::test_resolve | S+N；A2 P.2504 母件及四分件共5件 |
| AC-002-6 | units._merge_suggestions 不分配身份；test_units::test_merge_suggestions_only、test_paper_back_pair_and_compliant_units_not_suggested | S；WB/帙号只建议，不自动合并；真实对象另在A2查 |
| AC-002-7 | backup 镜像归属与角色优先级；test_units::test_backup_fragments_mapped、test_backup_can_supply_images_for_original_attachment_only_directory | S+N；A2 925个分片、原位置与对不上异常 |
| AC-002-8 | 号段存疑 key=None，不按号归并；test_identity::test_doubtful_numbers_not_merged | S+N；A2 三个 P.0901 对象分别保留 |
| AC-003-1 | resolve_images/resolve_items 与持久化；test_identity::test_reimport_keeps_ids、test_import::test_full_repeat_import_and_new_files_appear | S；ID/关联/历史不重复 |
| AC-003-2 | 先签名后位置的两阶段认领、image_path_history；test_identity::test_rename_move_and_swap；API历史详情测试 | S；真实改名/移动/互换，不复制算法 |
| AC-003-3 | UUIDv4 分配；test_identity::test_ids_not_path_derived、schema稳定UUID | S；相同路径独立初建不同ID |
| AC-003-4 | S0 同时决策与编号历史；test_identity::test_number_change_keeps_id；test_import::test_number_swap_end_to_end | S；ID保持、旧号历史化 |
| AC-003-5 | identity._item_decisions/_rollback_collisions；test_identity::test_unmatched_cases_kept_pending（五情形及改回） | P9已补全部参与ID/稳定顺序，38项identity及A4全套通过；待独立R2，不改算法 |
| AC-003-6 | 旧影像数量/serial确定新影像归属；test_identity::test_new_images_assignment、test_new_images_assignment_between_unkeyed_items、test_multi_number_new_images_shared | S；数量并列取较早登记 |
| AC-003-7 | 改号提案同时生效、临时唯一值释放；test_identity::test_swap_and_rotation_order_independent、test_import::test_number_swap_end_to_end | S；两件互换/三件轮换含真实SQL |
| AC-003-8 | 新增号与单号改写分开处理；test_identity::test_multi_number_add_and_rewrite | S；原ID/共享关联不丢 |
| AC-004-1 | identifiers.parse_identifiers、疑似号入口限定；test_identifiers::test_pelliot_variants_and_suspected、test_units::test_loose_files | S；原文、裸号/尺寸/年/多号区分 |
| AC-004-2 | PELLIOT_RANGES与存疑规范号；test_identifiers::test_ranges_and_doubtful | S；可检索但不作主号/归并 |
| AC-004-3 | nlc._resolve_identifiers 权威仅一级国图单元；test_nlc::test_pressmark_authority、test_import::test_nlc_authority_does_not_override_outside_vocabulary_child | S；大小写/冲突/缺清单/不合规及IDP来源 |
| AC-004-4 | sharer/zhihao 非主号；test_identifiers::test_sharer_and_zhihao_systems、test_import::test_share_numbers_and_zhihao_are_not_doubtful_collection_numbers | S；帙号需开宝藏上下文 |
| AC-004-5 | _identifier_rows 单一现行主号与SQL索引/检查；test_identifiers::test_primary_only_compliant、test_db::test_one_current_primary_but_history_kept | S；共享号/存疑号不能主号 |
| AC-005-1 | scan.read_facts/7字段三态/失败重读；test_scan::test_facts_by_kind；P7新增JPEG安全异常与compute流水线恢复回归 | S；C1已在A3/Python3.12/真库全套复验通过 |
| AC-005-2 | rules.detect_lineage/summarize_lineages；test_rules::test_lineage、test_directory_summary_only_direct_tiffs | S+N；A3 447/499/12/5138目录汇总待实料 |
| AC-005-3 | derivation 白名单、最后成功操作/证据行号、缺证据异常；test_derivation::test_stitch_and_psb_logs、test_api::test_derivation_details | S+N；A2 12个输出须逐对象有派生或异常 |
| AC-005-4 | nlc._map_canvases，索引从0起，strips列表或文件名回退；test_nlc::test_canvas_mapping | S+N；A4 真实TIFF对应率/异常 |
| AC-005-5 | item_image.source_directory/lineage、影像多对多；test_identity::test_image_sets_distinguishable；API影像详情/关系 | S；全部版本保留，不选择首选影像 |
| AC-006-1 | rules.source_policy/_inherited_policy 与逐字段basis；test_rules::test_license_defaults、test_nlc_attribution_from_manifest_or_explicit_default | S；默认规则/推断与未知显式保留 |
| AC-006-2 | item_display_policy 取最严格，API全登录墙；test_rules::test_item_policy_most_restrictive、test_auth 登录拒绝 | S；不是对外开放许可 |
| AC-006-3 | TRANSFER_EVENT/DOWNLOAD_EVENT/LOCAL_EVENT；test_rules::test_channel_is_specific_event | S+N；A2核对真实对象取得事件，不推断新增资料来源 |
| AC-007-1 | Provenance/status/evidence/judge/at；test_rules::test_every_item_has_provenance | S；无空初值 |
| AC-007-2 | 只凭合规号且无反证才确认；test_rules::test_confirmed_only_without_counter_evidence | S；未知/存疑不误确认 |
| AC-007-3 | 开宝藏/6类题名线索、冲突异常；test_rules::test_non_dunhuang_suggestions_and_conflicts | S+N；A2实际18+6目录逐对象核查 |
| AC-007-4 | user:结论/basis保留；test_import::test_human_conclusion_survives_reimport | S；真实PG中人工先验不会被规则覆盖 |
| AC-008-1 | original_positions/original_name/original_path与路径历史；test_import::test_raw_names_verbatim、test_api::test_details_attachments_history_and_reports | S；繁简/全角/法文/尾标/点均原样 |
| AC-008-2 | attachment.raw bytea、只读API响应；test_import::test_attachment_raw_roundtrip、test_api::test_details_attachments_history_and_reports | S；磁盘附件删后仍能原字节返回 |
| AC-009-1 | 新文件增量与未变记录；test_import::test_full_repeat_import_and_new_files_appear | S；真实文件+PG，不模拟DB |
| AC-009-2 | missing_since/state、保留item/identifier；test_import::test_missing_marked_not_deleted_and_reappearance | S；整件缺失不删除信息 |
| AC-009-3 | 大小/mtime/inode变化、位置延续及历史；test_import::test_changed_file_history_and_value_at_any_run | S；原子覆盖不与移动混测 |
| AC-009-4 | import_run起止/状态/触发者/版本/counts/health；test_import::test_full_repeat_import_and_new_files_appear、test_api::test_auth_and_admin_import | S；report CLI/API用保存报告不重算 |
| AC-009-5 | 回收站→原位/别处恢复；test_import::test_missing_marked_not_deleted_and_reappearance（双参数） | S；ID/原关联保留，重新出现计数 |
| AC-010-1 | _collect_anomalies/build_report及API分页；test_import::test_anomaly_categories（18类）、P7 JPEG流水线异常回归 | S；结构化对象/原文/说明，合并建议双端关联 |
| AC-010-2 | 34项固定JSON基线/只读compare/42个对照测试；无重扫或复制归并 | N；真实报告、差异说明及3项人工证据仍待A2 |
| AC-011-1 | 唯一HTTP认证边界/管理员/503/401/403/202/409；test_auth；test_api::test_auth_and_admin_import、test_secret_missing_rejects_data_and_trigger | S+N；T-25真实v0登录态/普通用户冒烟未做 |
| AC-011-2 | resolve只current、母号含分件；test_api::test_resolve | P8撤销pending不再冒充historical，过去history保留；A4真实PG/API断言通过、待R2；实际对象A2补证 |
| AC-011-3 | SQL筛选/稳定分页/只读事务；test_api::test_filters_and_pagination | S+N；A6全量NAS列表/详情各100次P95尚未测 |
| AC-011-4 | latest_valid_snapshot、viewer_link与目录存在检查；test_api::test_v0_links、test_v0_empty_failed_snapshot_and_never_valid | S+N；A7抽20真实卷链接，不能只看页面200 |
| AC-011-5 | 唯一写方法仅POST imports；test_api::test_no_mutating_routes | S；无目录写/取消/回滚/CLI导入 |
| AC-012-1 | compose四项ro、外部pgdata、运行契约；T24测试无真实宿主挂载/端口 | N；T25 inspect正式挂载，A5原图/备份前后元数据归因 |
| AC-012-2 | derivation.open_cache_record仅13名，导入不读users；test_import::test_v0_cache_access 实际open审计 | S+N；A5正式访问记录/ro核对，不遍历cache |
| AC-012-3 | compose/API512m=memswap、HealthMonitor；T24受限小规模合成容器 | P10后T32资源有改善仍未过放大条件：same6k153.01/varied160.58MiB，36k仅趋势532.82/586.54；P1未闭，已暂停，未36k，不以A5待验/423全绿掩盖 |
| AC-012-4 | 成功未变事实复用、失败重读；test_scan复用回归 | N；A5全量≤1小时、无变重跑≤10分钟未证明 |
| AC-013-1 | importer._basis、字段/关联/规则作者与版本；test_import::test_field_basis_and_author、test_changed_file_history_and_value_at_any_run | S；触发者非字段作者；P8共享/版本时间隔离/真PG JSON历史等价回归在A4通过，待独立R2 |
| AC-013-2 | file-header/外部清单为确定，谱系/默认规则为推断；test_import::test_field_basis_and_author、test_rules及nlc依据断言 | S；confidence实际断言在综合用例中 |
| AC-013-3 | history变化快照、value_at_run、API history；test_import::test_changed_file_history_and_value_at_any_run、test_rule_version_change_recorded_at_batch；API详情历史测试 | S；含任意后续无变化批次取最近已存值 |

## 3. plan 测试名与当前测试的对应

冻结 plan 中7个预期名称被实际综合用例合并/改名；未把不存在的名字当已执行，也未为凑名字复制业务或重复执行测试。实际命令跑完整文件，新增调用应使用右侧名称：

| plan 预期名称（test_import.py） | 实际综合测试 |
|---|---|
| test_new_files_appear | test_full_repeat_import_and_new_files_appear |
| test_import_run_record | test_full_repeat_import_and_new_files_appear |
| test_missing_marked_not_deleted | test_missing_marked_not_deleted_and_reappearance |
| test_reappearance | test_missing_marked_not_deleted_and_reappearance |
| test_changed_file_history | test_changed_file_history_and_value_at_any_run |
| test_value_at_any_run | test_changed_file_history_and_value_at_any_run + test_rule_version_change_recorded_at_batch |
| test_confidence_labels | test_field_basis_and_author（含确定/推断实际断言），并有rules/nlc来源置信度回归 |

## 4. Converge 缺口与当前处置

**C1 / T-27，AC-005-1/AC-010-1**：Pillow 的 DecompressionBombError 不是现有捕获父类，造成单个文件头问题中断整批。主会话合成复现后，P7 Astra 只在 scan.read_facts 明确捕获此已知库异常，沿用 missing/error 流程；新增两条真实文件回归验证三态、失败重读、有效头恢复、其他影像继续、对象身份不变与异常清单。没有关闭 Pillow 防护、提高资源限制、解码大图或宽泛吞异常。主会话本机362项通过/42个db跳过；新候选A3/NAS完整404项实际通过且资源清理完成。C1已关闭，不据此声称其他未知bug不存在或真实材料验收完成。

其他核对：正式读查询用只读 repeatable-read事务、外部值参数绑定；咨询锁/连接跨后台生命周期；有效空/失败快照不错误回退；附件原文逐单元消费；原有/缺失关联与人工出处保留；派生只信最终成功证据；许可取最严格；无新的原图写入或v0改动。没有因为猜测罕见情形引入Q-025已删机制。

## 5. 独立 Review 已返回，需修复后重审

R1实际审阅private-candidate-039。首选claude-bridge因接入不可用exit=1、无结论；回退同Claude模型经Anthropic API正常exit=0，报告「需修复后重审」。CR1-01为P1，主会话又用2000/6000影像、每卷6个微型PSB头的真实计算流程复测，约23KiB/影像首轮、30KiB/影像重导；36k含基线线性估算865.5/1111.4MiB（Windows/Py3.14，不是NAS实测），明确高于512MiB。其他确认的小缺口为撤销候选状态语义和冲突说明；未证实/低概率CR1-03/04留真实材料核查，不擅自改规则。

完整独立原文/范围在review.md与 CodeReview-R1（非公开历史记录）。用户批准后P8/P9已最小复用及修两处小缺口，源码/本机结果在 R1-fix-batch（非公开历史记录）；新候选private-candidate-042在A4/NAS/3.12/真PG全412项通过，不沿用旧404。

真实PG prepare/execute两次：2k首轮/重导RSS94.72/109.96MiB，6k133.24/175.71MiB；第二次全部事实复用、ID/basis摘要/history不变、变化为零。TIFF属性高度同质、仅外部HTTP替身，非真实材料吞吐/并发API/连续v0健康。两点RSS斜率16.832KiB/影像，36k线性约668.83MiB，不是全量实测/OOM；cgroup有可回收页缓存，不能当匿名内存外推。

独立6k只读S0探针加载前78.94/后143.17MiB，image.field_basis文本均值4803bytes。读取缓冲及Python常驻结构都需定位，不能保证只改游标足够。**已按停止条件暂停扩大/后续实施，T28资源目标未完成、未派R2。** 用户现已批准T31小幅设计调整：先Plan9/独立Checklist/Tasks/Analyze核对有界服务端游标抓取，保留完整字段、内存计算/持久化和事务锁；不擅自流式重构/缩列/扩限。T29/T30实现/真库回归完成仍不代独立审核关闭。A4全部临时资源与凭据已清理，无运行子agent。

T31/P10及T32最新结果：候选private-candidate-047全423真库通过，54db项/协议trace实际执行；same2k/6k重导RSS102.37/153.01MiB，varied6k160.58，原S0同口径峰值143.17→109.02MiB且文本大小不变。读取缓冲确有改善，但残余完整S0/扫描/读取与当前结果的对象/阶段占用尚未精确归因。事前放大判据要求same两点及varied6k投影均≤480MiB，实际532.8164/586.5352MiB，false；这是操作安全门槛非新AC，未做36k/未OOM。**再次按约定停止新实施与放大，未发R2；T33仅建议受限归因/方案对比，待用户决定，不先重构/改plan9。** T32五API自然exit0，临时库/PG卷/网络/镜像/快照/.env/raw全清理，v0状态不变；完整证据见T32-A1/README。

T33仅诊断返回：无hook6k160.48MiB、阶段160.99（CPU耗时3.63倍）；对象图去重71.677MiB，双状态四类影像外层25.269、策略循环独占4.108，图观察器seen约33MiB额外。生效S0读取后主增量是当前行构造。容量/可达子集不是RSS节省，未改业务/冻结计划；方案对比在memory-diagnosis.md，全部本轮资源清理，P1未闭。

Gate 2 需用户确认评审结果及部署后待验风险，不能由本报告自动批准。真实材料计数/对象关系、正式只读挂载/端口/pgdata、v0连续健康、全量资源/耗时、P95及链接抽查都留T-25/T-26；feature保持in-progress，不称全量已收敛，不启动正式部署。
