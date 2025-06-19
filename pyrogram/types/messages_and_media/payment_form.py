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

from typing import Optional

import pyrogram
from pyrogram import enums, raw, types

from ..object import Object


class PaymentForm(Object):
    """Contains information about an invoice payment form.

    Parameters:
        id (``int``):
            Form id.

        type (:obj:`~pyrogram.enums.PaymentFormType`):
            Type of the payment form.

        title (``str``, *optional*):
            Form title.

        description (``str``, *optional*):
            Form description.

        photo (:obj:`~pyrogram.types.Photo`, *optional*):
            Product photo.

        seller_bot_user_id (``int``, *optional*):
            User identifier of the seller bot.

        seller_bot (:obj:`~pyrogram.types.User`, *optional*):
            Information about the seller bot.

        payment_provider_user_id (``int``, *optional*):
            User identifier of the payment provider bot.

        payment_provider (:obj:`~pyrogram.types.User`, *optional*):
            Information about the payment provider.

        invoice (``str``, *optional*):
            Invoice.

        url (``str``, *optional*):
            Payment form URL.

        can_save_credentials (``str``, *optional*):
            True, if the user can choose to save credentials.

        need_password (``str``, *optional*):
            True, if the user will be able to save credentials, if sets up a 2-step verification password.

        native_provider (``str``, *optional*):
            Payment provider name.

        raw (:obj:`~raw.base.payments.PaymentForm`, *optional*):
            The raw object, as received from the Telegram API.
    """

    def __init__(
        self,
        *,
        client: "pyrogram.Client" = None,
        id: int,
        type: "enums.PaymentFormType",
        title: Optional[str] = None,
        description: Optional[str] = None,
        photo: Optional["types.Photo"] = None,
        seller_bot_user_id: Optional[int] = None,
        seller_bot: Optional["types.User"] = None,
        payment_provider_user_id: Optional[int] = None,
        payment_provider: Optional["types.User"] = None,
        invoice: Optional["types.Invoice"] = None,
        url: Optional[str] = None,
        can_save_credentials: Optional[bool] = None,
        need_password: Optional[bool] = None,
        native_provider: Optional[str] = None,
        raw: "raw.base.payments.PaymentForm" = None,
    ):
        super().__init__(client)

        self.id = id
        self.type = type
        self.seller_bot_user_id = seller_bot_user_id
        self.seller_bot = seller_bot
        self.payment_provider_user_id = payment_provider_user_id
        self.payment_provider = payment_provider
        self.title = title
        self.description = description
        self.photo = photo
        self.invoice = invoice
        self.url = url
        self.can_save_credentials = can_save_credentials
        self.need_password = need_password
        self.native_provider = native_provider
        self.raw = raw

    @staticmethod
    def _parse(client, form: "raw.base.payments.PaymentForm") -> "PaymentForm":
        users = {i.id: i for i in getattr(form, "users", [])}

        if isinstance(form, raw.types.payments.PaymentForm):
            return PaymentForm(
                id=form.form_id,
                type=enums.PaymentFormType.REGULAR,
                title=form.title,
                description=form.description,
                photo=types.Photo._parse(client, form.photo),
                seller_bot_user_id=form.bot_id,
                seller_bot=types.User._parse(client, users.get(form.bot_id)),
                payment_provider_user_id=form.provider_id,
                payment_provider=types.User._parse(client, users.get(form.provider_id)),
                invoice=types.Invoice._parse(client, form.invoice),
                url=form.url,
                can_save_credentials=form.can_save_credentials,
                need_password=form.password_missing,
                native_provider=form.native_provider,
                # native_params,
                # additional_methods,
                # saved_info,
                # saved_credentials,
                raw=form
            )
        elif isinstance(form, raw.types.payments.PaymentFormStarGift):
            return PaymentForm(
                id=form.form_id,
                type=enums.PaymentFormType.STAR_SUBSCRIPTION,
                invoice=types.Invoice._parse(client, form.invoice),
                raw=form
            )
        elif isinstance(form, raw.types.payments.PaymentFormStars):
            return PaymentForm(
                id=form.form_id,
                type=enums.PaymentFormType.STARS,
                title=form.title,
                description=form.description,
                photo=types.Photo._parse(client, form.photo),
                seller_bot_user_id=form.bot_id,
                seller_bot=types.User._parse(client, users.get(form.bot_id)),
                invoice=types.Invoice._parse(client, form.invoice),
                raw=form
            )
