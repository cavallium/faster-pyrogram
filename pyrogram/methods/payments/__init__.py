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

from .apply_gift_code import ApplyGiftCode
from .check_gift_code import CheckGiftCode
from .convert_star_gift import ConvertStarGift
from .get_payment_form import GetPaymentForm
from .get_star_gifts import GetStarGifts
from .get_user_star_gifts_count import GetUserStarGiftsCount
from .get_user_star_gifts import GetUserStarGifts
from .hide_star_gift import HideStarGift
from .send_payment_form import SendPaymentForm
from .send_star_gift import SendStarGift
from .show_star_gift import ShowStarGift

class Payments(
    ApplyGiftCode,
    CheckGiftCode,
    ConvertStarGift,
    GetPaymentForm,
    GetStarGifts,
    GetUserStarGiftsCount,
    GetUserStarGifts,
    HideStarGift,
    SendPaymentForm,
    SendStarGift,
    ShowStarGift
):
    pass
