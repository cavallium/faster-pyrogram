"""CDN redirects use an independent, unauthenticated session on the redirect's DC."""

from __future__ import annotations as _annotations

import asyncio
from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, call

import pytest

from pyrogram import Client, raw
from pyrogram.crypto import aes
from pyrogram.errors import CDNFileHashMismatch
from pyrogram.file_id import FileId, FileType


class SessionClient:
    get_session = Client.get_session

    def __init__(self):
        self.storage = SimpleNamespace(
            dc_id=AsyncMock(return_value=2),
            auth_key=AsyncMock(return_value=b"user-key"),
            test_mode=AsyncMock(return_value=False),
        )
        self.session = SimpleNamespace(auth_key=b"primary-key")
        self.sessions = {}
        self.media_sessions = {}
        self.ipv6 = False
        self.invoke = AsyncMock(return_value=SimpleNamespace(id=7, bytes=b"user-authorization"))
        self.get_dc_option = AsyncMock(
            return_value=SimpleNamespace(ip_address="cdn.example", port=443)
        )


@pytest.fixture
def session_factories(monkeypatch):
    auth = Mock(return_value=SimpleNamespace(create=AsyncMock(return_value=b"cdn-key")))
    session = Mock(
        side_effect=lambda *args, **kwargs: SimpleNamespace(
            auth_key=args[4], start=AsyncMock(), stop=AsyncMock(), invoke=AsyncMock()
        )
    )
    monkeypatch.setattr("pyrogram.client.Auth", auth)
    monkeypatch.setattr("pyrogram.client.Session", session)
    return auth, session


@pytest.mark.parametrize("dc_id", [2, 4])
@pytest.mark.parametrize("is_media", [False, True])
async def test_cdn_session_has_its_own_key_mode_and_cache(session_factories, dc_id, is_media):
    client = SessionClient()
    regular = SimpleNamespace(auth_key=b"regular-key")
    cache = client.media_sessions if is_media else client.sessions
    cache[dc_id] = regular
    auth, session_factory = session_factories

    cdn = await client.get_session(dc_id, is_media=is_media, is_cdn=True)

    assert cdn is not regular and cdn is not client.session
    assert cdn.auth_key == b"cdn-key"
    auth.assert_called_once_with(client, dc_id, "cdn.example", 443, False)
    client.storage.auth_key.assert_not_awaited()
    client.invoke.assert_not_awaited()
    cdn.invoke.assert_not_awaited()
    cdn.start.assert_awaited_once()
    assert session_factory.call_args.kwargs == {"is_media": is_media, "is_cdn": True}
    client.get_dc_option.assert_awaited_once_with(dc_id, is_media=is_media, ipv6=False, is_cdn=True)
    assert cache[dc_id] is regular
    assert await client.get_session(dc_id, is_media=is_media, is_cdn=True) is cdn
    assert (
        await client.get_session(dc_id, is_media=is_media, is_cdn=True, temporary=True) is not cdn
    )
    assert session_factory.call_count == 2
    assert client.invoke.await_count == 0


async def test_regular_primary_and_cached_sessions_are_preserved(session_factories):
    client = SessionClient()
    media = SimpleNamespace(auth_key=b"media-key")
    remote = SimpleNamespace(auth_key=b"remote-key")
    client.media_sessions[2] = media
    client.sessions[4] = remote

    assert await client.get_session(2) is client.session
    assert await client.get_session(2, is_media=True) is media
    assert await client.get_session(4) is remote
    session_factories[0].assert_not_called()
    session_factories[1].assert_not_called()


async def test_regular_remote_session_still_imports_user_authorization(session_factories):
    client = SessionClient()
    session = await client.get_session(4)

    client.invoke.assert_awaited_once()
    assert isinstance(client.invoke.call_args.args[0], raw.functions.auth.ExportAuthorization)
    assert client.invoke.call_args.args[0].dc_id == 4
    session.invoke.assert_awaited_once()
    imported = session.invoke.call_args.args[0]
    assert isinstance(imported, raw.functions.auth.ImportAuthorization)
    assert imported.id == 7 and imported.bytes == b"user-authorization"
    assert session_factories[1].call_args.kwargs == {"is_media": False, "is_cdn": False}


