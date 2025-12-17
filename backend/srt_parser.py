"""
SRT Parser Module
Parses and validates SRT subtitle files using proven regex pattern.
"""

import re
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class SRTEntry:
    """Represents a single SRT subtitle entry."""
    number: str
    timestamp: str
    text: str


class SRTParser:
    """Parser for SRT subtitle files."""

    # Regex pattern from fix_srt.py and count_tokens.py
    SRT_PATTERN = r'(\d+)\s+(\d{2}:\d{2}:\d{2},\d{3}\s+-->\s+\d{2}:\d{2}:\d{2},\d{3})\s+(.+?)(?=\n\d+\s+\d{2}:|\Z)'

    def __init__(self):
        self.pattern = re.compile(self.SRT_PATTERN, re.DOTALL)

    def parse(self, content: str) -> List[SRTEntry]:
        """
        Parse SRT content into list of SRTEntry objects.

        Args:
            content: Raw SRT file content as string

        Returns:
            List of SRTEntry objects

        Raises:
            ValueError: If content is invalid or empty
        """
        if not content or not content.strip():
            raise ValueError("SRT content is empty")

        matches = self.pattern.findall(content)

        if not matches:
            raise ValueError("No valid SRT entries found in content")

        entries = []
        for number, timestamp, text in matches:
            # Clean up text (remove extra whitespace but preserve intentional line breaks)
            cleaned_text = text.strip()
            if cleaned_text:  # Skip empty entries
                entries.append(SRTEntry(
                    number=number.strip(),
                    timestamp=timestamp.strip(),
                    text=cleaned_text
                ))

        return entries

    def validate(self, content: str) -> bool:
        """
        Validate if content appears to be valid SRT format.

        Args:
            content: Raw SRT file content

        Returns:
            True if content appears valid, False otherwise
        """
        if not content or not content.strip():
            return False

        # Check if there's at least one match
        matches = self.pattern.findall(content)
        return len(matches) > 0

    def format_output(self, entries: List[SRTEntry]) -> str:
        """
        Format SRTEntry objects into proper SRT file format.

        Args:
            entries: List of SRTEntry objects

        Returns:
            Formatted SRT content as string
        """
        if not entries:
            raise ValueError("No entries to format")

        lines = []
        for entry in entries:
            lines.append(entry.number)
            lines.append(entry.timestamp)
            lines.append(entry.text)
            lines.append('')  # Blank line between entries

        # Join with newlines, ensuring proper line endings
        return '\n'.join(lines)

    def get_entry_count(self, content: str) -> int:
        """
        Get the number of subtitle entries in content.

        Args:
            content: Raw SRT file content

        Returns:
            Number of entries
        """
        matches = self.pattern.findall(content)
        return len(matches)


def parse_srt_file(filepath: str) -> List[SRTEntry]:
    """
    Convenience function to parse SRT file directly.

    Args:
        filepath: Path to SRT file

    Returns:
        List of SRTEntry objects
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    parser = SRTParser()
    return parser.parse(content)
