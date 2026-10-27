# D-007 认证：登录墙 + 用户管理

- 日期：2026-10-27（追认登记；决策早于本文件）
- 状态：accepted

## 背景

`README-部署.md`「安全提醒」原把服务定位为「无登录认证，仅局域网 / Tailscale 内使用」。
历史服务扩展到公网后必须有登录墙；私人入口、开通日期、实例名称与配置非公开，不能据此推定授权。

## 备选方案

- 无认证、仅内网访问（旧状态）

## 结论

- `.env` 提供 `AUTH_USER`、`AUTH_PASS`、`AUTH_SECRET`、`AUTH_SESSION_HOURS`；三项 `AUTH_*` 齐全才启用登录墙
- 初始管理员由环境变量引导创建；用户表 `cache/users.json`，密码 pbkdf2_sha256
- 会话为 HMAC-SHA256 签名的 cookie `dh_session`；管理后台表单带 CSRF；登录失败按 IP 限流
- 公网可达期间登录墙必须开启

## 取舍理由

- 只用标准库（hashlib、hmac），无外部依赖
- 单 NAS 单实例，无需外部身份服务；签名会话在重启后仍然有效

## 影响

- `.env`（不入库）、`cache/users.json`
- 三项 `AUTH_*` 缺一项即 fail-open（全站匿名可访问），风险见 `plan.md` §10
- 细节见 `architecture.md` §7
