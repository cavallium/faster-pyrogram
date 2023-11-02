<p align="center">
    <a href="https://github.com/pyrogram/pyrogram">
        <img src="https://docs.pyrogram.org/_static/pyrogram.png" alt="Pyrogram" width="128">
    </a>
    <br>
    <b>Telegram MTProto API Framework for Python</b>
    <br>
    <a href="https://pyrogram.org">
        Homepage
    </a>
    •
    <a href="https://docs.pyrogram.org">
        Documentation
    </a>
    •
    <a href="https://docs.pyrogram.org/releases">
        Releases
    </a>
    •
    <a href="https://t.me/pyrogram">
        News
    </a>
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

app = Client("my_account")


@app.on_message(filters.private)
async def hello(client, message):
    await message.reply("Hello from Pyrogram!")


app.run()
```

**Pyrogram** is a modern, elegant and asynchronous [MTProto API](https://docs.pyrogram.org/topics/mtproto-vs-botapi)
framework. It enables you to easily interact with the main Telegram API through a user account (custom client) or a bot
identity (bot API alternative) using Python.

### Support

If you'd like to support Pyrogram, you can consider:

- [Become a GitHub sponsor](https://github.com/sponsors/delivrance).
- [Become a LiberaPay patron](https://liberapay.com/delivrance).
- [Become an OpenCollective backer](https://opencollective.com/pyrogram).

### Key Features

- **Ready**: Install Pyrogram with pip and start building your applications right away.
- **Easy**: Makes the Telegram API simple and intuitive, while still allowing advanced usages.
- **Elegant**: Low-level details are abstracted and re-presented in a more convenient way.
- **Fast**: Boosted up by [TgCrypto](https://github.com/pyrogram/tgcrypto), a high-performance cryptography library written in C.  
- **Type-hinted**: Types and methods are all type-hinted, enabling excellent editor support.
- **Async**: Fully asynchronous (also usable synchronously if wanted, for convenience).
- **Powerful**: Full access to Telegram's API to execute any official client action and more.

### Installing

``` bash
pip3 install pyrogram
```

### Resources

- Check out the docs at https://docs.pyrogram.org to learn more about Pyrogram, get started right
away and discover more in-depth material for building your client applications.
- Join the official channel at https://t.me/pyrogram and stay tuned for news, updates and announcements.
