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
- The possibility of turning off journaling and vacuum when starting a session.
- The possibility of turning off the fetch of pinned message on arrival of the service message.
- Improved implementation of rle_encode.
- Implementation of _parse_channel_chat without getattr.
- Cache of FileId and UniqueFileId instances and of their string-coded versions.
- Use of tcp abridged instead of tcp obfuscated as the default protocol.
- The possibility of turning off the fetch of set_name on arrival of a new sticker.
