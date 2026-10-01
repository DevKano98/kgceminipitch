"""
Chunk 1: LLM Gateway & Resilient Client
---------------------------------------
Educational Note for Students:
Calling external AI APIs in production requires:
1. Concurrency control (Async Semaphore) so student requests don't exhaust rate limits.
2. Exponential backoff retry on HTTP 429 (Too Many Requests).
3. JSON mode enforcement (Groq requires the word 'json' in messages).
4. Self-healing parser retry: if the model emits slightly invalid JSON or violates the
   Pydantic schema, we feed the error back once to let the LLM auto-repair it.
"""

import asyncio
import json
import logging
from typing import Type, TypeVar
from pydantic import BaseModel, ValidationError
from groq import AsyncGroq, APIStatusError, APITimeoutError
from config import GROQ_API_KEY, GROQ_MODEL, LLM_CONCURRENCY, HAS_KEY

logger = logging.getLogger("appforge.llm")

# Initialize async Groq client with resilient timeout if key is present
client: AsyncGroq | None = AsyncGroq(api_key=GROQ_API_KEY, timeout=90.0) if HAS_KEY else None

# Semaphore ensures max concurrent calls across the server
_semaphore = asyncio.Semaphore(LLM_CONCURRENCY)

T = TypeVar("T", bound=BaseModel)

async def raw_completion(system_prompt: str, user_prompt: str) -> str:
    """Execute a single JSON chat completion with concurrency slot & 429 retry."""
    if not client:
        raise RuntimeError("GROQ_API_KEY is not configured in .env")

    # Groq JSON mode requires the word 'json' in prompt messages
    if "json" not in system_prompt.lower() and "json" not in user_prompt.lower():
        system_prompt = f"{system_prompt}\nReturn valid JSON object only."

    async with _semaphore:
        for attempt in range(4):
            try:
                response = await client.chat.completions.create(
                    model=GROQ_MODEL,
                    temperature=0.3,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                )
                return response.choices[0].message.content or "{}"
            except APITimeoutError as err:
                if attempt < 2:
                    logger.warning(f"Groq API call timed out. Retrying (attempt {attempt+1})...")
                    await asyncio.sleep(1.0)
                    continue
                logger.error(f"Groq API timeout: {err}")
                raise err
            except APIStatusError as err:
                if err.status_code == 429 and attempt < 3:
                    wait_time = 1.0 * (2 ** attempt)
                    logger.warning(f"Rate limited (429). Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                if err.status_code == 400 and "json_validate_failed" in str(err) and attempt < 2:
                    logger.warning(f"Groq rejected invalid JSON syntax (attempt {attempt+1}). Retrying with strict JSON notice...")
                    user_prompt = user_prompt + "\nCRITICAL: Return strictly valid RFC 8259 JSON only. NEVER output JavaScript functions, loops, or expressions."
                    await asyncio.sleep(0.5)
                    continue
                logger.error(f"Groq API error: {err}")
                raise err

async def call_json(system_prompt: str, user_prompt: str, response_model: Type[T]) -> T:
    """
    Call Groq and validate output against a Pydantic model.
    If validation fails, performs exactly 1 self-healing repair retry showing the error.
    """
    text = await raw_completion(system_prompt, user_prompt)
    for attempt in range(2):
        try:
            data = json.loads(text)
            return response_model.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as err:
            if attempt >= 1:
                logger.error(f"Failed to parse LLM response into {response_model.__name__}: {err}")
                raise ValueError(f"Agent output invalid: {str(err)[:300]}")
            
            # Self-healing retry: send the exact schema error back to the model
            repair_prompt = (
                f"{user_prompt}\n\n"
                f"Your previous JSON was invalid for schema {response_model.__name__}:\n"
                f"{str(err)[:600]}\n\n"
                "Return the corrected JSON object only."
            )
            text = await raw_completion(system_prompt, repair_prompt)
    
    raise RuntimeError("Unreachable: call_json completed without result")
