import json, httpx
from app.core.config import settings
class LLMError(Exception): pass
async def chat(messages, tools):
    headers={'Authorization':f'Bearer {settings.llm_api_key}','Content-Type':'application/json'}
    payload={'model':settings.llm_model,'messages':messages,'tools':tools,'tool_choice':'auto','stream':False}
    async with httpx.AsyncClient(timeout=120) as c:
        r=await c.post(settings.llm_base_url.rstrip('/')+'/chat/completions',headers=headers,json=payload)
        r.raise_for_status(); return r.json()['choices'][0]['message']
