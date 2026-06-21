import asyncio
import httpx
import socket

async def check_dns():
    try:
        ip = socket.gethostbyname("api.freemodel.dev")
        print("DNS Resolution:", ip)
    except Exception as e:
        print("DNS Resolution failed:", e)

async def test_api():
    url = "https://api.freemodel.dev/v1/chat/completions"
    headers = {
        "Authorization": "Bearer fe_oa_6e1f632d40f53c8e0cab3cca0c2bdde68cfa8330807e52ac",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "gpt-5.5",
        "messages": [
            {"role": "user", "content": "ping"}
        ]
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(url, headers=headers, json=payload)
            print("HTTP Status:", resp.status_code)
            print("Response:", resp.text)
        except Exception as e:
            print("HTTP Request failed:", repr(e))

async def main():
    await check_dns()
    await test_api()

asyncio.run(main())
