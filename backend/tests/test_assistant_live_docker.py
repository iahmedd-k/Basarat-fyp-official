"""Real live testing of AI Assistant endpoints against Docker / live running server (http://localhost:8000)."""

import json
import sys
import time
import uuid
import httpx

# Ensure UTF-8 output on Windows console
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_URL = "http://localhost:8000/api/v1"


def run_live_assistant_test():
    print("=" * 95)
    print("STARTING COMPREHENSIVE LIVE DOCKER API TESTING: AI ASSISTANT & SSE STREAMING")
    print("=" * 95)

    client = httpx.Client(base_url="http://localhost:8000", timeout=60.0)

    # 1. Health check on live Docker
    health_resp = client.get("/api/v1/health")
    print(f"[1] Health Check: HTTP {health_resp.status_code} -> {health_resp.json()}")
    assert health_resp.status_code == 200, "Live server is not reachable"

    # 2. Authenticate User
    email = f"assistant_live_{uuid.uuid4().hex[:6]}@test.com"
    pwd = "AssistantLivePass123!"
    
    signup_resp = client.post(f"{BASE_URL}/auth/signup", json={"email": email, "password": pwd, "full_name": "AI Finance Tester"})
    print(f"[2] User Signup: HTTP {signup_resp.status_code}")
    
    login_resp = client.post(f"{BASE_URL}/auth/login", json={"email": email, "password": pwd})
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
    token = login_resp.json()["access_token"]
    user_id = login_resp.json()["user"]["id"]
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    print(f"    Authenticated user: {user_id}")

    # 3. Standard Non-Streaming Chat (Stock Inquiry with PSX Symbol Context)
    print("\n[3] Testing Standard REST Chat: POST /assistant/chat ...")
    chat_payload_1 = {
        "message": "What is the current price and technical outlook for OGDC on the Pakistan Stock Exchange?",
        "conversation_id": None
    }
    chat_resp_1 = client.post(f"{BASE_URL}/assistant/chat", json=chat_payload_1, headers=headers)
    print(f"    Status: HTTP {chat_resp_1.status_code}")
    assert chat_resp_1.status_code == 200, f"Chat failed: {chat_resp_1.text}"
    chat_data_1 = chat_resp_1.json()
    conv_id = chat_data_1["conversation_id"]
    print(f"    Conversation Auto-Created: {conv_id}")
    print(f"    AI Response:\n    {chat_data_1['message'][:250]}...\n")

    # 4. SSE Streaming Chat: POST /assistant/chat/stream
    print("\n[4] Testing SSE Streaming Chat: POST /assistant/chat/stream ...")
    time.sleep(2.5)
    stream_payload = {
        "message": "Can you explain how KSE-100 market index movement affects high-beta stocks?",
        "conversation_id": conv_id
    }
    
    stream_tokens = []
    events_received = []
    
    with client.stream("POST", f"{BASE_URL}/assistant/chat/stream", json=stream_payload, headers=headers) as stream_resp:
        print(f"    Stream HTTP Status: {stream_resp.status_code}")
        print(f"    Content-Type: {stream_resp.headers.get('content-type')}")
        assert stream_resp.status_code == 200, f"Stream failed: {stream_resp.status_code}"
        assert "text/event-stream" in stream_resp.headers.get("content-type", "")

        print("    [Live SSE Stream Receiving]: ", end="", flush=True)
        for line in stream_resp.iter_lines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("data: "):
                data_json = json.loads(line[6:])
                event_type = data_json.get("event")
                events_received.append(event_type)
                
                if event_type == "chunk":
                    chunk_text = data_json.get("chunk", "")
                    stream_tokens.append(chunk_text)
                    print(chunk_text, end="", flush=True)
                elif event_type == "done":
                    print(f"\n    [Stream Completed - Done Event Received]")
                elif event_type == "error":
                    print(f"\n    [Stream Error]: {data_json.get('error')}")

    full_streamed_text = "".join(stream_tokens)
    assert len(stream_tokens) > 0, "No token chunks were streamed!"
    assert "done" in events_received, "Stream did not emit done event!"
    print(f"\n    Total token chunks received: {len(stream_tokens)}")
    print(f"    Total response length: {len(full_streamed_text)} characters")

    # 5. Financial Risk Analysis Inquiry via Streaming
    print("\n[5] Testing Streaming with Financial Risk Concept (VaR / CVaR) ...")
    time.sleep(2.5)
    risk_payload = {
        "message": "What is the difference between VaR (Value at Risk) and CVaR (Conditional VaR) for portfolio risk management?",
        "conversation_id": conv_id
    }
    with client.stream("POST", f"{BASE_URL}/assistant/chat/stream", json=risk_payload, headers=headers) as stream_resp:
        assert stream_resp.status_code == 200
        risk_tokens = []
        for line in stream_resp.iter_lines():
            line = line.strip()
            if line.startswith("data: "):
                data_json = json.loads(line[6:])
                if data_json.get("event") == "chunk":
                    risk_tokens.append(data_json.get("chunk", ""))
        print(f"    Risk response received: {''.join(risk_tokens)[:160]}...")

    # 6. List Conversations
    print("\n[6] Testing GET /assistant/conversations ...")
    list_resp = client.get(f"{BASE_URL}/assistant/conversations", headers=headers)
    print(f"    Status: HTTP {list_resp.status_code}")
    assert list_resp.status_code == 200
    conversations = list_resp.json()["conversations"]
    print(f"    Found {len(conversations)} conversations for user.")
    for c in conversations:
        print(f"    - ID: {c['id']} | Title: {c['title']}")

    # 7. Get Conversation History with All Messages
    print(f"\n[7] Testing GET /assistant/conversations/{conv_id} ...")
    hist_resp = client.get(f"{BASE_URL}/assistant/conversations/{conv_id}", headers=headers)
    print(f"    Status: HTTP {hist_resp.status_code}")
    assert hist_resp.status_code == 200
    hist_data = hist_resp.json()
    messages = hist_data["messages"]
    print(f"    Conversation Title: {hist_data['conversation']['title']}")
    print(f"    Total Messages in thread: {len(messages)}")
    for i, m in enumerate(messages, 1):
        print(f"    [{i}] {m['role'].upper()}: {m['content'][:70]}...")

    # 8. Update Conversation Title
    print(f"\n[8] Testing PATCH /assistant/conversations/{conv_id} ...")
    patch_resp = client.patch(
        f"{BASE_URL}/assistant/conversations/{conv_id}",
        json={"title": "PSX Market & Risk Education"},
        headers=headers
    )
    print(f"    Status: HTTP {patch_resp.status_code}")
    assert patch_resp.status_code == 200
    assert patch_resp.json()["title"] == "PSX Market & Risk Education"
    print(f"    Updated Title: {patch_resp.json()['title']}")

    # 9. Regenerate Response
    print(f"\n[9] Testing POST /assistant/conversations/{conv_id}/regenerate ...")
    time.sleep(2.5)
    regen_resp = client.post(f"{BASE_URL}/assistant/conversations/{conv_id}/regenerate", headers=headers)
    print(f"    Status: HTTP {regen_resp.status_code}")
    assert regen_resp.status_code == 200
    print(f"    Regenerated Response snippet: {regen_resp.json()['message'][:120]}...")

    # 10. Delete Conversation
    print(f"\n[10] Testing DELETE /assistant/conversations/{conv_id} ...")
    del_resp = client.delete(f"{BASE_URL}/assistant/conversations/{conv_id}", headers=headers)
    print(f"    Status: HTTP {del_resp.status_code}")
    assert del_resp.status_code == 204
    print("    Conversation successfully deleted.")

    print("\n" + "=" * 95)
    print("ALL AI ASSISTANT ENDPOINTS (REST + SSE STREAMING + CRUD) TESTED LIVE & PASSED 100%!")
    print("=" * 95)


if __name__ == "__main__":
    run_live_assistant_test()
