"""
Translator Module
Integrates with Gemini API for async batch translation of subtitles.
Uses REST API for Cloud Run compatibility.
"""

import asyncio
import os
import json
from typing import List, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import requests

from chunker import Chunk


class TranslationError(Exception):
    """Custom exception for translation errors."""
    pass


class RateLimitError(Exception):
    """Exception for rate limit errors."""
    pass


class GeminiTranslator:
    """Translator using Google Gemini REST API with async batch processing."""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-1.5-flash",
        max_concurrent: int = 10
    ):
        """
        Initialize Gemini translator.

        Args:
            api_key: Google Gemini API key
            model: Gemini model name (default: gemini-1.5-flash)
            max_concurrent: Maximum concurrent API requests (default: 10)
        """
        self.api_key = api_key.strip()  # Remove any whitespace/newlines
        self.model_name = model
        self.max_concurrent = max_concurrent

        # REST API endpoint
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"

        # Semaphore for rate limiting
        self.semaphore = asyncio.Semaphore(max_concurrent)

    def _create_prompt(self, chunk: Chunk) -> str:
        """
        Create translation prompt for a chunk.

        Args:
            chunk: Chunk object containing entries to translate

        Returns:
            Formatted prompt string

        Note: This is a basic prompt structure. Will be optimized collaboratively.
        """
        # Optimized prompt for tarot reading YouTube content
        prompt = """You are a professional Korean-to-English subtitle translator specializing in spiritual and tarot reading content.

Translate the following Korean subtitles to natural English suitable for YouTube viewers, matching the style of these examples:

Example translations:
- 안녕하세요 → "Welcome."
- 많이 힘드셨죠? → "You must have felt frustrated"
- 연락이 안오셔서요 → "due to the lack of contact."

Guidelines:
- Use formal, polite tone with complete sentences
- Translate 안녕하세요 as "Welcome." (formal greeting)
- Translate 힘드셨죠 as "You must have felt [emotion]" (polite, third-person perspective)
- Translate 연락 as "contact" in formal context
- Keep spiritual/tarot terminology accurate (card, energy, fortune)
- Maintain professional subtitle style
- Keep translations concise for subtitle format (aim for 2 lines max per entry)
- Preserve line breaks from the original Korean text

"""

        # Add context if available
        if chunk.previous_context:
            prompt += f"Previous context (for continuity):\n"
            for i, entry in enumerate(chunk.previous_context[-3:], 1):
                prompt += f"{i}. {entry.text}\n"
            prompt += "\n"

        # Add current chunk info
        prompt += f"This is chunk {chunk.index}/{chunk.total}.\n\n"
        prompt += "Korean subtitles to translate:\n"

        for i, entry in enumerate(chunk.entries, 1):
            prompt += f"{i}. {entry.text}\n"

        prompt += "\n"
        prompt += "Provide ONLY the English translations, one per line, matching the exact count above.\n"
        prompt += "Do not include numbering in your response."

        return prompt

    def _parse_response(self, response_text: str, expected_count: int) -> List[str]:
        """
        Parse Gemini API response into list of translations.

        Args:
            response_text: Raw response from Gemini
            expected_count: Expected number of translations

        Returns:
            List of translated subtitle texts

        Raises:
            TranslationError: If response cannot be parsed correctly
        """
        # Split by newlines and clean
        lines = [line.strip() for line in response_text.strip().split('\n') if line.strip()]

        # Remove any numbering that might have been added
        cleaned_lines = []
        for line in lines:
            # Remove leading numbers like "1.", "1)", etc.
            import re
            cleaned = re.sub(r'^\d+[\.\)]\s*', '', line)
            if cleaned:
                cleaned_lines.append(cleaned)

        if len(cleaned_lines) != expected_count:
            # Try to handle mismatches gracefully
            if len(cleaned_lines) > expected_count:
                # Take first N
                cleaned_lines = cleaned_lines[:expected_count]
            else:
                raise TranslationError(
                    f"Expected {expected_count} translations, got {len(cleaned_lines)}"
                )

        return cleaned_lines

    def _call_gemini_rest(self, prompt: str) -> str:
        """
        Call Gemini REST API directly.

        Args:
            prompt: Translation prompt

        Returns:
            Response text from Gemini

        Raises:
            TranslationError: If API call fails
        """
        url = f"{self.base_url}/models/{self.model_name}:generateContent"

        headers = {
            "Content-Type": "application/json"
        }

        params = {
            "key": self.api_key
        }

        payload = {
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ]
        }

        try:
            response = requests.post(
                url,
                headers=headers,
                params=params,
                json=payload,
                timeout=60  # 60 second timeout
            )
            response.raise_for_status()

            result = response.json()

            # Extract text from response
            if 'candidates' not in result or len(result['candidates']) == 0:
                raise TranslationError("No candidates in response")

            candidate = result['candidates'][0]
            if 'content' not in candidate or 'parts' not in candidate['content']:
                raise TranslationError("Invalid response structure")

            parts = candidate['content']['parts']
            if len(parts) == 0 or 'text' not in parts[0]:
                raise TranslationError("No text in response")

            return parts[0]['text']

        except requests.exceptions.Timeout:
            raise asyncio.TimeoutError("Request timed out")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                raise RateLimitError(f"Rate limit exceeded: {e}")
            else:
                raise TranslationError(f"HTTP error: {e}")
        except Exception as e:
            raise TranslationError(f"API call failed: {e}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((asyncio.TimeoutError, RateLimitError))
    )
    async def _translate_chunk_with_retry(self, chunk: Chunk) -> List[str]:
        """
        Translate a single chunk with retry logic.

        Args:
            chunk: Chunk to translate

        Returns:
            List of translated texts

        Raises:
            TranslationError: If translation fails after retries
        """
        async with self.semaphore:
            try:
                prompt = self._create_prompt(chunk)

                # Call REST API (sync call, wrapped in async context)
                loop = asyncio.get_event_loop()
                response_text = await loop.run_in_executor(
                    None,
                    lambda: self._call_gemini_rest(prompt)
                )

                # Check for empty response
                if not response_text:
                    raise TranslationError("Empty response from Gemini API")

                # Parse response
                translations = self._parse_response(response_text, len(chunk.entries))
                return translations

            except (asyncio.TimeoutError, RateLimitError):
                raise  # Let retry handle these
            except Exception as e:
                raise TranslationError(f"Translation failed: {e}")

    async def translate_chunks_async(self, chunks: List[Chunk]) -> List[List[str]]:
        """
        Translate multiple chunks in parallel with rate limiting.

        Args:
            chunks: List of Chunk objects to translate

        Returns:
            List of translation lists (one list per chunk)

        Raises:
            TranslationError: If any chunk translation fails completely
        """
        tasks = [self._translate_chunk_with_retry(chunk) for chunk in chunks]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle results
        translations = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                raise TranslationError(
                    f"Chunk {i+1}/{len(chunks)} failed: {result}"
                )
            translations.append(result)

        return translations

    def translate_chunks(self, chunks: List[Chunk]) -> List[List[str]]:
        """
        Synchronous wrapper for async translation.

        Args:
            chunks: List of Chunk objects to translate

        Returns:
            List of translation lists (one list per chunk)
        """
        return asyncio.run(self.translate_chunks_async(chunks))


def translate_subtitles(
    chunks: List[Chunk],
    api_key: str,
    model: str = "gemini-1.5-flash",
    max_concurrent: int = 10
) -> List[List[str]]:
    """
    Convenience function to translate subtitle chunks.

    Args:
        chunks: List of Chunk objects
        api_key: Gemini API key
        model: Model name (default: gemini-1.5-flash)
        max_concurrent: Max concurrent requests (default: 10)

    Returns:
        List of translation lists
    """
    translator = GeminiTranslator(
        api_key=api_key,
        model=model,
        max_concurrent=max_concurrent
    )
    return translator.translate_chunks(chunks)
