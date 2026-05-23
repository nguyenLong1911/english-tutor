"""Pytest configuration and fixtures for tests."""
import pytest
import asyncio
import sys
import warnings


# Suppress the Redis event loop closed warning during tests
warnings.filterwarnings("ignore", message=".*Event loop is closed.*")


def pytest_configure(config):
    """Configure pytest markers and options."""
    config.addinivalue_line(
        "markers", "asyncio: mark test as async"
    )
    # Set event loop policy for Windows
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

