import pytest

from src.magic_index.embed import embed_all_bibles, get_client


@pytest.fixture(scope="session")
def indexed_client(tmp_path_factory):
    persist_dir = tmp_path_factory.mktemp("chroma_session")
    client = get_client(persist_dir)
    embed_all_bibles(client=client)
    return client
