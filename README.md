# dunhuang-viewer

敦煌开放资源研究平台（建设中）：面向敦煌研究者，梳理并关联写卷、壁画、研究论文与参考资料。
第一阶段整理 NAS 上现有的敦煌写卷影像（标注、分类、命名规范）。

v0 是基于 NAS / Docker 的高清查看器，直读 TIFF 扫描件、生成缩放图块，供电脑、手机、平板浏览器浏览。具体设备与服务入口由部署方非公开配置。

本仓库公开的是代码与通用说明，**不代表影像已获开放许可或服务开放注册**。第三方接收不构成机构授权；来源与许可不明的材料不对外展示高清影像。隐私发布边界见 [D-019](docs/decisions/20261030-public-code-and-privacy.md)。平台本身显示的仓库发布者身份不在隐藏承诺内；已有第三方副本也不能保证撤回。

- agent 与开发者入口：[AGENTS.md](AGENTS.md)
- 方案、架构与设计：[docs/](docs/)（总方案见 [docs/plan.md](docs/plan.md)）
- v0 部署与日常运维：[README-部署.md](README-部署.md)
- 目录服务与配置：[catalog/README.md](catalog/README.md)
- 历史测试与评审的脱敏衍生摘要：[docs/verification.md](docs/verification.md)
- 公开交接入口：[handoff/README.md](handoff/README.md)；原始详细档案非公开保全
- 当前规格与待验状态：[specs/README.md](specs/README.md)
