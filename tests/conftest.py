import pytest


@pytest.fixture(autouse=True)
def fresh_var(tmp_path, monkeypatch):
    """Every test gets its own empty register and SPE folder."""
    from hdab import data, register, rstudio, spe

    for module in (data, register, spe):
        monkeypatch.setattr(module, "VAR_DIR", tmp_path, raising=False)
    monkeypatch.setattr(rstudio, "_docker", lambda *args, check=True: "")  # never touch a real RStudio session
