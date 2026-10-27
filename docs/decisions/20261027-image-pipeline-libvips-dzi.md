# D-003 图像管线：libvips 流式解码 + DZI 图块

- 日期：2026-10-27（追认登记；决策早于本文件）
- 状态：accepted

## 背景

单卷可达数 GB，含 CMYK、16 位、超长卷；流式解码用于限制内存占用。
依据：`app.py` 导入处的 libvips 优先及流式解码说明；私人设备容量非公开。

## 备选方案

- Pillow 整卷解码：保留为没有 libvips 时的兜底，超过 1.5 亿像素直接拒绝

## 结论

- libvips（pyvips）以 `access="sequential"` 流式读取，`dzsave` 生成 DZI（JPEG 图块，参数 `TILE_SIZE`、`TILE_QUALITY`）
- tifffile 读取元数据；对未压缩 TIFF 自写按行/按区域流式读取，用于预览、缩略图与局部区域
- 前端用 OpenSeadragon 加载 DZI（D-004）

## 取舍理由

- 流式解码的内存只与图块行相关，不随整卷像素增长
- DZI 是 OpenSeadragon 原生格式，浏览器只下载可视区域的图块

## 影响

- `Dockerfile` 安装 `libvips42`；`requirements.txt` 含 `pyvips`
- 细节见 `architecture.md` §4、§5
