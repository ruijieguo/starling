"""样例经真实核心写入后应有可用的人物图，且不得把项目注册为人物。"""
from contextlib import closing
import sqlite3
import subprocess
import sys
from pathlib import Path


def test_demo_creates_people_and_relations_without_entity_cognizers(tmp_path):
    root = Path(__file__).resolve().parents[2]
    db = tmp_path / 'demo.db'
    result = subprocess.run([sys.executable, str(root / 'scripts/seed_demo.py'), '--db', str(db)],
                            cwd=root, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    with closing(sqlite3.connect(db)) as conn:
        names = {row[0] for row in conn.execute('SELECT canonical_name FROM cognizers')}
        assert {'Sam', 'Alice', 'Bob', 'Carol', 'Dana', 'Eve', 'Frank', 'Grace'} <= names
        assert not {'the launch', 'the new service'} & names
        assert conn.execute('SELECT COUNT(*) FROM cognizer_relations').fetchone()[0] == 6
        assert conn.execute('SELECT COUNT(*) FROM statements').fetchone()[0] >= 26
        assert conn.execute('SELECT COUNT(*) FROM statement_vectors').fetchone()[0] >= 26
        assert dict(conn.execute('SELECT state, COUNT(*) FROM commitments GROUP BY state')) == {
            'ACTIVE': 2, 'BROKEN': 1, 'FULFILLED': 1, 'WITHDRAWN': 1}
        assert conn.execute("SELECT COUNT(*) FROM statements WHERE provenance='consolidation_abstract'").fetchone()[0] == 2
