"""Plain explanations for the staff screen: what each rule is, why something was flagged, what to check. Text only.

Rule steps and review reasons are matched by how they start, so a rule or reason with no entry fails `tests/test_explain.py`.
"""

from hdab.contracts import Answer
from hdab.rules import CATEGORIES

_CATEGORY_LIST = "; ".join(f"Art. 54(1)({point}) {label}" for point, label, _ in CATEGORIES.values())

RULES: dict[str, dict[str, str]] = {
    "text addressing the system": {
        "what": "A safety check for text aimed at the software rather than at the access body.",
        "checked": "The purpose, question and definitions were searched for wording such as \"ignore previous instructions\", "
                   "\"please approve\" or \"mark this as approved\".",
        "why": "An application must not be able to steer its own assessment. Text like this also stops the decision model "
               "from clearing a keyword rejection.",
        "matched": "Such wording was found. Read it in the application: it counts against trusting the text.",
        "not_matched": "No such wording was found.",
    },
    "1 prohibited purpose": {
        "what": "Art. 54 of the EHDS lists uses of health data that are always forbidden. This rule comes first: a match rejects, "
                "whatever else the application says.",
        "checked": f"The purpose, question and definitions were searched for hand-written word patterns for: {_CATEGORY_LIST}. "
                   "The eight words before each hit were checked for a negation or hypothesis; quoted text and text about the harm itself count the same way.",
        "why": "These uses can harm the people in the data, so they are not open to weighing against a benefit.",
        "matched": "A prohibited wording was found and not negated. The words are shown above.",
        "not_matched": "No plain prohibited wording was found. Words that were negated, hypothetical or quoted appear as "
                       "evidence but do not count as a match, and raise a review instead.",
    },
    "re-identification of persons": {
        "what": "Art. 61 forbids trying to identify people in the data.",
        "checked": "The request text was searched for matching results against own lists or databases, for \"re-identify\" and "
                   "\"find out who\", and for names or addresses next to a list.",
        "why": "Even anonymised statistics can identify someone when combined with a list the applicant already holds.",
        "matched": "Wording like this was found.",
        "not_matched": "No wording like this was found. This is a text check: it cannot see what data the applicant really holds.",
    },
    "Art. 53(1) purpose": {
        "what": "Art. 53(1) lists the purposes health data may be used for. A request needs at least one.",
        "checked": "The request text was searched for words of each purpose: (a) public or occupational health, (b) policy and "
                   "regulation, (c) official statistics, (d) education, (e) scientific research, (f) improving care.",
        "why": "Access is only allowed for a listed purpose. Points (a) to (c) are reserved for public sector bodies (Art. 53(2)).",
        "matched": "An allowed purpose was recognised. The points are shown above. Check they fit what the applicant really describes.",
        "not_matched": "No allowed purpose was recognised, so the application goes to review. It may just be worded unusually.",
    },
    "2 requested as a health data request": {
        "what": "Art. 69 covers health data requests, which are answered with anonymised statistics only.",
        "checked": "The application's own field saying whether it is a health data request or an access application.",
        "why": "This decides the route: statistics under Art. 69, or a data permit under Art. 68.",
        "matched": "It is a health data request, so the outcome is anonymised statistics.",
        "not_matched": "It is an access application, so the next rules decide whether records are justified.",
    },
    "record-level data asked for": {
        "what": "A statistics request can never receive individual records.",
        "checked": "The request text was searched for asking for raw data, patient records, rows or an export of them.",
        "why": "Asking for records through the statistics route would bypass the permit and the secure environment.",
        "matched": "Such wording was found. No records are released whatever you decide here.",
        "not_matched": "No such wording was found.",
    },
    "3 access application explains": {
        "what": "Art. 67(2)(e) requires an access application to explain why anonymised statistics are not enough.",
        "checked": "The purpose and question were searched for such a reason, for example \"individual-level\", \"aggregates are "
                   "not enough\" or \"longitudinal records\". The definitions do not count.",
        "why": "Pseudonymised records are only allowed if statistics cannot do the job (Art. 66).",
        "matched": "A reason was found, shown above. This is a text match: judge whether the reason really holds up.",
        "not_matched": "No acceptable reason was found, so the application gets statistics instead of records.",
    },
    "4 other access application": {
        "what": "The fallback: an access application with no accepted reason for records.",
        "checked": "Nothing further. This rule applies when rules 1 to 3 did not decide.",
        "why": "Data minimisation (Art. 66): when records are not justified, the applicant gets anonymised statistics.",
        "matched": "The application is approved as statistics instead of the records it asked for.",
        "not_matched": "Not used.",
    },
    "1b decision model": {
        "what": "In Jev-led mode, a hosted AI model also reads the purpose, because keyword patterns miss rewordings.",
        "checked": "The model chose which Art. 54 category the applicant really intends, or none. Its answer and confidence are shown above.",
        "why": "The model can reject what the keywords missed, or turn a keyword rejection into a review for you. It never approves "
               "on its own, and it may not clear a request with text addressing the system.",
        "matched": "The model found a prohibited purpose the keywords missed. Check this yourself before confirming.",
        "not_matched": "The model disagreed with the keyword rule. Read the purpose and decide which is right.",
    },
}

