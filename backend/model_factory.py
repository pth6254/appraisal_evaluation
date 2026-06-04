"""
model_factory.py — LLM · 임베딩 프로바이더 팩토리

.env 설정:
    LLM_PROVIDER   = ollama | openai | anthropic | google  (기본: ollama)
    EMBED_PROVIDER = ollama | openai | google              (기본: LLM_PROVIDER, anthropic이면 ollama)

지원 프로바이더별 필요 패키지:
    ollama    → langchain-ollama (기본 설치)
    openai    → pip install langchain-openai
    anthropic → pip install langchain-anthropic  (임베딩 미지원 → EMBED_PROVIDER 별도 설정)
    google    → pip install langchain-google-genai
"""

from __future__ import annotations

import os
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

LLM_PROVIDER   = os.getenv("LLM_PROVIDER",   "ollama").lower().strip()
EMBED_PROVIDER = os.getenv("EMBED_PROVIDER",  "").lower().strip()

# Anthropic은 임베딩 미지원 → ollama 폴백
if not EMBED_PROVIDER:
    EMBED_PROVIDER = "ollama" if LLM_PROVIDER == "anthropic" else LLM_PROVIDER


# ─────────────────────────────────────────
#  LLM 팩토리
# ─────────────────────────────────────────

def get_llm():
    """일반 텍스트 출력 LLM"""
    if LLM_PROVIDER == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=os.getenv("OLLAMA_MODEL", "exaone3.5:7.8b"),
            base_url=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
            temperature=0.0,
        )

    if LLM_PROVIDER == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "gpt-4o"),
            api_key=os.getenv("OPENAI_API_KEY"),
            temperature=0.0,
        )

    if LLM_PROVIDER == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=os.getenv("ANTHROPIC_MODEL", "claude-opus-4-7"),
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            temperature=0.0,
            max_tokens=4096,
        )

    if LLM_PROVIDER == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=os.getenv("GOOGLE_MODEL", "gemini-2.0-flash"),
            google_api_key=os.getenv("GOOGLE_GENERATIVE_AI_API_KEY"),
            temperature=0.0,
        )

    raise ValueError(f"[model_factory] 지원하지 않는 LLM_PROVIDER: '{LLM_PROVIDER}'"
                     " (ollama | openai | anthropic | google)")


def get_llm_json():
    """JSON 출력 전용 LLM (프로바이더별 네이티브 JSON 모드 사용)"""
    if LLM_PROVIDER == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=os.getenv("OLLAMA_MODEL", "exaone3.5:7.8b"),
            base_url=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
            temperature=0.0,
            format="json",
        )

    if LLM_PROVIDER == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "gpt-4o"),
            api_key=os.getenv("OPENAI_API_KEY"),
            temperature=0.0,
            model_kwargs={"response_format": {"type": "json_object"}},
        )

    if LLM_PROVIDER == "anthropic":
        # Anthropic은 네이티브 JSON 모드 없음 → 프롬프트 기반 JSON 유도
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=os.getenv("ANTHROPIC_MODEL", "claude-opus-4-7"),
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            temperature=0.0,
            max_tokens=4096,
        )

    if LLM_PROVIDER == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=os.getenv("GOOGLE_MODEL", "gemini-2.0-flash"),
            google_api_key=os.getenv("GOOGLE_GENERATIVE_AI_API_KEY"),
            temperature=0.0,
            generation_config={"response_mime_type": "application/json"},
        )

    raise ValueError(f"[model_factory] 지원하지 않는 LLM_PROVIDER: '{LLM_PROVIDER}'")


# ─────────────────────────────────────────
#  임베딩 팩토리
# ─────────────────────────────────────────

def get_embeddings():
    """벡터 임베딩 모델 (RAG용)"""
    if EMBED_PROVIDER == "ollama":
        from langchain_ollama import OllamaEmbeddings
        return OllamaEmbeddings(
            model=os.getenv("OLLAMA_EMBED_MODEL", "mxbai-embed-large"),
            base_url=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
        )

    if EMBED_PROVIDER == "openai":
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(
            model=os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small"),
            api_key=os.getenv("OPENAI_API_KEY"),
        )

    if EMBED_PROVIDER == "google":
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        return GoogleGenerativeAIEmbeddings(
            model=os.getenv("GOOGLE_EMBED_MODEL", "models/text-embedding-004"),
            google_api_key=os.getenv("GOOGLE_GENERATIVE_AI_API_KEY"),
        )

    raise ValueError(f"[model_factory] 지원하지 않는 EMBED_PROVIDER: '{EMBED_PROVIDER}'"
                     " (ollama | openai | google)")


def print_config():
    model_name = {
        "ollama":    os.getenv("OLLAMA_MODEL",    "exaone3.5:7.8b"),
        "openai":    os.getenv("OPENAI_MODEL",    "gpt-4o"),
        "anthropic": os.getenv("ANTHROPIC_MODEL", "claude-opus-4-7"),
        "google":    os.getenv("GOOGLE_MODEL",    "gemini-3.5-flash"),
    }.get(LLM_PROVIDER, "?")

    embed_name = {
        "ollama": os.getenv("OLLAMA_EMBED_MODEL", "mxbai-embed-large"),
        "openai": os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small"),
        "google": os.getenv("GOOGLE_EMBED_MODEL", "models/text-embedding-004"),
    }.get(EMBED_PROVIDER, "?")

    print(f"[model_factory] LLM   : {LLM_PROVIDER} / {model_name}")
    print(f"[model_factory] Embed : {EMBED_PROVIDER} / {embed_name}")
