"""Tests for actionable errors from the firmware update entity."""

import pytest

from custom_components.aquarea.update import (
    _firmware_http_error,
    _firmware_upload_error,
)


@pytest.mark.parametrize(
    ("status", "reason"),
    [(401, "Unauthorized"), (403, "Forbidden")],
)
def test_auth_failure_explains_web_update_password(status, reason):
    error = _firmware_upload_error(status, reason, "", "4.3.1")

    assert f"HTTP {status} {reason}" in str(error)
    assert "does not send web/update credentials" in str(error)
    assert "HeishaMon web UI" in str(error)


def test_other_upload_failure_reports_http_status():
    error = _firmware_http_error("upload", 500, "Internal Server Error", "4.3.1")

    assert "HTTP 500 Internal Server Error" in str(error)
    assert "version 4.3.1" in str(error)
    assert "web/update credentials" not in str(error)


def test_firmware_reported_failure_is_detected_even_with_http_200():
    error = _firmware_upload_error(
        200,
        "OK",
        "Update failed! Please try again... ERROR[12]: MD5 Failed",
        "4.3.1",
    )

    assert error is not None
    assert "Update failed" in str(error)
    assert "MD5 Failed" in str(error)


def test_successful_http_200_is_not_an_error():
    assert (
        _firmware_upload_error(
            200, "OK", "Update success! Rebooting.", "4.3.1"
        )
        is None
    )
