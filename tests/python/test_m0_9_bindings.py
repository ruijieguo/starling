from starling import _core


def test_classes_exist():
    for n in ["EmbeddingAdapter", "StubEmbeddingAdapter", "SqliteBlobVectorIndex",
              "EmbeddingWorker", "SemanticRetriever", "SemanticRetrieverParams"]:
        assert hasattr(_core, n), n


def test_construct_stub_and_index():
    assert _core.StubEmbeddingAdapter(8) is not None
    assert _core.SqliteBlobVectorIndex() is not None
