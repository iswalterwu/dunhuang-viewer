"""导入内部的浅只读映射：共享键索引，不缓存行值或冻结 JSON 叶。"""

from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(slots=True)
class _Shape:
    keys: tuple
    index: dict


class CompactMap(Mapping):
    """只保存形状与值 tuple；写入前由调用方显式建立新的 dict。"""

    __slots__ = ("_shape", "_values")

    def __init__(self, shape, values):
        self._shape = shape
        self._values = values

    def __getitem__(self, key):
        return self._values[self._shape.index[key]]

    def __iter__(self):
        return iter(self._shape.keys)

    def __len__(self):
        return len(self._values)


class ShapePool:
    """每次 loader / compute 独有的 64 形状 LRU，无绑定方法缓存或行引用。"""

    __slots__ = ("_shapes", "__weakref__")

    def __init__(self):
        self._shapes = OrderedDict()

    def compact(self, mapping):
        if isinstance(mapping, CompactMap):
            return mapping
        keys = tuple(mapping)
        shape = self._shapes.get(keys)
        if shape is None:
            shape = _Shape(keys, {key: index for index, key in enumerate(keys)})
            self._shapes[keys] = shape
            if len(self._shapes) > 64:
                self._shapes.popitem(last=False)
        else:
            self._shapes.move_to_end(keys)
        return CompactMap(shape, tuple(mapping.values()))
