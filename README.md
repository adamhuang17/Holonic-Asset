# Batch Image Edit API

一个可直接运行的 FastAPI 后端：先通过 `deepseek-v4-flash` 将用户描述拆成统一风格、共同修改和逐图修改，再把 2～6 张游戏素材排入规则画布，只调用一次 `openai/gpt-image-2` 图像编辑接口，最后按 Manifest 拆回独立的透明 PNG。

处理链路：

```text
上传图片与带 `@imageN` 引用的描述
→ 校验并读取 RGBA
→ 按上传顺序动态生成 `image1...imageN`
→ 校验必填的 `image_mapping` 与实际 multipart 文件顺序完全一致
→ DeepSeek 语义解析一次
→ 校验并保存 Semantic Edit Plan
→ 缩放到 Slot
→ 生成 Composite Canvas 与 Manifest
→ 根据 Edit Plan 和网格位置编译最终 Prompt
→ Canvas 编码成 Base64 Data URL
→ 一次图像编辑请求
→ 解码 Edited Canvas
→ 按缩放后的 Manifest 坐标裁剪
→ 恢复原始 Alpha
→ 输出多张 PNG
```

## 环境要求

- Python 3.11+
- 本地磁盘可写（运行数据保存在 `data/`）

## 安装

```bash
python -m venv .venv
```

Windows：

```bash
.venv\Scripts\activate
```

安装依赖：

```bash
pip install -r requirements.txt
```

## 环境变量

Windows：

```bash
copy .env.example .env
```

填写两个实际 Token：

```env
QNAIGC_API_TOKEN=实际token
DEEPSEEK_API_KEY=实际token
```

其余变量已有默认值，可在 `.env` 中覆盖：

```env
QNAIGC_API_HOST=api.qnaigc.com
QNAIGC_API_PATH=/v1/images/edits
IMAGE_MODEL=openai/gpt-image-2
IMAGE_QUALITY=high
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_API_PATH=/chat/completions
DEEPSEEK_MODEL=deepseek-v4-flash
SEMANTIC_REQUEST_TIMEOUT_SECONDS=60
REQUEST_TIMEOUT_SECONDS=300
```

Token 不会写入代码、响应或正常日志。Token 缺失不会导致应用启动失败；实际创建任务时，缺少 DeepSeek Key 返回 `MISSING_SEMANTIC_API_KEY`，缺少图像服务 Token 返回 `MISSING_API_TOKEN`。

## 启动

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

健康检查：

```text
GET http://127.0.0.1:8000/health
```

## Apifox 调试

请求：

```text
POST http://127.0.0.1:8000/api/v1/jobs
```

Body 选择：

```text
form-data
```

添加字段：

```text
files          file       black_chess.png
files          file       red_chess.png
files          file       wood_original.png
instruction    string     将所有素材统一改成青铜材质。@image1 将字体设置为黑色。@image2 将字体设置为红色。
image_mapping  string     {"image1":"black_chess.png","image2":"red_chess.png","image3":"wood_original.png"}
```

注意：

- 多张图片使用相同字段名 `files`。
- 不要写成 `files[]`。
- 图片按上传顺序对应 `image1`、`image2`，依此类推。
- `image_mapping` 是必填的 JSON 字符串；键必须恰好覆盖本次动态生成的全部 `imageN`，值为对应上传文件名。
- `image_mapping` 的 JSON 键书写顺序不重要，但每个 `imageN` 的文件名必须与 multipart 中该位置的实际文件名一致。
- 如果映射与实际上传顺序不一致，接口返回 `IMAGE_MAPPING_MISMATCH`，且不会调用 DeepSeek 或图像模型。
- 单素材修改使用 `@imageN` 明确引用；没有单独要求的图片只执行公共要求。
- 产品概念中的 description 在当前 HTTP 接口中使用字段名 `instruction`。
- 不要手动设置 `Content-Type`。
- Apifox 会自动生成 multipart boundary。
- 请求会同步等待模型完成，可能执行较久，需要适当提高请求超时时间（建议超过 300 秒）。

查询已保存任务：

```text
GET http://127.0.0.1:8000/api/v1/jobs/job_xxx
```

## DeepSeek 语义解析请求格式

