import json
import urllib.error
from email.message import Message
from unittest.mock import MagicMock, patch

from updater.download import temp_download_path
from updater.github import check_latest_release
from updater.version import is_newer, parse_version


def test_parse_version_com_prefixo_v():
    assert parse_version("v0.2.1") == (0, 2, 1)


def test_parse_version_sem_prefixo():
    assert parse_version("1.0.0") == (1, 0, 0)


def test_parse_version_com_prerelease():
    assert parse_version("v1.0.0-beta.1") == (1, 0, 0)


def test_parse_version_maior():
    assert parse_version("v0.10.0") > parse_version("v0.9.9")


def test_is_newer_true():
    assert is_newer("v0.2.2", "v0.2.1") is True


def test_is_newer_false_mesma_versao():
    assert is_newer("v0.2.1", "v0.2.1") is False


def test_is_newer_false_menor():
    assert is_newer("v0.1.0", "v0.2.1") is False


def test_check_latest_release_sem_token():
    result = check_latest_release("", "owner/repo")
    assert result is None


def test_check_latest_release_404():
    headers = Message()
    error = urllib.error.HTTPError(url="", code=404, msg="Not Found", hdrs=headers, fp=None)
    with patch("updater.github.urllib.request.urlopen", side_effect=error):
        result = check_latest_release("fake-token", "owner/repo")
    assert result is None


def test_check_latest_release_com_asset():
    fake_response = {
        "tag_name": "v0.3.0",
        "body": "Novidades",
        "assets": [
            {
                "name": "DracmaSort.exe",
                "browser_download_url": "https://example.com/DracmaSort.exe",
                "size": 1024000,
            }
        ],
    }
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(fake_response).encode()
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)

    with patch("updater.github.urllib.request.urlopen", return_value=mock_resp):
        result = check_latest_release("fake-token", "owner/repo")

    assert result is not None
    assert result.tag == "v0.3.0"
    assert result.asset_size == 1024000


def test_check_latest_release_sem_asset():
    fake_response = {
        "tag_name": "v0.3.0",
        "body": "Sem exe",
        "assets": [],
    }
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(fake_response).encode()
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)

    with patch("updater.github.urllib.request.urlopen", return_value=mock_resp):
        result = check_latest_release("fake-token", "owner/repo")

    assert result is None


def test_temp_download_path_formatacao():
    path = temp_download_path("v0.3.0", "DracmaSort.exe")
    assert "DracmaSort_v0.3.0.exe" in path.name
    assert path.parent.name == "Temp" or "temp" in str(path.parent).lower()
