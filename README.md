<p align="center">
    <a href="https://github.com/pyrogram/pyrogram">
        <img src="https://docs.pyrogram.org/_static/pyrogram.png" alt="Pyrogram" width="128">
    </a>
    <br>
    <b>Telegram MTProto API Framework for Python</b>
    <br>
</p>

## WARNING
We've made faster-pyrogram publicly available in order to facilitate conversation about potentially upstreaming some of this work to Pyrogram and to reduce duplication of effort among people working on Pyrogram performance.

faster-pyrogram is not polished or documented for anyone else's use. We don't have the capacity to support faster-pyrogram as an independent open-source project, nor any desire for it to become an alternative to Pyrogram. Our goal in making this code available is a unified faster Pyrogram. So while we do run faster-pyrogram in production, if you choose to do so you are on your own. We can't commit to fixing external bug reports or reviewing pull requests. We make sure faster-pyrogram is sufficiently stable and fast for our production workload, but we make no assurances about its stability or correctness or performance for any other workload or use.

### CHANGES STILL TO BE MERGED IN THE UPSTREAM
- Lock-free and asynchronous implementation of the sqlite session.
- SQLite sessions use WAL by default; a custom `SQLiteStorage(use_wal=False, ...)` can select rollback journaling.
- The possibility of turning off the fetch of pinned message on arrival of the service message.
- Improved implementation of rle_encode.
- Implementation of _parse_channel_chat without getattr.
- Per-instance caching of encoded FileId and FileUniqueId values.
- Use of tcp abridged instead of tcp obfuscated as the default protocol.
- Sticker-set name fetching is disabled by default; enable it with `fetch_stickers=True`.

## Upstream

Synchronized with [Kurigram](https://github.com/KurimuzonAkuma/pyrogram) main at `d4d069817a51bf8543b5083e525dd83acfca20da` (2026-10-14). Python 3.10 or newer is required.
