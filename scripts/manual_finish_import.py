"""One-off: finish importing Chapters 5-13 into books/aethon/ WITHOUT any LLM
calls, matching the file format InkOS's own importer already used for
Chapters 1-4 (docx header re-cast as "# Chapter N: Title", "### Saga S, Arc A"
subheading, "---" divider, then body verbatim, footer kept as-is).

Used because inkos import chapters' per-chapter reverse-engineering (LLM
analysis via the chapter-analyzer agent, which defaulted to the expensive
writer model) was cut short on cost grounds after chapter 4. This script only
adds the chapter body files + chapters/index.json entries so InkOS knows
Chapters 5-13 exist and can be used as context for future writing. It does
NOT reconstruct character_matrix/current_state/hooks for these chapters -
those remain accurate only through Chapter 4 until a cheaper re-run is
worth doing.
"""
import json
import re
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "_source" / "AETHON_SAGA1_CHAPTERS_1-13.md"
CHAPTERS_DIR = ROOT / "books" / "aethon" / "chapters"
INDEX_PATH = CHAPTERS_DIR / "index.json"

ARC_BY_CHAPTER = {5: 1, 6: 2, 7: 2, 8: 3, 9: 3, 10: 3, 11: 3, 12: 3, 13: 3}
START_CHAPTER = 5
END_CHAPTER = 13

CHAPTER_HEADING_RE = re.compile(r"^#\s*Chapter\s+(\d+)\s*(?:—|-)?\s*(.*)$", re.MULTILINE)


def slugify_title(title: str) -> str:
    cleaned = re.sub(r"[^\w\s]", "", title)
    return re.sub(r"\s+", "_", cleaned.strip())


def main() -> None:
    text = SOURCE.read_text(encoding="utf-8")
    headings = list(CHAPTER_HEADING_RE.finditer(text))

    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    existing_numbers = {entry["number"] for entry in index}

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + f"{datetime.now().microsecond // 1000:03d}Z"

    for i, m in enumerate(headings):
        num = int(m.group(1))
        if num < START_CHAPTER or num > END_CHAPTER:
            continue
        if num in existing_numbers:
            print(f"chapter {num}: already in index.json, skipping")
            continue

        title = m.group(2).strip()
        start = m.start()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        raw_body = text[start:end].rstrip() + "\n"

        # Strip the original heading line, keep everything after it.
        body_after_heading = raw_body.split("\n", 1)[1].lstrip("\n")

        arc = ARC_BY_CHAPTER[num]
        formatted = (
            f"# Chapter {num}: {title}\n\n"
            f"### Saga 1, Arc {arc}\n\n"
            f"{body_after_heading}"
        )

        word_count = len(re.findall(r"\S+", body_after_heading))
        filename = f"{num:04d}_{slugify_title(title)}.md"
        out_path = CHAPTERS_DIR / filename
        out_path.write_text(formatted, encoding="utf-8")

        index.append({
            "number": num,
            "title": title,
            "status": "imported",
            "wordCount": word_count,
            "createdAt": now,
            "updatedAt": now,
            "auditIssues": [],
            "lengthWarnings": [],
        })
        print(f"wrote {out_path.relative_to(ROOT)} ({word_count}w, arc {arc})")

    index.sort(key=lambda e: e["number"])
    INDEX_PATH.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    print(f"index.json now has {len(index)} chapters")


if __name__ == "__main__":
    main()
