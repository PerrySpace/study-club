"""文档 → 接口出参的序列化。

**实现已移到 `app/core/serializers.py`**（唯一真源），这里只是控制层的历史入口。
放在 core 的原因：`core/response.py` 的响应信封兜底也要用它，
而 core 不应反向依赖 controllers。保留本模块是为了不动各控制器里已经写好的
`from .serializers import serialize` —— 内部导入路径同样遵循「只增不改不删」，
能用一行 re-export 解决，就不要改十个文件。
"""

from __future__ import annotations

from ..core.serializers import serialize, serialize_many, to_iso

__all__ = ["serialize", "serialize_many", "to_iso"]
