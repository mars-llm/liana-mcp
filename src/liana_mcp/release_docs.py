"""Read the packaged upstream documentation for the supported Liana release."""

import re
from functools import cache
from importlib.resources import files
from typing import Literal

from pydantic import BaseModel

from .errors import SafetyError

LIANA_RELEASE = "16.0"
LIANA_SOURCE = "ad203b7fbefae6f2b5b36f25db41ff0e0e2acd13"
DocName = Literal["USAGE", "RECOVER", "SIGNING_DEVICES", "LABELS", "TRY", "API"]
DOCUMENTS: tuple[DocName, ...] = ("USAGE", "RECOVER", "SIGNING_DEVICES", "LABELS", "TRY", "API")


class DocExcerpt(BaseModel):
    document: DocName
    source: str
    start_line: int
    end_line: int
    next_line: int | None
    text: str


class DocSearch(BaseModel):
    release: str = LIANA_RELEASE
    matches: list[DocExcerpt]


@cache
def lines_for(document: DocName) -> tuple[str, ...]:
    path = files("liana_mcp").joinpath("upstream", f"liana-{LIANA_RELEASE}", f"{document}.md")
    return tuple(path.read_text(encoding="utf-8").splitlines())


def read_document(document: DocName, start: int, count: int) -> DocExcerpt:
    lines = lines_for(document)
    if start > len(lines):
        raise SafetyError("The requested line is past the end of the release document.")
    end = min(start + count - 1, len(lines))
    return DocExcerpt(
        document=document,
        source=f"https://github.com/wizardsardine/liana/blob/{LIANA_SOURCE}/doc/{document}.md#L{start}-L{end}",
        start_line=start,
        end_line=end,
        next_line=end + 1 if end < len(lines) else None,
        text="\n".join(lines[start - 1 : end]),
    )


def words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]{2,}", text.casefold()))


def search_documents(query: str) -> DocSearch:
    terms = words(query) - {
        "about",
        "and",
        "can",
        "does",
        "how",
        "in",
        "is",
        "of",
        "the",
        "to",
        "what",
    }
    candidates = []
    for doc in DOCUMENTS:
        lines = lines_for(doc)
        for index, line in enumerate(lines):
            exact = len(terms & words(line))
            if exact:
                start = max(0, index - 3)
                context = " ".join(lines[start : start + 12])
                score = (len(terms & words(context)), exact)
                candidates.append((score, doc, start + 1))
    candidates.sort(key=lambda item: item[0], reverse=True)
    matches: list[DocExcerpt] = []
    for _, doc, start in candidates:
        if any(match.document == doc and abs(match.start_line - start) < 12 for match in matches):
            continue
        matches.append(read_document(doc, start, 12))
        if len(matches) == 5:
            break
    return DocSearch(matches=matches)
