# 会话全套 CRUD 接口完全原样
import sqlite3
from datetime import datetime
from fastapi import APIRouter
from app.db.database import db_cursor, DB_PATH
# 顶部新增导入
from pydantic import BaseModel

# 消息保存请求模型（完美匹配前端传参格式，彻底解决422校验）
class MessageSaveRequest(BaseModel):
    conv_id: int
    role: str
    content: str

router = APIRouter()

@router.get("/api/conversations")
def get_conversations():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, title, created_at FROM conversations ORDER BY created_at DESC")
    rows = c.fetchall()
    conn.close()
    return [{"conv_id": r[0], "title": r[1], "created_at": r[2]} for r in rows]

@router.post("/api/conversation")
async def create_conversation():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO conversations (title, created_at) VALUES (?, ?)", ("新对话", datetime.now()))
    conv_id = c.lastrowid
    conn.commit()
    conn.close()
    return {"conv_id": conv_id}

@router.delete("/api/conversation/{conv_id}")
def delete_conversation(conv_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM messages WHERE conv_id=?", (conv_id,))
    c.execute("DELETE FROM conversations WHERE id=?", (conv_id,))
    conn.commit()
    conn.close()
    return {"ok": True}

@router.delete("/api/conversation/{conv_id}/clear_messages")
def clear_messages(conv_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM messages WHERE conv_id = ?", (conv_id,))
    conn.commit()
    conn.close()
    return {"status": "ok"}

@router.get("/api/conversation/{conv_id}/messages")
def get_messages(conv_id: int):
    conn = sqlite3.connect("chat.db")
    c = conn.cursor()
    c.execute("SELECT id, role, content, created_at FROM messages WHERE conv_id=? ORDER BY created_at ASC", (conv_id,))
    rows = c.fetchall()
    conn.close()
    return [{"id": r[0], "role": r[1], "content": r[2], "created_at": r[3]} for r in rows]

# 直接全覆盖替换原来的 save_message
@router.post("/api/message")
async def save_message(data: MessageSaveRequest):
    # 直接解构参数，不再裸读request，FastAPI校验100%兼容
    conv_id = data.conv_id
    role = data.role
    content = data.content

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO messages (conv_id, role, content, created_at) VALUES (?,?,?,?)",
              (conv_id, role, content, datetime.now()))
    msg_id = c.lastrowid
    conn.commit()
    conn.close()
    return {"ok": True, "msg_id": msg_id}

@router.delete("/api/message/{msg_id}")
def delete_message(msg_id: int):
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH, timeout=5.0)
        c = conn.cursor()
        c.execute("SELECT id FROM messages WHERE id = ?", (msg_id,))
        if not c.fetchone():
            return {"ok": True, "msg": "消息不存在"}
        c.execute("DELETE FROM feedback WHERE msg_id = ?", (msg_id,))
        c.execute("DELETE FROM good_answers WHERE msg_id = ?", (msg_id,))
        c.execute("DELETE FROM messages WHERE id = ?", (msg_id,))
        conn.commit()
        print(f"✅ 后端消息【{msg_id}】全部物理删除成功")
        return {"ok": True, "msg": "删除成功"}
    except Exception as e:
        print(f"❌ 删除消息【{msg_id}】失败，异常详情：{e}")
        if conn:
            conn.rollback()
        return {"ok": False, "error": str(e)}
    finally:
        if conn:
            conn.close()