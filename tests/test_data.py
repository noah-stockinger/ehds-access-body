from hdab.data import DATA_DIR, load_expected, load_requests


def test_all_requests_parse():
    assert [r.id for r in load_requests()] == [f"R{i:02d}" for i in range(1, 11)]


def test_expected_parses_and_covers_requests():
    expected = load_expected()
    assert set(expected) == {r.id for r in load_requests()}
    assert sum(a.decision != "REJECT" for a in expected.values()) == 6


def test_csvs_present():
    for name in ["patients", "conditions", "medications", "observations", "encounters"]:
        assert (DATA_DIR / f"{name}.csv").is_file()
