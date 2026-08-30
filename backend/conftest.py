import pytest


@pytest.fixture(autouse=True)
def reset_lightrag_pool():
    """每个测试前重置 LightRAGClient 连接池，防止跨测试状态污染。"""
    from app.services.lightrag_client import LightRAGClient
    LightRAGClient._entries.clear()
    LightRAGClient._shared_client = None
    yield
    LightRAGClient._entries.clear()
    LightRAGClient._shared_client = None


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: requires external services (skipped by default)")


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--run-integration", default=False):
        skip = pytest.mark.skip(reason="integration test — pass --run-integration to run")
        for item in items:
            if item.get_closest_marker("integration"):
                item.add_marker(skip)


def pytest_addoption(parser):
    parser.addoption("--run-integration", action="store_true", default=False)
