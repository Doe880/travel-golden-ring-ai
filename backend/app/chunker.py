import re
from pathlib import Path
from typing import Any, Dict, List


def parse_frontmatter(text: str) -> tuple[Dict[str, str], str]:
    """
    Парсит мета-информацию в начале markdown-файла:

    ---
    city: Суздаль
    region: Владимирская область
    lat: 56.4270
    lon: 40.4526
    ---
    """

    metadata: Dict[str, str] = {}

    if not text.startswith("---"):
        return metadata, text

    parts = text.split("---", 2)

    if len(parts) < 3:
        return metadata, text

    raw_meta = parts[1].strip()
    body = parts[2].strip()

    for line in raw_meta.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            metadata[key.strip()] = value.strip()

    return metadata, body


def split_markdown_by_headings(text: str) -> List[Dict[str, str]]:
    """
    Делит markdown на чанки по заголовкам ## и ###.
    """

    lines = text.splitlines()
    chunks = []

    current_title = "Общая информация"
    current_lines = []

    for line in lines:
        if re.match(r"^#{2,3}\s+", line):
            if current_lines:
                chunks.append(
                    {
                        "title": current_title,
                        "content": "\n".join(current_lines).strip(),
                    }
                )

            current_title = re.sub(r"^#{2,3}\s+", "", line).strip()
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_lines:
        chunks.append(
            {
                "title": current_title,
                "content": "\n".join(current_lines).strip(),
            }
        )

    return [chunk for chunk in chunks if chunk["content"]]


def build_chunks_from_file(file_path: Path) -> List[Dict[str, Any]]:
    raw_text = file_path.read_text(encoding="utf-8")
    metadata, body = parse_frontmatter(raw_text)

    city = metadata.get("city", file_path.stem)
    file_chunks = split_markdown_by_headings(body)

    chunks = []

    for i, chunk in enumerate(file_chunks):
        chunk_text = f"""
Город: {city}
Раздел: {chunk["title"]}

{chunk["content"]}
""".strip()

        chunks.append(
            {
                "id": f"{file_path.stem}_{i}",
                "city": city,
                "source_file": file_path.name,
                "title": chunk["title"],
                "text": chunk_text,
                "metadata": metadata,
            }
        )

    return chunks


def build_all_chunks(knowledge_base_dir: Path) -> List[Dict[str, Any]]:
    all_chunks = []

    for file_path in sorted(knowledge_base_dir.glob("*.md")):
        all_chunks.extend(build_chunks_from_file(file_path))

    return all_chunks