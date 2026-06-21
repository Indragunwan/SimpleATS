import asyncio
import httpx

async def main():
    url = "https://api.freemodel.dev/v1/chat/completions"
    headers = {
        "Authorization": "Bearer fe_oa_c36580023383aa0344b4505f08e296fcd338504f852b3e69",
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
            print("Status:", resp.status_code)
            print("Response:", resp.text)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print("Error:", repr(e))

asyncio.run(main())
