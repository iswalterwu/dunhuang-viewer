"""命名规则与数据登记的唯一源头；随导入批次记录规则版本。"""

RULE_VERSION = "2026-10-28.1"

NLC_CATEGORY = "中国国博馆藏"
BATCH_CATEGORIES = {
    "188敦煌001": ("2018年", "2019年新增1", "2019年新增2", "2019年新增3", "2501-2600"),
    "188 敦煌002": ("202106新增",),
}
KNOWN_CATEGORIES = frozenset((*BATCH_CATEGORIES, "敦煌003", "敦煌004", NLC_CATEGORY))
PELLIOT_RANGES = ((2001, 4099), (4500, 5043), (5522, 6038))
TIFF_EXTENSIONS = frozenset({".tif", ".tiff", ".btf"})
NLC_ATTACHMENTS = {"manifest.json": "manifest", "report.json": "report", "index.json": "index"}

SEGMENT_NAMES = frozenset({
    "分段", "分", "切片", "片", "斷巻分段", "全巻分段", "全巻分", "全卷分", "寫 1巻分段",
})
CONTEXT_PRIORITY = {"regular": 0, "segment": 1, "version": 2, "page": 3}


def image_role(kind: str, filename: str, root: str, context: str, ordinary_tiffs: int) -> str:
    """plan §4.4 的角色优先级；参数均已由扫描与单元入口确定。"""
    if kind == "psb":
        return "PSB 源文件"
    if kind == "tiff" and filename.lstrip(".").startswith("合并长卷"):
        return "合并长卷"
    if root == "backup":
        return "已迁出的分片"
    if context == "page":
        return "页图"
    if context == "version" or (kind == "jpg" and filename.endswith("_preview.jpg")):
        return "另一版本"
    if context == "segment":
        return "分段"
    return "单幅整卷" if ordinary_tiffs == 1 else "分段"


PSB_COLOR_MODES = {
    0: "BITMAP", 1: "GRAYSCALE", 2: "INDEXED", 3: "RGB", 4: "CMYK",
    7: "MULTICHANNEL", 8: "DUOTONE", 9: "LAB",
}
