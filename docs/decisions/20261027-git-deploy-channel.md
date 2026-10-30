# D-009 历史代码与部署通道：GitHub + NAS 部署目录 git 化

> 公开隐私修订：私人部署实例与原件非公开保全；历史验证为脱敏衍生记录，不是逐字原文。配置占位不代表真实主机。

- 日期：2026-10-27
- 状态：部署通道约定仍 accepted；原私有可见性要求已被 D-019 取代，现行仓库保持 Public

## 背景

部署目录 `${DH_DEPLOY_DIR}` 原本没有版本管理，代码只存在 NAS 上。2026-10-27 用户要求把项目推送为 GitHub 私有仓库 `dunhuang-viewer`。

## 备选方案

- NAS 直接推送 GitHub：需要单独配置托管平台授权，不采用该通道；私人账户与密钥配置不公开

## 结论

- 本项目 GitHub 仓库（远端 `origin`，默认分支 `main`）为代码权威；当时的私有要求仅作历史记录，当前可见性按 D-019
- NAS 部署目录初始化为 git 仓库，设置 `receive.denyCurrentBranch=updateInstead`，接收推送即更新工作区
- 本机工作副本配置 `origin`（代码托管）与 `nas`（部署远端角色名）；工作站位置由操作者非公开配置，迁移不改变部署通道。部署目录由 `DH_DEPLOY_DIR` 指定
- `.gitignore` 排除 `.env`、`cache/`、`pyramids/`、`thumbs/`、`build.log`；`.gitattributes` 统一 LF 行尾

## 取舍理由

- 托管平台授权仅由本机操作角色管理，不要求在 NAS 上新增托管密钥
- updateInstead 省去在 NAS 上手动拉取的步骤
- 代价：NAS 部署目录的工作区必须保持干净，禁止在 NAS 上直接改代码

## 影响

- `AGENTS.md` §4 部署约定；`architecture.md` §9
