"""Split a concatenated chapters file (headed '# Chapter N — Title') into
individual vault/02-Chapters/Saga-<n>/chapter-NN.md files with frontmatter.

POV is read directly from '— Name —' break markers in the text (HR-09).
Arc/status must be supplied by hand per the known arc boundaries (BUILD_PLAN
Section 3.4 + chapter-log.md arc headers) - never guessed from content alone.

Usage: uv run python scripts/split_chapters.py
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "_source" / "AETHON_SAGA1_CHAPTERS_1-13.md"
OUT_DIR = ROOT / "vault" / "02-Chapters" / "Saga-1"

# Known arc boundaries for Chapters 1-13 (Saga 1), cross-referenced from
# chapter-log.md arc section headers + BUILD_PLAN.md Section 3.4 ("Arc 4
# ch. 14-22" implies Arc 3 ends at ch. 13). Not inferred from prose alone.
ARC_BY_CHAPTER = {
    1: 1, 2: 1, 3: 1, 4: 1, 5: 1,
    6: 2, 7: 2,
    8: 3, 9: 3, 10: 3, 11: 3, 12: 3, 13: 3,
}

CHAPTER_HEADING_RE = re.compile(r"^#\s*Chapter\s+(\d+)\s*(?:—|-)?\s*(.*)$", re.MULTILINE)
POV_MARKER_RE = re.compile(r"^—\s*(.+?)\s*—$", re.MULTILINE)


def main() -> None:
    text = SOURCE.read_text(encoding="utf-8")
    headings = list(CHAPTER_HEADING_RE.finditer(text))
    if not headings:
        raise SystemExit("No '# Chapter N — Title' headings found.")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for i, m in enumerate(headings):
        num = int(m.group(1))
        title = m.group(2).strip()
        start = m.start()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        body = text[start:end].rstrip() + "\n"

        pov_names = []
        for pm in POV_MARKER_RE.finditer(body):
            name = pm.group(1).strip()
            if name not in pov_names:
                pov_names.append(name)
        if not pov_names:
            raise SystemExit(f"Chapter {num}: no POV marker found - refusing to guess.")

        arc = ARC_BY_CHAPTER.get(num)
        if arc is None:
            raise SystemExit(f"Chapter {num}: no known arc mapping - add it by hand first.")

        word_count = len(re.findall(r"\S+", body))
        pov_yaml = "[" + ", ".join(pov_names) + "]"

        frontmatter = (
            "---\n"
            f"chapter: {num}\n"
            f"arc: {arc}\n"
            "saga: 1\n"
            f"pov: {pov_yaml}\n"
            "status: approved\n"
            f"characters: {pov_yaml}\n"
            "hooks_advanced: []\n"
            "hooks_resolved: []\n"
            "new_canon: []\n"
            f"word_count: {word_count}\n"
            "---\n\n"
        )

        out_path = OUT_DIR / f"chapter-{num:02d}.md"
        out_path.write_text(frontmatter + body, encoding="utf-8")
        print(f"wrote {out_path.relative_to(ROOT)}  (arc {arc}, pov {pov_names}, {word_count}w)")


if __name__ == "__main__":
    main()
