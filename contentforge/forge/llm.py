from __future__ import annotations

import json
import re
import time

from openai import OpenAI

from forge.config import settings


def _friendly_error(exc: Exception) -> Exception:
    message = str(exc)
    lowered = message.lower()
    if "30001" in message or "balance is insufficient" in lowered:
        return RuntimeError(
            "模型账户余额不足。请为当前模型服务充值，"
            "或配置 DEEPSEEK_API_KEY 后将 config.yaml 的 llm.provider 改为 deepseek。"
        )
    return exc


def siliconflow_client() -> OpenAI:
    return OpenAI(
        api_key=settings.siliconflow_api_key,
        base_url=settings.siliconflow_base_url,
        timeout=120.0,
    )


def deepseek_client() -> OpenAI:
    return OpenAI(
        api_key=settings.deepseek_api_key,
        base_url="https://api.deepseek.com",
        timeout=120.0,
    )


def client() -> OpenAI:
    if settings.provider == "deepseek":
        return deepseek_client()
    return siliconflow_client()


def resolve_model(model: str | None) -> str:
    value = model or settings.chat_model
    if settings.provider == "deepseek" and value.startswith("deepseek-ai/"):
        return "deepseek-chat"
    return value


def chat(system: str, user: str, model: str | None = None,
         temperature: float | None = None, json_mode: bool = False,
         max_tokens: int = 2000, max_retries: int = 3) -> str:
    m = resolve_model(model)
    kwargs = {}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    last = None
    for attempt in range(max_retries):
        try:
            c = client()
            resp = c.chat.completions.create(
                model=m,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": user}],
                temperature=settings.temperature if temperature is None else temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
            return resp.choices[0].message.content or ""
        except Exception as e:  # noqa: BLE001
            last = e
            friendly = _friendly_error(e)
            if friendly is not e:
                raise friendly from e
            time.sleep(0.8 * (attempt + 1))
    raise _friendly_error(last)


def chat_json(system: str, user: str, model: str | None = None,
              temperature: float | None = None) -> dict:
    last = None
    for attempt in range(2):
        text = chat(system, user, model=model, temperature=temperature, json_mode=True)
        try:
            return extract_json(text)
        except ValueError as e:
            last = e
    raise last


def extract_json(text: str) -> dict:
    cleaned = re.sub(r"```(?:json)?", "", text.strip())
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    candidate = cleaned[start:end + 1] if (start != -1 and end > start) else cleaned
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as e:
        raise ValueError(f"无法解析 JSON ({e}): {candidate[:500]}")


def embed(texts: list[str], model: str | None = None) -> list[list[float]]:
    c = siliconflow_client()
    m = model or settings.embed_model
    resp = c.embeddings.create(model=m, input=texts)
    return [d.embedding for d in resp.data]
