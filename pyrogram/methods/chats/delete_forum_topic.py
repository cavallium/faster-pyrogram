#  Pyrogram - Telegram MTProto API Client Library for Python
#  Copyright (C) 2017-present Dan <https://github.com/delivrance>
#
#  This file is part of Pyrogram.
#
#  Pyrogram is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Lesser General Public License as published
#  by the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  Pyrogram is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public License
#  along with Pyrogram.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import annotations as _annotations

import pyrogram
from pyrogram import raw


class DeleteForumTopic:
    async def delete_forum_topic(
        self: pyrogram.Client, chat_id: int | str, message_thread_id: int
    ) -> bool:
        """Use this method to delete a forum topic along with all its messages in a forum supergroup chat or a private chat with a user.
        In the case of a supergroup chat the bot must be an administrator in the chat for this to work and must have the `can_delete_messages` administrator rights.

        .. include:: /_includes/usable-by/users-bots.rst

        Parameters:
            chat_id (``int`` | ``str``):
                Unique identifier (int) or username (str) of the target chat.

            message_thread_id (``int``):
                Unique identifier for the target message thread of the forum topic.

        Returns:
            ``bool``: On success, True is returned.

        Example:
            .. code-block:: python

                await app.delete_forum_topic(chat_id, message_thread_id)
        """
        r = await self.invoke(
            raw.functions.messages.DeleteTopicHistory(
                peer=await self.resolve_peer(chat_id), top_msg_id=message_thread_id
            )
        )

        return bool(r)
