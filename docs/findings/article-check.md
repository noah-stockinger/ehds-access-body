# Finding: the "unverified" articles of SPECS.md, checked by hand (30 Oct 2026)

Analysis note, not binding (rules: `SPECS.md`). Goal: an estimate of whether the five articles SPECS.md marks
**unverified** (61, 66, 69, 71, 73) say what our reasons and views claim.

**How:** EUR-Lex (and lawplayer.com) are blocked by this session's network policy, so the Official Journal text could
not be read directly. Checked instead through web search snippets of the regulation text and of secondary sources
(TEHDAS draft guidelines, EC FAQ, law-firm memos, streamlex.eu). So: an estimate, not a legal check. Before quoting an
article to a real applicant, read <https://eur-lex.europa.eu/eli/reg/2025/327/oj/eng> itself.

| Art. | What we claim | What the sources say | Verdict |
|---|---|---|---|
| 69 | Health data request: answers only in anonymised statistical form; legal basis of the small-cell rule | Applicant can ask for an answer in anonymised statistical format; the access body produces it and the user never handles personal data; evaluation within 3 months | **Confirmed.** But the `<10` threshold and rounding are the *challenge's* rule, not in Art. 69; say "anonymised statistics (Art. 69)", not "small-cell rule (Art. 69)" |
| 66 | Data minimisation; anonymised by default, pseudonymised only with a justification | Access body provides anonymised data where the purpose can be met with it; pseudonymised only where the user shows anonymised data cannot achieve the purpose; re-identification keys stay with the access body or a trusted third party | **Confirmed.** One source ties the justification test to Art. 68(1)(c); our reason cites **Art. 67(2)(e)** for it, which is still unchecked |
| 71 | Opt-out: data of persons who objected is excluded everywhere | Opt-out at any time, without a reason, reversible; does not affect permits granted before; Member States may make exceptions for important public-interest research (71(4)) | **Confirmed**, with nuances we do not model: exceptions under 71(4), and no effect on earlier permits. Excluding everywhere is the challenge's rule and the safe reading |
| 73 | SPE: only authorised persons, every access logged, only anonymised results may be downloaded | Access only through an SPE; only persons named in the permit; minimise unauthorised reading/copying/removal; logs kept ≥ 1 year; users may download only non-personal data, incl. anonymised statistics, **after review by the access body** (73(2)) | **Confirmed.** The law has a reviewed export path; we refuse every download, which is stricter and stays inside it |
| 61 | Duties: no re-identification, publish results within 18 months, credit the EHDS | Re-identification and attempts are prohibited; processing only under a permit or approved request; results published within 18 months, anonymised, crediting the EHDS (TEHDAS draft); significant health findings about a person must be reported to the access body (61(5)) | **Confirmed** (publication and credit via a draft guideline only). Missing from our duties text: the 61(5) duty to report significant findings |

**Estimate:** all five say, in substance, what the app claims; none changes a decision, article set or number. Two
wording fixes are worth making: don't call the `<10` rule an Art. 69 rule, and check whether the SPE justification
belongs to Art. 67(2)(e) or Art. 68(1)(c). Optional: add the Art. 61(5) duty to `spe.DUTIES`.

Sources: [EUR-Lex OJ L 2025/327](https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=OJ:L_202500327) (search
snippets only), [streamlex.eu Art. 69](https://streamlex.eu/articles/ehds-en-art-69/),
[Art. 71](https://streamlex.eu/articles/ehds-en-art-71/), [Art. 73](https://streamlex.eu/articles/ehds-en-art-73/),
[lawplayer Art. 61](https://lawplayer.com/eu/article/32025R0327/art_61),
[TEHDAS draft guideline on minimisation and pseudonymisation](https://tehdas.eu/wp-content/uploads/2025/09/draft-guideline-on-data-minimisation-pseudonymisation-anonymisation-and-synthetic-data.pdf),
[TEHDAS draft guideline on opt-out](https://tehdas.eu/wp-content/uploads/2025/09/draft-guideline-to-health-data-access-bodies-how-to-implement-opt-out-from-secondary-use-of-electronic-health-data.pdf),
[EC EHDS FAQ](https://health.ec.europa.eu/document/download/4dd47ec2-71dd-49fc-b036-ad7c14f6ed68_en?filename=ehealth_ehds_qa_en.pdf).

## Follow-up (30 Oct, M-23)
- **`<10` and Art. 69:** the app's own texts never call the small-cell rule an Art. 69 rule; only the legal-basis table
  in `SPECS.md` does ("Legal basis of the small-cell rule"). `SPECS.md` changes go via `master`, so this is a proposed
  wording for the team: "Art. 69 requires anonymised statistics; the `<10` threshold and rounding are the challenge's
  rule for achieving that."
- **Art. 67(2)(e) vs. 68(1)(c):** both apply, to different actors. Art. 67 lists what the applicant must write
  (point (e): why anonymised data is not enough; "67(2)(e)" comes from the team's extract of the regulation text, while
  secondary sources disagree on the paragraph number). Art. 68(1)(c) is the access body's check that the justification
  is sufficient, and Art. 66 grants pseudonymised access "in accordance with Article 68(1), point (c)". The SPE
  reason now cites both. The paragraph number of Art. 67 is still to be read in the Official Journal.
- **Art. 61(5):** added to the duties of SPE users and to the permit's conditions of use; not to statistical answers,
  which cannot show anything about one person.

Source for the follow-up: [streamlex.eu Art. 67](https://streamlex.eu/articles/ehds-en-art-67/),
[TEHDAS draft guideline on access procedures](https://tehdas.eu/wp-content/uploads/2025/09/draft-guideline-for-health-data-access-bodies-on-the-procedures-and-formats-for-data-access.pdf).
