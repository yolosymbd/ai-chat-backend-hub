# 所有初始化、跨域、限流、异常捕获、路由挂载全部在这里，启动不变
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.core.logger import logger
from app.db.database import init_db
# from app import routers
# 直接导入路由（不用从 app 导入，不掉坑）
from app.api.chat import router as chat_router
from app.api.conversation import router as conv_router
from app.api.feedback import router as feedback_router
from app.api.knowledge import router as knowledge_router
from app.api.gen_title import router as title_router

# 应用初始化
app = FastAPI(title="企业级AI助手", version="1.0")

# 接口限流
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 跨域
app.add_middleware(
    CORSMiddleware,
    # allow_origins=["*"],
    allow_origins=[
        # 本地开发地址
        "http://localhost:5175",
        "http://127.0.0.1:5175",
        # 线上静态网站域名
        "https://ai-chat-vue-front-d8d2jy6c43054c-1314889124.tcloudbaseapp.com"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局异常捕获
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": f"服务器异常：{str(exc)}"}
    )

# 数据库初始化
init_db()

# 批量挂载所有路由
# for router in routers:
#     app.include_router(router)
# 直接注册路由
app.include_router(chat_router)
app.include_router(conv_router)
app.include_router(feedback_router)
app.include_router(knowledge_router)
app.include_router(title_router)

# 测试接口，用来验证前后端连通性
@app.get("/api/health")
async def health_check():
    return {"code": 200, "message": "API 服务正常", "status": "ok"}

# 启动
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=9000, reload=True)