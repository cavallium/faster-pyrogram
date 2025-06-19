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

from typing import List, Optional

import pyrogram
from pyrogram import raw, types

from ..object import Object


class FormattedText(Object):
    """Contains information about a text with some entities.

    Parameters:
        text (``str``):
            The text.

        entities (List of :obj:`~pyrogram.types.MessageEntity`):
            Entities contained in the text. Entities can be nested, but must not mutually intersect with each other.
    """

    def __init__(
        self,
        *,
        text: str,
        entities: Optional[List["types.MessageEntity"]] = None,
    ):
        super().__init__()

        self.text = text
        self.entities = entities

    @staticmethod
    def _parse(client: "pyrogram.Client", text: "raw.types.TextWithEntities") -> "FormattedText":
        entities = types.List(
            filter(
                lambda x: x is not None,
                [types.MessageEntity._parse(client, entity, {}) for entity in text.entities]
            )
        )

        return FormattedText(
            text=text.text,
            entities=entities or None,
        )
