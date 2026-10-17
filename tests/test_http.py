import http.client
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit

import pytest

from localcast.http_server import MediaServer


@pytest.fixture
def server():
    instance = MediaServer("127.0.0.1", 0)
    yield instance
    instance.close()


def request(server, path, method="GET", headers=None):
    client = http.client.HTTPConnection("127.0.0.1", server.port, timeout=5)
    try:
        client.request(method, path, headers=headers or {})
        response = client.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        client.close()


@pytest.mark.parametrize(
    "range_value,code,body,content_range",
    [
        (None, 200, b"0123456789", None),
        ("bytes=2-5", 206, b"2345", "bytes 2-5/10"),
        ("bytes=7-", 206, b"789", "bytes 7-9/10"),
        ("bytes=-4", 206, b"6789", "bytes 6-9/10"),
        ("bytes=0-999", 206, b"0123456789", "bytes 0-9/10"),
        ("bytes=-999", 206, b"0123456789", "bytes 0-9/10"),
        ("bytes=10-", 416, b"", "bytes */10"),
        ("bytes=5-2", 416, b"", "bytes */10"),
        ("bytes=-0", 416, b"", "bytes */10"),
        ("bytes=0-1,3-4", 416, b"", "bytes */10"),
        ("nonsense", 416, b"", "bytes */10"),
    ],
)
def test_real_http_ranges(server, media_info, range_value, code, body, content_range):
    token = server.register_file(media_info.path)
    headers = {"Range": range_value} if range_value else {}
    status, response, result = request(server, f"/{token}/media.mp4", headers=headers)
    assert (status, result) == (code, body)
    assert response.get("Content-Range") == content_range
    assert int(response["Content-Length"]) == len(body)
    assert response["Access-Control-Allow-Origin"] == "*"


def test_head_options_and_revocation(server, media_info):
    token = server.register_file(media_info.path)
    path = urlsplit(server.url(token, "127.0.0.1")).path
    status, headers, body = request(server, path, "HEAD", {"Range": "bytes=1-2"})
    assert status == 206 and headers["Content-Length"] == "2" and not body
    assert request(server, path, "OPTIONS")[0] == 204
    assert server.stats(token)["head_ok"] == 1
    server.unregister(token)
    assert request(server, path)[0] == 404


def test_hls_types_and_traversal(server, tmp_path):
    (tmp_path / "master.m3u8").write_text("#EXTM3U\nstream.m3u8\n")
    (tmp_path / "segment_000000.ts").write_bytes(b"ts")
    (tmp_path / "segment_000001.ts.tmp").write_bytes(b"partial")
    (tmp_path / "private.txt").write_text("secret")
    token = server.register_hls(tmp_path)
    assert (
        request(server, f"/{token}/master.m3u8")[1]["Content-Type"]
        == "application/vnd.apple.mpegurl"
    )
    assert request(server, f"/{token}/segment_000000.ts")[1]["Content-Type"] == "video/mp2t"
    for name in (
        "../private.txt",
        "%2e%2e/private.txt",
        "private.txt",
        "segment_000001.ts.tmp",
        "",
        "sub/master.m3u8",
    ):
        assert request(server, f"/{token}/{name}")[0] == 404


def test_concurrent_requests_and_empty_file(server, tmp_path):
    path = tmp_path / "media.mp4"
    path.write_bytes(bytes(range(256)) * 5000)
    token = server.register_file(path)
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [
            pool.submit(
                request,
                server,
                f"/{token}/media.mp4",
                headers={"Range": f"bytes={i * 256}-{i * 256 + 255}"},
            )
            for i in range(8)
        ]
        for future in futures:
            code, _, body = future.result()
            assert code == 206 and body == bytes(range(256))
    path.write_bytes(b"")
    assert request(server, f"/{token}/media.mp4")[2] == b""
    assert request(server, f"/{token}/media.mp4", headers={"Range": "bytes=0-"})[0] == 416


@pytest.mark.parametrize('data,mime', [(b'\xff\xd8\xffposter', 'image/jpeg'),
                                      (b'\x89PNG\r\n\x1a\nposter', 'image/png')])
def test_cover_bytes_transport_and_revocation(server, data, mime):
    token = server.register_image(data)
    path = f'/{token}/cover'
    status, headers, body = request(server, path)
    assert status == 200 and body == data and headers['Content-Type'] == mime
    assert headers['Access-Control-Allow-Origin'] == '*'
    assert request(server, path, 'HEAD')[2] == b''
    assert request(server, path, headers={'Range': 'bytes=0-2'})[2] == data[:3]
    assert request(server, f'/{token}/other')[0] == 404
    server.unregister(token)
    assert request(server, path)[0] == 404
    for invalid in (b'', b'<html>error</html>', b'\xff\xd8\xff' + b'x' * (6 * 1024 * 1024)):
        with pytest.raises(ValueError):
            server.register_image(invalid)
