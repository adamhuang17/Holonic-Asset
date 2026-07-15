"""Provider prompt construction for one composite-canvas edit."""

from __future__ import annotations

from app.exceptions.errors import ErrorCode, error_for
from app.models.edit_plan import EditPlan
from app.models.manifest import CanvasManifest


class PromptService:
    """Compile shared and per-image intent into one grid-aware edit prompt."""

    def build(
        self,
        plan: EditPlan,
        manifest: CanvasManifest,
        image_refs: list[str],
    ) -> str:
        manifest_items = sorted(manifest.items, key=lambda item: item.index)
        if (
            not image_refs
            or len(image_refs) != len(manifest_items)
            or len(image_refs) != len(set(image_refs))
            or [item.index for item in manifest_items]
            != list(range(len(image_refs)))
        ):
            raise error_for(ErrorCode.INTERNAL_ERROR)

        plan_items_by_ref = {item.image: item for item in plan.items}
        if (
            len(plan.items) != len(image_refs)
            or set(plan_items_by_ref) != set(image_refs)
        ):
            raise error_for(ErrorCode.INTERNAL_ERROR)

        item_instructions: list[str] = []
        for sequence, item in enumerate(manifest_items, start=1):
            try:
                image_ref = image_refs[item.index]
            except IndexError as exc:
                raise error_for(ErrorCode.INTERNAL_ERROR) from exc

            row, column = divmod(item.index, manifest.cols)
            edit = plan_items_by_ref[image_ref].edit
            if not edit:
                edit = "无额外单独修改，只执行统一视觉风格和共同修改"
            item_instructions.append(
                f"{sequence}. {image_ref} 位于第 {row + 1} 行第 "
                f"{column + 1} 列：{edit}。"
            )

        shared_style = plan.shared_style or (
            "未指定新的视觉风格；保持各素材主体特征，并使整体色板、光照、"
            "描边和细节密度协调一致"
        )
        shared_edit = plan.shared_edit or "无额外共同内容修改"
        item_block = "\n".join(item_instructions)

        return f"""这是一张由多个独立游戏素材组成的规则网格画布，共包含 {len(manifest_items)} 个需要编辑的素材，布局为 {manifest.rows} 行 × {manifest.cols} 列。

【统一视觉风格】
{shared_style}。
所有素材必须保持一致的色板、像素颗粒、描边方式、光照方向和细节密度。

【所有素材的共同修改】
{shared_edit}。

【各素材的单独修改】
{item_block}

【必须严格遵守】
1. 每一个非空网格区域都是相互独立的素材。
2. 单独修改只能作用于其指定的网格区域。
3. 保留每个素材的主体身份、主要轮廓、方向、位置和尺寸比例。
4. 不得交换、合并、删除或复制任何素材，也不得增加额外的独立素材对象。
5. 不得让素材跨越其原有网格区域。
6. 保持输入画布原有的行列布局、素材数量、空白间隔和宽高比例。
7. 不生成游戏场景、展示板、标题、标签、说明文字或额外装饰。
8. 保持浅灰色背景和网格间的空白隔离区域干净。
9. 输出一张与输入结构和宽高比例一致的完整大画布。"""
