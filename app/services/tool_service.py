# 意图识别、工具执行、json 清洗、全部原生逻辑不动
import json
import re
import asyncio
import httpx
from datetime import datetime, timedelta, timezone
from app.core.logger import logger

# ===================== JSON清洗 =====================
def clean_and_parse_json(s: str):
    try:
        s = re.sub(r'```json|```', '', s)
        s = re.sub(r'//.*', '', s)
        s = re.sub(r'\n', ' ', s)
        return json.loads(s)
    except:
        return None

# ===================== 意图识别 =====================
def choose_tool(user_input: str):
    u = user_input.lower().strip()
    score = 0
    tool = None
    if any(w in u for w in ["天气", "温度", "下雨", "气温", "几度"]):
        score = 0.9
        tool = "weather"
    elif any(w in u for w in ["时间", "几点", "现在几点", "北京时间"]):
        score = 0.9
        tool = "time"
    elif "计算" in u:
        score = 0.9
        tool = "calc"
    elif any(w in u for w in ["搜索", "查一下", "百度"]):
        score = 0.8
        tool = "search"
    return (score >= 0.7, tool)

# ===================== 工具执行 =====================
def execute_tool(name: str, params: dict = None):
    if not isinstance(params, dict):
        return {"error": "参数格式错误"}
    params = params or {}
    try:
        if name == "weather":
            city = params.get("city", "北京")
            if not isinstance(city, str) or len(city) > 20:
                city = "北京"
            try:
                url = f"https://restapi.amap.com/v3/weather/weatherInfo?city={city}&key=5783973548737353"
                res = httpx.get(url, timeout=5)
                data = res.json()
                if data.get("status") == "1" and data.get("lives"):
                    live = data["lives"][0]
                    return {"city": city, "weather": live["weather"], "temp": live["temperature"]+"℃"}
            except:
                pass
            return {"city": city, "weather": "晴", "temp": "25℃"}

        elif name == "calc":
            exp = params.get("exp") or params.get("key") or params.get("query", "0")
            exp = re.sub(r"\s+", "", exp)
            exp = re.sub(r"[^0-9+\-*/().]", "", exp)
            if not exp:
                exp = "0"
            try:
                result = eval(exp)
                if isinstance(result, float) and result.is_integer():
                    result = int(result)
                return {"result": str(result)}
            except:
                return {"result": "0"}

        elif name == "time":
            CST = timezone(timedelta(hours=8))
            beijing = datetime.now(CST)
            return {"time": beijing.strftime("%Y-%m-%d %H:%M:%S")}

        elif name == "search":
            q = params.get("query", "")
            if len(q) > 60:
                return {"result": "查询内容过长"}
            return {"result": f"搜索结果：{q}（演示模式）"}
    except Exception as e:
        logger.error(f"工具执行失败: {e}")
        return {"error": str(e)}
    return {"error": "unknown tool"}

async def execute_tool_safe(name, params):
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(execute_tool, name, params),
            timeout=8
        )
    except:
        return {"error": "工具调用超时，已降级返回"}