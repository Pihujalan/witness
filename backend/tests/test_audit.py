from app.audit import AuditLog


def _log(tmp_path, name):
    return AuditLog(database_url=f"sqlite:///{tmp_path}/{name}.db")


def test_chain_starts_valid(tmp_path):
    log = _log(tmp_path, "t1")
    log.append({"a": 1})
    log.append({"a": 2})
    valid, broken = log.verify_chain()
    assert valid
    assert broken is None


def test_tampering_is_detected(tmp_path):
    log = _log(tmp_path, "t2")
    log.append({"a": 1})
    log.append({"a": 2})
    log.append({"a": 3})
    log.tamper_for_demo(1, {"a": "tampered"})
    valid, broken = log.verify_chain()
    assert not valid
    assert broken == 1


def test_persists_across_instances(tmp_path):
    db_url = f"sqlite:///{tmp_path}/t3.db"
    log1 = AuditLog(database_url=db_url)
    log1.append({"x": 1})
    log2 = AuditLog(database_url=db_url)
    assert len(log2.all_entries()) == 1
    valid, _ = log2.verify_chain()
    assert valid
