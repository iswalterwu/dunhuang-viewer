# D-005 内存安全红线

- 日期：2026-10-27（追认登记；决策于 2026-10-18 事故后生效）
- 状态：accepted

## 背景

2026-10-18，NAS 对一个 4GB 单卷做整卷解码，被拖进交换；设备容量、容器数量与交换现场非公开。
依据：`README-部署.md`「内存安全设计」、`docker-compose.yml` 头部注释。

## 备选方案

- 不设限的整卷解码（事故前状态）

## 结论

1. 每个容器 `mem_limit` = `memswap_limit`（禁用额外 swap），超限由 cgroup 杀掉容器，NAS 本身不受影响
2. `VIPS_CONCURRENCY=1`；在线图块生成、拼接各自单并发
3. 可用内存低于 `MEM_GUARD_MB` 时拒绝解码（在线图块、缩略图、局部区域、拼接分片预览）
4. 像素数超过 `FULL_DZI_MAX_PIXELS`，或色彩/位深不属于 RGB / 灰度 / uint8 时，只生成预览分辨率
5. 后台生成器在可用内存低于 `BUILD_MEM_FLOOR_MB` 时等待，并按 `BUILD_STRIP_MB` 选择图块尺寸
6. 以上阈值只许收紧；放宽须先登记新 ADR

## 取舍理由

牺牲超大卷的全分辨率与生成速度，换取 NAS 整机稳定：查看器出问题只会自己被杀并自动重启。

## 影响

- `docker-compose.yml`、`app.py`、`pyramid_worker.py`
- 参数一览见 `architecture.md` §10
