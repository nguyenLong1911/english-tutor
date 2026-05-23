import asyncio
from app.utils.llm import GroqLLMClient, GeminiLLMClient
from app.core.config import get_settings

async def test():
    settings = get_settings()
    
    print("=== CONFIG ===")
    print(f"Gemini key set: {bool(settings.GEMINI_API_KEY)}")
    print(f"Groq key set: {bool(settings.GROQ_API_KEY)}")
    print(f"Gemini key len: {len(settings.GEMINI_API_KEY) if settings.GEMINI_API_KEY else 0}")
    print(f"Groq key len: {len(settings.GROQ_API_KEY) if settings.GROQ_API_KEY else 0}")
    
    print("\n=== GEMINI CLIENT ===")
    gemini = GeminiLLMClient()
    print(f"Gemini enabled: {gemini.enabled}")
    
    if gemini.enabled:
        try:
            result = await gemini.generate_chat_completion(
                [{"role": "user", "content": "Say GEMINI_TEST."}],
                temperature=0, max_tokens=20
            )
            print(f"Gemini SUCCESS: {gemini.last_provider}")
            print(f"Response: {result[:60]}")
        except Exception as e:
            print(f"Gemini FAILED: {type(e).__name__}: {str(e)[:80]}")
    
    print("\n=== GROQ CLIENT ===")
    groq = GroqLLMClient()
    print(f"Groq enabled: {groq.enabled}")
    
    if groq.enabled:
        try:
            result = await groq.generate_chat_completion(
                [{"role": "user", "content": "Say GROQ_TEST."}],
                temperature=0, max_tokens=20
            )
            print(f"Groq SUCCESS: {groq.last_provider}")
            print(f"Response: {result[:60]}")
        except Exception as e:
            print(f"Groq FAILED: {type(e).__name__}: {str(e)[:80]}")

asyncio.run(test())
