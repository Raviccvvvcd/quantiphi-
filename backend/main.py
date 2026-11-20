import os, time
from datetime import datetime, timezone
from typing import Literal
from fastapi import FastAPI
from fastapi.responses import StreamingResponse, PlainTextResponse
from pydantic import BaseModel
from pymongo import MongoClient

app = FastAPI(title="Quantiphi AI Chat Assistant")
STORE = {}
try:
    col = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"), serverSelectionTimeoutMS=1500)["quantiphi_chat"]["threads"]
    col.database.client.admin.command("ping")
    USE_MONGO = True
except Exception:
    USE_MONGO = False

TONES = {
    "Professional": "Respond formally and clearly like an enterprise consultant.",
    "Casual": "Respond in a friendly, casual, conversational tone.",
    "Concise": "Respond in under 3 short bullet points with zero fluff.",
}

class ChatReq(BaseModel):
    thread_id: str
    prompt: str
    tone: Literal["Professional", "Casual", "Concise"] = "Professional"

@app.get("/threads")
def list_threads():
    if USE_MONGO:
        return {"threads": list(col.find({}, {"_id": 0, "thread_id": 1, "title": 1}))}
    return {"threads": [{"thread_id": k, "title": v["title"]} for k, v in STORE.items()]}

@app.get("/threads/{tid}")
def get_thread(tid: str):
    if USE_MONGO:
        return col.find_one({"thread_id": tid}, {"_id": 0}) or {"messages": []}
    return STORE.get(tid, {"messages": []})

@app.post("/chat/stream")
def chat_stream(req: ChatReq):
    sys_msg = TONES[req.tone]
    def gen():
        t0 = time.time()
        api_key = os.getenv("OPENAI_API_KEY", "")
        chunks = []
        if api_key:
            from openai import OpenAI
            stream = OpenAI(api_key=api_key).chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": sys_msg}, {"role": "user", "content": req.prompt}],
                stream=True,
            )
            for c in stream:
                txt = c.choices[0].delta.content or ""
                chunks.append(txt)
                yield txt
        else:
            demo = {
                "Professional": f"Thank you for your query on '{req.prompt}'. Here is a structured, enterprise-ready response streamed in real time.",
                "Casual": f"Hey! About '{req.prompt}' — here is a quick, friendly answer streaming live for you!",
                "Concise": f"• Topic: {req.prompt}\n• Status: Streamed & saved.",
            }[req.tone]
            for ch in demo:
                time.sleep(0.015)
                chunks.append(ch)
                yield ch
        rec = {"timestamp": datetime.now(timezone.utc).isoformat(), "user": req.prompt, "ai": "".join(chunks), "tone": req.tone, "ms": round((time.time()-t0)*1000, 1)}
        if USE_MONGO:
            col.update_one({"thread_id": req.thread_id}, {"$setOnInsert": {"thread_id": req.thread_id, "title": req.prompt[:35]}, "$push": {"messages": rec}}, upsert=True)
        else:
            STORE.setdefault(req.thread_id, {"title": req.prompt[:35], "messages": []})["messages"].append(rec)
    return StreamingResponse(gen(), media_type="text/plain")

@app.get("/threads/{tid}/export", response_class=PlainTextResponse)
def export_md(tid: str):
    data = get_thread(tid)
    return "\n\n".join([f"**[{m['tone']}] User:** {m['user']}\n**AI:** {m['ai']}" for m in data.get("messages", [])])
