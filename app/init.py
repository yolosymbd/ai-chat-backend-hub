from app.api import chat,conversation,feedback,knowledge,gen_title

# 导出路由列表
routers = [
    chat.router,
    conversation.router,
    feedback.router,
    knowledge.router,
    gen_title.router
]