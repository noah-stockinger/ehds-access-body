from hdab.redteam import run


def test_s060_redteam_no_silent_wrong_approval_no_wrong_numbers():
    rows = run()
    assert len(rows) >= 20
    assert [r["name"] for r in rows if r["silent_wrong_approval"] or r["wrong_numbers"]] == []
    assert [r["name"] for r in rows if not r["ok"]] == []
