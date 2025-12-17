"""
Chunker Module
Splits subtitle entries into optimal chunks for batch translation.
"""

from dataclasses import dataclass
from typing import List
from srt_parser import SRTEntry


@dataclass
class Chunk:
    """Represents a chunk of subtitle entries for translation."""
    entries: List[SRTEntry]
    index: int  # 1-based index
    total: int  # Total number of chunks
    previous_context: List[SRTEntry]  # Entries from previous chunk for context


class SubtitleChunker:
    """Creates optimal chunks for subtitle translation."""

    def __init__(self, chunk_size: int = 50, context_size: int = 3):
        """
        Initialize chunker with configurable sizes.

        Args:
            chunk_size: Number of entries per chunk (default: 50)
            context_size: Number of entries from previous chunk to include as context (default: 3)
        """
        self.chunk_size = chunk_size
        self.context_size = context_size

    def create_chunks(self, entries: List[SRTEntry]) -> List[Chunk]:
        """
        Split entries into chunks with overlap for context.

        Args:
            entries: List of SRTEntry objects to chunk

        Returns:
            List of Chunk objects
        """
        if not entries:
            raise ValueError("Cannot create chunks from empty entries list")

        chunks = []
        total_chunks = (len(entries) + self.chunk_size - 1) // self.chunk_size  # Ceiling division

        for i in range(0, len(entries), self.chunk_size):
            chunk_entries = entries[i:i + self.chunk_size]
            chunk_index = (i // self.chunk_size) + 1  # 1-based index

            # Get previous context (last N entries from previous chunk)
            previous_context = []
            if i > 0:
                context_start = max(0, i - self.context_size)
                previous_context = entries[context_start:i]

            chunk = Chunk(
                entries=chunk_entries,
                index=chunk_index,
                total=total_chunks,
                previous_context=previous_context
            )
            chunks.append(chunk)

        return chunks

    def get_chunk_info(self, chunks: List[Chunk]) -> dict:
        """
        Get information about chunks for logging/debugging.

        Args:
            chunks: List of Chunk objects

        Returns:
            Dictionary with chunk statistics
        """
        if not chunks:
            return {
                "total_chunks": 0,
                "total_entries": 0,
                "avg_chunk_size": 0,
                "chunk_sizes": []
            }

        chunk_sizes = [len(chunk.entries) for chunk in chunks]
        total_entries = sum(chunk_sizes)

        return {
            "total_chunks": len(chunks),
            "total_entries": total_entries,
            "avg_chunk_size": total_entries / len(chunks),
            "chunk_sizes": chunk_sizes,
            "context_size": self.context_size
        }


def create_chunks(entries: List[SRTEntry], chunk_size: int = 50) -> List[Chunk]:
    """
    Convenience function to create chunks with default settings.

    Args:
        entries: List of SRTEntry objects
        chunk_size: Number of entries per chunk (default: 50)

    Returns:
        List of Chunk objects
    """
    chunker = SubtitleChunker(chunk_size=chunk_size)
    return chunker.create_chunks(entries)
