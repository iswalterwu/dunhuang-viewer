# D-018 目录服务的技术形态：Python + FastAPI，独立部署，与 v0 共用登录

- 日期：2026-10-27
- 状态：accepted（`catalog-foundation` Plan 阶段，依据 D-002、D-012、D-016 推定；用户可在 Gate 2 否决）

## 背景

`catalog-foundation` 是前后端分离（D-011、D-016）后的第一个后端服务。D-016 定了数据库（PostgreSQL）与前端（Vue 3），没有定后端语言与部署形态。
该服务要在 受限内存的 NAS 上与 v0 并存（D-005、plan.md RK-01），并与 v0 共用账号（spec R-011）。

## 备选方案

- 后端用 Node / TypeScript，与前端同语言
- 把目录接口并入 v0 的 `app.py`
- 与 v0 共用 `docker-compose.yml`

## 结论

1. **语言与框架**：Python 3.12 + FastAPI + uvicorn，与 v0 的运行时一致（D-002）
2. **部署**：独立的 compose 项目 `dunhuang-catalog`（`catalog/docker-compose.yml`），含 `catalog-db`（PostgreSQL 17）与 `catalog-api` 两个服务；不修改 v0 的 `docker-compose.yml`
3. **资源**：容器内存硬上限、禁用额外 swap（`catalog-db` 384m、`catalog-api` 512m）；原图目录、备份目录与 v0 的 `cache/` 一律只读挂载
4. **访问**：Phase 1 只在局域网与 Tailscale 开放（端口 8504）；公网入口留到 Phase 3（D-012）
5. **认证**：校验 v0 的会话 cookie 与用户表，与 v0 共用账号；缺少 `AUTH_SECRET` 时拒绝所有请求（fail-closed，不同于 v0 的 fail-open）

## 取舍理由

- 影像元数据的读取依赖 Python 的 tifffile / Pillow 生态，v0 已验证；与 related-project 的后端选型一致
- 独立 compose 项目与 v0 互不影响：v0 不重建、不重启，回滚只需停掉新项目
- 只读挂载在结构上保证不会写原始材料（spec R-012）
- 共用登录让用户不用再管一套账号

## 影响

- 新增 `catalog/` 目录；`.gitignore` 增加 `catalog/.env`
- NAS 新增两个容器，内存上限合计 896m；上线前确认可用内存（plan.md RK-01）
- v0 若改变会话 cookie 的格式，目录服务的认证须同步修改
- `architecture.md` 在 `catalog-foundation` Handoff 时补入目标架构
