"""人工配置夹具：仅描述测试协议，不代表历史运行或真实模型评测证据。"""


def source_config(profile='capacity'):
    config = {
        'core_sha256': 'fa538db8dd1afcea01817e590ae893c59e0ff85f19e90e263dbe24c3dcc226de',
        'recall_mode': 'sources', 'retain_sources': True, 'source_strategy': 'focused_window',
        'k': 30, 'max_context_bytes': 8000, 'http_budget': 1314,
        'answer_policy': 'grounded_v1', 'answer_max_tokens': 1024,
        'judge_max_tokens': 64, 'extract_max_tokens': 4096,
        'extract_model': 'qwen3.8-27b', 'answer_model': 'qwen3.8-27b',
        'embedding_model': 'text-embedding-v4', 'embedding_dim': 1024,
        'embedding_max_batch_inputs': 10, 'answer_key_env': 'DASHSCOPE_API_KEY',
        'extract_endpoint': 'http://127.0.0.1:1/v1', 'answer_endpoint': 'http://127.0.0.1:1/v1',
        'embedding_endpoint': 'http://127.0.0.1:1/v1',
        'extract_enable_thinking': False, 'answer_enable_thinking': False,
        'judge_enable_thinking': None, 'max_retries': 0, 'timeout_ms': 120000,
        'include_unknown_time': False, 'lifecycle': 'immediate',
        'created_at': '2026-06-01T00:00:00Z', 'query_time': '2026-12-08T00:00:00Z',
    }
    profiles = {
        'capacity': {},
        'grounded': {'answer_max_tokens': 512},
        'focus': {'core_sha256': '3b3ee4ab11ac278761b0a55db9ae079f3770c1fa279346dc0607b32282339f63',
                  'answer_policy': 'legacy', 'answer_max_tokens': 512},
        'baseline': {'core_sha256': '6f5dcfac904a77d5402c1f59fecb6b67e00a0d169d1c0ccfba681be0e73dad6f',
                     'k': 10, 'http_budget': 1848, 'source_strategy': 'bm25',
                     'answer_policy': 'legacy', 'answer_max_tokens': 512},
        'source_full': {'core_sha256': '89f08596f37a1511b499a591b9612a204d4fef5b39e1e743d0548625f24db923',
                        'k': 10, 'http_budget': 1848, 'source_strategy': 'bm25',
                        'answer_policy': 'legacy', 'answer_max_tokens': 512},
        'k30': {'core_sha256': '6f5dcfac904a77d5402c1f59fecb6b67e00a0d169d1c0ccfba681be0e73dad6f',
                'source_strategy': 'bm25', 'answer_policy': 'legacy', 'answer_max_tokens': 512},
        'dialogue': {'core_sha256': '280bf95bd2fbb186f35b4630993e5590249d67810946802ed1adf62ed669f22f',
                     'source_strategy': 'focused_dialogue', 'k': 60, 'max_context_bytes': 16000,
                     'source_seed_k': 30, 'source_seed_max_context_bytes': 8000, 'source_dialogue_radius': 2},
    }
    config.update(profiles[profile])
    return config
