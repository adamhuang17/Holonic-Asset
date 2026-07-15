"""DeepSeek-backed semantic planning for batch image edits."""

from __future__ import annotations

import json
import logging
from typing import Any, Protocol

import httpx
from pydantic import ValidationError

from app.config import Settings
from app.exceptions.errors import AppError, ErrorCode
from app.models.edit_plan import EditPlan


logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """你是批量图片编辑任务解析器。

你不会看到图片内容，只负责解析用户的文字描述。输入 JSON 中的 images 是本次请求唯一合法的图片引用列表。

你的任务：
1. 提取所有图片共同遵守的视觉风格，写入 shared_style。
2. 提取所有图片共同执行的内容修改，写入 shared_edit。
3. 为 images 中的每一个图片引用生成一个 items 元素；该图片独有的修改写入 edit。

输出必须严格符合以下 JSON 结构：
{
  "shared_style": "所有图片共享的视觉风格；没有则为空字符串",
  "shared_edit": "所有图片共享的内容修改；没有则为空字符串",
  "items": [
    {
      "image": "来自输入 images 的图片引用",
      "edit": "仅应用于该图片的修改；没有则为空字符串"
    }
  ]
}

必须遵守：
1. 只能使用输入 images 中存在的图片引用。
2. images 中的每个引用必须在 items 中出现一次且只能出现一次。
3. 不得根据图片名称猜测或编造图片内容。
4. 不得输出批次、调用计划、模型参数、解释、注释或 Markdown。
5. 只输出一个完整 JSON 对象。"""


class SemanticPlanner(Protocol):
    """Interface used by the job orchestrator and offline test doubles."""

    async def plan(self, description: str, image_refs: list[str]) -> EditPlan:
        """Convert one description into a validated per-image edit plan."""


class DeepSeekSemanticPlanner:
    """Call DeepSeek's OpenAI-compatible Chat Completions endpoint once."""

    def __init__(
        self,
        settings: Settings,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.settings = settings
        self._transport = transport

    async def plan(self, description: str, image_refs: list[str]) -> EditPlan:
        token = self.settings.DEEPSEEK_API_KEY.strip()
        if not token:
            raise AppError(ErrorCode.MISSING_SEMANTIC_API_KEY)

        user_input = json.dumps(
            {
                "description": description.strip(),
                "images": image_refs,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        payload = {
            "model": self.settings.DEEPSEEK_MODEL,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_input},
            ],
            "thinking": {"type": "disabled"},
            "temperature": 0,
            "stream": False,
        }
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        timeout = httpx.Timeout(
            float(self.settings.SEMANTIC_REQUEST_TIMEOUT_SECONDS)
        )

        try:
            if self._transport is None:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(
                        self.settings.deepseek_api_url,
                        json=payload,
                        headers=headers,
                    )
            else:
                async with httpx.AsyncClient(
                    timeout=timeout,
                    transport=self._transport,
                ) as client:
                    response = await client.post(
                        self.settings.deepseek_api_url,
                        json=payload,
                        headers=headers,
                    )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "DeepSeek semantic request failed: status=%s",
                exc.response.status_code,
            )
            raise AppError(
                ErrorCode.SEMANTIC_PROVIDER_REQUEST_FAILED,
                details={"provider_status": exc.response.status_code},
            ) from exc
        except httpx.RequestError as exc:
            logger.error(
                "DeepSeek semantic transport failure: type=%s",
                type(exc).__name__,
            )
            raise AppError(ErrorCode.SEMANTIC_PROVIDER_REQUEST_FAILED) from exc

        response_payload = self._parse_response_json(response)
        content = self._extract_content(response_payload)
        plan = self._parse_plan(content)
        return self._validate_and_order_refs(plan, image_refs)

    @staticmethod
    def _parse_response_json(response: httpx.Response) -> dict[str, Any]:
        try:
            payload = response.json()
        except (ValueError, UnicodeError) as exc:
            raise AppError(ErrorCode.INVALID_SEMANTIC_PROVIDER_RESPONSE) from exc
        if not isinstance(payload, dict):
            raise AppError(ErrorCode.INVALID_SEMANTIC_PROVIDER_RESPONSE)
        return payload

    @staticmethod
    def _extract_content(payload: dict[str, Any]) -> str:
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise AppError(ErrorCode.INVALID_SEMANTIC_PROVIDER_RESPONSE)
        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise AppError(ErrorCode.INVALID_SEMANTIC_PROVIDER_RESPONSE)
        if first_choice.get("finish_reason") == "length":
            raise AppError(ErrorCode.INVALID_SEMANTIC_PROVIDER_RESPONSE)
        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise AppError(ErrorCode.INVALID_SEMANTIC_PROVIDER_RESPONSE)
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise AppError(ErrorCode.INVALID_SEMANTIC_PROVIDER_RESPONSE)
        return content.strip()

    @classmethod
    def _parse_plan(cls, content: str) -> EditPlan:
        normalized = cls._remove_json_fence(content)
        try:
            raw_plan = json.loads(normalized)
            if not isinstance(raw_plan, dict):
                raise TypeError("semantic plan must be a JSON object")
            return EditPlan.model_validate(raw_plan)
        except (json.JSONDecodeError, TypeError, ValidationError) as exc:
            raise AppError(ErrorCode.INVALID_SEMANTIC_PLAN) from exc

    @staticmethod
    def _remove_json_fence(content: str) -> str:
        if not content.startswith("```"):
            return content

        lines = content.splitlines()
        if (
            len(lines) < 3
            or lines[0].strip().lower() not in {"```", "```json"}
            or lines[-1].strip() != "```"
        ):
            raise AppError(ErrorCode.INVALID_SEMANTIC_PLAN)
        normalized = "\n".join(lines[1:-1]).strip()
        if not normalized:
            raise AppError(ErrorCode.INVALID_SEMANTIC_PLAN)
        return normalized

    @staticmethod
    def _validate_and_order_refs(
        plan: EditPlan,
        image_refs: list[str],
    ) -> EditPlan:
        actual_refs = [item.image for item in plan.items]
        if (
            len(actual_refs) != len(image_refs)
            or len(actual_refs) != len(set(actual_refs))
            or set(actual_refs) != set(image_refs)
        ):
            raise AppError(ErrorCode.INVALID_SEMANTIC_PLAN)

        items_by_ref = {item.image: item for item in plan.items}
        ordered_items = [items_by_ref[image_ref] for image_ref in image_refs]
        return plan.model_copy(update={"items": ordered_items})
