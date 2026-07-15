# Batch Image Edit API

一个可直接运行的 FastAPI 后端：把 2～6 张游戏素材排入规则画布，只调用一次 `openai/gpt-image-2` 图像编辑接口，再按 Manifest 拆回独立的透明 PNG。

处理链路：

```text
上传图片与统一描述
→ 校验并读取 RGBA
→ 缩放到 Slot
→ 生成 Composite Canvas 与 Manifest
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

填写实际 Token：

```env
QNAIGC_API_TOKEN=实际token
```

其余变量已有默认值，可在 `.env` 中覆盖：

```env
QNAIGC_API_HOST=api.qnaigc.com
QNAIGC_API_PATH=/v1/images/edits
IMAGE_MODEL=openai/gpt-image-2
IMAGE_QUALITY=high
REQUEST_TIMEOUT_SECONDS=300
```

Token 不会写入代码、响应或正常日志。Token 缺失不会导致应用启动失败；实际创建任务时会返回 `MISSING_API_TOKEN`。

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
files        file       sword.png
files        file       shield.png
instruction string     将所有素材统一改成暗黑像素风
```

注意：

- 多张图片使用相同字段名 `files`。
- 不要写成 `files[]`。
- 不要手动设置 `Content-Type`。
- Apifox 会自动生成 multipart boundary。
- 请求会同步等待模型完成，可能执行较久，需要适当提高请求超时时间（建议超过 300 秒）。

查询已保存任务：

```text
GET http://127.0.0.1:8000/api/v1/jobs/job_xxx
```

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
    "prompt": "统一编辑提示词",
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
data/jobs/{job_id}/job.json
```

`data/` 挂载在 `/files`，例如：

```text
/files/outputs/job_xxx/item_0.png
/files/composite/job_xxx/composite.png
/files/edited/job_xxx/edited_canvas.png
/files/jobs/job_xxx/manifest.json
```

上传文件使用 UUID 磁盘名，原始文件名只作为经过清洗的元数据保存，不作为磁盘路径。

## 测试

```bash
pytest
```

测试通过 Mock Provider/HTTP Mock 完成，不会调用真实图像接口。

## 已知限制

1. 当前使用同步 HTTP 任务接口，请求会一直等待编辑和拆图完成。
2. 当前只支持一次上传 2～6 张 PNG、JPG、JPEG 或 WEBP。
3. 当前只调用一次大画布编辑，不会逐图调用模型。
4. 当前未使用 Mask 接口。
5. 当前通过复用每张原图的 Alpha 通道恢复透明背景，以优先保持游戏素材的透明边缘和原始轮廓。
6. 模型在原轮廓之外新增的特效或内容可能被原 Alpha 裁掉，也不适合大幅改变对象外形。
7. 模型输出必须基本保持原画布宽高比例；差异超过 2% 时任务失败。
8. 大画布 Base64 Data URL 会增加 JSON 请求体积和内存占用。
9. 第一版主要用于验证多张素材跨图片统一风格修改能力。

