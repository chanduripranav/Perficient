from src.data import demo_records, query_records, save_contract, DB_PATH


def test_demo_contract_has_all_codes():
    df = demo_records()
    assert set(df["procedure_code"]) == {"73721", "70551", "74176"}
    assert df["is_demo"].all()


def test_positive_demo_query(tmp_path):
    db = tmp_path / "test.db"
    save_contract(demo_records(), db)
    rows = query_records("73721", live_only=False, db_path=db)
    assert len(rows) == 7
    assert (rows["price"] > 0).all()
