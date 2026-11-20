import uuid, requests, streamlit as st

API = "http://127.0.0.1:8000"
st.set_page_config(page_title="AI Chat Assistant", layout="wide")
if "tid" not in st.session_state:
    st.session_state.tid = str(uuid.uuid4())

with st.sidebar:
    st.header("History")
    if st.button("New Chat", use_container_width=True):
        st.session_state.tid = str(uuid.uuid4())
        st.rerun()
    try:
        for t in requests.get(f"{API}/threads", timeout=2).json().get("threads", []):
            if st.button(t["title"], key=t["thread_id"], use_container_width=True):
                st.session_state.tid = t["thread_id"]
                st.rerun()
        exp = requests.get(f"{API}/threads/{st.session_state.tid}/export", timeout=2)
        if exp.status_code == 200 and exp.text:
            st.download_button("Export Chat (.md)", exp.text, "chat.md", use_container_width=True)
    except Exception:
        st.info("Start backend: uvicorn backend.main:app --port 8000")

tone = st.radio("Vibe Check (Tone)", ["Professional", "Casual", "Concise"], horizontal=True)
starter = st.selectbox("Quick Prompt Starters", ["", "Explain RAG in AI", "Summarize Cloud Risks", "Write a Client Follow-up"])

try:
    msgs = requests.get(f"{API}/threads/{st.session_state.tid}", timeout=2).json().get("messages", [])
except Exception:
    msgs = []

for m in msgs:
    with st.chat_message("user"):
        st.write(m["user"])
    with st.chat_message("assistant"):
        st.write(m["ai"])
        st.caption(f"Tone: {m['tone']} | {m['timestamp']} | {m.get('ms', 0)} ms")

prompt = st.chat_input("Ask anything...") or starter
if prompt:
    with st.chat_message("user"):
        st.write(prompt)
    with st.chat_message("assistant"):
        def stream():
            with requests.post(f"{API}/chat/stream", json={"thread_id": st.session_state.tid, "prompt": prompt, "tone": tone}, stream=True) as r:
                for c in r.iter_content(1, decode_unicode=True):
                    if c:
                        yield c
        st.write_stream(stream())
    st.rerun()
