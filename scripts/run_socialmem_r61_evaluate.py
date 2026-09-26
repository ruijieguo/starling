#!/usr/bin/env python3
"""R6.1 检索与fresh QA入口：复用完整评测引擎，保留旧版身份。"""
from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


engine = load(ROOT / 'scripts/run_socialmem_r59_evaluate.py', 'r61_evaluation_engine')
engine.builder = load(ROOT / 'scripts/run_socialmem_r61_expanded.py', 'r61_evaluation_builder').engine
engine.CORE_SHA256 = engine.builder.CORE_SHA256
engine.SEAL_SCHEMA = 'r61-evaluation-seal-v1'
engine.IDENTITY_SCHEMA = 'r61-evaluation-identity-v1'
engine.FAILURE_SCHEMA = 'r61-evaluation-failure-v1'
engine.OWN_FILES = (*engine.OWN_FILES, 'scripts/run_socialmem_r61_evaluate.py', 'tests/python/test_socialmem_r61_evaluate.py')
engine.previous, engine.baseline = engine.builder.previous, engine.builder.baseline
engine.qa_helpers, engine.ablation = engine.previous.qa_helpers, engine.previous.ablation
engine.read, engine.write, engine.sha, engine.inventory = engine.builder.read, engine.builder.write, engine.builder.sha, engine.builder.inventory
engine.query_one, engine.run_task = engine.ablation.query_one, engine.qa_helpers.run_task


if __name__ == '__main__':
    raise SystemExit(engine.main())