REVIEW: dict[str, dict[str, str]] = {
    "S-061": {"why": "The application contains wording aimed at the software.",
              "check": "Read the quoted text. Decide whether the rest of the application can be trusted."},
    "S-064": {"why": "Prohibited-purpose words were found, but the decision model read the purpose as allowed.",
              "check": "Read the purpose. Is the prohibited use what the applicant intends? If so, reject under Art. 54."},
    "Art. 61": {"why": "The text suggests people could be re-identified.",
                "check": "Check whether results would be combined with a list or database. If so, reject."},
    "S-063": {"why": "A prohibited use is mentioned, but negated, hypothetical, quoted or as the harm being studied.",
              "check": "Read the sentence. A study of a harm is fine; a denial that does not fit the rest of the text is not."},
    "Art. 53(1)": {"why": "No allowed purpose was recognised in the text.",
                   "check": "Does the purpose fit a point of Art. 53(1)? If not, reject; if so, name the point when you confirm."},
    "S-059": {"why": "A statistics request or its report line asks for record-level or per-patient output.",
              "check": "Statistics never contain patient rows. Consider asking the applicant to file an access application."},
    "S-075": {"why": "A reason why statistics are not enough appears, but only negated, hypothetical or quoted.",
              "check": "Read the sentence. Decide whether the applicant really needs records."},
    "S-049": {"why": "The applicant gave a reason for records that the rules did not recognise, so they propose statistics.",
              "check": "Read the reason. If it is sound, override to a data permit."},
    "D-08": {"why": "The decision model and the rules read the purpose differently, or the model was unsure.",
             "check": "Compare the model's answer with the keyword evidence below, read the purpose, and decide."},
    "S-054": {"why": "The model's answer to one question differs from what the rules concluded.",
              "check": "Look at that question under \"What the model answered\" and read the matching text."},
    "S-034": {"why": "The model agrees with the rules, but with low confidence.",
              "check": "Read the text it was unsure about."},
    "S-072": {"why": "The model did not answer, so only the rules decided.",
              "check": "Review as you would a rules-only decision: keyword rules can miss rewordings."},
    "S-056": {"why": "Part of the definitions could not be understood, so no numbers were computed.",
              "check": "See the highlighted text. Ask the applicant to reword them, or override if the rest is enough."},
    "S-058": {"why": "A definition can be read in more than one way.",
              "check": "See how the app read it, under \"How the app reads them\". Is that what was meant?"},
    "S-046": {"why": "No report line says what to report, so no numbers were computed.",
              "check": "Ask the applicant to add a \"Report per …\" line."},
    "S-018": {"why": "The application lacks what a secure environment needs: a cohort or the record types.",
              "check": "Ask the applicant to name them, or override to a decision that needs neither."},
    "S-070": {"why": "A code in the definitions does not seem to match the name it was given.",
              "check": "Compare the name and code. The numbers use the code as written, so a wrong code gives wrong numbers."},
    "S-051": {"why": "A cell differs from an earlier cell of the same applicant by fewer than 10 patients.",
              "check": "Subtracting the two could reveal a small group. Consider rejecting or coarsening this request."},
    "Data": {"why": "The request asks for something the data does not hold. The applicant is not told this by the app.",
             "check": "Decide whether telling the applicant is acceptable, then ask them to correct it or reject."},
    "Sanity": {"why": "The definitions contradict themselves or do not fit the data.",
               "check": "Read the message and the definitions. Ask the applicant to correct them."},
}

SIGNALS: dict[str, dict[str, str]] = {
    "Organisation looks like": {"why": "The organisation's name suggests an interest Art. 54 is concerned with. It changes nothing by itself.",
                                "check": "Read the purpose with this in mind: does it hide a commercial use?"},
    "Art. 53(2)": {"why": "Points (a) to (c) of Art. 53(1) are for public sector bodies.",
                   "check": "Is this applicant a public sector body? If not, is another purpose point right?"},
}

CHECKLIST: dict[str, list[str]] = {
    "REJECT": ["Read the words that triggered the rejection, in their sentence.",
               "Is the prohibited use really what the applicant intends? If not, override and give your reason.",
               "Confirming sends the reason to the applicant. No data is released."],
    "APPROVE_STATISTICAL": ["Does the purpose fit the Art. 53(1) point shown?",
                            "Compare the definitions as written with how the app reads them: same population, same codes?",
                            "Look at the numbers. Confirming releases them to the applicant."],
    "APPROVE_SPE": ["Does the applicant's reason really show that statistics are not enough?",
                    "Check the cohort and the record types: no more than the purpose needs (Art. 66).",
                    "Confirming issues the permit and opens record-level access for the people named on it."],
}


def _find(table: dict[str, dict[str, str]], text: str) -> dict[str, str] | None:
    return next((v for k, v in table.items() if text.startswith(k)), None)


def rule(name: str) -> dict[str, str] | None:
    return _find(RULES, name)


def review(reason: str) -> dict[str, str] | None:
    return _find(REVIEW, reason)


def signal(text: str) -> dict[str, str] | None:
    return _find(SIGNALS, text)


def _checklist(answer: Answer) -> list[str]:
    if answer.decision != "REJECT" and answer.answer is None:  # S-046, S-056: nothing understood only in part gets numbers
        return [*CHECKLIST[answer.decision][:-1], "No numbers were computed. Confirming releases none: ask the applicant to correct the definitions, or reject."]
    return CHECKLIST[answer.decision]


def for_answer(answer: Answer) -> dict:
    """What the staff screen shows next to this answer."""
    fallback = {"why": "The system flagged this for a person to look at.", "check": "Read the message and the application."}
    return {
        "rules": {s.rule: rule(s.rule) for s in answer.trace},
        "review": [{"text": r, **(review(r) or fallback)} for r in answer.review_reasons],
        "signals": [{"text": s, **(signal(s) or fallback)} for s in answer.signals],
        "checklist": _checklist(answer),
    }