@pytest.mark.parametrize("phase", ["start", "export", "import"])
@pytest.mark.parametrize("error_type", [RuntimeError, asyncio.CancelledError])
async def test_session_setup_failure_is_stopped_and_can_be_retried(
    session_factories, phase, error_type
):
    client = SessionClient()
    _, session_factory = session_factories
    failed = SimpleNamespace(start=AsyncMock(), stop=AsyncMock(), invoke=AsyncMock())
    ready = SimpleNamespace(start=AsyncMock(), stop=AsyncMock(), invoke=AsyncMock())
    session_factory.side_effect = [failed, ready]

    async def fail(*args, **kwargs):
        assert 4 not in client.sessions
        raise error_type("session setup interrupted")

    if phase == "export":
        client.invoke.side_effect = fail
    else:
        getattr(failed, "start" if phase == "start" else "invoke").side_effect = fail

    with pytest.raises(error_type, match="session setup interrupted"):
        await client.get_session(4)

    assert 4 not in client.sessions
    failed.stop.assert_awaited_once()
    client.invoke.side_effect = None

    async def check_unpublished(*args, **kwargs):
        assert 4 not in client.sessions

    ready.start.side_effect = check_unpublished
    ready.invoke.side_effect = check_unpublished
    assert await client.get_session(4) is ready
    ready.start.assert_awaited_once()
    ready.invoke.assert_awaited_once()
    ready.stop.assert_not_awaited()
    assert client.sessions[4] is ready
    assert await client.get_session(4) is ready
    assert session_factory.call_count == 2


async def test_failed_media_setup_keeps_the_ready_authorization_session(session_factories):
    client = SessionClient()
    _, session_factory = session_factories
    regular = SimpleNamespace(
        auth_key=b"regular-key", start=AsyncMock(), stop=AsyncMock(), invoke=AsyncMock()
    )
    failed_media = SimpleNamespace(
        start=AsyncMock(side_effect=RuntimeError("media startup failed")), stop=AsyncMock()
    )
    ready_media = SimpleNamespace(start=AsyncMock(), stop=AsyncMock(), invoke=AsyncMock())
    session_factory.side_effect = [regular, failed_media, ready_media]

    with pytest.raises(RuntimeError, match="media startup failed"):
        await client.get_session(4, is_media=True)

    assert client.sessions[4] is regular
    assert 4 not in client.media_sessions
    failed_media.stop.assert_awaited_once()
    regular.stop.assert_not_awaited()
    assert await client.get_session(4, is_media=True) is ready_media
    assert client.media_sessions[4] is ready_media
    regular.start.assert_awaited_once()
    assert session_factory.call_args_list[1].args[4] == b"regular-key"
    assert session_factory.call_args_list[2].args[4] == b"regular-key"


@pytest.mark.parametrize("valid_hash", [True, False])
async def test_cdn_redirect_download_uses_redirect_dc_and_closes_session(valid_hash):
    payload = b"a CDN download"
    key, iv = bytes(32), bytes(16)
    redirect = raw.types.upload.FileCdnRedirect(
        dc_id=4,
        file_token=b"token",
        encryption_key=key,
        encryption_iv=iv,
        file_hashes=[],
    )
    media = SimpleNamespace(
        invoke=AsyncMock(
            side_effect=[
                redirect,
                [],  # ReuploadCdnFile response, followed by a retried CDN request.
                [
                    raw.types.FileHash(
                        offset=0,
                        limit=len(payload),
                        hash=sha256(payload if valid_hash else b"corrupted").digest(),
                    )
                ],
            ]
        )
    )
    cdn = SimpleNamespace(
        invoke=AsyncMock(
            side_effect=[
                raw.types.upload.CdnFileReuploadNeeded(request_token=b"reupload"),
                raw.types.upload.CdnFile(bytes=aes.ctr256_encrypt(payload, key, bytearray(iv))),
            ]
        ),
        stop=AsyncMock(),
    )
    client = SimpleNamespace(
        get_file_semaphore=asyncio.Semaphore(1),
        executor=None,
        get_session=AsyncMock(side_effect=[media, cdn]),
    )
    file_id = FileId(
        file_type=FileType.DOCUMENT, dc_id=2, media_id=1, access_hash=1, file_reference=b"ref"
    )

    if valid_hash:
        assert [chunk async for chunk in Client.get_file(client, file_id)] == [payload]
    else:
        with pytest.raises(CDNFileHashMismatch):
            _ = [chunk async for chunk in Client.get_file(client, file_id)]
    assert client.get_session.await_args_list == [
        call(2, is_media=True),
        call(4, is_media=True, is_cdn=True, temporary=True),
    ]
    reupload = media.invoke.await_args_list[1].args[0]
    assert isinstance(reupload, raw.functions.upload.ReuploadCdnFile)
    assert reupload.file_token == b"token" and reupload.request_token == b"reupload"
    hashes = media.invoke.await_args_list[2].args[0]
    assert isinstance(hashes, raw.functions.upload.GetCdnFileHashes)
    assert cdn.invoke.await_count == 2
    cdn.stop.assert_awaited_once()
