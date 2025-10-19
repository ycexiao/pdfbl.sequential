"""Unit tests for __version__.py."""

import pdfbl.sequential  # noqa


def test_package_version():
    """Ensure the package version is defined and not set to the initial
    placeholder."""
    assert hasattr(pdfbl.sequential, "__version__")
    assert pdfbl.sequential.__version__ != "0.0.0"
