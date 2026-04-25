# 对话标题生成、多模型兼容、数据库锁修复全部原样
from fastapi import APIRouter, Request
import httpx
import os
from app.core.config import MODEL_CONFIG
from app.core.logger import logger
from app.db.database import db_cursor

router = APIRouter()

@router.post("/api/gen_title")
async def gen_title(request: Request):
    data = await request.json()
    conv_id = data.get("conv_id")
    model_type = data.get("model_type", "glm")
    print("==========="+ model_type + "===========")
    if not conv_id:
        logger.error("gen_title: 缺少 conv_id")
        return {"ok": False, "error": "缺少 conv_id"}
    with db_cursor() as cur:
        cur.execute("SELECT content FROM messages WHERE conv_id=? AND role='user' ORDER BY created_at ASC LIMIT 1", (conv_id,))
        row = cur.fetchone()
    if not row:
        logger.error(f"gen_title: 对话 {conv_id} 没有用户消息")
        return {"ok": False, "error": "没有用户消息"}
    question = row[0][:40]
    try:
        if model_type not in MODEL_CONFIG:
            logger.warning(f"gen_title: 未知模型{model_type}，自动回退glm")
            model_type = "glm"
        cfg = MODEL_CONFIG[model_type]
        API_URL = cfg["url"]
        API_KEY = os.getenv(cfg["key_env"])
        if not API_KEY:
            API_KEY = cfg.get("hard_key", "")
        if not API_KEY:
            logger.error(f"gen_title: {model_type} 模型API Key为空，终止标题生成")
            return {"ok": False, "error": "模型密钥无效"}
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(API_URL, headers={
                "Authorization": f"Bearer {API_KEY}"
            }, json={
                "model": cfg["name"],
                "messages": [
                    {"role": "user", "content": f"把这句话精简成6个字以内的简短对话标题，只返回标题文字不要多余内容：{question}"}
                ],
                "temperature": 0.2,
                "top_p": 0.3,
                "max_tokens": 16
            })
        resp.raise_for_status()
        res = resp.json()
        title = res["choices"][0]["message"]["content"].strip()
        logger.info(f"gen_title: {model_type}模型生成标题成功 → {title}")
        with db_cursor() as cur:
            cur.execute("UPDATE conversations SET title=? WHERE id=?", (title, conv_id))
        return {"ok": True, "title": title}
    except Exception as e:
        logger.error(f"gen_title: {model_type}模型调用大模型失败 → {str(e)}")
        import traceback
        traceback.print_exc()
        return {"ok": False, "error": str(e)}