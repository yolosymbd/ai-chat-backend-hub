# 知识库上传、检测接口原样
from fastapi import APIRouter, UploadFile, File, HTTPException
from app.services.rag import extract_txt, extract_docx, extract_pdf, split_chunks, build_vector_db, load_vector_db, cached_hybrid_search

router = APIRouter()

@router.get("/api/check_knowledge")
def check_knowledge():
    _, chunks = load_vector_db()
    return {"has_content": len(chunks) > 0}

@router.post("/api/upload_knowledge")
async def upload_knowledge(files: list[UploadFile] = File(...)):
    all_text = ""
    for f in files:
        buf = await f.read()
        if len(buf) < 10:
            raise HTTPException(400, "文件内容为空")
        fname = f.filename.lower()
        if fname.endswith(".txt"):
            t = extract_txt(buf)
        elif fname.endswith(".docx"):
            t = extract_docx(buf)
        elif fname.endswith(".pdf"):
            t = extract_pdf(buf)
        else:
            raise HTTPException(400, "不支持的格式")
        all_text += t + "\n\n"
    chunks = split_chunks(all_text)
    build_vector_db(chunks)
    cached_hybrid_search.cache_clear()
    return {"success": True, "msg": f"已构建知识库，共{len(chunks)}段"}