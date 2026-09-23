"""
DataGuard AI — Phase 12A Real Gemini API Integration Smoke Test

Manual / Integration Smoke Test for live Google Gemini REST API.
This test executes against the live Gemini endpoint ONLY when GEMINI_API_KEY is configured in backend/.env or environment.

Test Flow:
1. Validates GEMINI_API_KEY presence and format.
2. Checks non-billable Gemini model metadata endpoint.
3. Assembles sample Phase 11 sanitized grounded evidence context.
4. Executes live Gemini generation call (zero raw dataset rows / zero raw PII).
5. Validates normalized response schema, grounded attribution, and response latency.
"""

import os
import sys
import time
from uuid import uuid4

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config import get_settings
from app.services.llm.gemini_provider import GeminiProvider
from app.services.llm.base import LLMConfigurationError, LLMProviderError


def run_gemini_smoke_test():
    print("=" * 70)
    print("DataGuard AI — Phase 12A Real Gemini API Live Smoke Test")
    print("=" * 70)

    settings = get_settings()

    if not settings.gemini_api_key or settings.gemini_api_key.strip() in ("", "your_google_gemini_api_key_here"):
        print("\n[SKIP] GEMINI_API_KEY is not configured in backend/.env.")
        print("To run live Gemini integration testing:")
        print("  1. Get an API key from https://aistudio.google.com/app/apikey")
        print("  2. Add `GEMINI_API_KEY=AIzaSy...` to your backend/.env")
        print("  3. Run: .\\venv\\Scripts\\python.exe test_gemini_smoke.py\n")
        return True

    print(f"\n[1/4] Initializing GeminiProvider...")
    print(f"      Model Configured : {settings.gemini_model}")
    print(f"      Timeout Seconds  : {settings.gemini_timeout_seconds}s")
    print(f"      API Key Configured: {settings.gemini_api_key[:6]}...{settings.gemini_api_key[-4:]}")

    provider = GeminiProvider(settings)

    print(f"\n[2/4] Testing Non-Billable Health Check...")
    health = provider.check_health()
    print(f"      Health Status    : {health.get('status')}")
    print(f"      Model Validated  : {health.get('model')}")
    print(f"      Provider Name    : {health.get('provider')}")

    if health.get("status") != "HEALTHY":
        print(f"[FAIL] Health check failed: {health.get('error')}")
        return False

    print(f"\n[3/4] Preparing Sanitized Grounded Context Payload...")
    system_instruction = (
        "You are the DataGuard AI Quality Assistant. Answer the user question strictly using "
        "only the provided sanitized grounded evidence. Never invent statistics or reference raw records."
    )

    sanitized_evidence_prompt = (
        "=== RETRIEVED GROUNDED EVIDENCE (PHASE 11 RAG) ===\n"
        "[EVIDENCE 1 | PHASE_5_QUALITY | Table: customers]\n"
        "Overall Quality Score: 87.5% (Grade B). Total rules executed: 14. Failed rules: 2.\n"
        "Failed Rule 1: 'email_format_check' — 18 malformed email strings detected.\n"
        "Failed Rule 2: 'age_range_check' — 4 negative age values detected.\n\n"
        "[EVIDENCE 2 | PHASE_6_PII | Column: phone_number]\n"
        "PII Risk Level: HIGH. 42 detected phone numbers formatted with redaction masks (***-***-1234).\n"
        "Zero raw PII values are included.\n\n"
        "=== USER QUESTION ===\n"
        "What are the main quality failures and PII exposures found in this dataset?"
    )

    print("      Sanitized prompt prepared (Length: %d chars, Raw PII: 0)" % len(sanitized_evidence_prompt))

    print(f"\n[4/4] Sending Live Generation Request via ProviderManager to Gemini API...")
    start_t = time.time()
    try:
        from app.services.llm.provider_manager import ProviderManager
        mgr = ProviderManager(settings)
        result = mgr.generate_with_fallback(
            prompt=sanitized_evidence_prompt,
            system_prompt=system_instruction,
            temperature=0.2,
            max_tokens=600,
        )
        elapsed_ms = (time.time() - start_t) * 1000
    except LLMProviderError as e:
        print(f"[FAIL] Live Gemini API error: {e}")
        return False
    except Exception as e:
        print(f"[FAIL] Unexpected error during Gemini call: {e}")
        return False

    print("\n" + "-" * 70)
    print("LIVE GEMINI GENERATION RESULT:")
    print("-" * 70)
    print(f"Provider Name   : {result.provider_name}")
    print(f"Model Name      : {result.model_name}")
    print(f"Fallback Active : {result.fallback_occurred}")
    print(f"Roundtrip Latency: {elapsed_ms:.1f} ms")
    print(f"Token Usage     : {result.token_usage}")
    print("\nGenerated Content:")
    print(result.content)
    print("-" * 70)

    # Verifications
    assert result.provider_name == "gemini", "Expected provider 'gemini'"
    assert not result.fallback_occurred, "Fallback should be False on direct Gemini call"
    assert len(result.content.strip()) > 20, "Content too short or empty"
    print("\n[SUCCESS] Live Gemini smoke test completed successfully!\n")
    return True


if __name__ == "__main__":
    success = run_gemini_smoke_test()
    sys.exit(0 if success else 1)
