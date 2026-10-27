# D-009 代码与部署通道：GitHub 私有仓库 + NAS 部署目录 git 化

- 日期：2026-10-27
- 状态：accepted

## 背景

部署目录 `/srv/example/viewer` 原本没有版本管理，代码只存在 NAS 上。2026-10-27 用户要求把项目推送为 GitHub 私有仓库 `dunhuang-viewer`。

## 备选方案

- NAS 直接推送 GitHub：NAS 上现有的 GitHub 密钥是另一个仓库（legacy-operator）的 deploy key，无权推送本仓库；需另配 deploy key

## 结论

- GitHub 私有仓库 `contributor/dunhuang-viewer`（默认分支 `main`）为代码权威
- NAS 部署目录初始化为 git 仓库，设置 `receive.denyCurrentBranch=updateInstead`，接收推送即更新工作区
- 本机工作副本 `/srv/example/project` 配两个远端：`origin`（GitHub）、`nas`（NAS 部署目录）
- `.gitignore` 排除 `.env`、`cache/`、`pyramids/`、`thumbs/`、`build.log`；`.gitattributes` 统一 LF 行尾

## 取舍理由

- 本机已有 GitHub 凭据，无需在 NAS 上新增密钥
- updateInstead 省去在 NAS 上手动拉取的步骤
- 代价：NAS 部署目录的工作区必须保持干净，禁止在 NAS 上直接改代码

## 影响

- `AGENTS.md` §4 部署约定；`architecture.md` §9
