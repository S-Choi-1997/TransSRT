"""
Translator Module
Integrates with Gemini API for async batch translation of subtitles.
"""

import asyncio
import os
from typing import List, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

try:
    import google.generativeai as genai
except ImportError:
    genai = None

from chunker import Chunk


class TranslationError(Exception):
    """Custom exception for translation errors."""
    pass


class RateLimitError(Exception):
    """Exception for rate limit errors."""
    pass


class GeminiTranslator:
    """Translator using Google Gemini API with async batch processing."""

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
        if not genai:
            raise ImportError("google-generativeai package not installed")

        self.api_key = api_key
        self.model_name = model
        self.max_concurrent = max_concurrent

        # Configure Gemini
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model)

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

                # Generate content (sync call, but wrapped in async context)
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: self.model.generate_content(prompt)
                )

                # Check for rate limit or errors
                if not response or not response.text:
                    raise TranslationError("Empty response from Gemini API")

                # Parse response
                translations = self._parse_response(response.text, len(chunk.entries))
                return translations

            except Exception as e:
                error_msg = str(e).lower()
                if '429' in error_msg or 'rate limit' in error_msg:
                    raise RateLimitError(f"Rate limit exceeded: {e}")
                elif 'timeout' in error_msg:
                    raise asyncio.TimeoutError(f"Request timed out: {e}")
                else:
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