服务只把用户描述和本次请求动态生成的图片引用发给 DeepSeek，不上传图片、文件路径或 Base64：

```json
{
  "model": "deepseek-v4-flash",
  "messages": [
    {
      "role": "system",
      "content": "语义拆解规则和 JSON 输出要求"
    },
    {
      "role": "user",
      "content": "{\"description\":\"...\",\"images\":[\"image1\",\"image2\"]}"
    }
  ],
  "thinking": {
    "type": "disabled"
  },
  "temperature": 0,
  "stream": false
}
```

期望模型只返回以下结构；后端会校验每个动态图片引用恰好出现一次：

```json
{
  "shared_style": "统一视觉风格",
  "shared_edit": "所有素材共同执行的内容修改",
  "items": [
    {
      "image": "image1",
      "edit": "只应用于 image1 的修改"
    }
  ]
}
```

真实实现使用异步 `httpx.AsyncClient` 请求 `https://api.deepseek.com/chat/completions`，不依赖 OpenAI SDK，也不依赖 DeepSeek 是否支持额外的 Structured Output 参数。

## QnAIGC 请求格式

服务把 Composite Canvas 转为带 MIME 前缀的 Data URL，并且 `image` 数组中只放这一张画布：

```python
import base64
from pathlib import Path

import httpx


composite_path = Path("data/composite/job_xxx/composite.png")
encoded = base64.b64encode(
    composite_path.read_bytes()
).decode("ascii")

image_data_url = f"data:image/png;base64,{encoded}"

payload = {
    "model": "openai/gpt-image-2",
    "prompt": "由语义计划和网格位置编译出的完整编辑提示词",
    "image": [
        image_data_url
    ],
    "quality": "high",
}

headers = {
    "Authorization": "Bearer <token>",
    "Content-Type": "application/json",
}

response = httpx.post(
    "https://api.qnaigc.com/v1/images/edits",
    json=payload,
    headers=headers,
    timeout=300,
)
```

真实实现使用异步 `httpx.AsyncClient`，并严格检查 HTTP 状态、JSON 结构、Base64 以及解码后的图片内容。日志只会保留 Provider 错误响应前 2000 个字符，不会记录 Authorization Header 或完整 Base64 图片。

## 文件与访问地址

每个任务使用 `job_<uuid>` 作为 ID，并写入：

```text
data/uploads/{job_id}/
data/composite/{job_id}/composite.png
data/edited/{job_id}/edited_canvas.png
data/outputs/{job_id}/item_0.png
data/jobs/{job_id}/manifest.json
data/jobs/{job_id}/semantic_plan.json
data/jobs/{job_id}/generation_prompt.txt
data/jobs/{job_id}/job.json
```

`data/` 挂载在 `/files`，例如：

```text
/files/outputs/job_xxx/item_0.png
/files/composite/job_xxx/composite.png
/files/edited/job_xxx/edited_canvas.png
/files/jobs/job_xxx/manifest.json
```

`semantic_plan.json` 和 `generation_prompt.txt` 用于在服务端检查 DeepSeek 的结构化结果以及最终发送给图像模型的完整 Prompt。

上传文件使用 UUID 磁盘名，原始文件名只作为经过清洗的元数据保存，不作为磁盘路径。

## 测试

```bash
pytest
```

测试通过 Fake Semantic Planner、Mock HTTP 和 Mock Image Provider 完成，不会调用真实 DeepSeek 或图像接口。

## 已知限制

1. 当前使用同步 HTTP 任务接口，请求会一直等待编辑和拆图完成。
2. 当前只支持一次上传 2～6 张 PNG、JPG、JPEG 或 WEBP。
3. 每个任务调用一次语义模型，并且只调用一次大画布图像编辑，不会逐图调用模型。
4. 当前未使用 Mask 接口。
5. 当前通过复用每张原图的 Alpha 通道恢复透明背景，以优先保持游戏素材的透明边缘和原始轮廓。
6. 模型在原轮廓之外新增的特效或内容可能被原 Alpha 裁掉，也不适合大幅改变对象外形。
7. 模型输出必须基本保持原画布宽高比例；差异超过 2% 时任务失败。
8. 大画布 Base64 Data URL 会增加 JSON 请求体积和内存占用。
9. 第一版主要用于验证多张素材跨图片统一风格修改能力。
