from src.ai import extract_intent


def test_knee_mri_maps_to_cpt():
    assert extract_intent("What is the knee MRI without contrast?").code == "73721"


def test_ambiguous_mri_requires_clarification():
    intent = extract_intent("How much is an MRI?")
    assert intent.ambiguous


def test_c_section_unsupported():
    assert extract_intent("How much is a C-section?").intent == "unsupported"


def test_out_of_pocket_safe_limit():
    assert extract_intent("What will I have to pay?").intent == "benefit"


def test_comparison_uses_context(tmp_path):
    from src.data import demo_records, save_contract
    from src.engine import resolve
    db = tmp_path / "t.db"
    save_contract(demo_records(), db)
    r = resolve("Which is cheapest?", last_code="73721", db_path=db)
    assert r.code == "73721" and r.records.iloc[0]["hospital_name"] in r.text


def test_all_acceptance_tests_pass(tmp_path):
    from src.data import demo_records, save_contract
    from src.engine import run_acceptance
    db = tmp_path / "t.db"
    save_contract(demo_records(), db)
    assert all(r["passed"] for r in run_acceptance(db_path=db))


def test_replies_have_no_asterisks_or_em_dashes():
    from src.ai import clean_stream, format_answer
    import pandas as pd
    s = "The **lowest** rate — at Methodist — is $350*. Range $350–$560."
    for out in ("".join(clean_stream([s[i:i + 3] for i in range(0, len(s), 3)])),
                format_answer("How much is an MRI?", pd.DataFrame())):
        assert "*" not in out and "—" not in out and "–" not in out
    assert "$350 to $560" in "".join(clean_stream([s]))
