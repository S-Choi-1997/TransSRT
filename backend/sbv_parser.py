"""
SBV Parser Module
Parses YouTube SBV (SubViewer) subtitle files and converts to SRT format.
"""

import re
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class SBVEntry:
    """Represents a single SBV subtitle entry."""
    timestamp: str  # Original SBV timestamp (e.g., "0:01:30.400,0:01:34.050")
    text: str


class SBVParser:
    """Parser for SBV subtitle files."""

    # SBV timestamp pattern: 0:01:30.400,0:01:34.050
    TIMESTAMP_PATTERN = r'(\d+:\d{2}:\d{2}\.\d{3}),(\d+:\d{2}:\d{2}\.\d{3})'

    def __init__(self):
        self.timestamp_re = re.compile(self.TIMESTAMP_PATTERN)

    def parse(self, content: str) -> List[SBVEntry]:
        """
        Parse SBV content into list of SBVEntry objects.

        Args:
            content: Raw SBV file content as string

        Returns:
            List of SBVEntry objects

        Raises:
            ValueError: If content is invalid or empty
        """
        if not content or not content.strip():
            raise ValueError("SBV content is empty")

        lines = content.split('\n')
        entries = []
        current_timestamp = None
        current_text_lines = []

        for line in lines:
            line = line.strip()

            # Check if line is a timestamp
            if self.timestamp_re.match(line):
                # Save previous entry if exists
                if current_timestamp and current_text_lines:
                    text = '\n'.join(current_text_lines).strip()
                    if text:  # Only add non-empty entries
                        entries.append(SBVEntry(
                            timestamp=current_timestamp,
                            text=text
                        ))

                # Start new entry
                current_timestamp = line
                current_text_lines = []

            elif line:  # Non-empty line that's not a timestamp
                if current_timestamp:  # Only add if we have a timestamp
                    current_text_lines.append(line)

        # Add last entry
        if current_timestamp and current_text_lines:
            text = '\n'.join(current_text_lines).strip()
            if text:
                entries.append(SBVEntry(
                    timestamp=current_timestamp,
                    text=text
                ))

        if not entries:
            raise ValueError("No valid SBV entries found in content")

        return entries

    def validate(self, content: str) -> bool:
        """
        Validate if content appears to be valid SBV format.

        Args:
            content: Raw SBV file content

        Returns:
            True if content appears valid, False otherwise
        """
        if not content or not content.strip():
            return False

        # Check if there's at least one timestamp match
        return bool(self.timestamp_re.search(content))

    def sbv_to_srt_timestamp(self, sbv_timestamp: str) -> str:
        """
        Convert SBV timestamp to SRT format.

        SBV: 0:01:30.400,0:01:34.050
        SRT: 00:01:30,400 --> 00:01:34,050

        Args:
            sbv_timestamp: SBV format timestamp

        Returns:
            SRT format timestamp
        """
        match = self.timestamp_re.match(sbv_timestamp)
        if not match:
            raise ValueError(f"Invalid SBV timestamp: {sbv_timestamp}")

        start, end = match.groups()

        # Convert time format: 0:01:30.400 -> 00:01:30,400
        def convert_time(time_str: str) -> str:
            # Replace . with , for milliseconds
            time_str = time_str.replace('.', ',')
            # Ensure hour has 2 digits
            parts = time_str.split(':')
            if len(parts[0]) == 1:
                parts[0] = '0' + parts[0]
            return ':'.join(parts)

        srt_start = convert_time(start)
        srt_end = convert_time(end)

        return f"{srt_start} --> {srt_end}"

    def to_srt_format(self, entries: List[SBVEntry]) -> str:
        """
        Convert SBV entries to SRT format string.

        Args:
            entries: List of SBVEntry objects

        Returns:
            SRT formatted string
        """
        if not entries:
            raise ValueError("No entries to format")

        lines = []
        for i, entry in enumerate(entries, 1):
            lines.append(str(i))  # Entry number
            lines.append(self.sbv_to_srt_timestamp(entry.timestamp))
            lines.append(entry.text)
            lines.append('')  # Blank line between entries

        return '\n'.join(lines)

    def get_entry_count(self, content: str) -> int:
        """
        Get the number of subtitle entries in content.

        Args:
            content: Raw SBV file content

        Returns:
            Number of entries
        """
        try:
            entries = self.parse(content)
            return len(entries)
        except ValueError:
            return 0


def parse_sbv_file(filepath: str) -> List[SBVEntry]:
    """
    Convenience function to parse SBV file directly.

    Args:
        filepath: Path to SBV file

    Returns:
        List of SBVEntry objects
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    parser = SBVParser()
    return parser.parse(content)
