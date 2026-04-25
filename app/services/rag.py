# 全部文档解析、清洗、分块、faiss 向量库、混合检索、缓存、提示词构建，原汁原味
import os
# 配置国内镜像
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
import re
import pickle
import numpy as np
import faiss
from functools import lru_cache
from sentence_transformers import SentenceTransformer
from PyPDF2 import PdfReader
import docx
from app.core.config import DB_PATH



# 向量模型
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

# ===================== 文件解析 =====================
def extract_txt(content: bytes) -> str:
    try:
        return content.decode("utf-8")
    except:
        return content.decode("gbk", ignore=True)

def extract_docx(content: bytes) -> str:
    try:
        with open("temp.docx", "wb") as f:
            f.write(content)
        doc = docx.Document("temp.docx")
        text = "\n".join([p.text for p in doc.paragraphs])
        os.remove("temp.docx")
        return text
    except:
        return ""

def extract_pdf(content: bytes) -> str:
    try:
        with open("temp.pdf", "wb") as f:
            f.write(content)
        reader = PdfReader("temp.pdf")
        if len(reader.pages) == 0:
            os.remove("temp.pdf")
            return ""
        text = ""
        for page in reader.pages:
            try:
                t = page.extract_text()
                if t:
                    text += t + "\n"
            except:
                continue
        os.remove("temp.pdf")
        return text
    except Exception as e:
        try:
            os.remove("temp.pdf")
        except:
            pass
        return ""

# ===================== 文本清洗分块 =====================
def clean_text(text: str) -> str:
    text = re.sub(r'\u3000', ' ', text)
    text = re.sub(r'[\t\r\f\v]', ' ', text)
    text = re.sub(r' +', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()
    return text

def split_chunks(text: str, max_len=350, overlap=80) -> list[str]:
    text = clean_text(text)
    if not text:
        return []
    paras = re.split(r'\n\s*\n', text)
    chunks = []
    for p in paras:
        p = p.strip()
        if not p:
            continue
        if len(p) <= max_len:
            chunks.append(p)
            continue
        i = 0
        while i < len(p):
            end = i + max_len
            chunk = p[i:end].strip()
            if chunk:
                chunks.append(chunk)
            i += max_len - overlap
    chunks = [c for c in chunks if len(c) >= 15]
    return chunks

# ===================== 向量库 =====================
def build_vector_db(chunks: list[str]):
    if not chunks:
        return None, []
    embeddings = embedding_model.encode(chunks, convert_to_numpy=True)
    index = faiss.IndexFlatL2(embeddings.shape[1])
    index.add(embeddings)
    faiss.write_index(index, "faiss.index")
    with open("chunks.pkl", "wb") as f:
        pickle.dump(chunks, f)

def load_vector_db():
    if not os.path.exists("faiss.index") or not os.path.exists("chunks.pkl"):
        return None, []
    index = faiss.read_index("faiss.index")
    with open("chunks.pkl", "rb") as f:
        chunks = pickle.load(f)
    return index, chunks

# ===================== 关键词+语义检索 =====================
# def keyword_search(query: str, chunks: list[str], top_k=3):
#     q = query.lower()
#     scores = []
#     for i, c in enumerate(chunks):
#         cnt = c.lower().count(q)
#         scores.append((-cnt, i))
#     scores.sort()
#     res = []
#     seen = set()
#     for s, i in scores[:top_k]:
#         if i not in seen:
#             seen.add(i)
#             res.append(chunks[i])
#     return res

# def semantic_search(query: str, top_k=3):
#     index, chunks = load_vector_db()
#     if not index or not chunks:
#         return []
#     q_emb = embedding_model.encode(query, convert_to_numpy=True)
#     q_emb = np.expand_dims(q_emb, axis=0)
#     D, I = index.search(q_emb, top_k)
#     res = []
#     for i in range(len(I[0])):
#         if D[0][i] < 1.0:
#             res.append(chunks[I[0][i]])
#     return res

# ===================== 混合检索+缓存 =====================
@lru_cache(maxsize=128)
def cached_hybrid_search(query: str, top_k=3):
    return hybrid_search(query, top_k)

def hybrid_search(query: str, top_k=3):
    index, chunks = load_vector_db()
    if not chunks:
        return []
    k_res = keyword_search(query, chunks, top_k=6)
    s_res = semantic_search(query, top_k=6)
    scored = {}
    for i, c in enumerate(s_res):
        scored[c] = scored.get(c, 0) + (6 - i) * 0.6
    for i, c in enumerate(k_res):
        scored[c] = scored.get(c, 0) + (6 - i) * 0.4
    sorted_chunks = sorted(scored.keys(), key=lambda x: scored[x], reverse=True)
    seen = set()
    final = []
    for c in sorted_chunks:
        fp = hash(c.strip()[:200])
        if fp not in seen:
            seen.add(fp)
            final.append(c)
    final = final[:top_k]
    return final

# ===================== RAG提示词构建 =====================
def build_rag_prompt(query: str, chunks: list[str]):
    if not chunks:
        return query
    context = "\n".join([f"【参考{i+1}】{c}" for i, c in enumerate(chunks)])
    prompt = f"""
【严格约束·禁止幻觉】
1. 只使用下方参考资料内容，绝不编造资料外信息。
2. 资料无对应答案 → 必须回复：文档中暂无相关信息。
3. 仅本次使用了参考资料时，回答末尾**必须标注本次用到的资料来源**，格式固定：
引用来源：参考1、参考2

参考资料：
{context}

用户问题：{query}
"""
    return prompt

# ===================== 优质回答检索 =====================
def get_good_answers(query: str, top_k=1):
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT answer FROM good_answers WHERE question = ? LIMIT ?", (query, top_k))
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows] if rows else []