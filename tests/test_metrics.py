from hdab.contracts import Answer
from hdab.data import load_expected
from hdab.metrics import articles_ok, leaks, numbers_ok


def test_expected_answers_pass_their_own_checks():
    for want in load_expected().values():
        assert articles_ok(want, want)
        assert numbers_ok(want.answer, want.answer)
        assert leaks(want) == []


def test_articles_allow_67_and_71_only():
    want = Answer(decision="APPROVE_SPE", articles=["53", "66", "68", "73"], reason="")
    assert articles_ok(want.model_copy(update={"articles": ["53", "66", "67", "68", "71", "73"]}), want)
    assert not articles_ok(want.model_copy(update={"articles": ["53", "66", "68", "73", "54"]}), want)


def test_numbers_layout_free_but_values_must_match():
    want = {"Wien": {"n": 14, "mean": 26.6}, "Tirol": 28}
    assert numbers_ok({"Wien": {"a": 26.6, "b": 14}, "Tirol": {"stays": 28}}, want)
    assert not numbers_ok({"Wien": {"n": 14, "mean": 26.7}, "Tirol": 28}, want)
    assert not numbers_ok({"Wien": {"n": 14, "mean": 26.6}}, want)
    assert not numbers_ok(None, want)


def test_leaks_found():
    bad = Answer(decision="APPROVE_STATISTICAL", articles=[], reason="",
                 answer={"Wien": {"n": "<10", "mean": 25.1}, "Tirol": {"n": 7}, "x": "p-1eb050e7"})
    assert len(leaks(bad)) == 3
