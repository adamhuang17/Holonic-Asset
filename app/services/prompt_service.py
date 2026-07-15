"""Provider prompt construction for one composite-canvas edit."""

from __future__ import annotations


class PromptService:
    """Build the fixed structural prompt required by the image editor."""

    def build(self, instruction: str, item_count: int) -> str:
        return f"""这是一张由多个独立游戏素材组成的规则网格画布，共包含 {item_count} 个需要编辑的素材。

请对画布中的每一个素材执行完全相同的编辑：
{instruction.strip()}

必须严格遵守：
1. 每一个网格区域中的素材都是相互独立的对象。
2. 同时修改所有非空网格区域中的素材。
3. 保留每个对象的主体身份、主要轮廓、方向、位置和所在网格区域。
4. 不得把不同区域的对象合并。
5. 不得让对象跨越其原有网格区域。
6. 不得增加、删除或复制对象。
7. 保持输入画布原有的行列布局和对象数量。
8. 不生成游戏场景、展示板、标题、说明文字或额外装饰。
9. 所有对象必须使用统一的美术风格、色板、光照方向、描边方式和细节密度。
10. 保持浅灰色背景和网格间的空白隔离区域干净。
11. 输出一张与输入结构和宽高比例一致的大画布。"""
