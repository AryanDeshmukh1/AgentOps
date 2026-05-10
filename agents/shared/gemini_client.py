"""
Gemini API client with built-in rate limiting.
Respects free tier limits: 10 RPM for Flash, 15 RPM for Flash-Lite.
"""
import os
import asyncio
import time
import json
from typing import Optional
from collections import deque

import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_exponential

from shared.logger import get_logger

logger = get_logger(__name__)


class GeminiRateLimiter:
    """
    Thread-safe rate limiter for Gemini API.
    Tracks request timestamps in a sliding 60-second window.
    Blocks new requests if limit would be exceeded.
    """

    def __init__(self, max_rpm: int = 10):
        self.max_rpm = max_rpm
        self.request_timestamps: deque[float] = deque()
        self.lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Wait until we have capacity within the RPM window."""
        async with self.lock:
            now = time.time()

            # Remove timestamps older than 60 seconds
            while self.request_timestamps and now - self.request_timestamps[0] >= 60:
                self.request_timestamps.popleft()

            # If at capacity, wait until oldest timestamp expires
            if len(self.request_timestamps) >= self.max_rpm:
                wait_seconds = 60 - (now - self.request_timestamps[0]) + 0.1
                logger.info(f"Rate limit reached, waiting {wait_seconds:.1f}s")
                await asyncio.sleep(wait_seconds)

                # Clean up after waiting
                now = time.time()
                while self.request_timestamps and now - self.request_timestamps[0] >= 60:
                    self.request_timestamps.popleft()

            # Record this request
            self.request_timestamps.append(time.time())


class GeminiClient:
    """
    Wrapper around Google Generative AI with rate limiting and retries.
    """

    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not set in environment")

        genai.configure(api_key=api_key)

        self.primary_model = os.getenv("GEMINI_MODEL_PRIMARY", "gemini-2.5-flash")
        self.light_model = os.getenv("GEMINI_MODEL_LIGHT", "gemini-2.5-flash-lite")

        self.primary_limiter = GeminiRateLimiter(
            max_rpm=int(os.getenv("GEMINI_RATE_LIMIT_RPM", "10"))
        )
        self.light_limiter = GeminiRateLimiter(
            max_rpm=int(os.getenv("GEMINI_RATE_LIMIT_LIGHT_RPM", "15"))
        )

        logger.info(f"Gemini client initialized — primary={self.primary_model}, light={self.light_model}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def generate_json(
        self,
        prompt: str,
        use_light_model: bool = False,
        temperature: float = 0.2,
    ) -> dict:
        """
        Generate a structured JSON response.
        Retries up to 3 times on failure with exponential backoff.

        Args:
            prompt: The full prompt including JSON schema instructions
            use_light_model: True to use Flash-Lite (lighter tasks)
            temperature: 0.0-1.0, lower = more deterministic

        Returns:
            Parsed JSON response as a dict

        Raises:
            ValueError: If response can't be parsed as JSON after retries
        """
        model_name = self.light_model if use_light_model else self.primary_model
        limiter = self.light_limiter if use_light_model else self.primary_limiter

        await limiter.acquire()

        logger.debug(f"Calling {model_name}, prompt length={len(prompt)}")

        model = genai.GenerativeModel(
            model_name=model_name,
            generation_config={
                "temperature": temperature,
                "response_mime_type": "application/json",
            },
        )

        # google-generativeai is sync, run in thread pool
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: model.generate_content(prompt),
        )

        text = response.text.strip()

        # Strip markdown code fences if present
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from Gemini: {e}")
            logger.error(f"Raw response: {text[:500]}")
            raise ValueError(f"Invalid JSON from Gemini: {e}") from e


# Global singleton
_client: Optional[GeminiClient] = None


def get_gemini_client() -> GeminiClient:
    """Get or create the singleton Gemini client."""
    global _client
    if _client is None:
        _client = GeminiClient()
    return _client 