"""Do a definition's name and code agree (S-070)? The rules check the facts against the WHO file, the model judges the
meaning. Both only add warnings: the numbers still use the exact code (S-007) and the model decides nothing (S-054).
"""

from dataclasses import dataclass, field

from hdab import icd10, kev, vocab
from hdab.contracts import DefinitionWarning
from hdab.data import load_tables
from hdab.plan import Plan


@dataclass
class Checked:
    warnings: list[DefinitionWarning] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    asked: list[dict] = field(default_factory=list)  # the model's answers, for the register (S-038)


def _exists(code: str) -> bool:
    return icd10.exists(code) or bool(load_tables()["conditions"]["icd10"].str.startswith(code).any())


def _condition(name: str, codes: tuple[str, ...], relation: str | None) -> tuple[str, str] | None:
    """The table of the design: (severity, message) from what the rules found and what the model said; None if fine."""
    shown = " or ".join(codes)
    if missing := [c for c in codes if not _exists(c)]:
        return "wrong", f'"{name}": {", ".join(missing)} is not a WHO ICD-10 code and does not occur in this data.'
    if relation == "different":
        return "wrong", f'"{name}": {shown} looks like a different condition. WHO: {_titles(codes)}'
    wording = " ".join(icd10.text(c) for c in codes)
    known = icd10.name_words(name) <= icd10.words(wording)
    if not known and (usual := vocab.usual_code(name, "condition", codes)):
        if relation is None:
            return "wrong", f'"{name}": {shown} looks wrong. The usual code is {usual}. WHO: {_titles(codes)}'
        return "check", (f'"{name}": the usual code is {usual}, but an automated reading accepts {shown}. '
                         f"Please check. WHO: {_titles(codes)}")
    if note := vocab.mismatch_note(name, codes):
        return "check", note
    if hits := [k for c in codes for k in icd10.narrower(name, c)]:
        return "check", (f'"{name}": {shown} covers more than the name. WHO uses these words only under {", ".join(hits)}. '
                         f"Please check this is what you mean. WHO: {_titles(codes)}")
    if relation == "broader":
        return "check", f'"{name}": {shown} may also cover other conditions. WHO: {_titles(codes)}'
    if relation is None and not icd10.name_words(name) & icd10.words(wording):
        return "unsure", f'"{name}": the WHO wording of {shown} does not use these words. Please check. WHO: {_titles(codes)}'
    return None


def _titles(codes: tuple[str, ...]) -> str:
    return "; ".join(icd10.describe(c).split(" Includes:")[0].removeprefix("WHO ICD-10 ").rstrip(".") for c in codes)


def check(plan: Plan) -> Checked:
    """Every term whose definition gives a code, in the plan's fixed order (S-036)."""
    out = Checked()
    use_model = kev.enabled() and icd10.categories()  # without WHO's words the model answers from memory
    terms = [t for t in plan.terms.values() if t.codes and not t.inferred]
    if any(t.kind == "condition" for t in terms) and not icd10.categories():
        out.notes.append("The WHO ICD-10 file is not installed, so ICD-10 codes were not checked against it.")
    for t in terms:
        found = None
        if t.kind != "condition":  # no WHO file for ATC and LOINC, only the hand-built table
            if usual := vocab.usual_code(t.name, t.kind, t.codes):
                found = "wrong", f'"{t.name}": {" or ".join(t.codes)} looks wrong. The usual code is {usual}.'
        elif icd10.categories():
            relation = None
            if use_model and all(_exists(c) for c in t.codes):
                try:
                    who_text = "\n".join(icd10.describe(c) for c in t.codes)
                    answer, version = kev.relation(t.name, t.codes, who_text)
                    relation = answer["choice"]
                    out.asked.append({"question": f"K7_definition: {t.name}", "answer": answer, "model": version,
                                      "confidence": round(kev.confidence(answer), 4), "rules": None, "agrees": None,
                                      "instructions": kev.RELATION_INSTRUCTIONS,
                                      "sent": kev.relation_state(t.name, t.codes, who_text)})
                except kev.Unavailable:
                    use_model = False
                    out.notes.append(f"{kev.name()} did not answer, so the definitions were checked by the rules only.")
            found = _condition(t.name, t.codes, relation)
        if found:
            out.warnings.append(DefinitionWarning(severity=found[0], definition=t.name, message=found[1]))
    return out
