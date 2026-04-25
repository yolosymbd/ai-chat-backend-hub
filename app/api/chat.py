# 核心流式聊天、SSE、模型切换、token 截断、重试、背压延迟全部原版照搬
import json
import asyncio
import time
import httpx
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from app.core.config import MODEL_CONFIG, SYSTEM_PROMPT_NORMAL, SYSTEM_PROMPT_TOOL, MIN_SEND_INTERVAL
from app.core.logger import logger
from app.services.rag import cached_hybrid_search, build_rag_prompt, get_good_answers
from app.services.tool_service import choose_tool, execute_tool_safe, clean_and_parse_json

router = APIRouter()

last_send_time = 0

async def sse_delay():
    global last_send_time
    now = time.time()
    if now - last_send_time < MIN_SEND_INTERVAL:
        await asyncio.sleep(MIN_SEND_INTERVAL - (now - last_send_time))
    last_send_time = time.time()

# Token截断
def trim_messages(messages, max_tokens=1800):
    messages = [msg for msg in messages if msg["content"].strip()]
    total = 0
    kept = []
    for msg in reversed(messages):
        cnt = len(msg["content"])
        token_est = cnt // 2
        if total + token_est > max_tokens:
            break
        total += token_est
        kept.append(msg)
    kept = list(reversed(kept))
    system = [m for m in kept if m["role"] == "system"]
    others = [m for m in kept if m["role"] != "system"]
    return (system[:1] + others) if system else others

# 请求重试
async def fetch_with_retry(client, url, json, headers, max_retries=4):
    delay = 0.5
    for i in range(max_retries):
        try:
            return await client.post(url, json=json, headers=headers)
        except Exception as e:
            if i == max_retries - 1:
                raise e
            await asyncio.sleep(delay)
            delay = min(delay * 1.5, 2)

# 流式生成器
async def chat_stream(messages, temperature=0, top_p=0.7, max_tokens=2048, stream=True, model_type="glm"):
    import os
    print("==================== 当前使用模型：", model_type, "====================")
    cached_hybrid_search.cache_clear()

    if model_type not in MODEL_CONFIG:
        model_type = "glm"
    cfg = MODEL_CONFIG[model_type]
    MODEL_NAME = cfg["name"]
    API_URL = cfg["url"]
    API_KEY = os.getenv(cfg["key_env"])
    if not API_KEY:
        API_KEY = cfg.get("hard_key", "")

    print(f"\n=====【模型切换日志】=====")
    print(f"当前模型类型: {model_type}")
    print(f"模型名称: {MODEL_NAME}")
    print(f"请求地址: {API_URL}")
    print(f"密钥是否有效: {bool(API_KEY)}")
    print(f"密钥前10位: {API_KEY[:10]}...")
    print("===========================\n")

    messages = [msg for msg in messages if msg["content"] and msg["content"].strip()]
    messages = trim_messages(messages)
    user_msg = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")

    need_tool, tool_name = choose_tool(user_msg)
    logger.info(f"🧠 意图识别：need_tool={need_tool}, tool={tool_name}")

    if need_tool:
        await sse_delay()
        yield f"data: {json.dumps({'type':'tool'}, ensure_ascii=False)}\n\n"
        messages = [{"role":"system","content":SYSTEM_PROMPT_TOOL}] + messages
    else:
        doc_chunks = cached_hybrid_search(user_msg)
        has_upload_doc = len(doc_chunks) > 0
        if has_upload_doc:
            good_answers = get_good_answers(user_msg)
            all_chunks = good_answers + doc_chunks
            prompt = build_rag_prompt(user_msg, all_chunks)
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT_NORMAL},
                {"role": "user", "content": prompt}
            ]
        else:
            messages = [{"role": "system", "content": SYSTEM_PROMPT_NORMAL}] + messages
        await sse_delay()
        yield f"data: {json.dumps({'type':'normal'}, ensure_ascii=False)}\n\n"

    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": max_tokens,
        "stream": stream,
    }

    if model_type == "glm":
        payload["frequency_penalty"] = 0.0
        payload["presence_penalty"] = 0.0
    if model_type == "doubao":
        payload["do_sample"] = True

    full = ""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            async with client.stream("POST", API_URL, json=payload, headers=headers) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    body = line[6:].strip()
                    if body == "[DONE]" or body == "":
                        break
                    if not body:
                        continue
                    try:
                        j = json.loads(body)
                        c = j["choices"][0]["delta"].get("content", "")
                        if c:
                            full += c
                            if not need_tool:
                                await sse_delay()
                                yield f"data: {json.dumps({'content': c}, ensure_ascii=False)}\n\n"
                    except json.JSONDecodeError:
                        continue
    except httpx.TimeoutException:
        logger.warning("⚠️ 请求大模型超时，流自动结束")
        await sse_delay()
        yield f"data: {json.dumps({'content':'\\n\\n请求超时，请重试'}, ensure_ascii=False)}\n\n"
    except Exception as e:
        logger.error(f"❌ 流式生成异常：{str(e)}")
        await sse_delay()
        yield f"data: {json.dumps({'content':'\\n\\n服务异常，请重试'}, ensure_ascii=False)}\n\n"

    if need_tool:
        try:
            j = clean_and_parse_json(full)
            if not j:
                logger.warning(f"模型工具输出解析失败，原始内容：{full}")
                await sse_delay()
                yield f"data: {json.dumps({'type':'normal'}, ensure_ascii=False)}\n\n"
                yield f"data: {json.dumps({'content': full}, ensure_ascii=False)}\n\n"
                return
            if "name" not in j or j["name"] not in ["weather","calc","time","search"]:
                logger.warning(f"未知工具名：{j.get('name')}")
                await sse_delay()
                yield f"data: {json.dumps({'type':'normal'}, ensure_ascii=False)}\n\n"
                yield f"data: {json.dumps({'content': full}, ensure_ascii=False)}\n\n"
                return
            res = await execute_tool_safe(j["name"], j.get("parameters", {}))
            tool_data = {
                "tool_name": j["name"],
                "tool_params": j.get("parameters", {}),
                "tool_result": res
            }
            await sse_delay()
            yield f"data: {json.dumps({'type': 'tool_data', 'data': tool_data}, ensure_ascii=False)}\n\n"
            ans = ""
            if j["name"] == "weather": ans = f"{res['city']}天气：{res['weather']}，{res['temp']}"
            if j["name"] == "calc": ans = f"计算结果：{res['result']}"
            if j["name"] == "time": ans = f"当前时间：{res['time']}"
            if j["name"] == "search": ans = res["result"]
            await sse_delay()
            yield f"data: {json.dumps({'content': ans}, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error(f"工具调用全流程异常：{e}")
            await sse_delay()
            yield f"data: {json.dumps({'type':'normal'}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'content': '我已为你解答：'+full}, ensure_ascii=False)}\n\n"
    yield "data: [DONE]\n\n"

@router.post("/api/chat")
async def chat(request: Request):
    from slowapi import Limiter
    from slowapi.util import get_remote_address
    limiter = Limiter(key_func=get_remote_address)
    data = await request.json()
    messages = data.get("messages", [])
    temperature = data.get("temperature", 0)
    top_p = data.get("top_p", 0.7)
    max_tokens = data.get("max_tokens", 2048)
    stream = data.get("stream", True)
    model_type = data.get("model_type", "glm")
    return StreamingResponse(
        chat_stream(messages, temperature, top_p, max_tokens, stream, model_type),
        media_type="text/event-stream"
    )