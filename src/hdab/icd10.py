"""The WHO ICD-10 classification (`data/icd10/`, ClaML XML): does a code exist, what does it cover, does a name fit it.

Word matching only, no model (S-053). It cannot see synonyms ("heart attack" is "myocardial infarction"); `definitions.py`
asks the model about those when one is enabled.
"""

import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

XML = Path(os.environ.get("ICD10_XML", Path(__file__).resolve().parents[2] / "data" / "icd10" / "icd102019en.xml"))
STOP = {"of", "and", "the", "with", "other", "in", "or", "to", "unspecified", "disease", "diseases", "disorder",
        "disorders", "type"}
ALIAS = {"copd": "chronic obstructive pulmonary disease", "cancer": "malignant neoplasm"}


@dataclass(frozen=True)
class Category:
    labels: tuple[str, ...]  # the preferred title first, then the inclusion terms
    modified: bool  # subcodes come from a WHO modifier and are not listed in the file (E11.9)


@lru_cache(maxsize=1)
def categories() -> dict[str, Category]:
    """Empty if the file is not installed; callers say so instead of failing."""
    if not XML.exists():
        return {}
    out = {}
    for c in ET.parse(XML).getroot().iter("Class"):
        if c.get("kind") == "category":
            labels = [" ".join("".join(label.itertext()).split()) for kind in ("preferred", "inclusion")
                      for rubric in c.findall("Rubric") if rubric.get("kind") == kind for label in rubric.findall("Label")]
            out[c.get("code")] = Category(tuple(labels), c.find("ModifiedBy") is not None)
    return out


def words(text: str) -> set[str]:
    return {w[:6] for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOP}  # 6 letters: depression, depressive


def name_words(name: str) -> set[str]:
    return words(" ".join(ALIAS.get(w, w) for w in name.lower().split()))


def _kids(code: str) -> list[str]:
    return [k for k in categories() if k.startswith(code + ".")]


def _title(code: str) -> str:
    return categories()[code].labels[0]


def _home(code: str) -> str | None:
    """The category that describes a code: itself, or E11 for a modifier subcode such as E11.65."""
    if code in categories():
        return code
    parent = categories().get(code.split(".")[0])
    # shortcut: any subcode of a modified category counts as valid, compare with the modifier's list if that lets errors through
    return code.split(".")[0] if parent and parent.modified else None


def exists(code: str) -> bool:
    return _home(code) is not None


def text(code: str) -> str:
    """All WHO wording of a code and its subcodes."""
    home = _home(code)
    return " ".join(label for k in [home, *_kids(home)] for label in categories()[k].labels) if home else ""


def describe(code: str) -> str:
    """What the model reads about a code: WHO's words, so it does not answer from memory."""
    home = _home(code)
    if home is None:
        return f"WHO ICD-10 {code}: not listed."
    labels = categories()[home].labels
    subcodes = "; ".join(f"{k} {_title(k)}" for k in _kids(home)[:12]) or "-"
    return f"WHO ICD-10 {home}: {labels[0]}. Includes: {'; '.join(labels[1:6]) or '-'}. Subcodes: {subcodes}."


def also_covers(name: str, code: str) -> dict[str, str]:
    """Subcodes about something other than the name, when the name fits only part of the category title: "atrial
    fibrillation" in I48 "Atrial fibrillation and flutter" also covers the flutter subcodes. Empty if the code is as wide as the name."""
    if code not in categories():
        return {}
    wanted, title = name_words(name), words(_title(code))
    if not wanted <= title:
        return {}
    kids = {k: words(_title(k)) for k in _kids(code)}
    wanted &= set().union(*kids.values()) if kids else set()  # "malignant" is in C34's title but not in its subcodes
    other = title - name_words(name)
    if not any(w & other and not wanted <= w for w in kids.values()):
        return {}
    return {k: _title(k) for k, w in kids.items() if w & other}


def narrower(name: str, code: str) -> list[str]:
    """Subcodes that fit the name when the category as a whole does not: Gaucher disease is E75.2, not all of E75."""
    if code not in categories() or name_words(name) <= words(_title(code)):
        return []
    kids = _kids(code)
    hits = [k for k in kids if name_words(name) <= words(" ".join(categories()[k].labels))]
    return hits if len(hits) < len(kids) else []
