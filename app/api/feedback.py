# 点赞、优质库入库、回滚、事务游标全部原版
from fastapi import APIRouter
from pydantic import BaseModel
from app.db.database import db_cursor
from app.core.logger import logger

router = APIRouter()

class FeedbackRequest(BaseModel):
    msg_id: int
    rate: str

@router.post("/api/feedback")
async def save_feedback(data: FeedbackRequest):
    print("\n" + "="*50)
    print("🔥 收到前端点赞请求！")
    print(f"入参 msg_id = {data.msg_id}")
    print(f"入参 rate = {data.rate}")
    print("="*50)
    try:
        with db_cursor() as cur:
            cur.execute('''
                INSERT INTO feedback (msg_id, rate) VALUES (?, ?)
                ON CONFLICT(msg_id) DO UPDATE SET rate=excluded.rate
            ''', (data.msg_id, data.rate))
            print("✅ 【步骤1】feedback表写入/更新完成")

            if data.rate == "good":
                print("\n===== 进入优质库入库流程 =====")
                cur.execute("SELECT id FROM good_answers WHERE msg_id=?", (data.msg_id,))
                if cur.fetchone():
                    print("✅ 优质库已存在该记录，跳过重复插入")
                    return {"ok": True, "msg": "已存在，不重复入库"}
                cur.execute("SELECT id, conv_id, content FROM messages WHERE id=?", (data.msg_id,))
                ai_row = cur.fetchone()
                if not ai_row:
                    print("❌ 错误：messages表中找不到这条AI消息")
                    raise Exception("消息不存在")
                ai_id, conv_id, answer = ai_row
                print(f"✅ 找到AI消息：对话ID={conv_id}")
                cur.execute("""
                    SELECT content FROM messages 
                    WHERE conv_id = ? 
                    AND role = 'user'
                    AND id < ?
                    ORDER BY id DESC LIMIT 1
                """, (conv_id, ai_id))
                q_row = cur.fetchone()
                if not q_row:
                    print("❌ 错误：找不到对应用户提问")
                    raise Exception("无对应用户提问")
                question = q_row[0]
                print(f"✅ 精准匹配到用户提问：{question[:80]}...")
                cur.execute('''
                    INSERT INTO good_answers (msg_id, question, answer) VALUES (?, ?, ?)
                    ON CONFLICT(msg_id) DO UPDATE SET question=excluded.question, answer=excluded.answer
                ''', (data.msg_id, question, answer))
                print("🎉 【最终成功】问答写入good_answers优质库！")
            else:
                print("\n===== 取消点赞/点踩 =====")
                cur.execute("DELETE FROM good_answers WHERE msg_id = ?", (data.msg_id,))
                print("✅ 已从优质库删除")
        print("\n✅ 整条流程执行完毕")
        return {"ok": True, "msg": "状态更新成功"}
    except Exception as e:
        print(f"\n❌ 报错已自动回滚：{str(e)}")
        import traceback
        traceback.print_exc()
        return {"ok": False, "error": f"操作失败，已回滚：{str(e)}"}

@router.get("/api/feedback/{msg_id}")
def get_feedback(msg_id: int):
    import sqlite3
    from app.core.config import DB_PATH
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT rate FROM feedback WHERE msg_id=?", (msg_id,))
    row = c.fetchone()
    conn.close()
    return {"rate": row[0] if row else ""}

@router.post("/api/good/remove/{msg_id}")
async def remove_good_by_msgid(msg_id: int):
    import sqlite3
    from app.core.config import DB_PATH
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM good_answers WHERE msg_id = ?", (msg_id,))
    c.execute("UPDATE feedback SET rate='' WHERE msg_id=?", (msg_id,))
    conn.commit()
    conn.close()
    return {"code": 200, "msg": "已移出优质库"}