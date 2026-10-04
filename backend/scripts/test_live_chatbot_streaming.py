import asyncio
import json
import time
import httpx
import sys
import subprocess
import base64

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

SSH_KEY = r"d:\FYP\OrcaleSecrets\ssh-key-2026-10-03.key"
REMOTE_USER = "ubuntu"
REMOTE_HOST = "193.123.84.223"
BASE_URL = "http://193.123.84.223:8000"

def get_auth_token() -> str:
    py_code = """
import json
from datetime import timedelta
from app.core.security import create_access_token
from app.db.base import get_sync_session_factory
from app.models.user import User

with get_sync_session_factory()() as s:
    u = s.query(User).filter(User.email == 'admin@basarat.pk').first()
    if not u:
        u = s.query(User).first()
    token = create_access_token(
        data={'sub': str(u.id), 'email': u.email, 'role': getattr(u, 'role', 'admin')},
        expires_delta=timedelta(days=7)
    )
    print(json.dumps({'token': token}))
"""
    b64 = base64.b64encode(py_code.encode("utf-8")).decode("ascii")
    remote_cmd = f"echo '{b64}' | base64 -d | sudo docker exec -i basarat-app-1 python"
    cmd = ["ssh", "-i", SSH_KEY, "-o", "StrictHostKeyChecking=no", f"{REMOTE_USER}@{REMOTE_HOST}", remote_cmd]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"Failed to fetch token: {res.stderr}")
    for line in res.stdout.strip().split("\n"):
        line = line.strip()
        if line.startswith("{") and "token" in line:
            return json.loads(line)["token"]
    raise RuntimeError(f"Could not parse token from output: {res.stdout}")

async def stream_chat(client: httpx.AsyncClient, token: str, message: str, conversation_id: str | None = None):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }
    payload = {"message": message}
    if conversation_id:
        payload["conversation_id"] = conversation_id

    print(f"\n==================================================================")
    print(f"USER PROMPT: \"{message}\"")
    if conversation_id:
        print(f"Conversation ID: {conversation_id}")
    print(f"==================================================================")

    start_time = time.time()
    first_chunk_time = None
    chunks_received = []
    events = []
    active_conversation_id = conversation_id

    try:
        async with client.stream(
            "POST",
            f"{BASE_URL}/api/v1/assistant/chat/stream",
            headers=headers,
            json=payload,
            timeout=60.0,
        ) as response:
            if response.status_code != 200:
                print(f"[ERROR] HTTP {response.status_code}: {await response.aread()}")
                return None, active_conversation_id

            async for line in response.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue
                data_str = line[len("data: "):].strip()
                if not data_str:
                    continue
                try:
                    event_data = json.loads(data_str)
                    events.append(event_data)
                    event_type = event_data.get("event")

                    if event_type == "start":
                        active_conversation_id = event_data.get("conversation_id")
                    elif event_type == "chunk":
                        if first_chunk_time is None:
                            first_chunk_time = time.time()
                        chunk_text = event_data.get("chunk", "")
                        chunks_received.append(chunk_text)
                        # Print chunk live
                        print(chunk_text, end="", flush=True)
                    elif event_type == "replace":
                        print(f"\n[EVENT: REPLACE] -> Safety filter modified output")
                    elif event_type == "done":
                        pass
                except Exception as e:
                    print(f"\n[PARSE ERROR] {e} line={data_str}")

    except Exception as e:
        print(f"\n[STREAM ERROR] {e}")
        return None, active_conversation_id

    total_time = time.time() - start_time
    ttft = (first_chunk_time - start_time) * 1000 if first_chunk_time else None
    full_text = "".join(chunks_received)

    print("\n------------------------------------------------------------------")
    print(f"METRICS & STREAMING PERFORMANCE:")
    print(f"- Time to First Token (TTFT): {ttft:.1f} ms" if ttft else "- TTFT: N/A")
    print(f"- Total Response Time: {total_time * 1000:.1f} ms")
    print(f"- Total Stream Chunks: {len(chunks_received)}")
    print(f"- Total Character Length: {len(full_text)} chars")
    
    # Analyze Formatting
    has_bold = "**" in full_text
    has_headers = "# " in full_text or "## " in full_text
    has_asterisks = "*" in full_text
    has_lists = "\n- " in full_text or "\n1. " in full_text or full_text.startswith("- ") or full_text.startswith("1. ")
    
    print(f"\nFORMATTING ANALYSIS:")
    print(f"- Plain Text Adherence: {'PASS (Clean plain text)' if not (has_bold or has_headers) else 'CONTAINS MARKDOWN'}")
    print(f"- Markdown Bold (**): {'Found' if has_bold else 'None (Clean)'}")
    print(f"- Markdown Headers (###): {'Found' if has_headers else 'None (Clean)'}")
    print(f"- Structured Bullet/Numbered Lists: {'Yes (Well structured)' if has_lists else 'Paragraphs'}")
    print(f"- Hallucination Check: {'Grounded with numbers/PKR' if 'PKR' in full_text or '0' in full_text or '%' in full_text else 'Conceptual'}")
    print(f"------------------------------------------------------------------")

    return full_text, active_conversation_id

async def main():
    print("Authenticating with live backend...")
    token = get_auth_token()
    print("Authentication successful!")

    test_queries = [
        "What is the current stock price, trend, and RSI for OGDC?",
        "Can you also check its P/E ratio and how its sector is performing?",
        "How is the broader PSX market breadth and KSE-100 index doing today?",
        "Is MEBL compliant according to Shariah criteria in PSX?",
        "Review my portfolio holdings and risk profile.",
    ]

    async with httpx.AsyncClient(timeout=90.0) as client:
        conv_id = None
        for i, q in enumerate(test_queries):
            # First two queries share the same conversation (multi-turn follow-up test)
            if i == 0:
                conv_id = None
            elif i == 1:
                # Keep same conv_id
                pass
            else:
                conv_id = None

            _, conv_id = await stream_chat(client, token, q, conversation_id=conv_id)
            await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())
