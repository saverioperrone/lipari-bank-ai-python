def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Split text into chunks of ~chunk_size chars with overlap."""
    if not text.strip():
        return []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        # Try to break at sentence boundary
        if end < len(text):
            # Find nearest `.` `\n` `;`
            for sep in [". ", ".\n", "? ", "! ", "\n\n"]:
                idx = text.rfind(sep, start, end)
                if idx > start + chunk_size // 2:  # at least half-full
                    end = idx + len(sep)
                    break
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end - overlap
        if end >= len(text):
            break
    return chunks
