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

import logging
from datetime import datetime
from functools import partial
from typing import BinaryIO, Callable, Dict, List, Match, Optional, Union

import pyrogram
from pyrogram import enums, raw, types, utils
from pyrogram.errors import ChannelForumMissing, ChannelPrivate, MessageIdsEmpty, PeerIdInvalid, ChatAdminRequired
from pyrogram.parser import Parser
from pyrogram.parser import utils as parser_utils

from ..object import Object
from ..update import Update

log = logging.getLogger(__name__)


class Str(str):
    def __init__(self, *args):
        super().__init__()

        self.entities: Optional[List["types.MessageEntity"]] = None

    def init(self, entities: list):
        self.entities = entities

        return self

    @property
    def markdown(self) -> str:
        return Parser.unparse(self, self.entities, False)

    @property
    def html(self) -> str:
        return Parser.unparse(self, self.entities, True)

    def __getitem__(self, item) -> str:
        return parser_utils.remove_surrogates(parser_utils.add_surrogates(self)[item])


class Message(Object, Update):
    """A message.

    Parameters:
        id (``int``):
            Unique message identifier inside this chat.

        from_user (:obj:`~pyrogram.types.User`, *optional*):
            Sender, empty for messages sent to channels.

        sender_chat (:obj:`~pyrogram.types.Chat`, *optional*):
            Sender of the message, sent on behalf of a chat.
            The channel itself for channel messages.
            The supergroup itself for messages from anonymous group administrators.
            The linked channel for messages automatically forwarded to the discussion group.

        sender_boost_count (``int``, *optional*):
            If the sender of the message boosted the chat, the number of boosts added by the user.

        sender_business_bot (:obj:`~pyrogram.types.User`, *optional*):
            The bot that actually sent the message on behalf of the business account. Available only for outgoing messages sent on behalf of the connected business account.

        date (:py:obj:`~datetime.datetime`, *optional*):
            Date the message was sent.

        chat (:obj:`~pyrogram.types.Chat`, *optional*):
            Conversation the message belongs to.

        topic_message (``bool``, *optional*):
            True, if the message is a forum topic message.

        automatic_forward (``bool``, *optional*):
            True, if the message is a channel post that was automatically forwarded to the connected discussion group.

        from_offline (``bool``, *optional*):
            True, if the message was sent by an implicit action, for example, as an away or a greeting business message, or as a scheduled message.

        topic (:obj:`~pyrogram.types.ForumTopic`, *optional*):
            Topic the message belongs to.

        forward_origin (:obj:`~pyrogram.types.MessageOrigin`, *optional*):
            Information about the original message for forwarded messages.

        message_thread_id (``int``, *optional*):
            Unique identifier of a message thread to which the message belongs.
            For forums only.

        direct_messages_chat_topic_id (``int``, *optional*):
            Unique identifier of a topic in a channel direct messages chat administered by the current user.
            For direct chats only.

        effect_id (``int``, *optional*):
            Unique identifier of the message effect.
            For private chats only.

        reply_to_message_id (``int``, *optional*):
            The id of the message which this message directly replied to.

        reply_to_story_id (``int``, *optional*):
            The id of the story which this message directly replied to.

        reply_to_story_user_id (``int``, *optional*):
            The id of the story sender which this message directly replied to.

        reply_to_top_message_id (``int``, *optional*):
            The id of the first message which started this message thread.

        reply_to_message (:obj:`~pyrogram.types.Message`, *optional*):
            For replies, the original message. Note that the Message object in this field will not contain
            further reply_to_message fields even if it itself is a reply.

        reply_to_story (:obj:`~pyrogram.types.Story`, *optional*):
            For replies, the original story.

        mentioned (``bool``, *optional*):
            The message contains a mention.

        empty (``bool``, *optional*):
            The message is empty.
            A message can be empty in case it was deleted or you tried to retrieve a message that doesn't exist yet.

        service (:obj:`~pyrogram.enums.MessageServiceType`, *optional*):
            The message is a service message.
            This field will contain the enumeration type of the service message.
            You can use ``service = getattr(message, message.service.value)`` to access the service message.

        media (:obj:`~pyrogram.enums.MessageMediaType`, *optional*):
            The message is a media message.
            This field will contain the enumeration type of the media message.
            You can use ``media = getattr(message, message.media.value)`` to access the media message.

        paid_media (:obj:`~pyrogram.types.PaidMediaInfo`, *optional*):
            The message is a paid media message.

        checklist (:obj:`~pyrogram.types.Checklist`, *optional*):
            The message is a checklist message.

        show_caption_above_media (``bool``, *optional*):
            If True, caption must be shown above the message media.

        edit_date (:py:obj:`~datetime.datetime`, *optional*):
            Date the message was last edited.

        edit_hidden (``bool``, *optional*):
            The message shown as not modified.
            A message can be not modified in case it has received a reaction.

        media_group_id (``int``, *optional*):
            The unique identifier of a media message group this message belongs to.

        author_signature (``str``, *optional*):
            Signature of the post author for messages in channels, or the custom title of an anonymous group
            administrator.

        has_protected_content (``bool``, *optional*):
            True, if the message can't be forwarded.

        has_media_spoiler (``bool``, *optional*):
            True, if the message media is covered by a spoiler animation.

        text (``str``, *optional*):
            For text messages, the actual UTF-8 text of the message, 0-4096 characters.
            If the message contains entities (bold, italic, ...) you can access *text.markdown* or
            *text.html* to get the marked up message text. In case there is no entity, the fields
            will contain the same text as *text*.

        entities (List of :obj:`~pyrogram.types.MessageEntity`, *optional*):
            For text messages, special entities like usernames, URLs, bot commands, etc. that appear in the text.

        caption_entities (List of :obj:`~pyrogram.types.MessageEntity`, *optional*):
            For messages with a caption, special entities like usernames, URLs, bot commands, etc. that appear
            in the caption.

        audio (:obj:`~pyrogram.types.Audio`, *optional*):
            Message is an audio file, information about the file.

        document (:obj:`~pyrogram.types.Document`, *optional*):
            Message is a general file, information about the file.

        photo (:obj:`~pyrogram.types.Photo`, *optional*):
            Message is a photo, information about the photo.

        sticker (:obj:`~pyrogram.types.Sticker`, *optional*):
            Message is a sticker, information about the sticker.

        animation (:obj:`~pyrogram.types.Animation`, *optional*):
            Message is an animation, information about the animation.

        game (:obj:`~pyrogram.types.Game`, *optional*):
            Message is a game, information about the game.

        giveaway (:obj:`~pyrogram.types.Giveaway`, *optional*):
            Message is a giveaway, information about the giveaway.

        invoice (:obj:`~pyrogram.types.Invoice`, *optional*):
            Message is a invoice, information about the invoice.
            `More about payments » <https://core.telegram.org/bots/api#payments>`_

        story (:obj:`~pyrogram.types.Story`, *optional*):
            Message is a story, information about the story.

        video (:obj:`~pyrogram.types.Video`, *optional*):
            Message is a video, information about the video.

        video_processing_pending (``bool``, *optional*):
            True, if the video is still processing.

        voice (:obj:`~pyrogram.types.Voice`, *optional*):
            Message is a voice message, information about the file.

        video_note (:obj:`~pyrogram.types.VideoNote`, *optional*):
            Message is a video note, information about the video message.

        caption (``str``, *optional*):
            Caption for the audio, document, photo, video or voice, 0-1024 characters.
            If the message contains caption entities (bold, italic, ...) you can access *caption.markdown* or
            *caption.html* to get the marked up caption text. In case there is no caption entity, the fields
            will contain the same text as *caption*.

        contact (:obj:`~pyrogram.types.Contact`, *optional*):
            Message is a shared contact, information about the contact.

        location (:obj:`~pyrogram.types.Location`, *optional*):
            Message is a shared location, information about the location.

        venue (:obj:`~pyrogram.types.Venue`, *optional*):
            Message is a venue, information about the venue.

        web_page (:obj:`~pyrogram.types.WebPage`, *optional*):
            Message was sent with a webpage preview.

        link_preview_options (:obj:`~pyrogram.types.LinkPreviewOptions`, *optional*):
            Options used for link preview generation for the message.

        poll (:obj:`~pyrogram.types.Poll`, *optional*):
            Message is a native poll, information about the poll.

        dice (:obj:`~pyrogram.types.Dice`, *optional*):
            A dice containing a value that is randomly generated by Telegram.

        new_chat_members (List of :obj:`~pyrogram.types.User`, *optional*):
            New members that were added to the group or supergroup and information about them
            (the bot itself may be one of these members).

        left_chat_member (:obj:`~pyrogram.types.User`, *optional*):
            A member was removed from the group, information about them (this member may be the bot itself).

        chat_join_type (:obj:`~pyrogram.enums.ChatJoinType`, *optional*):
            This field will contain the enumeration type of how the user had joined the chat.

        new_chat_title (``str``, *optional*):
            A chat title was changed to this value.

        new_chat_photo (:obj:`~pyrogram.types.Photo`, *optional*):
            A chat photo was change to this value.

        delete_chat_photo (``bool``, *optional*):
            Service message: the chat photo was deleted.

        group_chat_created (``bool``, *optional*):
            Service message: the group has been created.

        supergroup_chat_created (``bool``, *optional*):
            Service message: the supergroup has been created.
            This field can't be received in a message coming through updates, because bot can't be a member of a
            supergroup when it is created. It can only be found in reply_to_message if someone replies to a very
            first message in a directly created supergroup.

        channel_chat_created (``bool``, *optional*):
            Service message: the channel has been created.
            This field can't be received in a message coming through updates, because bot can't be a member of a
            channel when it is created. It can only be found in reply_to_message if someone replies to a very
            first message in a channel.

        migrate_to_chat_id (``int``, *optional*):
            The group has been migrated to a supergroup with the specified identifier.
            This number may be greater than 32 bits and some programming languages may have difficulty/silent defects
            in interpreting it. But it is smaller than 52 bits, so a signed 64 bit integer or double-precision float
            type are safe for storing this identifier.

        migrate_from_chat_id (``int``, *optional*):
            The supergroup has been migrated from a group with the specified identifier.
            This number may be greater than 32 bits and some programming languages may have difficulty/silent defects
            in interpreting it. But it is smaller than 52 bits, so a signed 64 bit integer or double-precision float
            type are safe for storing this identifier.

        pinned_message (:obj:`~pyrogram.types.Message`, *optional*):
            Specified message was pinned.
            Note that the Message object in this field will not contain further reply_to_message fields even if it
            is itself a reply.

        game_high_score (:obj:`~pyrogram.types.GameHighScore`, *optional*):
            The game score for a user.
            The reply_to_message field will contain the game Message.

        views (``int``, *optional*):
            Channel post views.

        forwards (``int``, *optional*):
            Channel post forwards.

        via_bot (:obj:`~pyrogram.types.User`):
            The information of the bot that generated the message from an inline query of a user.

        outgoing (``bool``, *optional*):
            Whether the message is incoming or outgoing.
            Messages received from other chats are incoming (*outgoing* is False).
            Messages sent from yourself to other chats are outgoing (*outgoing* is True).
            An exception is made for your own personal chat; messages sent there will be incoming.

        external_reply (:obj:`~pyrogram.types.ExternalReplyInfo`, *optional*):
            Information about the message that is being replied to, which may come from another chat or forum topic.

        quote (:obj:`~pyrogram.types.TextQuote`, *optional*):
            Chosen quote from the replied message.

        matches (List of regex Matches, *optional*):
            A list containing all `Match Objects <https://docs.python.org/3/library/re.html#match-objects>`_ that match
            the text of this message. Only applicable when using :obj:`Filters.regex <pyrogram.Filters.regex>`.

        command (List of ``str``, *optional*):
            A list containing the command and its arguments, if any.
            E.g.: "/start 1 2 3" would produce ["start", "1", "2", "3"].
            Only applicable when using :obj:`~pyrogram.filters.command`.

        forum_topic_created (:obj:`~pyrogram.types.ForumTopicCreated`, *optional*):
            Service message: forum topic created

        forum_topic_closed (:obj:`~pyrogram.types.ForumTopicClosed`, *optional*):
            Service message: forum topic closed

        forum_topic_reopened (:obj:`~pyrogram.types.ForumTopicReopened`, *optional*):
            Service message: forum topic reopened

        forum_topic_edited (:obj:`~pyrogram.types.ForumTopicEdited`, *optional*):
            Service message: forum topic edited

        general_forum_topic_hidden (:obj:`~pyrogram.types.GeneralForumTopicHidden`, *optional*):
            Service message: general forum topic hidden

        general_forum_topic_unhidden (:obj:`~pyrogram.types.GeneralForumTopicUnhidden`, *optional*):
            Service message: general forum topic unhidden

        video_chat_scheduled (:obj:`~pyrogram.types.VideoChatScheduled`, *optional*):
            Service message: voice chat scheduled.

        history_cleared (:obj:`~pyrogram.types.HistoryCleared`, *optional*):
            Service message: history cleared

        video_chat_started (:obj:`~pyrogram.types.VideoChatStarted`, *optional*):
            Service message: the voice chat started.

        video_chat_ended (:obj:`~pyrogram.types.VideoChatEnded`, *optional*):
            Service message: the voice chat has ended.

        video_chat_members_invited (:obj:`~pyrogram.types.VoiceChatParticipantsInvited`, *optional*):
            Service message: new members were invited to the voice chat.

        phone_call_started (:obj:`~pyrogram.types.PhoneCallStarted`, *optional*):
            Service message: phone call started.

        phone_call_ended (:obj:`~pyrogram.types.PhoneCallEnded`, *optional*):
            Service message: phone call ended.

        web_app_data (:obj:`~pyrogram.types.WebAppData`, *optional*):
            Service message: web app data sent to the bot.

        paid_messages_refunded (:obj:`~pyrogram.types.PaidMessagesRefunded`, *optional*):
            Service message: paid messages refunded.

        paid_messages_price_changed (:obj:`~pyrogram.types.PaidMessagesPriceChanged`, *optional*):
            Service message: paid messages price.

        direct_message_price_changed (:obj:`~pyrogram.types.DirectMessagePriceChanged`, *optional*):
            Service message: direct messages price.

        checklist_tasks_done (:obj:`~pyrogram.types.ChecklistTasksDone`, *optional*):
            Service message: checklist tasks done.

        checklist_tasks_added (:obj:`~pyrogram.types.ChecklistTasksAdded`, *optional*):
            Service message: checklist tasks added.

        gift_code (:obj:`~pyrogram.types.GiftCode`, *optional*):
            Service message: gift code information.

        gifted_premium (:obj:`~pyrogram.types.GiftedPremium`, *optional*):
            Service message: gifted premium information.

        gifted_stars (:obj:`~pyrogram.types.GiftedStars`, *optional*):
            Service message: gifted stars information.

        gift (:obj:`~pyrogram.types.Gift`, *optional*):
            Service message: star gift information.

        suggest_profile_photo (:obj:`~pyrogram.types.Photo`, *optional*):
            Service message: suggested profile photo.

        users_shared (:obj:`~pyrogram.types.UsersShared`, *optional*):
            Service message: users shared information.

        chat_shared (:obj:`~pyrogram.types.ChatShared`, *optional*):
            Service message: chat shared information.

        successful_payment (:obj:`~pyrogram.types.SuccessfulPayment`, *optional*):
            Service message: successful payment.

        refunded_payment (:obj:`~pyrogram.types.RefundedPayment`, *optional*):
            Service message: refunded payment.

        giveaway_created (``bool``, *optional*):
            Service message: giveaway launched.

        giveaway_winners (:obj:`~pyrogram.types.GiveawayWinners`, *optional*):
            A giveaway with public winners was completed.

        giveaway_completed (:obj:`~pyrogram.types.GiveawayCompleted`, *optional*):
            Service message: a giveaway without public winners was completed.

        chat_set_theme (:obj:`~pyrogram.types.ChatTheme`, *optional*):
            Service message: The chat theme was changed.

        chat_set_background (:obj:`~pyrogram.types.ChatBackground`, *optional*):
            Service message: The chat background was changed.

        set_message_auto_delete_time (``int``, *optional*):
            Service message: The auto-delete or self-destruct timer for messages in the chat has been changed.

        chat_boost (``int``, *optional*):
            Service message: The chat was boosted by the sender of the message.
            Number of times the chat was boosted.

        write_access_allowed (:obj:`~pyrogram.types.WriteAccessAllowed`, *optional*):
            Service message: the user allowed the bot to write messages after adding it to the attachment or side menu, launching a Web App from a link, or accepting an explicit request from a Web App sent by the method `requestWriteAccess <https://core.telegram.org/bots/webapps#initializing-mini-apps>`__

        connected_website (``str``, *optional*):
            The domain name of the website on which the user has logged in. `More about Telegram Login <https://core.telegram.org/widgets/login>`__

        contact_registered (:obj:`~pyrogram.types.ContactRegistered`, *optional*):
            Service message: Contact registered in Telegram.

        proximity_alert_triggered (:obj:`~pyrogram.types.ProximityAlertTriggered`, *optional*):
            Service message: A user in the chat came within proximity alert range.

        giveaway_prize_stars (:obj:`~pyrogram.types.GiveawayPrizeStars`, *optional*):
            Service message: Stars were received by the current user from a giveaway.

        screenshot_taken (:obj:`~pyrogram.types.ScreenshotTaken`, *optional*):
            Service message: screenshot of a message in the chat has been taken.

        business_connection_id (``str``, *optional*):
            Unique identifier of the business connection from which the message was received.
            If non-empty, the message belongs to a chat of the corresponding business account that is independent from any potential bot chat which might share the same identifier.
            This update may at times be triggered by unavailable changes to message fields that are either unavailable or not actively used by the current bot.

        reply_markup (:obj:`~pyrogram.types.InlineKeyboardMarkup` | :obj:`~pyrogram.types.ReplyKeyboardMarkup` | :obj:`~pyrogram.types.ReplyKeyboardRemove` | :obj:`~pyrogram.types.ForceReply`, *optional*):
            Additional interface options. An object for an inline keyboard, custom reply keyboard,
            instructions to remove reply keyboard or to force a reply from the user.

        reactions (:obj:`~pyrogram.types.MessageReactions`):
            Reactions of this message.

        send_paid_messages_stars (``int``, *optional*):
            The number of Telegram Stars the sender paid to send the message.

        raw (:obj:`~pyrogram.raw.types.Message`, *optional*):
            The raw message object, as received from the Telegram API.

        link (``str``, *property*):
            Generate a link to this message, only for groups and channels.

        content (``str``, *property*):
            The text or caption content of the message.

        unread_media (``bool``, *optional*):
            True, if there are unread media attachments in this message.

        silent (``bool``, *optional*):
            True, if the message sent without notification.

        legacy (``bool``, *optional*):
            True, if the message is a legacy message.
            This means that the message is based on the old layer and should be refetched with the new layer.

        pinned (``bool``, *optional*):
            True, if the message is pinned.

        restriction_reason (List of :obj:`~pyrogram.types.RestrictionReason`, *optional*):
            Contains a list of human-readable description of the reason why access to this message must be restricted.

        fact_check (:obj:`~pyrogram.types.FactCheck`, *optional*):
            Information about fact-check added to the message.

        channel_post (``bool``, *optional*):
            True, if the message is a channel post.
    """
    def __init__(
        self,
        *,
        client: "pyrogram.Client" = None,
        id: int,
        from_user: Optional["types.User"] = None,
        sender_chat: Optional["types.Chat"] = None,
        sender_boost_count: Optional[int] = None,
        sender_business_bot: Optional["types.User"] = None,
        date: Optional[datetime] = None,
        chat: Optional["types.Chat"] = None,
        topic_message: Optional[bool] = None,
        automatic_forward: Optional[bool] = None,
        from_offline: Optional[bool] = None,
        show_caption_above_media: Optional[bool] = None,
        external_reply: Optional["types.ExternalReplyInfo"] = None,
        quote: Optional["types.TextQuote"] = None,
        topic: Optional["types.ForumTopic"] = None,
        forward_origin: Optional["types.MessageOrigin"] = None,
        message_thread_id: Optional[int] = None,
        direct_messages_chat_topic_id: Optional[int] = None,
        effect_id: Optional[int] = None,
        reply_to_message_id: Optional[int] = None,
        reply_to_story_id: Optional[int] = None,
        reply_to_story_user_id: Optional[int] = None,
        reply_to_top_message_id: Optional[int] = None,
        reply_to_message: Optional["Message"] = None,
        reply_to_story: Optional["types.Story"] = None,
        mentioned: Optional[bool] = None,
        empty: Optional[bool] = None,
        service: Optional["enums.MessageServiceType"] = None,
        scheduled: Optional[bool] = None,
        from_scheduled: Optional[bool] = None,
        media: Optional["enums.MessageMediaType"] = None,
        paid_media: Optional["types.PaidMediaInfo"] = None,
        checklist: Optional["types.Checklist"] = None,
        edit_date: Optional[datetime] = None,
        edit_hidden: Optional[bool] = None,
        media_group_id: Optional[int] = None,
        author_signature: Optional[str] = None,
        has_protected_content: Optional[bool] = None,
        has_media_spoiler: Optional[bool] = None,
        text: Optional[Str] = None,
        entities: Optional[List["types.MessageEntity"]] = None,
        caption_entities: Optional[List["types.MessageEntity"]] = None,
        audio: Optional["types.Audio"] = None,
        document: Optional["types.Document"] = None,
        photo: Optional["types.Photo"] = None,
        sticker: Optional["types.Sticker"] = None,
        animation: Optional["types.Animation"] = None,
        game: Optional["types.Game"] = None,
        giveaway: Optional["types.Giveaway"] = None,
        giveaway_winners: Optional["types.GiveawayWinners"] = None,
        giveaway_completed: Optional["types.GiveawayCompleted"] = None,
        invoice: Optional["types.Invoice"] = None,
        story: Optional["types.Story"] = None,
        video: Optional["types.Video"] = None,
        video_processing_pending: Optional[bool] = None,
        voice: Optional["types.Voice"] = None,
        video_note: Optional["types.VideoNote"] = None,
        caption: Optional[Str] = None,
        contact: Optional["types.Contact"] = None,
        location: Optional["types.Location"] = None,
        venue: Optional["types.Venue"] = None,
        web_page: Optional["types.WebPage"] = None,
        link_preview_options: Optional["types.LinkPreviewOptions"] = None,
        poll: Optional["types.Poll"] = None,
        dice: Optional["types.Dice"] = None,
        new_chat_members: Optional[List["types.User"]] = None,
        left_chat_member: Optional["types.User"] = None,
        chat_join_type: Optional["enums.ChatJoinType"] = None,
        new_chat_title: Optional[str] = None,
        new_chat_photo: Optional["types.Photo"] = None,
        delete_chat_photo: Optional[bool] = None,
        group_chat_created: Optional[bool] = None,
        supergroup_chat_created: Optional[bool] = None,
        channel_chat_created: Optional[bool] = None,
        migrate_to_chat_id: Optional[int] = None,
        migrate_from_chat_id: Optional[int] = None,
        pinned_message: Optional["Message"] = None,
        game_high_score: Optional[int] = None,
        views: Optional[int] = None,
        forwards: Optional[int] = None,
        via_bot: Optional["types.User"] = None,
        outgoing: Optional[bool] = None,
        matches: Optional[List[Match]] = None,
        command: Optional[List[str]] = None,
        forum_topic_created: Optional["types.ForumTopicCreated"] = None,
        forum_topic_closed: Optional["types.ForumTopicClosed"] = None,
        forum_topic_reopened: Optional["types.ForumTopicReopened"] = None,
        forum_topic_edited: Optional["types.ForumTopicEdited"] = None,
        general_forum_topic_hidden: Optional["types.GeneralForumTopicHidden"] = None,
        general_forum_topic_unhidden: Optional["types.GeneralForumTopicUnhidden"] = None,
        video_chat_scheduled: Optional["types.VideoChatScheduled"] = None,
        history_cleared: Optional["types.HistoryCleared"] = None,
        video_chat_started: Optional["types.VideoChatStarted"] = None,
        video_chat_ended: Optional["types.VideoChatEnded"] = None,
        video_chat_members_invited: Optional["types.VideoChatMembersInvited"] = None,
        phone_call_started: Optional["types.PhoneCallStarted"] = None,
        phone_call_ended: Optional["types.PhoneCallEnded"] = None,
        web_app_data: Optional["types.WebAppData"] = None,
        paid_messages_refunded: Optional["types.PaidMessagesRefunded"] = None,
        paid_messages_price_changed: Optional["types.PaidMessagesPriceChanged"] = None,
        direct_message_price_changed: Optional["types.DirectMessagePriceChanged"] = None,
        checklist_tasks_done: Optional[List["types.ChecklistTasksDone"]] = None,
        checklist_tasks_added: Optional[List["types.ChecklistTasksAdded"]] = None,
        gift_code: Optional["types.GiftCode"] = None,
        gifted_premium: Optional["types.GiftedPremium"] = None,
        gifted_stars: Optional["types.GiftedStars"] = None,
        gift: Optional["types.Gift"] = None,
        suggest_profile_photo: Optional["types.Photo"] = None,
        users_shared: Optional["types.UsersShared"] = None,
        chat_shared: Optional["types.ChatShared"] = None,
        successful_payment: Optional["types.SuccessfulPayment"] = None,
        refunded_payment: Optional["types.RefundedPayment"] = None,
        giveaway_created: Optional[bool] = None,
        chat_set_theme: Optional["types.ChatTheme"] = None,
        chat_set_background: Optional["types.ChatBackground"] = None,
        set_message_auto_delete_time: Optional[int] = None,
        chat_boost: Optional[int] = None,
        write_access_allowed: Optional["types.WriteAccessAllowed"] = None,
        connected_website: Optional[str] = None,
        contact_registered: Optional["types.ContactRegistered"] = None,
        proximity_alert_triggered: Optional["types.ProximityAlertTriggered"] = None,
        giveaway_prize_stars: Optional["types.GiveawayPrizeStars"] = None,
        screenshot_taken: Optional["types.ScreenshotTaken"] = None,
        business_connection_id: Optional[str] = None,
        reply_markup: Optional[
            Union[
                "types.InlineKeyboardMarkup",
                "types.ReplyKeyboardMarkup",
                "types.ReplyKeyboardRemove",
                "types.ForceReply"
            ]
        ] = None,
        reactions: Optional["types.MessageReactions"] = None,
        send_paid_messages_stars: Optional[int] = None,
        unread_media: Optional[bool] = None,
        silent: Optional[bool] = None,
        legacy: Optional[bool] = None,
        pinned: Optional[bool] = None,
        restriction_reason: Optional[List["types.RestrictionReason"]] = None,
        fact_check: Optional["types.FactCheck"] = None,
        channel_post: Optional[bool] = None,
        raw: Optional["raw.types.Message"] = None
    ):
        super().__init__(client)

        self.id = id
        self.from_user = from_user
        self.sender_chat = sender_chat
        self.sender_boost_count = sender_boost_count
        self.sender_business_bot = sender_business_bot
        self.date = date
        self.chat = chat
        self.topic_message = topic_message
        self.automatic_forward = automatic_forward
        self.from_offline = from_offline
        self.show_caption_above_media = show_caption_above_media
        self.external_reply = external_reply
        self.quote = quote
        self.topic = topic
        self.forward_origin = forward_origin
        self.message_thread_id = message_thread_id
        self.direct_messages_chat_topic_id = direct_messages_chat_topic_id
        self.effect_id = effect_id
        self.reply_to_message_id = reply_to_message_id
        self.reply_to_story_id = reply_to_story_id
        self.reply_to_story_user_id = reply_to_story_user_id
        self.reply_to_top_message_id = reply_to_top_message_id
        self.reply_to_message = reply_to_message
        self.reply_to_story = reply_to_story
        self.mentioned = mentioned
        self.empty = empty
        self.service = service
        self.scheduled = scheduled
        self.from_scheduled = from_scheduled
        self.media = media
        self.paid_media = paid_media
        self.checklist = checklist
        self.edit_date = edit_date
        self.edit_hidden = edit_hidden
        self.media_group_id = media_group_id
        self.author_signature = author_signature
        self.has_protected_content = has_protected_content
        self.has_media_spoiler = has_media_spoiler
        self.text = text
        self.entities = entities
        self.caption_entities = caption_entities
        self.audio = audio
        self.document = document
        self.photo = photo
        self.sticker = sticker
        self.animation = animation
        self.game = game
        self.giveaway = giveaway
        self.giveaway_winners = giveaway_winners
        self.giveaway_completed = giveaway_completed
        self.invoice = invoice
        self.story = story
        self.video = video
        self.video_processing_pending = video_processing_pending
        self.voice = voice
        self.video_note = video_note
        self.caption = caption
        self.contact = contact
        self.location = location
        self.venue = venue
        self.web_page = web_page
        self.link_preview_options = link_preview_options
        self.poll = poll
        self.dice = dice
        self.new_chat_members = new_chat_members
        self.left_chat_member = left_chat_member
        self.chat_join_type = chat_join_type
        self.new_chat_title = new_chat_title
        self.new_chat_photo = new_chat_photo
        self.delete_chat_photo = delete_chat_photo
        self.group_chat_created = group_chat_created
        self.supergroup_chat_created = supergroup_chat_created
        self.channel_chat_created = channel_chat_created
        self.migrate_to_chat_id = migrate_to_chat_id
        self.migrate_from_chat_id = migrate_from_chat_id
        self.pinned_message = pinned_message
        self.game_high_score = game_high_score
        self.views = views
        self.forwards = forwards
        self.via_bot = via_bot
        self.outgoing = outgoing
        self.matches = matches
        self.command = command
        self.giveaway_prize_stars = giveaway_prize_stars
        self.screenshot_taken = screenshot_taken
        self.business_connection_id = business_connection_id
        self.reply_markup = reply_markup
        self.forum_topic_created = forum_topic_created
        self.forum_topic_closed = forum_topic_closed
        self.forum_topic_reopened = forum_topic_reopened
        self.forum_topic_edited = forum_topic_edited
        self.general_forum_topic_hidden = general_forum_topic_hidden
        self.general_forum_topic_unhidden = general_forum_topic_unhidden
        self.video_chat_scheduled = video_chat_scheduled
        self.history_cleared = history_cleared
        self.video_chat_started = video_chat_started
        self.video_chat_ended = video_chat_ended
        self.video_chat_members_invited = video_chat_members_invited
        self.phone_call_started = phone_call_started
        self.phone_call_ended = phone_call_ended
        self.web_app_data = web_app_data
        self.paid_messages_refunded = paid_messages_refunded
        self.paid_messages_price_changed = paid_messages_price_changed
        self.direct_message_price_changed = direct_message_price_changed
        self.checklist_tasks_done = checklist_tasks_done
        self.checklist_tasks_added = checklist_tasks_added
        self.gift_code = gift_code
        self.gifted_premium = gifted_premium
        self.gifted_stars = gifted_stars
        self.gift = gift
        self.suggest_profile_photo = suggest_profile_photo
        self.users_shared = users_shared
        self.chat_shared = chat_shared
        self.successful_payment = successful_payment
        self.refunded_payment = refunded_payment
        self.giveaway_created = giveaway_created
        self.chat_set_theme = chat_set_theme
        self.chat_set_background = chat_set_background
        self.set_message_auto_delete_time = set_message_auto_delete_time
        self.chat_boost = chat_boost
        self.write_access_allowed = write_access_allowed
        self.connected_website = connected_website
        self.contact_registered = contact_registered
        self.proximity_alert_triggered = proximity_alert_triggered
        self.reactions = reactions
        self.send_paid_messages_stars = send_paid_messages_stars
        self.unread_media = unread_media
        self.silent = silent
        self.legacy = legacy
        self.pinned = pinned
        self.restriction_reason = restriction_reason
        self.fact_check = fact_check
        self.channel_post = channel_post
        self.raw = raw

    @staticmethod
    async def _parse_service(
        client: "pyrogram.Client",
        message: "raw.types.MessageService",
        users: Dict[int, "raw.base.User"],
        chats: Dict[int, "raw.base.Chat"],
        replies: int = 1,
        business_connection_id: str = None,
    ) -> "Message":
        from_id = utils.get_raw_peer_id(message.from_id)
        peer_id = utils.get_raw_peer_id(message.peer_id)

        if isinstance(message.from_id, raw.types.PeerUser) and isinstance(message.peer_id, raw.types.PeerUser):
            if from_id not in users or peer_id not in users:
                try:
                    r = await client.invoke(
                        raw.functions.users.GetUsers(
                            id=[
                                await client.resolve_peer(from_id),
                                await client.resolve_peer(peer_id)
                            ]
                        )
                    )
                except PeerIdInvalid:
                    pass
                else:
                    users.update({i.id: i for i in r})

        from_user = types.User._parse(client, users.get(from_id or peer_id))
        sender_chat = types.Chat._parse(client, message, users, chats, is_chat=False) if not from_user else None
        chat = types.Chat._parse(client, message, users, chats, is_chat=True)

        action = message.action

        connected_website = None
        write_access_allowed = None
        chat_boost = None
        supergroup_chat_created = None
        channel_chat_created = None
        migrate_from_chat_id = None
        new_chat_members = None
        chat_join_type = None
        group_chat_created = None
        delete_chat_photo = None
        left_chat_member = None
        new_chat_photo = None
        new_chat_title = None
        migrate_to_chat_id = None
        contact_registered = None
        text = None
        proximity_alert_triggered = None
        gift_code = None
        gifted_premium = None
        gifted_stars = None
        giveaway_created = None
        giveaway_completed = None
        video_chat_ended = None
        video_chat_started = None
        video_chat_scheduled = None
        history_cleared = None
        video_chat_members_invited = None
        refunded_payment = None
        successful_payment = None
        phone_call_ended = None
        phone_call_started = None
        giveaway_prize_stars = None
        users_shared = None
        chat_shared = None
        screenshot_taken = None
        # passport_data_send = None
        # passport_data_received = None
        chat_set_theme = None
        chat_set_background = None
        set_message_auto_delete_time = None
        gift = None
        suggest_profile_photo = None
        forum_topic_created = None
        forum_topic_edited = None
        general_forum_topic_hidden = None
        forum_topic_closed = None
        general_forum_topic_unhidden = None
        forum_topic_reopened = None
        web_app_data = None
        paid_messages_refunded = None
        paid_messages_price_changed = None
        direct_message_price_changed = None
        checklist_tasks_done = None
        checklist_tasks_added = None

        service_type = enums.MessageServiceType.UNSUPPORTED

        if isinstance(action, raw.types.MessageActionBotAllowed):
            if getattr(action, "domain", None):
                service_type = enums.MessageServiceType.CONNECTED_WEBSITE
                connected_website = action.domain
            else:
                service_type = enums.MessageServiceType.WRITE_ACCESS_ALLOWED
                write_access_allowed = types.WriteAccessAllowed._parse(action)
        elif isinstance(action, raw.types.MessageActionBoostApply):
            service_type = enums.MessageServiceType.BOOST_APPLY
            chat_boost = action.boosts
        elif isinstance(action, raw.types.MessageActionChannelCreate):
            service_type = enums.MessageServiceType.CHANNEL_CHAT_CREATED

            if chat.type == enums.ChatType.SUPERGROUP:
                supergroup_chat_created = True
                service_type = enums.MessageServiceType.SUPERGROUP_CHAT_CREATED
            else:
                channel_chat_created = True
                service_type = enums.MessageServiceType.CHANNEL_CHAT_CREATED
        elif isinstance(action, raw.types.MessageActionChannelMigrateFrom):
            service_type = enums.MessageServiceType.MIGRATE_FROM_CHAT_ID
            migrate_from_chat_id = -action.chat_id
        elif isinstance(action, raw.types.MessageActionChatAddUser):
            service_type = enums.MessageServiceType.NEW_CHAT_MEMBERS
            new_chat_members = [types.User._parse(client, users[i]) for i in action.users]
            chat_join_type = enums.ChatJoinType.BY_ADD
        elif isinstance(action, raw.types.MessageActionChatCreate):
            service_type = enums.MessageServiceType.GROUP_CHAT_CREATED
            group_chat_created = True
        elif isinstance(action, raw.types.MessageActionChatDeletePhoto):
            service_type = enums.MessageServiceType.DELETE_CHAT_PHOTO
            delete_chat_photo = True
        elif isinstance(action, raw.types.MessageActionChatDeleteUser):
            service_type = enums.MessageServiceType.LEFT_CHAT_MEMBERS
            left_chat_member = types.User._parse(client, users[action.user_id])
        elif isinstance(action, raw.types.MessageActionChatEditPhoto):
            service_type = enums.MessageServiceType.NEW_CHAT_PHOTO
            new_chat_photo = types.Photo._parse(client, action.photo)
        elif isinstance(action, raw.types.MessageActionChatEditTitle):
            service_type = enums.MessageServiceType.NEW_CHAT_TITLE
            new_chat_title = action.title
        elif isinstance(action, raw.types.MessageActionChatJoinedByLink):
            service_type = enums.MessageServiceType.NEW_CHAT_MEMBERS
            new_chat_members = [types.User._parse(client, users[utils.get_raw_peer_id(message.from_id)])]
            chat_join_type = enums.ChatJoinType.BY_LINK
        elif isinstance(action, raw.types.MessageActionChatJoinedByRequest):
            service_type = enums.MessageServiceType.NEW_CHAT_MEMBERS
            new_chat_members = [types.User._parse(client, users[utils.get_raw_peer_id(message.from_id)])]
            chat_join_type = enums.ChatJoinType.BY_REQUEST
        elif isinstance(action, raw.types.MessageActionChatMigrateTo):
            service_type = enums.MessageServiceType.MIGRATE_TO_CHAT_ID
            migrate_to_chat_id = utils.get_channel_id(action.channel_id)
        elif isinstance(action, raw.types.MessageActionContactSignUp):
            service_type = enums.MessageServiceType.CONTACT_REGISTERED
            contact_registered = types.ContactRegistered()
        elif isinstance(action, raw.types.MessageActionCustomAction):
            service_type = enums.MessageServiceType.CUSTOM_ACTION
            text = action.message
        #TODO: elif isinstance(action, raw.types.MessageActionEmpty):
        elif isinstance(action, raw.types.MessageActionGeoProximityReached):
            service_type = enums.MessageServiceType.PROXIMITY_ALERT_TRIGGERED
            proximity_alert_triggered = types.ProximityAlertTriggered._parse(client, action, users, chats)
        elif isinstance(action, raw.types.MessageActionGiftCode):
            service_type = enums.MessageServiceType.GIFT_CODE
            gift_code = types.GiftCode._parse(client, action, users, chats)
        elif isinstance(action, raw.types.MessageActionGiftPremium):
            service_type = enums.MessageServiceType.GIFTED_PREMIUM
            gifted_premium = await types.GiftedPremium._parse(
                client,
                action,
                gifter=users.get(from_id),
                receiver=users.get(peer_id or from_id),
                users=users
            )
        elif isinstance(action, raw.types.MessageActionGiftStars):
            service_type = enums.MessageServiceType.GIFTED_STARS
            gifted_stars = await types.GiftedStars._parse(
                client,
                action,
                gifter=users.get(from_id),
                receiver=users.get(peer_id or from_id)
            )
        elif isinstance(action, raw.types.MessageActionGiveawayLaunch):
            service_type = enums.MessageServiceType.GIVEAWAY_CREATED
            giveaway_created = types.GiveawayCreated._parse(client, action)
        elif isinstance(action, raw.types.MessageActionGiveawayResults):
            service_type = enums.MessageServiceType.GIVEAWAY_COMPLETED
            giveaway_completed = await types.GiveawayCompleted._parse(
                client,
                action,
                types.Chat._parse(client, message, users, chats, is_chat=True),
                getattr(
                    getattr(
                        message,
                        "reply_to",
                        None
                    ),
                    "reply_to_msg_id",
                    None
                )
            )
        elif isinstance(action, raw.types.MessageActionGroupCall):
            if action.duration:
                service_type = enums.MessageServiceType.VIDEO_CHAT_ENDED
                video_chat_ended = types.VideoChatEnded._parse(action)
            else:
                service_type = enums.MessageServiceType.VIDEO_CHAT_STARTED
                video_chat_started = types.VideoChatStarted()
        elif isinstance(action, raw.types.MessageActionGroupCallScheduled):
            service_type = enums.MessageServiceType.VIDEO_CHAT_SCHEDULED
            video_chat_scheduled = types.VideoChatScheduled._parse(action)
        if isinstance(action, raw.types.MessageActionHistoryClear):
            service_type = enums.MessageServiceType.HISTORY_CLEARED
            history_cleared = types.HistoryCleared()
        elif isinstance(action, raw.types.MessageActionInviteToGroupCall):
            service_type = enums.MessageServiceType.VIDEO_CHAT_MEMBERS_INVITED
            video_chat_members_invited = types.VideoChatMembersInvited._parse(client, action, users)
        elif isinstance(action, raw.types.MessageActionPaymentRefunded):
            service_type = enums.MessageServiceType.REFUNDED_PAYMENT
            refunded_payment = types.RefundedPayment._parse(action)
        elif isinstance(action, (raw.types.MessageActionPaymentSent, raw.types.MessageActionPaymentSentMe)):
            service_type = enums.MessageServiceType.SUCCESSFUL_PAYMENT
            successful_payment = types.SuccessfulPayment._parse(action)
        elif isinstance(action, raw.types.MessageActionPhoneCall):
            if action.reason:
                service_type = enums.MessageServiceType.PHONE_CALL_ENDED
                phone_call_ended = types.PhoneCallEnded._parse(action)
            else:
                service_type = enums.MessageServiceType.PHONE_CALL_STARTED
                phone_call_started = types.PhoneCallStarted._parse(action)
        elif isinstance(action, raw.types.MessageActionPrizeStars):
            service_type = enums.MessageServiceType.GIVEAWAY_PRIZE_STARS
            giveaway_prize_stars = await types.GiveawayPrizeStars._parse(client, action, chats)
        elif isinstance(action, (raw.types.MessageActionRequestedPeer, raw.types.MessageActionRequestedPeerSentMe)):
            _requested_chat = types.ChatShared._parse(client, action, chats)

            if _requested_chat is None:
                service_type = enums.MessageServiceType.USERS_SHARED
                users_shared = types.UsersShared._parse(client, action, users)
            else:
                service_type = enums.MessageServiceType.CHAT_SHARED
                chat_shared = _requested_chat
        elif isinstance(action, raw.types.MessageActionScreenshotTaken):
            service_type = enums.MessageServiceType.SCREENSHOT_TAKEN
            screenshot_taken = types.ScreenshotTaken()
        # TODO: elif isinstance(action, raw.types.MessageActionSecureValuesSent):
            # service_type = enums.MessageServiceType.PASSPORT_DATA_SEND
            # passport_data_send = ...
        # TODO: elif isinstance(action, raw.types.MessageActionSecureValuesSentMe):
            # service_type = enums.MessageServiceType.PASSPORT_DATA_RECEIVED
            # passport_data_received = ...
        elif isinstance(action, raw.types.MessageActionSetChatTheme):
            service_type = enums.MessageServiceType.CHAT_SET_THEME
            chat_set_theme = types.ChatTheme._parse(action)
        elif isinstance(action, raw.types.MessageActionSetChatWallPaper):
            service_type = enums.MessageServiceType.CHAT_SET_BACKGROUND
            chat_set_background = types.ChatBackground._parse(client, action.wallpaper, action.same, action.for_both)
        elif isinstance(action, raw.types.MessageActionSetMessagesTTL):
            service_type = enums.MessageServiceType.CHAT_TTL_CHANGED
            set_message_auto_delete_time = action.period
        elif isinstance(action, (raw.types.MessageActionStarGift, raw.types.MessageActionStarGiftUnique)):
            service_type = enums.MessageServiceType.GIFT
            gift = await types.Gift._parse_action(client, message, users, chats)
        elif isinstance(action, raw.types.MessageActionSuggestProfilePhoto):
            service_type = enums.MessageServiceType.SUGGEST_PROFILE_PHOTO
            suggest_profile_photo = types.Photo._parse(client, action.photo)
        elif isinstance(action, raw.types.MessageActionTopicCreate):
            service_type = enums.MessageServiceType.FORUM_TOPIC_CREATED
            forum_topic_created = types.ForumTopicCreated._parse(message)
        elif isinstance(action, raw.types.MessageActionTopicEdit):
            if action.hidden is True:
                service_type = enums.MessageServiceType.GENERAL_FORUM_TOPIC_HIDDEN
                general_forum_topic_hidden = types.GeneralForumTopicHidden()
            elif action.hidden is False:
                service_type = enums.MessageServiceType.GENERAL_FORUM_TOPIC_UNHIDDEN
                general_forum_topic_unhidden = types.GeneralForumTopicUnhidden()
            elif action.closed is True:
                service_type = enums.MessageServiceType.FORUM_TOPIC_CLOSED
                forum_topic_closed = types.ForumTopicClosed()
            elif action.closed is False:
                service_type = enums.MessageServiceType.FORUM_TOPIC_REOPENED
                forum_topic_reopened = types.ForumTopicReopened()
            else:
                service_type = enums.MessageServiceType.FORUM_TOPIC_EDITED
                forum_topic_edited = types.ForumTopicEdited._parse(action)
        elif isinstance(action, (raw.types.MessageActionWebViewDataSent, raw.types.MessageActionWebViewDataSentMe)):
            service_type = enums.MessageServiceType.WEB_APP_DATA
            web_app_data = types.WebAppData._parse(action)
        elif isinstance(action, raw.types.MessageActionPaidMessagesRefunded):
            service_type = enums.MessageServiceType.PAID_MESSAGES_REFUNDED
            paid_messages_refunded = types.PaidMessagesRefunded._parse(action)
        elif isinstance(action, raw.types.MessageActionPaidMessagesPrice):
            if chat.type == enums.ChatType.DIRECT:
                service_type = enums.MessageServiceType.DIRECT_MESSAGE_PRICE_CHANGED
                direct_message_price_changed = types.DirectMessagePriceChanged._parse(action)
            else:
                service_type = enums.MessageServiceType.PAID_MESSAGES_PRICE_CHANGED
                paid_messages_price_changed = types.PaidMessagesPriceChanged._parse(action)
        elif isinstance(action, raw.types.MessageActionTodoCompletions):
            service_type = enums.MessageServiceType.CHECKLIST_TASKS_DONE
            checklist_tasks_done = types.ChecklistTasksDone._parse(message)
        elif isinstance(action, raw.types.MessageActionTodoAppendTasks):
            service_type = enums.MessageServiceType.CHECKLIST_TASKS_ADDED
            checklist_tasks_added = types.ChecklistTasksAdded._parse(client, message)

        parsed_message = Message(
            id=message.id,
            date=utils.timestamp_to_datetime(message.date),
            chat=chat,
            from_user=from_user,
            sender_chat=sender_chat,
            service=service_type,
            connected_website=connected_website,
            write_access_allowed=write_access_allowed,
            chat_boost=chat_boost,
            supergroup_chat_created=supergroup_chat_created,
            channel_chat_created=channel_chat_created,
            migrate_from_chat_id=migrate_from_chat_id,
            new_chat_members=new_chat_members,
            chat_join_type=chat_join_type,
            group_chat_created=group_chat_created,
            delete_chat_photo=delete_chat_photo,
            left_chat_member=left_chat_member,
            new_chat_photo=new_chat_photo,
            new_chat_title=new_chat_title,
            migrate_to_chat_id=migrate_to_chat_id,
            contact_registered=contact_registered,
            text=text,
            proximity_alert_triggered=proximity_alert_triggered,
            gift_code=gift_code,
            gifted_premium=gifted_premium,
            gifted_stars=gifted_stars,
            giveaway_created=giveaway_created,
            giveaway_completed=giveaway_completed,
            video_chat_ended=video_chat_ended,
            video_chat_started=video_chat_started,
            video_chat_scheduled=video_chat_scheduled,
            history_cleared=history_cleared,
            video_chat_members_invited=video_chat_members_invited,
            refunded_payment=refunded_payment,
            successful_payment=successful_payment,
            phone_call_ended=phone_call_ended,
            phone_call_started=phone_call_started,
            giveaway_prize_stars=giveaway_prize_stars,
            users_shared=users_shared,
            chat_shared=chat_shared,
            screenshot_taken=screenshot_taken,
            chat_set_theme=chat_set_theme,
            chat_set_background=chat_set_background,
            set_message_auto_delete_time=set_message_auto_delete_time,
            gift=gift,
            suggest_profile_photo=suggest_profile_photo,
            forum_topic_created=forum_topic_created,
            forum_topic_edited=forum_topic_edited,
            general_forum_topic_hidden=general_forum_topic_hidden,
            forum_topic_closed=forum_topic_closed,
            general_forum_topic_unhidden=general_forum_topic_unhidden,
            forum_topic_reopened=forum_topic_reopened,
            web_app_data=web_app_data,
            paid_messages_refunded=paid_messages_refunded,
            paid_messages_price_changed=paid_messages_price_changed,
            direct_message_price_changed=direct_message_price_changed,
            checklist_tasks_done=checklist_tasks_done,
            checklist_tasks_added=checklist_tasks_added,
            reactions=types.MessageReactions._parse(client, message.reactions, users, chats),
            business_connection_id=business_connection_id,
            raw=message,
            client=client
        )

        if isinstance(action, raw.types.MessageActionGameScore):
            parsed_message.game_high_score = types.GameHighScore._parse_action(client, message, users)
            parsed_message.service = enums.MessageServiceType.GAME_HIGH_SCORE

            if client.fetch_replies and message.reply_to and replies:
                try:
                    parsed_message.reply_to_message = await client.get_messages(
                        chat_id=parsed_message.chat.id,
                        message_ids=message.id,
                        reply=True,
                        replies=0
                    )
                except (MessageIdsEmpty, ChannelPrivate):
                    pass
        elif isinstance(action, raw.types.MessageActionPinMessage):
            parsed_message.service = enums.MessageServiceType.PINNED_MESSAGE

            if client.fetch_replies:
                try:
                    parsed_message.pinned_message = await client.get_messages(
                        chat_id=parsed_message.chat.id,
                        pinned=True,
                        replies=0
                    )

                except (MessageIdsEmpty, ChannelPrivate):
                    pass

        if message.reply_to and message.reply_to.forum_topic:
            parsed_message.topic_message = True
            if message.reply_to.reply_to_top_id:
                parsed_message.message_thread_id = message.reply_to.reply_to_top_id
            elif message.reply_to.reply_to_msg_id:
                parsed_message.message_thread_id = message.reply_to.reply_to_msg_id
            else:
                parsed_message.message_thread_id = 1

        client.message_cache[(parsed_message.chat.id, parsed_message.id)] = parsed_message

        return parsed_message

    @staticmethod
    async def _parse_message(
        client: "pyrogram.Client",
        message: "raw.types.Message",
        users: Dict[int, "raw.base.User"],
        chats: Dict[int, "raw.base.Chat"],
        topics: Dict[int, "raw.base.ForumTopic"] = None,
        is_scheduled: bool = False,
        replies: int = 1,
        business_connection_id: str = None,
        raw_reply_to_message: "raw.base.Message" = None
    ) -> "Message":
        from_id = utils.get_raw_peer_id(message.from_id)
        peer_id = utils.get_raw_peer_id(message.peer_id)

        if isinstance(message.from_id, raw.types.PeerUser) and isinstance(message.peer_id, raw.types.PeerUser):
            if from_id not in users or peer_id not in users:
                try:
                    r = await client.invoke(
                        raw.functions.users.GetUsers(
                            id=[
                                await client.resolve_peer(from_id),
                                await client.resolve_peer(peer_id)
                            ]
                        )
                    )
                except PeerIdInvalid:
                    pass
                else:
                    users.update({i.id: i for i in r})

        from_user = types.User._parse(client, users.get(from_id or peer_id))
        sender_chat = types.Chat._parse(client, message, users, chats, is_chat=False) if not from_user else None
        chat = types.Chat._parse(client, message, users, chats, is_chat=True)

        entities = types.List(
            filter(
                lambda x: x is not None,
                [types.MessageEntity._parse(client, entity, users) for entity in message.entities]
            )
        )

        forward_header = message.fwd_from
        forward_origin = None

        if forward_header:
            forward_origin = types.MessageOrigin._parse(
                client,
                forward_header,
                users,
                chats,
            )

        photo = None
        location = None
        contact = None
        venue = None
        game = None
        giveaway = None
        giveaway_winners = None
        invoice = None
        story = None
        audio = None
        voice = None
        animation = None
        video = None
        video_note = None
        sticker = None
        document = None
        web_page = None
        link_preview_options = None
        poll = None
        dice = None
        paid_media = None
        checklist = None

        media = message.media
        media_type = None
        has_media_spoiler = None

        if media:
            if isinstance(media, raw.types.MessageMediaPhoto):
                photo = types.Photo._parse(client, media.photo, media.ttl_seconds)
                media_type = enums.MessageMediaType.PHOTO
                has_media_spoiler = media.spoiler
            elif isinstance(media, raw.types.MessageMediaGeo):
                location = types.Location._parse(client, media.geo)
                media_type = enums.MessageMediaType.LOCATION
            elif isinstance(media, raw.types.MessageMediaContact):
                contact = types.Contact._parse(client, media)
                media_type = enums.MessageMediaType.CONTACT
            elif isinstance(media, raw.types.MessageMediaVenue):
                venue = types.Venue._parse(client, media)
                media_type = enums.MessageMediaType.VENUE
            elif isinstance(media, raw.types.MessageMediaGame):
                game = types.Game._parse(client, media)
                media_type = enums.MessageMediaType.GAME
            elif isinstance(media, raw.types.MessageMediaGiveaway):
                giveaway = types.Giveaway._parse(client, media, chats)
                media_type = enums.MessageMediaType.GIVEAWAY
            elif isinstance(media, raw.types.MessageMediaGiveawayResults):
                giveaway_winners = await types.GiveawayWinners._parse(client, media, users, chats)
                media_type = enums.MessageMediaType.GIVEAWAY_WINNERS
            elif isinstance(media, raw.types.MessageMediaInvoice):
                invoice = types.Invoice._parse(client, media)
                media_type = enums.MessageMediaType.INVOICE
            elif isinstance(media, raw.types.MessageMediaStory):
                story = await types.Story._parse(client, media, media.peer, users, chats)
                media_type = enums.MessageMediaType.STORY
            elif isinstance(media, raw.types.MessageMediaDocument):
                doc = media.document

                if isinstance(doc, raw.types.Document):
                    attributes = {type(i): i for i in doc.attributes}

                    file_name = getattr(
                        attributes.get(
                            raw.types.DocumentAttributeFilename, None
                        ), "file_name", None
                    )

                    if raw.types.DocumentAttributeAnimated in attributes:
                        video_attributes = attributes.get(raw.types.DocumentAttributeVideo, None)
                        animation = types.Animation._parse(client, doc, video_attributes, file_name)
                        media_type = enums.MessageMediaType.ANIMATION
                        has_media_spoiler = media.spoiler
                    elif raw.types.DocumentAttributeSticker in attributes:
                        sticker = await types.Sticker._parse(client, doc, attributes)
                        media_type = enums.MessageMediaType.STICKER
                    elif raw.types.DocumentAttributeVideo in attributes:
                        video_attributes = attributes[raw.types.DocumentAttributeVideo]

                        if video_attributes.round_message:
                            video_note = types.VideoNote._parse(client, doc, video_attributes, media.ttl_seconds)
                            media_type = enums.MessageMediaType.VIDEO_NOTE
                        else:
                            video = types.Video._parse(client, doc, video_attributes, file_name, media.ttl_seconds, media.video_cover, media.video_timestamp, media.alt_documents)
                            media_type = enums.MessageMediaType.VIDEO
                            has_media_spoiler = media.spoiler
                    elif raw.types.DocumentAttributeAudio in attributes:
                        audio_attributes = attributes[raw.types.DocumentAttributeAudio]

                        if audio_attributes.voice:
                            voice = types.Voice._parse(client, doc, audio_attributes, media.ttl_seconds)
                            media_type = enums.MessageMediaType.VOICE
                        else:
                            audio = types.Audio._parse(client, doc, audio_attributes, file_name)
                            media_type = enums.MessageMediaType.AUDIO
                    else:
                        document = types.Document._parse(client, doc, file_name)
                        media_type = enums.MessageMediaType.DOCUMENT
            elif isinstance(media, raw.types.MessageMediaWebPage):
                media_type = enums.MessageMediaType.WEB_PAGE
                web_page = types.WebPage._parse(client, media)
            elif isinstance(media, raw.types.MessageMediaPoll):
                poll = types.Poll._parse(client, media)
                media_type = enums.MessageMediaType.POLL
            elif isinstance(media, raw.types.MessageMediaDice):
                dice = types.Dice._parse(client, media)
                media_type = enums.MessageMediaType.DICE
            elif isinstance(media, raw.types.MessageMediaPaidMedia):
                paid_media = types.PaidMediaInfo._parse(client, media)
                media_type = enums.MessageMediaType.PAID_MEDIA
            elif isinstance(media, raw.types.MessageMediaToDo):
                media_type = enums.MessageMediaType.CHECKLIST
                checklist = types.Checklist._parse(client, media, users)
            else:
                media_type = enums.MessageMediaType.UNSUPPORTED
                media = None

        link_preview_options = types.LinkPreviewOptions._parse(
            media,
            getattr(getattr(media, "webpage", None), "url", utils.get_first_url(message.message)),
            message.invert_media
        )

        reply_markup = message.reply_markup

        if reply_markup:
            if isinstance(reply_markup, raw.types.ReplyKeyboardForceReply):
                reply_markup = types.ForceReply.read(reply_markup)
            elif isinstance(reply_markup, raw.types.ReplyKeyboardMarkup):
                reply_markup = types.ReplyKeyboardMarkup.read(reply_markup)
            elif isinstance(reply_markup, raw.types.ReplyInlineMarkup):
                reply_markup = types.InlineKeyboardMarkup.read(reply_markup)
            elif isinstance(reply_markup, raw.types.ReplyKeyboardHide):
                reply_markup = types.ReplyKeyboardRemove.read(reply_markup)
            else:
                reply_markup = None

        reactions = types.MessageReactions._parse(client, message.reactions, users, chats)

        parsed_message = Message(
            id=message.id,
            effect_id=getattr(message, "effect", None),
            date=utils.timestamp_to_datetime(message.date),
            chat=chat,
            from_user=from_user,
            sender_chat=sender_chat,
            sender_business_bot=types.User._parse(
                client,
                users.get(getattr(message, "via_business_bot_id", None))
            ),
            text=(
                Str(message.message).init(entities) or None
                if media is None or web_page is not None
                else None
            ),
            caption=(
                Str(message.message).init(entities) or None
                if media is not None and web_page is None
                else None
            ),
            entities=(
                entities or None
                if media is None or web_page is not None
                else None
            ),
            caption_entities=(
                entities or None
                if media is not None and web_page is None
                else None
            ),
            author_signature=message.post_author,
            has_protected_content=message.noforwards,
            has_media_spoiler=has_media_spoiler,
            forward_origin=forward_origin,
            mentioned=message.mentioned,
            scheduled=is_scheduled,
            from_scheduled=message.from_scheduled,
            media=media_type,
            paid_media=paid_media,
            checklist=checklist,
            show_caption_above_media=getattr(message, "invert_media", None),
            edit_date=utils.timestamp_to_datetime(message.edit_date),
            edit_hidden=message.edit_hide,
            media_group_id=message.grouped_id,
            photo=photo,
            location=location,
            contact=contact,
            venue=venue,
            audio=audio,
            voice=voice,
            animation=animation,
            game=game,
            giveaway=giveaway,
            giveaway_winners=giveaway_winners,
            invoice=invoice,
            story=story,
            video=video,
            video_processing_pending=getattr(message, "video_processing_pending", None),
            video_note=video_note,
            sticker=sticker,
            document=document,
            web_page=web_page,
            link_preview_options=link_preview_options,
            poll=poll,
            dice=dice,
            views=message.views,
            forwards=message.forwards,
            sender_boost_count=getattr(message, "from_boosts_applied", None),
            via_bot=types.User._parse(client, users.get(message.via_bot_id, None)),
            outgoing=message.out,
            business_connection_id=business_connection_id,
            reply_markup=reply_markup,
            reactions=reactions,
            from_offline=getattr(message, "offline", None),
            send_paid_messages_stars=getattr(message, "paid_message_stars", None),
            unread_media=getattr(message, "media_unread", None),
            silent=getattr(message, "silent", None),
            pinned=getattr(message, "pinned", None),
            restriction_reason=types.List(
                types.RestrictionReason._parse(reason)
                for reason in getattr(message, "restriction_reason", [])
            ) or None,
            fact_check=types.FactCheck._parse(client, getattr(message, "fact_check", None), users),
            channel_post=getattr(message, "post", None),
            raw=message,
            client=client
        )

        if (
            forward_header and
            forward_header.saved_from_peer and
            forward_header.saved_from_msg_id
        ):
            saved_from_peer_id = utils.get_raw_peer_id(forward_header.saved_from_peer)
            saved_from_peer_chat = chats.get(saved_from_peer_id)
            if (
                isinstance(saved_from_peer_chat, raw.types.Channel) and
                not saved_from_peer_chat.megagroup
            ):
                parsed_message.automatic_forward = True

        if message.reply_to:
            parsed_message.external_reply = await types.ExternalReplyInfo._parse(
                client,
                message.reply_to,
                users,
                chats
            )

            if isinstance(message.reply_to, raw.types.MessageReplyHeader):
                parsed_message.reply_to_message_id = message.reply_to.reply_to_msg_id
                parsed_message.reply_to_top_message_id = message.reply_to.reply_to_top_id

                if message.reply_to.forum_topic:
                    parsed_message.topic_message = True

                    if message.reply_to.reply_to_top_id:
                        parsed_message.message_thread_id = message.reply_to.reply_to_top_id
                    elif message.reply_to.reply_to_msg_id:
                        parsed_message.message_thread_id = message.reply_to.reply_to_msg_id
                    else:
                        parsed_message.message_thread_id = 1

                if message.reply_to.quote:
                    parsed_message.quote = types.TextQuote._parse(
                        client,
                        users,
                        message.reply_to
                    )
            elif isinstance(message.reply_to, raw.types.MessageReplyStoryHeader):
                parsed_message.reply_to_story_id = message.reply_to.story_id
                parsed_message.reply_to_story_user_id = utils.get_peer_id(message.reply_to.peer)

                if client.fetch_stories and client.me and not client.me.is_bot:
                    parsed_message.reply_to_story = await client.get_stories(
                        utils.get_peer_id(message.reply_to.peer),
                        message.reply_to.story_id
                    )

            if raw_reply_to_message:
                parsed_message.reply_to_message = await types.Message._parse(
                    client,
                    raw_reply_to_message,
                    users,
                    chats,
                    business_connection_id=business_connection_id,
                    replies=0
                )
            elif replies:
                if isinstance(message.reply_to, raw.types.MessageReplyHeader):
                    if message.reply_to.reply_to_peer_id:
                        key = (utils.get_peer_id(message.reply_to.reply_to_peer_id), message.reply_to.reply_to_msg_id)
                        reply_to_params = {"chat_id": key[0], 'message_ids': key[1]}
                    else:
                        key = (parsed_message.chat.id, parsed_message.reply_to_message_id)
                        reply_to_params = {'chat_id': key[0], 'message_ids': message.id, 'reply': True}

                    reply_to_message = client.message_cache[key]

                    if not reply_to_message and client.fetch_replies:
                        try:
                            reply_to_message = await client.get_messages(
                                replies=replies - 1,
                                **reply_to_params
                            )
                        except (ChannelPrivate, MessageIdsEmpty):
                            pass

                    parsed_message.reply_to_message = reply_to_message

        if topics:
            parsed_message.topic = types.ForumTopic._parse(
                client,
                topics.get(parsed_message.message_thread_id), users=users, chats=chats
            )

            if parsed_message.topic:
                client.topic_cache[(parsed_message.chat.id, parsed_message.topic.id)] = parsed_message.topic

        if not parsed_message.topic and parsed_message.chat.is_forum:
            parsed_topic = client.topic_cache[(parsed_message.chat.id, parsed_message.message_thread_id)]

            if parsed_topic:
                parsed_message.topic = parsed_topic
            elif client.fetch_topics and client.me and not client.me.is_bot:
                try:
                    parsed_message.topic = await client.get_forum_topics_by_id(
                        chat_id=parsed_message.chat.id,
                        topic_ids=parsed_message.message_thread_id or 1
                    )

                    if parsed_message.topic:
                        client.topic_cache[(parsed_message.chat.id, parsed_message.topic.id)] = parsed_message.topic
                except (ChannelPrivate, ChannelForumMissing):
                    pass

        if chat.type == enums.ChatType.DIRECT:
            parsed_message.direct_messages_chat_topic_id = message.saved_peer_id.user_id

            parsed_topic = client.topic_cache[(parsed_message.chat.id, parsed_message.direct_messages_chat_topic_id)]

            if parsed_topic:
                parsed_message.topic = parsed_topic
            elif client.fetch_topics:
                try:
                    parsed_message.topic = await client.get_direct_messages_topics_by_id(
                        chat_id=parsed_message.chat.id,
                        topic_ids=parsed_message.direct_messages_chat_topic_id
                    )

                    if parsed_message.topic:
                        client.topic_cache[(parsed_message.chat.id, parsed_message.topic.id)] = parsed_message.topic
                except ChatAdminRequired:
                    pass

        if not parsed_message.poll:  # Do not cache poll messages
            client.message_cache[(parsed_message.chat.id, parsed_message.id)] = parsed_message

        return parsed_message

    @staticmethod
    async def _parse(
        client: "pyrogram.Client",
        message: "raw.base.Message",
        users: Dict[int, "raw.base.User"],
        chats: Dict[int, "raw.base.Chat"],
        topics: Optional[Dict[int, "raw.base.ForumTopic"]] = None,
        is_scheduled: bool = False,
        replies: int = 1,
        business_connection_id: Optional[str] = None,
        raw_reply_to_message: Optional["raw.base.Message"] = None
    ) -> "Message":
        if isinstance(message, raw.types.MessageEmpty):
            return Message(
                id=message.id,
                empty=True,
                business_connection_id=business_connection_id,
                raw=message,
                client=client,
            )

        if isinstance(message, raw.types.MessageService):
            return await types.Message._parse_service(
                client=client,
                message=message,
                users=users,
                chats=chats,
                replies=replies,
                business_connection_id=business_connection_id
            )

        if isinstance(message, raw.types.Message):
            return await types.Message._parse_message(
                client=client,
                message=message,
                users=users,
                chats=chats,
                topics=topics,
                is_scheduled=is_scheduled,
                replies=replies,
                business_connection_id=business_connection_id,
                raw_reply_to_message=raw_reply_to_message
            )

    @property
    def link(self) -> str:
        if self.chat.type in (enums.ChatType.PRIVATE, enums.ChatType.BOT):
            return ""

        if self.chat.username:
            if self.message_thread_id:
                return f"https://t.me/{self.chat.username}/{self.message_thread_id}/{self.id}"
            else:
                return f"https://t.me/{self.chat.username}/{self.id}"
        else:
            if self.message_thread_id:
                return f"https://t.me/c/{utils.get_channel_id(self.chat.id)}/{self.message_thread_id}/{self.id}"
            else:
                return f"https://t.me/c/{utils.get_channel_id(self.chat.id)}/{self.id}"

    @property
    def content(self) -> Str:
        return self.text or self.caption or Str("").init([])

    # region Deprecated
    # TODO: Remove later

    @property
    def forward_from(self) -> Optional["types.User"]:
        log.warning(
            "`message.forward_from` is deprecated and will be removed in future updates. Use `message.forward_origin.sender_user` instead."
        )
        return getattr(self.forward_origin, "sender_user", None)

    @property
    def forward_sender_name(self) -> Optional[str]:
        log.warning(
            "`message.forward_sender_name` property is deprecated and will be removed in future updates. Use `message.forward_origin.sender_user_name` instead."
        )
        return getattr(self.forward_origin, "sender_user_name", None)

    @property
    def forward_from_chat(self) -> Optional["types.Chat"]:
        log.warning(
            "`message.forward_from_chat` property is deprecated and will be removed in future updates. Use `message.forward_origin.chat.sender_chat` instead."
        )
        return getattr(
            self.forward_origin,
            "chat",
            getattr(
                self.forward_origin,
                "sender_chat",
                None
            )
        )

    @property
    def forward_from_message_id(self) -> Optional[int]:
        log.warning(
            "`message.forward_from_message_id` property is deprecated and will be removed in future updates. Use `message.forward_origin.message_id` instead."
        )
        return getattr(self.forward_origin, "message_id", None)

    @property
    def forward_signature(self) -> Optional[str]:
        log.warning(
            "`message.forward_signature` property is deprecated and will be removed in future updates. Use `message.forward_origin.author_signature` instead."
        )
        return getattr(self.forward_origin, "author_signature", None)

    @property
    def forward_date(self) -> Optional[datetime]:
        log.warning(
            "`message.forward_date` property is deprecated and will be removed in future updates. Use `message.forward_origin.date` instead."
        )
        return getattr(self.forward_origin, "date", None)

    # endregion

    async def get_media_group(self) -> List["types.Message"]:
        """Bound method *get_media_group* of :obj:`~pyrogram.types.Message`.

        Use as a shortcut for:

        .. code-block:: python

            await client.get_media_group(
                chat_id=message.chat.id,
                message_id=message.id
            )

        Example:
            .. code-block:: python

                await message.get_media_group()

        Returns:
            List of :obj:`~pyrogram.types.Message`: On success, a list of messages of the media group is returned.

        Raises:
            ValueError: In case the passed message id doesn't belong to a media group.
        """
        return await self._client.get_media_group(
            chat_id=self.chat.id,
            message_id=self.id
        )

    async def reply_text(
        self,
        text: str,
        quote: bool = None,
        parse_mode: Optional["enums.ParseMode"] = None,
        entities: List["types.MessageEntity"] = None,
        link_preview_options: "types.LinkPreviewOptions" = None,
        disable_notification: bool = None,
        message_thread_id: int = None,
        direct_messages_chat_topic_id: int = None,
        effect_id: int = None,
        show_caption_above_media: bool = None,
        reply_parameters: "types.ReplyParameters" = None,
        schedule_date: datetime = None,
        protect_content: bool = None,
        business_connection_id: str = None,
        allow_paid_broadcast: bool = None,
        paid_message_star_count: int = None,
        reply_markup=None,

        disable_web_page_preview: bool = None,
        reply_to_message_id: int = None,
        quote_text: str = None,
        quote_entities: List["types.MessageEntity"] = None,
    ) -> "Message":
        """Bound method *reply_text* of :obj:`~pyrogram.types.Message`.

        An alias exists as *reply*.

        Use as a shortcut for:

        .. code-block:: python

            await client.send_message(
                chat_id=message.chat.id,
                text="hello",
                reply_to_message_id=message.id
            )

        Example:
            .. code-block:: python

                await message.reply_text("hello", quote=True)

        Parameters:
            text (``str``):
                Text of the message to be sent.

            quote (``bool``, *optional*):
                If ``True``, the message will be sent as a reply to this message.
                If *reply_parameters* is passed, this parameter will be ignored.
                Defaults to ``True`` in group chats and ``False`` in private chats.

            parse_mode (:obj:`~pyrogram.enums.ParseMode`, *optional*):
                By default, texts are parsed using both Markdown and HTML styles.
                You can combine both syntaxes together.

            entities (List of :obj:`~pyrogram.types.MessageEntity`):
                List of special entities that appear in message text, which can be specified instead of *parse_mode*.

            link_preview_options (:obj:`~pyrogram.types.LinkPreviewOptions`, *optional*):
                Options used for link preview generation for the message.

            disable_notification (``bool``, *optional*):
                Sends the message silently.
                Users will receive a notification with no sound.

            message_thread_id (``int``, *optional*):
                Unique identifier of a message thread to which the message belongs.
                For forums only.

            direct_messages_chat_topic_id (``int``, *optional*):
                Unique identifier of the topic in a channel direct messages chat administered by the current user.
                For directs only.

            effect_id (``int``, *optional*):
                Unique identifier of the message effect.
                For private chats only.

            show_caption_above_media (``bool``, *optional*):
                Pass True, if the caption must be shown above the message media.

            reply_parameters (:obj:`~pyrogram.types.ReplyParameters`, *optional*):
                Describes reply parameters for the message that is being sent.

            schedule_date (:py:obj:`~datetime.datetime`, *optional*):
                Date when the message will be automatically sent.

            protect_content (``bool``, *optional*):
                Protects the contents of the sent message from forwarding and saving.

            business_connection_id (``str``, *optional*):
                Unique identifier of the business connection on behalf of which the message will be sent.

            allow_paid_broadcast (``bool``, *optional*):
                If True, you will be allowed to send up to 1000 messages per second.
                Ignoring broadcasting limits for a fee of 0.1 Telegram Stars per message.
                The relevant Stars will be withdrawn from the bot's balance.
                For bots only.

            paid_message_star_count (``int``, *optional*):
                The number of Telegram Stars the user agreed to pay to send the messages.

            reply_markup (:obj:`~pyrogram.types.InlineKeyboardMarkup` | :obj:`~pyrogram.types.ReplyKeyboardMarkup` | :obj:`~pyrogram.types.ReplyKeyboardRemove` | :obj:`~pyrogram.types.ForceReply`, *optional*):
                Additional interface options. An object for an inline keyboard, custom reply keyboard,
                instructions to remove reply keyboard or to force a reply from the user.

        Returns:
            On success, the sent Message is returned.

        Raises:
            RPCError: In case of a Telegram RPC error.
        """
        if quote is None:
            quote = self.chat.type != enums.ChatType.PRIVATE

        if reply_parameters is None and quote:
            reply_parameters = types.ReplyParameters(
                message_id=self.id
            )

        if message_thread_id is None:
            message_thread_id = self.message_thread_id

        if direct_messages_chat_topic_id is None:
            direct_messages_chat_topic_id = self.direct_messages_chat_topic_id

        if business_connection_id is None:
            business_connection_id = self.business_connection_id

        return await self._client.send_message(
            chat_id=self.chat.id,
            text=text,
            parse_mode=parse_mode,
            entities=entities,
            link_preview_options=link_preview_options,
            disable_notification=disable_notification,
            message_thread_id=message_thread_id,
            direct_messages_chat_topic_id=direct_messages_chat_topic_id,
            effect_id=effect_id,
            show_caption_above_media=show_caption_above_media,
            reply_parameters=reply_parameters,
            schedule_date=schedule_date,
            protect_content=protect_content,
            business_connection_id=business_connection_id,
            allow_paid_broadcast=allow_paid_broadcast,
            paid_message_star_count=paid_message_star_count,
            reply_markup=reply_markup,

            disable_web_page_preview=disable_web_page_preview,
            reply_to_message_id=reply_to_message_id,
            quote_text=quote_text,
            quote_entities=quote_entities,
        )

    reply = reply_text

    async def reply_animation(
        self,
        animation: Union[str, BinaryIO],
        quote: bool = None,
        caption: str = "",
        parse_mode: Optional["enums.ParseMode"] = None,
        caption_entities: List["types.MessageEntity"] = None,
        has_spoiler: bool = None,
        show_caption_above_media: bool = None,
        duration: int = 0,
        width: int = 0,
        height: int = 0,
        thumb: Union[str, BinaryIO] = None,
        disable_notification: bool = None,
        business_connection_id: str = None,
        allow_paid_broadcast: bool = None,
        paid_message_star_count: int = None,
        reply_markup: Union[
            "types.InlineKeyboardMarkup",
            "types.ReplyKeyboardMarkup",
            "types.ReplyKeyboardRemove",
            "types.ForceReply"
        ] = None,
        message_thread_id: int = None,
        direct_messages_chat_topic_id: int = None,
        effect_id: int = None,
        reply_parameters: "types.ReplyParameters" = None,
        progress: Callable = None,
        progress_args: tuple = (),

        reply_to_message_id: int = None,
        quote_text: str = None,
        quote_entities: List["types.MessageEntity"] = None,
    ) -> "Message":
        """Bound method *reply_animation* :obj:`~pyrogram.types.Message`.

        Use as a shortcut for:

        .. code-block:: python

            await client.send_animation(
                chat_id=message.chat.id,
                animation=animation
            )

        Example:
            .. code-block:: python

                await message.reply_animation(animation)

        Parameters:
            animation (``str``):
                Animation to send.
                Pass a file_id as string to send an animation that exists on the Telegram servers,
                pass an HTTP URL as a string for Telegram to get an animation from the Internet, or
                pass a file path as string to upload a new animation that exists on your local machine.

            quote (``bool``, *optional*):
                If ``True``, the message will be sent as a reply to this message.
                If *reply_parameters* is passed, this parameter will be ignored.
                Defaults to ``True`` in group chats and ``False`` in private chats.

            caption (``str``, *optional*):
                Animation caption, 0-1024 characters.

            parse_mode (:obj:`~pyrogram.enums.ParseMode`, *optional*):
                By default, texts are parsed using both Markdown and HTML styles.
                You can combine both syntaxes together.

            caption_entities (List of :obj:`~pyrogram.types.MessageEntity`):
                List of special entities that appear in the caption, which can be specified instead of *parse_mode*.

            has_spoiler (``bool``, *optional*):
                Pass True if the animation needs to be covered with a spoiler animation.

            show_caption_above_media (``bool``, *optional*):
                Pass True, if the caption must be shown above the message media.

            duration (``int``, *optional*):
                Duration of sent animation in seconds.

            width (``int``, *optional*):
                Animation width.

            height (``int``, *optional*):
                Animation height.

            thumb (``str`` | ``BinaryIO``, *optional*):
                Thumbnail of the animation file sent.
                The thumbnail should be in JPEG format and less than 200 KB in size.
                A thumbnail's width and height should not exceed 320 pixels.
                Thumbnails can't be reused and can be only uploaded as a new file.

            disable_notification (``bool``, *optional*):
                Sends the message silently.
                Users will receive a notification with no sound.

            message_thread_id (``int``, *optional*):
                Unique identifier of a message thread to which the message belongs.
                For forums only.

            direct_messages_chat_topic_id (``int``, *optional*):
                Unique identifier of the topic in a channel direct messages chat administered by the current user.
                For directs only.

            effect_id (``int``, *optional*):
                Unique identifier of the message effect.
                For private chats only.

            reply_parameters (:obj:`~pyrogram.types.ReplyParameters`, *optional*):
                Describes reply parameters for the message that is being sent.

            business_connection_id (``str``, *optional*):
                Unique identifier of the business connection on behalf of which the message will be sent.

            allow_paid_broadcast (``bool``, *optional*):
                If True, you will be allowed to send up to 1000 messages per second.
                Ignoring broadcasting limits for a fee of 0.1 Telegram Stars per message.
                The relevant Stars will be withdrawn from the bot's balance.
                For bots only.

            paid_message_star_count (``int``, *optional*):
                The number of Telegram Stars the user agreed to pay to send the messages.

            reply_markup (:obj:`~pyrogram.types.InlineKeyboardMarkup` | :obj:`~pyrogram.types.ReplyKeyboardMarkup` | :obj:`~pyrogram.types.ReplyKeyboardRemove` | :obj:`~pyrogram.types.ForceReply`, *optional*):
                Additional interface options. An object for an inline keyboard, custom reply keyboard,
                instructions to remove reply keyboard or to force a reply from the user.

            progress (``Callable``, *optional*):
                Pass a callback function to view the file transmission progress.
                The function must take *(current, total)* as positional arguments (look at Other Parameters below for a
                detailed description) and will be called back each time a new file chunk has been successfully
                transmitted.

            progress_args (``tuple``, *optional*):
                Extra custom arguments for the progress callback function.
                You can pass anything you need to be available in the progress callback scope; for example, a Message
                object or a Client instance in order to edit the message with the updated progress status.

        Other Parameters:
            current (``int``):
                The amount of bytes transmitted so far.

            total (``int``):
                The total size of the file.

            *args (``tuple``, *optional*):
                Extra custom arguments as defined in the ``progress_args`` parameter.
                You can either keep ``*args`` or add every single extra argument in your function signature.

        Returns:
            On success, the sent :obj:`~pyrogram.types.Message` is returned.
            In case the upload is deliberately stopped with :meth:`~pyrogram.Client.stop_transmission`, None is returned
            instead.

        Raises:
            RPCError: In case of a Telegram RPC error.
        """
        if quote is None:
            quote = self.chat.type != enums.ChatType.PRIVATE

        if reply_parameters is None and quote:
            reply_parameters = types.ReplyParameters(
                message_id=self.id
            )

        if message_thread_id is None:
            message_thread_id = self.message_thread_id

        if direct_messages_chat_topic_id is None:
            direct_messages_chat_topic_id = self.direct_messages_chat_topic_id

        if business_connection_id is None:
            business_connection_id = self.business_connection_id

        return await self._client.send_animation(
            chat_id=self.chat.id,
            animation=animation,
            caption=caption,
            parse_mode=parse_mode,
            caption_entities=caption_entities,
            has_spoiler=has_spoiler,
            show_caption_above_media=show_caption_above_media,
            duration=duration,
            width=width,
            height=height,
            thumb=thumb,
            disable_notification=disable_notification,
            message_thread_id=message_thread_id,
            direct_messages_chat_topic_id=direct_messages_chat_topic_id,
            effect_id=effect_id,
            reply_parameters=reply_parameters,
            business_connection_id=business_connection_id,
            allow_paid_broadcast=allow_paid_broadcast,
            paid_message_star_count=paid_message_star_count,
            reply_markup=reply_markup,
            progress=progress,
            progress_args=progress_args,

            reply_to_message_id=reply_to_message_id,
            quote_text=quote_text,
            quote_entities=quote_entities,
        )

    async def reply_audio(
        self,
        audio: Union[str, BinaryIO],
        quote: bool = None,
        caption: str = "",
        parse_mode: Optional["enums.ParseMode"] = None,
        caption_entities: List["types.MessageEntity"] = None,
        duration: int = 0,
        performer: str = None,
        title: str = None,
        thumb: Union[str, BinaryIO] = None,
        disable_notification: bool = None,
        message_thread_id: int = None,
        direct_messages_chat_topic_id: int = None,
        effect_id: int = None,
        reply_parameters: "types.ReplyParameters" = None,
        business_connection_id: str = None,
        allow_paid_broadcast: bool = None,
        paid_message_star_count: int = None,
        reply_markup: Union[
            "types.InlineKeyboardMarkup",
            "types.ReplyKeyboardMarkup",
            "types.ReplyKeyboardRemove",
            "types.ForceReply"
        ] = None,
        progress: Callable = None,
        progress_args: tuple = (),

        reply_to_message_id: int = None,
        quote_text: str = None,
        quote_entities: List["types.MessageEntity"] = None,
    ) -> "Message":
        """Bound method *reply_audio* of :obj:`~pyrogram.types.Message`.

        Use as a shortcut for:

        .. code-block:: python

            await client.send_audio(
                chat_id=message.chat.id,
                audio=audio
            )

        Example:
            .. code-block:: python

                await message.reply_audio(audio)

        Parameters:
            audio (``str``):
                Audio file to send.
                Pass a file_id as string to send an audio file that exists on the Telegram servers,
                pass an HTTP URL as a string for Telegram to get an audio file from the Internet, or
                pass a file path as string to upload a new audio file that exists on your local machine.

            quote (``bool``, *optional*):
                If ``True``, the message will be sent as a reply to this message.
                If *reply_parameters* is passed, this parameter will be ignored.
                Defaults to ``True`` in group chats and ``False`` in private chats.

            caption (``str``, *optional*):
                Audio caption, 0-1024 characters.

            parse_mode (:obj:`~pyrogram.enums.ParseMode`, *optional*):
                By default, texts are parsed using both Markdown and HTML styles.
                You can combine both syntaxes together.

            caption_entities (List of :obj:`~pyrogram.types.MessageEntity`):
                List of special entities that appear in the caption, which can be specified instead of *parse_mode*.

            duration (``int``, *optional*):
                Duration of the audio in seconds.

            performer (``str``, *optional*):
                Performer.

            title (``str``, *optional*):
                Track name.

            thumb (``str`` | ``BinaryIO``, *optional*):
                Thumbnail of the music file album cover.
                The thumbnail should be in JPEG format and less than 200 KB in size.
                A thumbnail's width and height should not exceed 320 pixels.
                Thumbnails can't be reused and can be only uploaded as a new file.

            disable_notification (``bool``, *optional*):
                Sends the message silently.
                Users will receive a notification with no sound.

            message_thread_id (``int``, *optional*):
                Unique identifier of a message thread to which the message belongs.
                For forums only.

            direct_messages_chat_topic_id (``int``, *optional*):
                Unique identifier of the topic in a channel direct messages chat administered by the current user.
                For directs only.

            effect_id (``int``, *optional*):
                Unique identifier of the message effect.
                For private chats only.

            reply_parameters (:obj:`~pyrogram.types.ReplyParameters`, *optional*):
                Describes reply parameters for the message that is being sent.

            business_connection_id (``str``, *optional*):
                Unique identifier of the business connection on behalf of which the message will be sent.

            allow_paid_broadcast (``bool``, *optional*):
                If True, you will be allowed to send up to 1000 messages per second.
                Ignoring broadcasting limits for a fee of 0.1 Telegram Stars per message.
                The relevant Stars will be withdrawn from the bot's balance.
                For bots only.

            paid_message_star_count (``int``, *optional*):
                The number of Telegram Stars the user agreed to pay to send the messages.

            reply_markup (:obj:`~pyrogram.types.InlineKeyboardMarkup` | :obj:`~pyrogram.types.ReplyKeyboardMarkup` | :obj:`~pyrogram.types.ReplyKeyboardRemove` | :obj:`~pyrogram.types.ForceReply`, *optional*):
                Additional interface options. An object for an inline keyboard, custom reply keyboard,
                instructions to remove reply keyboard or to force a reply from the user.

            progress (``Callable``, *optional*):
                Pass a callback function to view the file transmission progress.
                The function must take *(current, total)* as positional arguments (look at Other Parameters below for a
                detailed description) and will be called back each time a new file chunk has been successfully
                transmitted.

            progress_args (``tuple``, *optional*):
                Extra custom arguments for the progress callback function.
                You can pass anything you need to be available in the progress callback scope; for example, a Message
                object or a Client instance in order to edit the message with the updated progress status.

        Other Parameters:
            current (``int``):
                The amount of bytes transmitted so far.

            total (``int``):
                The total size of the file.

            *args (``tuple``, *optional*):
                Extra custom arguments as defined in the ``progress_args`` parameter.
                You can either keep ``*args`` or add every single extra argument in your function signature.

        Returns:
            On success, the sent :obj:`~pyrogram.types.Message` is returned.
            In case the upload is deliberately stopped with :meth:`~pyrogram.Client.stop_transmission`, None is returned
            instead.

        Raises:
            RPCError: In case of a Telegram RPC error.
        """
        if quote is None:
            quote = self.chat.type != enums.ChatType.PRIVATE

        if reply_parameters is None and quote:
            reply_parameters = types.ReplyParameters(
                message_id=self.id
            )

        if message_thread_id is None:
            message_thread_id = self.message_thread_id

        if direct_messages_chat_topic_id is None:
            direct_messages_chat_topic_id = self.direct_messages_chat_topic_id

        if business_connection_id is None:
            business_connection_id = self.business_connection_id

        return await self._client.send_audio(
            chat_id=self.chat.id,
            audio=audio,
            caption=caption,
            parse_mode=parse_mode,
            caption_entities=caption_entities,
            duration=duration,
            performer=performer,
            title=title,
            thumb=thumb,
            disable_notification=disable_notification,
            message_thread_id=message_thread_id,
            direct_messages_chat_topic_id=direct_messages_chat_topic_id,
            effect_id=effect_id,
            reply_parameters=reply_parameters,
            business_connection_id=business_connection_id,
            allow_paid_broadcast=allow_paid_broadcast,
            paid_message_star_count=paid_message_star_count,
            reply_markup=reply_markup,
            progress=progress,
            progress_args=progress_args,

            reply_to_message_id=reply_to_message_id,
            quote_text=quote_text,
            quote_entities=quote_entities,
        )

    async def reply_cached_media(
        self,
        file_id: str,
        quote: bool = None,
        caption: str = "",
        parse_mode: Optional["enums.ParseMode"] = None,
        caption_entities: List["types.MessageEntity"] = None,
        disable_notification: bool = None,
        message_thread_id: int = None,
        direct_messages_chat_topic_id: int = None,
        reply_parameters: "types.ReplyParameters" = None,
        business_connection_id: str = None,
        allow_paid_broadcast: bool = None,
        paid_message_star_count: int = None,
        reply_markup: Union[
            "types.InlineKeyboardMarkup",
            "types.ReplyKeyboardMarkup",
            "types.ReplyKeyboardRemove",
            "types.ForceReply"
        ] = None,

        reply_to_message_id: int = None,
        quote_text: str = None,
        quote_entities: List["types.MessageEntity"] = None,
    ) -> "Message":
        """Bound method *reply_cached_media* of :obj:`~pyrogram.types.Message`.

        Use as a shortcut for:

        .. code-block:: python

            await client.send_cached_media(
                chat_id=message.chat.id,
                file_id=file_id
            )

        Example:
            .. code-block:: python

                await message.reply_cached_media(file_id)

        Parameters:
            file_id (``str``):
                Media to send.
                Pass a file_id as string to send a media that exists on the Telegram servers.

            quote (``bool``, *optional*):
                If ``True``, the message will be sent as a reply to this message.
                If *reply_parameters* is passed, this parameter will be ignored.
                Defaults to ``True`` in group chats and ``False`` in private chats.

            caption (``bool``, *optional*):
                Media caption, 0-1024 characters.

            parse_mode (:obj:`~pyrogram.enums.ParseMode`, *optional*):
                By default, texts are parsed using both Markdown and HTML styles.
                You can combine both syntaxes together.

            caption_entities (List of :obj:`~pyrogram.types.MessageEntity`):
                List of special entities that appear in the caption, which can be specified instead of *parse_mode*.

            disable_notification (``bool``, *optional*):
                Sends the message silently.
                Users will receive a notification with no sound.

            message_thread_id (``int``, *optional*):
                Unique identifier of a message thread to which the message belongs.
                For forums only.

            direct_messages_chat_topic_id (``int``, *optional*):
                Unique identifier of the topic in a channel direct messages chat administered by the current user.
                For directs only.

            reply_parameters (:obj:`~pyrogram.types.ReplyParameters`, *optional*):
                Describes reply parameters for the message that is being sent.

            business_connection_id (``str``, *optional*):
                Unique identifier of the business connection on behalf of which the message will be sent.

            allow_paid_broadcast (``bool``, *optional*):
                If True, you will be allowed to send up to 1000 messages per second.
                Ignoring broadcasting limits for a fee of 0.1 Telegram Stars per message.
                The relevant Stars will be withdrawn from the bot's balance.
                For bots only.

            paid_message_star_count (``int``, *optional*):
                The number of Telegram Stars the user agreed to pay to send the messages.

            reply_markup (:obj:`~pyrogram.types.InlineKeyboardMarkup` | :obj:`~pyrogram.types.ReplyKeyboardMarkup` | :obj:`~pyrogram.types.ReplyKeyboardRemove` | :obj:`~pyrogram.types.ForceReply`, *optional*):
                Additional interface options. An object for an inline keyboard, custom reply keyboard,
                instructions to remove reply keyboard or to force a reply from the user.

        Returns:
            On success, the sent :obj:`~pyrogram.types.Message` is returned.

        Raises:
            RPCError: In case of a Telegram RPC error.
        """
        if quote is None:
            quote = self.chat.type != enums.ChatType.PRIVATE

        if reply_parameters is None and quote:
            reply_parameters = types.ReplyParameters(
                message_id=self.id
            )

        if message_thread_id is None:
            message_thread_id = self.message_thread_id

        if direct_messages_chat_topic_id is None:
            direct_messages_chat_topic_id = self.direct_messages_chat_topic_id

        if business_connection_id is None:
            business_connection_id = self.business_connection_id

        return await self._client.send_cached_media(
            chat_id=self.chat.id,
            file_id=file_id,
            caption=caption,
            parse_mode=parse_mode,
            caption_entities=caption_entities,
            disable_notification=disable_notification,
            message_thread_id=message_thread_id,
            direct_messages_chat_topic_id=direct_messages_chat_topic_id,
            reply_parameters=reply_parameters,
            business_connection_id=business_connection_id,
            allow_paid_broadcast=allow_paid_broadcast,
            paid_message_star_count=paid_message_star_count,
            reply_markup=reply_markup,

            reply_to_message_id=reply_to_message_id,
            quote_text=quote_text,
            quote_entities=quote_entities,
        )

    async def reply_chat_action(
        self,
        action: "enums.ChatAction",
        business_connection_id: str = None
    ) -> bool:
        """Bound method *reply_chat_action* of :obj:`~pyrogram.types.Message`.

        Use as a shortcut for:

        .. code-block:: python

            from pyrogram import enums

            await client.send_chat_action(
                chat_id=message.chat.id,
                action=enums.ChatAction.TYPING
            )

        Example:
            .. code-block:: python

                from pyrogram import enums

                await message.reply_chat_action(enums.ChatAction.TYPING)

        Parameters:
            action (:obj:`~pyrogram.enums.ChatAction`):
                Type of action to broadcast.

            business_connection_id (``str``, *optional*):
                Unique identifier of the business connection on behalf of which the message will be sent.

        Returns:
            ``bool``: On success, True is returned.

        Raises:
            RPCError: In case of a Telegram RPC error.
            ValueError: In case the provided string is not a valid chat action.
        """
        if business_connection_id is None:
            business_connection_id = self.business_connection_id

        return await self._client.send_chat_action(
            chat_id=self.chat.id,
            action=action,
            business_connection_id=business_connection_id
        )

    async def reply_contact(
        self,
        phone_number: str,
        first_name: str,
        quote: bool = None,
        last_name: str = "",
        vcard: str = "",
        disable_notification: bool = None,
        message_thread_id: int = None,
        direct_messages_chat_topic_id: int = None,
        effect_id: int = None,
        reply_parameters: "types.ReplyParameters" = None,
        business_connection_id: str = None,
        allow_paid_broadcast: bool = None,
        paid_message_star_count: int = None,
        reply_markup: Union[
            "types.InlineKeyboardMarkup",
            "types.ReplyKeyboardMarkup",
            "types.ReplyKeyboardRemove",
            "types.ForceReply"
        ] = None,

        reply_to_message_id: int = None,
        quote_text: str = None,
        parse_mode: Optional["enums.ParseMode"] = None,
        quote_entities: List["types.MessageEntity"] = None,
    ) -> "Message":
        """Bound method *reply_contact* of :obj:`~pyrogram.types.Message`.

        Use as a shortcut for:

        .. code-block:: python

            await client.send_contact(
                chat_id=message.chat.id,
                phone_number=phone_number,
                first_name=first_name
            )

        Example:
            .. code-block:: python

                await message.reply_contact("+1-123-456-7890", "Name")

        Parameters:
            phone_number (``str``):
                Contact's phone number.

            first_name (``str``):
                Contact's first name.

            quote (``bool``, *optional*):
                If ``True``, the message will be sent as a reply to this message.
                If *reply_parameters* is passed, this parameter will be ignored.
                Defaults to ``True`` in group chats and ``False`` in private chats.

            last_name (``str``, *optional*):
                Contact's last name.

            vcard (``str``, *optional*):
                Additional data about the contact in the form of a vCard, 0-2048 bytes

            disable_notification (``bool``, *optional*):
                Sends the message silently.
                Users will receive a notification with no sound.

            message_thread_id (``int``, *optional*):
                Unique identifier of a message thread to which the message belongs.
                For forums only.

            direct_messages_chat_topic_id (``int``, *optional*):
                Unique identifier of the topic in a channel direct messages chat administered by the current user.
                For directs only.

            effect_id (``int``, *optional*):
                Unique identifier of the message effect.
                For private chats only.

            reply_parameters (:obj:`~pyrogram.types.ReplyParameters`, *optional*):
                Describes reply parameters for the message that is being sent.

            business_connection_id (``str``, *optional*):
                Unique identifier of the business connection on behalf of which the message will be sent.

            allow_paid_broadcast (``bool``, *optional*):
                If True, you will be allowed to send up to 1000 messages per second.
                Ignoring broadcasting limits for a fee of 0.1 Telegram Stars per message.
                The relevant Stars will be withdrawn from the bot's balance.
                For bots only.

            paid_message_star_count (``int``, *optional*):
                The number of Telegram Stars the user agreed to pay to send the messages.

            reply_markup (:obj:`~pyrogram.types.InlineKeyboardMarkup` | :obj:`~pyrogram.types.ReplyKeyboardMarkup` | :obj:`~pyrogram.types.ReplyKeyboardRemove` | :obj:`~pyrogram.types.ForceReply`, *optional*):
                Additional interface options. An object for an inline keyboard, custom reply keyboard,
                instructions to remove reply keyboard or to force a reply from the user.

        Returns:
            On success, the sent :obj:`~pyrogram.types.Message` is returned.

        Raises:
            RPCError: In case of a Telegram RPC error.
        """
        if quote is None:
            quote = self.chat.type != enums.ChatType.PRIVATE

        if reply_parameters is None and quote:
            reply_parameters = types.ReplyParameters(
                message_id=self.id
            )

        if message_thread_id is None:
            message_thread_id = self.message_thread_id

        if direct_messages_chat_topic_id is None:
            direct_messages_chat_topic_id = self.direct_messages_chat_topic_id

        if business_connection_id is None:
            business_connection_id = self.business_connection_id

        return await self._client.send_contact(
            chat_id=self.chat.id,
            phone_number=phone_number,
            first_name=first_name,
            last_name=last_name,
            vcard=vcard,
            disable_notification=disable_notification,
            message_thread_id=message_thread_id,
            direct_messages_chat_topic_id=direct_messages_chat_topic_id,
            effect_id=effect_id,
            reply_parameters=reply_parameters,
            business_connection_id=business_connection_id,
            allow_paid_broadcast=allow_paid_broadcast,
            paid_message_star_count=paid_message_star_count,
            reply_markup=reply_markup,

            reply_to_message_id=reply_to_message_id,
            quote_text=quote_text,
            parse_mode=parse_mode,
            quote_entities=quote_entities,
        )

    async def reply_document(
        self,
        document: Union[str, BinaryIO],
        quote: bool = None,
        thumb: Union[str, BinaryIO] = None,
        caption: str = "",
        parse_mode: Optional["enums.ParseMode"] = None,
        caption_entities: List["types.MessageEntity"] = None,
        file_name: str = None,
        force_document: bool = None,
        disable_notification: bool = None,
        message_thread_id: int = None,
        direct_messages_chat_topic_id: int = None,
        effect_id: int = None,
        reply_parameters: "types.ReplyParameters" = None,
        schedule_date: datetime = None,
        protect_content: bool = None,
        business_connection_id: str = None,
        allow_paid_broadcast: bool = None,
        paid_message_star_count: int = None,
        reply_markup: Union[
            "types.InlineKeyboardMarkup",
            "types.ReplyKeyboardMarkup",
            "types.ReplyKeyboardRemove",
            "types.ForceReply"
        ] = None,
        progress: Callable = None,
        progress_args: tuple = (),

        reply_to_message_id: int = None,
        quote_text: str = None,
        quote_entities: List["types.MessageEntity"] = None,
    ) -> "Message":
        """Bound method *reply_document* of :obj:`~pyrogram.types.Message`.

        Use as a shortcut for:

        .. code-block:: python

            await client.send_document(
                chat_id=message.chat.id,
                document=document
            )

        Example:
            .. code-block:: python

                await message.reply_document(document)

        Parameters:
            document (``str``):
                File to send.
                Pass a file_id as string to send a file that exists on the Telegram servers,
                pass an HTTP URL as a string for Telegram to get a file from the Internet, or
                pass a file path as string to upload a new file that exists on your local machine.

            quote (``bool``, *optional*):
                If ``True``, the message will be sent as a reply to this message.
                If *reply_parameters* is passed, this parameter will be ignored.
                Defaults to ``True`` in group chats and ``False`` in private chats.

            thumb (``str`` | ``BinaryIO``, *optional*):
                Thumbnail of the file sent.
                The thumbnail should be in JPEG format and less than 200 KB in size.
                A thumbnail's width and height should not exceed 320 pixels.
                Thumbnails can't be reused and can be only uploaded as a new file.

            caption (``str``, *optional*):
                Document caption, 0-1024 characters.

            parse_mode (:obj:`~pyrogram.enums.ParseMode`, *optional*):
                By default, texts are parsed using both Markdown and HTML styles.
                You can combine both syntaxes together.

            caption_entities (List of :obj:`~pyrogram.types.MessageEntity`):
                List of special entities that appear in the caption, which can be specified instead of *parse_mode*.

            file_name (``str``, *optional*):
                File name of the document sent.
                Defaults to file's path basename.

            force_document (``bool``, *optional*):
                Pass True to force sending files as document. Useful for video files that need to be sent as
                document messages instead of video messages.
                Defaults to False.

            disable_notification (``bool``, *optional*):
                Sends the message silently.
                Users will receive a notification with no sound.

            message_thread_id (``int``, *optional*):
                Unique identifier of a message thread to which the message belongs.
                For forums only.

            direct_messages_chat_topic_id (``int``, *optional*):
                Unique identifier of the topic in a channel direct messages chat administered by the current user.
                For directs only.

            effect_id (``int``, *optional*):
                Unique identifier of the message effect.
                For private chats only.

            reply_parameters (:obj:`~pyrogram.types.ReplyParameters`, *optional*):
                Describes reply parameters for the message that is being sent.

            schedule_date (:py:obj:`~datetime.datetime`, *optional*):
                Date when the message will be automatically sent.

            protect_content (``bool``, *optional*):
                Protects the contents of the sent message from forwarding and saving.

            business_connection_id (``str``, *optional*):
                Unique identifier of the business connection on behalf of which the message will be sent.

            allow_paid_broadcast (``bool``, *optional*):
                If True, you will be allowed to send up to 1000 messages per second.
                Ignoring broadcasting limits for a fee of 0.1 Telegram Stars per message.
                The relevant Stars will be withdrawn from the bot's balance.
                For bots only.

            paid_message_star_count (``int``, *optional*):
                The number of Telegram Stars the user agreed to pay to send the messages.

            reply_markup (:obj:`~pyrogram.types.InlineKeyboardMarkup` | :obj:`~pyrogram.types.ReplyKeyboardMarkup` | :obj:`~pyrogram.types.ReplyKeyboardRemove` | :obj:`~pyrogram.types.ForceReply`, *optional*):
                Additional interface options. An object for an inline keyboard, custom reply keyboard,
                instructions to remove reply keyboard or to force a reply from the user.

            progress (``Callable``, *optional*):
                Pass a callback function to view the file transmission progress.
                The function must take *(current, total)* as positional arguments (look at Other Parameters below for a
                detailed description) and will be called back each time a new file chunk has been successfully
                transmitted.

            progress_args (``tuple``, *optional*):
                Extra custom arguments for the progress callback function.
                You can pass anything you need to be available in the progress callback scope; for example, a Message
                object or a Client instance in order to edit the message with the updated progress status.

        Other Parameters:
            current (``int``):
                The amount of bytes transmitted so far.

            total (``int``):
                The total size of the file.

            *args (``tuple``, *optional*):
                Extra custom arguments as defined in the ``progress_args`` parameter.
                You can either keep ``*args`` or add every single extra argument in your function signature.

        Returns:
            On success, the sent :obj:`~pyrogram.types.Message` is returned.
            In case the upload is deliberately stopped with :meth:`~pyrogram.Client.stop_transmission`, None is returned
            instead.

        Raises:
            RPCError: In case of a Telegram RPC error.
        """
        if quote is None:
            quote = self.chat.type != enums.ChatType.PRIVATE

        if reply_parameters is None and quote:
            reply_parameters = types.ReplyParameters(
                message_id=self.id
            )

        if message_thread_id is None:
            message_thread_id = self.message_thread_id

        if direct_messages_chat_topic_id is None:
            direct_messages_chat_topic_id = self.direct_messages_chat_topic_id

        if business_connection_id is None:
            business_connection_id = self.business_connection_id

        return await self._client.send_document(
            chat_id=self.chat.id,
            document=document,
            thumb=thumb,
            caption=caption,
            parse_mode=parse_mode,
            caption_entities=caption_entities,
            file_name=file_name,
            force_document=force_document,
            disable_notification=disable_notification,
            message_thread_id=message_thread_id,
            direct_messages_chat_topic_id=direct_messages_chat_topic_id,
            effect_id=effect_id,
            reply_parameters=reply_parameters,
            schedule_date=schedule_date,
            protect_content=protect_content,
            business_connection_id=business_connection_id,
            allow_paid_broadcast=allow_paid_broadcast,
            paid_message_star_count=paid_message_star_count,
            reply_markup=reply_markup,
            progress=progress,
            progress_args=progress_args,

            reply_to_message_id=reply_to_message_id,
            quote_text=quote_text,
            quote_entities=quote_entities,
        )

    async def reply_game(
        self,
        game_short_name: str,
        quote: bool = None,
        disable_notification: bool = None,
        message_thread_id: int = None,
        effect_id: int = None,
        reply_parameters: "types.ReplyParameters" = None,
        allow_paid_broadcast: bool = None,
        reply_markup: Union[
            "types.InlineKeyboardMarkup",
            "types.ReplyKeyboardMarkup",
            "types.ReplyKeyboardRemove",
            "types.ForceReply"
        ] = None,

        reply_to_message_id: int = None,
    ) -> "Message":
        """Bound method *reply_game* of :obj:`~pyrogram.types.Message`.

        Use as a shortcut for:

        .. code-block:: python

            await client.send_game(
                chat_id=message.chat.id,
                game_short_name="lumberjack"
            )

        Example:
            .. code-block:: python

                await message.reply_game("lumberjack")

        Parameters:
            game_short_name (``str``):
                Short name of the game, serves as the unique identifier for the game. Set up your games via Botfather.

            quote (``bool``, *optional*):
                If ``True``, the message will be sent as a reply to this message.
                If *reply_parameters* is passed, this parameter will be ignored.
                Defaults to ``True`` in group chats and ``False`` in private chats.

            disable_notification (``bool``, *optional*):
                Sends the message silently.
                Users will receive a notification with no sound.

            message_thread_id (``int``, *optional*):
                Unique identifier of a message thread to which the message belongs.
                For supergroups only.

            effect_id (``int``, *optional*):
                Unique identifier of the message effect.
                For private chats only.

            reply_parameters (:obj:`~pyrogram.types.ReplyParameters`, *optional*):
                Describes reply parameters for the message that is being sent.

            allow_paid_broadcast (``bool``, *optional*):
                If True, you will be allowed to send up to 1000 messages per second.
                Ignoring broadcasting limits for a fee of 0.1 Telegram Stars per message.
                The relevant Stars will be withdrawn from the bot's balance.
                For bots only.

            reply_markup (:obj:`~pyrogram.types.InlineKeyboardMarkup`, *optional*):
                An object for an inline keyboard. If empty, one ‘Play game_title’ button will be shown automatically.
                If not empty, the first button must launch the game.

        Returns:
            On success, the sent :obj:`~pyrogram.types.Message` is returned.

        Raises:
            RPCError: In case of a Telegram RPC error.
        """
        if quote is None:
            quote = self.chat.type != enums.ChatType.PRIVATE

        if reply_parameters is None and quote:
            reply_parameters = types.ReplyParameters(
                message_id=self.id
            )

        if message_thread_id is None:
            message_thread_id = self.message_thread_id

        return await self._client.send_game(
            chat_id=self.chat.id,
            game_short_name=game_short_name,
            disable_notification=disable_notification,
            message_thread_id=message_thread_id,
            effect_id=effect_id,
            reply_parameters=reply_parameters,
            allow_paid_broadcast=allow_paid_broadcast,
            reply_markup=reply_markup,

            reply_to_message_id=reply_to_message_id,
        )

    async def reply_inline_bot_result(
        self,
        query_id: int,
        result_id: str,
        quote: bool = None,
        disable_notification: bool = None,
        message_thread_id: bool = None,
        direct_messages_chat_topic_id: int = None,
        reply_parameters: "types.ReplyParameters" = None,
        paid_message_star_count: int = None,

        reply_to_message_id: int = None,
        quote_text: str = None,
        parse_mode: Optional["enums.ParseMode"] = None,
        quote_entities: List["types.MessageEntity"] = None,
    ) -> "Message":
        """Bound method *reply_inline_bot_result* of :obj:`~pyrogram.types.Message`.

        Use as a shortcut for:

        .. code-block:: python

            await client.send_inline_bot_result(
                chat_id=message.chat.id,
                query_id=query_id,
                result_id=result_id
            )

        Example:
            .. code-block:: python

                await message.reply_inline_bot_result(query_id, result_id)

        Parameters:
            query_id (``int``):
                Unique identifier for the answered query.

            result_id (``str``):
                Unique identifier for the result that was chosen.

            quote (``bool``, *optional*):
                If ``True``, the message will be sent as a reply to this message.
                If *reply_parameters* is passed, this parameter will be ignored.
                Defaults to ``True`` in group chats and ``False`` in private chats.

            disable_notification (``bool``, *optional*):
                Sends the message silently.
                Users will receive a notification with no sound.

            message_thread_id (``int``, *optional*):
                Unique identifier of a message thread to which the message belongs.
                For forums only.

            direct_messages_chat_topic_id (``int``, *optional*):
                Unique identifier of the topic in a channel direct messages chat administered by the current user.
                For directs only.

            reply_parameters (:obj:`~pyrogram.types.ReplyParameters`, *optional*):
                Describes reply parameters for the message that is being sent.

            paid_message_star_count (``int``, *optional*):
                The number of Telegram Stars the user agreed to pay to send the messages.

        Returns:
            On success, the sent Message is returned.

        Raises:
            RPCError: In case of a Telegram RPC error.
        """
        if quote is None:
            quote = self.chat.type != enums.ChatType.PRIVATE

        if reply_parameters is None and quote:
            reply_parameters = types.ReplyParameters(
                message_id=self.id
            )

        if message_thread_id is None:
            message_thread_id = self.message_thread_id

        if direct_messages_chat_topic_id is None:
            direct_messages_chat_topic_id = self.direct_messages_chat_topic_id

        return await self._client.send_inline_bot_result(
            chat_id=self.chat.id,
            query_id=query_id,
            result_id=result_id,
            disable_notification=disable_notification,
            message_thread_id=message_thread_id,
            direct_messages_chat_topic_id=direct_messages_chat_topic_id,
            reply_parameters=reply_parameters,
            paid_message_star_count=paid_message_star_count,

            reply_to_message_id=reply_to_message_id,
            quote_text=quote_text,
            parse_mode=parse_mode,
            quote_entities=quote_entities,
        )

    async def reply_location(
        self,
        latitude: float,
        longitude: float,
        quote: bool = None,
        disable_notification: bool = None,
        message_thread_id: int = None,
        direct_messages_chat_topic_id: int = None,
        effect_id: int = None,
        reply_parameters: "types.ReplyParameters" = None,
        business_connection_id: str = None,
        allow_paid_broadcast: bool = None,
        paid_message_star_count: int = None,
        reply_markup: Union[
            "types.InlineKeyboardMarkup",
            "types.ReplyKeyboardMarkup",
            "types.ReplyKeyboardRemove",
            "types.ForceReply"
        ] = None,

        reply_to_message_id: int = None,
        quote_text: str = None,
        quote_entities: List["types.MessageEntity"] = None,
    ) -> "Message":
        """Bound method *reply_location* of :obj:`~pyrogram.types.Message`.

        Use as a shortcut for:

        .. code-block:: python

            await client.send_location(
                chat_id=message.chat.id,
                latitude=latitude,
                longitude=longitude
            )

        Example:
            .. code-block:: python

                await message.reply_location(latitude, longitude)

        Parameters:
            latitude (``float``):
                Latitude of the location.

            longitude (``float``):
                Longitude of the location.

            quote (``bool``, *optional*):
                If ``True``, the message will be sent as a reply to this message.
                If *reply_parameters* is passed, this parameter will be ignored.
                Defaults to ``True`` in group chats and ``False`` in private chats.

            disable_notification (``bool``, *optional*):
                Sends the message silently.
                Users will receive a notification with no sound.

            message_thread_id (``int``, *optional*):
                Unique identifier of a message thread to which the message belongs.
                For forums only.

            direct_messages_chat_topic_id (``int``, *optional*):
                Unique identifier of the topic in a channel direct messages chat administered by the current user.
                For directs only.

            effect_id (``int``, *optional*):
                Unique identifier of the message effect.
                For private chats only.

            reply_parameters (:obj:`~pyrogram.types.ReplyParameters`, *optional*):
                Describes reply parameters for the message that is being sent.

            business_connection_id (``str``, *optional*):
                Unique identifier of the business connection on behalf of which the message will be sent.

            allow_paid_broadcast (``bool``, *optional*):
                If True, you will be allowed to send up to 1000 messages per second.
                Ignoring broadcasting limits for a fee of 0.1 Telegram Stars per message.
                The relevant Stars will be withdrawn from the bot's balance.
                For bots only.

            paid_message_star_count (``int``, *optional*):
                The number of Telegram Stars the user agreed to pay to send the messages.

            reply_markup (:obj:`~pyrogram.types.InlineKeyboardMarkup` | :obj:`~pyrogram.types.ReplyKeyboardMarkup` | :obj:`~pyrogram.types.ReplyKeyboardRemove` | :obj:`~pyrogram.types.ForceReply`, *optional*):
                Additional interface options. An object for an inline keyboard, custom reply keyboard,
                instructions to remove reply keyboard or to force a reply from the user.

        Returns:
            On success, the sent :obj:`~pyrogram.types.Message` is returned.

        Raises:
            RPCError: In case of a Telegram RPC error.
        """
        if quote is None:
            quote = self.chat.type != enums.ChatType.PRIVATE

        if reply_parameters is None and quote:
            reply_parameters = types.ReplyParameters(
                message_id=self.id
            )

        if message_thread_id is None:
            message_thread_id = self.message_thread_id

        if direct_messages_chat_topic_id is None:
            direct_messages_chat_topic_id = self.direct_messages_chat_topic_id

        if business_connection_id is None:
            business_connection_id = self.business_connection_id

        return await self._client.send_location(
            chat_id=self.chat.id,
            latitude=latitude,
            longitude=longitude,
            disable_notification=disable_notification,
            message_thread_id=message_thread_id,
            direct_messages_chat_topic_id=direct_messages_chat_topic_id,
            effect_id=effect_id,
            reply_parameters=reply_parameters,
            business_connection_id=business_connection_id,
            allow_paid_broadcast=allow_paid_broadcast,
            paid_message_star_count=paid_message_star_count,
            reply_markup=reply_markup,

            reply_to_message_id=reply_to_message_id,
            quote_text=quote_text,
            quote_entities=quote_entities,
        )

    async def reply_media_group(
        self,
        media: List[Union["types.InputMediaPhoto", "types.InputMediaVideo"]],
        quote: bool = None,
        disable_notification: bool = None,
        message_thread_id: int = None,
        direct_messages_chat_topic_id: int = None,
        effect_id: int = None,
        reply_parameters: "types.ReplyParameters" = None,
        allow_paid_broadcast: bool = None,
        paid_message_star_count: int = None,
        business_connection_id: str = None,

        reply_to_message_id: int = None,
        quote_text: str = None,
        parse_mode: Optional["enums.ParseMode"] = None,
        quote_entities: List["types.MessageEntity"] = None,
    ) -> List["types.Message"]:
        """Bound method *reply_media_group* of :obj:`~pyrogram.types.Message`.

        Use as a shortcut for:

        .. code-block:: python

            await client.send_media_group(
                chat_id=message.chat.id,
                media=list_of_media
            )

        Example:
            .. code-block:: python

                await message.reply_media_group(list_of_media)

        Parameters:
            media (``list``):
                A list containing either :obj:`~pyrogram.types.InputMediaPhoto` or
                :obj:`~pyrogram.types.InputMediaVideo` objects
                describing photos and videos to be sent, must include 2–10 items.

            quote (``bool``, *optional*):
                If ``True``, the message will be sent as a reply to this message.
                If *reply_parameters* is passed, this parameter will be ignored.
                Defaults to ``True`` in group chats and ``False`` in private chats.

            disable_notification (``bool``, *optional*):
                Sends the message silently.
                Users will receive a notification with no sound.

            message_thread_id (``int``, *optional*):
                Unique identifier of a message thread to which the message belongs.
                For forums only.

            direct_messages_chat_topic_id (``int``, *optional*):
                Unique identifier of the topic in a channel direct messages chat administered by the current user.
                For directs only.

            effect_id (``int``, *optional*):
                Unique identifier of the message effect.
                For private chats only.

            reply_parameters (:obj:`~pyrogram.types.ReplyParameters`, *optional*):
                Describes reply parameters for the message that is being sent.

            allow_paid_broadcast (``bool``, *optional*):
                If True, you will be allowed to send up to 1000 messages per second.
                Ignoring broadcasting limits for a fee of 0.1 Telegram Stars per message.
                The relevant Stars will be withdrawn from the bot's balance.
                For bots only.

            paid_message_star_count (``int``, *optional*):
                The number of Telegram Stars the user agreed to pay to send the messages.

            business_connection_id (``str``, *optional*):
                Unique identifier of the business connection on behalf of which the message will be sent.

        Returns:
            On success, a :obj:`~pyrogram.types.Messages` object is returned containing all the
            single messages sent.

        Raises:
            RPCError: In case of a Telegram RPC error.
        """
        if quote is None:
            quote = self.chat.type != enums.ChatType.PRIVATE

        if reply_parameters is None and quote:
            reply_parameters = types.ReplyParameters(
                message_id=self.id
            )

        if message_thread_id is None:
            message_thread_id = self.message_thread_id

        if direct_messages_chat_topic_id is None:
            direct_messages_chat_topic_id = self.direct_messages_chat_topic_id

        if business_connection_id is None:
            business_connection_id = self.business_connection_id

        return await self._client.send_media_group(
            chat_id=self.chat.id,
            media=media,
            disable_notification=disable_notification,
            message_thread_id=message_thread_id,
            direct_messages_chat_topic_id=direct_messages_chat_topic_id,
            effect_id=effect_id,
            reply_parameters=reply_parameters,
            allow_paid_broadcast=allow_paid_broadcast,
            paid_message_star_count=paid_message_star_count,
            business_connection_id=business_connection_id,

            reply_to_message_id=reply_to_message_id,
            quote_text=quote_text,
            parse_mode=parse_mode,
            quote_entities=quote_entities,
        )

    async def reply_photo(
        self,
        photo: Union[str, BinaryIO],
        quote: bool = None,
        caption: str = "",
        parse_mode: Optional["enums.ParseMode"] = None,
        caption_entities: List["types.MessageEntity"] = None,
        has_spoiler: bool = None,
        show_caption_above_media: bool = None,
        ttl_seconds: int = None,
        disable_notification: bool = None,
        message_thread_id: int = None,
        direct_messages_chat_topic_id: int = None,
        effect_id: int = None,
        reply_parameters: "types.ReplyParameters" = None,
        view_once: bool = None,
        business_connection_id: str = None,
        allow_paid_broadcast: bool = None,
        paid_message_star_count: int = None,
        reply_markup: Union[
            "types.InlineKeyboardMarkup",
            "types.ReplyKeyboardMarkup",
            "types.ReplyKeyboardRemove",
            "types.ForceReply"
        ] = None,
        progress: Callable = None,
        progress_args: tuple = (),

        reply_to_message_id: int = None,
        quote_text: str = None,
        quote_entities: List["types.MessageEntity"] = None,
    ) -> "Message":
        """Bound method *reply_photo* of :obj:`~pyrogram.types.Message`.

        Use as a shortcut for:

        .. code-block:: python

            await client.send_photo(
                chat_id=message.chat.id,
                photo=photo
            )

        Example:
            .. code-block:: python

                await message.reply_photo(photo)

        Parameters:
            photo (``str``):
                Photo to send.
                Pass a file_id as string to send a photo that exists on the Telegram servers,
                pass an HTTP URL as a string for Telegram to get a photo from the Internet, or
                pass a file path as string to upload a new photo that exists on your local machine.

            quote (``bool``, *optional*):
                If ``True``, the message will be sent as a reply to this message.
                If *reply_parameters* is passed, this parameter will be ignored.
                Defaults to ``True`` in group chats and ``False`` in private chats.

            caption (``str``, *optional*):
                Photo caption, 0-1024 characters.

            parse_mode (:obj:`~pyrogram.enums.ParseMode`, *optional*):
                By default, texts are parsed using both Markdown and HTML styles.
                You can combine both syntaxes together.

            caption_entities (List of :obj:`~pyrogram.types.MessageEntity`):
                List of special entities that appear in the caption, which can be specified instead of *parse_mode*.

            has_spoiler (``bool``, *optional*):
                Pass True if the photo needs to be covered with a spoiler animation.

            show_caption_above_media (``bool``, *optional*):
                Pass True, if the caption must be shown above the message media.

            ttl_seconds (``int``, *optional*):
                Self-Destruct Timer.
                If you set a timer, the photo will self-destruct in *ttl_seconds*
                seconds after it was viewed.

            disable_notification (``bool``, *optional*):
                Sends the message silently.
                Users will receive a notification with no sound.

            message_thread_id (``int``, *optional*):
                Unique identifier of a message thread to which the message belongs.
                For forums only.

            direct_messages_chat_topic_id (``int``, *optional*):
                Unique identifier of the topic in a channel direct messages chat administered by the current user.
                For directs only.

            effect_id (``int``, *optional*):
                Unique identifier of the message effect.
                For private chats only.

            reply_parameters (:obj:`~pyrogram.types.ReplyParameters`, *optional*):
                Describes reply parameters for the message that is being sent.

            view_once (``bool``, *optional*):
                Self-Destruct Timer.
                If True, the photo will self-destruct after it was viewed.

            business_connection_id (``str``, *optional*):
                Unique identifier of the business connection on behalf of which the message will be sent.

            allow_paid_broadcast (``bool``, *optional*):
                If True, you will be allowed to send up to 1000 messages per second.
                Ignoring broadcasting limits for a fee of 0.1 Telegram Stars per message.
                The relevant Stars will be withdrawn from the bot's balance.
                For bots only.

            paid_message_star_count (``int``, *optional*):
                The number of Telegram Stars the user agreed to pay to send the messages.

            reply_markup (:obj:`~pyrogram.types.InlineKeyboardMarkup` | :obj:`~pyrogram.types.ReplyKeyboardMarkup` | :obj:`~pyrogram.types.ReplyKeyboardRemove` | :obj:`~pyrogram.types.ForceReply`, *optional*):
                Additional interface options. An object for an inline keyboard, custom reply keyboard,
                instructions to remove reply keyboard or to force a reply from the user.

            progress (``Callable``, *optional*):
                Pass a callback function to view the file transmission progress.
                The function must take *(current, total)* as positional arguments (look at Other Parameters below for a
                detailed description) and will be called back each time a new file chunk has been successfully
                transmitted.

            progress_args (``tuple``, *optional*):
                Extra custom arguments for the progress callback function.
                You can pass anything you need to be available in the progress callback scope; for example, a Message
                object or a Client instance in order to edit the message with the updated progress status.

        Other Parameters:
            current (``int``):
                The amount of bytes transmitted so far.

            total (``int``):
                The total size of the file.

            *args (``tuple``, *optional*):
                Extra custom arguments as defined in the ``progress_args`` parameter.
                You can either keep ``*args`` or add every single extra argument in your function signature.

        Returns:
            On success, the sent :obj:`~pyrogram.types.Message` is returned.
            In case the upload is deliberately stopped with :meth:`~pyrogram.Client.stop_transmission`, None is returned
            instead.

        Raises:
            RPCError: In case of a Telegram RPC error.
        """
        if quote is None:
            quote = self.chat.type != enums.ChatType.PRIVATE

        if reply_parameters is None and quote:
            reply_parameters = types.ReplyParameters(
                message_id=self.id
            )

        if message_thread_id is None:
            message_thread_id = self.message_thread_id

        if direct_messages_chat_topic_id is None:
            direct_messages_chat_topic_id = self.direct_messages_chat_topic_id

        if business_connection_id is None:
            business_connection_id = self.business_connection_id

        return await self._client.send_photo(
            chat_id=self.chat.id,
            photo=photo,
            caption=caption,
            parse_mode=parse_mode,
            caption_entities=caption_entities,
            has_spoiler=has_spoiler,
            show_caption_above_media=show_caption_above_media,
            ttl_seconds=ttl_seconds,
            disable_notification=disable_notification,
            message_thread_id=message_thread_id,
            direct_messages_chat_topic_id=direct_messages_chat_topic_id,
            effect_id=effect_id,
            reply_parameters=reply_parameters,
            view_once=view_once,
            business_connection_id=business_connection_id,
            allow_paid_broadcast=allow_paid_broadcast,
            paid_message_star_count=paid_message_star_count,
            reply_markup=reply_markup,
            progress=progress,
            progress_args=progress_args,

            reply_to_message_id=reply_to_message_id,
            quote_text=quote_text,
            quote_entities=quote_entities,
        )

    async def reply_poll(
        self,
        question: str,
        options: List[str],
        is_anonymous: bool = True,
        type: "enums.PollType" = enums.PollType.REGULAR,
        allows_multiple_answers: bool = None,
        correct_option_id: int = None,
        question_parse_mode: Optional["enums.ParseMode"] = None,
        question_entities: Optional[List["types.MessageEntity"]] = None,
        explanation: str = None,
        explanation_parse_mode: "enums.ParseMode" = None,
        explanation_entities: List["types.MessageEntity"] = None,
        open_period: int = None,
        close_date: datetime = None,
        is_closed: bool = None,
        quote: bool = None,
        disable_notification: bool = None,
        protect_content: bool = None,
        message_thread_id: int = None,
        effect_id: int = None,
        reply_parameters: "types.ReplyParameters" = None,
        schedule_date: datetime = None,
        business_connection_id: str = None,
        options_parse_mode: List["types.MessageEntity"] = None,
        allow_paid_broadcast: bool = None,
        paid_message_star_count: int = None,
        reply_markup: Union[
            "types.InlineKeyboardMarkup",
            "types.ReplyKeyboardMarkup",
            "types.ReplyKeyboardRemove",
            "types.ForceReply"
        ] = None,

        reply_to_message_id: int = None,
        quote_text: str = None,
        quote_parse_mode: Optional["enums.ParseMode"] = None,
        quote_entities: List["types.MessageEntity"] = None,
        quote_offset: Optional[int] = None,
    ) -> "Message":
        """Bound method *reply_poll* of :obj:`~pyrogram.types.Message`.

        Use as a shortcut for:

        .. code-block:: python

            await client.send_poll(
                chat_id=message.chat.id,
                question="This is a poll",
                options=["A", "B", "C]
            )

        Example:
            .. code-block:: python

                await message.reply_poll("This is a poll", ["A", "B", "C"])

        Parameters:
            question (``str``):
                Poll question, 1-255 characters.

            options (List of ``str``):
                List of answer options, 2-10 strings 1-100 characters each.

            is_anonymous (``bool``, *optional*):
                True, if the poll needs to be anonymous.
                Defaults to True.

            type (:obj`~pyrogram.enums.PollType`, *optional*):
                Poll type, :obj:`~pyrogram.enums.PollType.QUIZ` or :obj:`~pyrogram.enums.PollType.REGULAR`.
                Defaults to :obj:`~pyrogram.enums.PollType.REGULAR`.

            allows_multiple_answers (``bool``, *optional*):
                True, if the poll allows multiple answers, ignored for polls in quiz mode.
                Defaults to False.

            correct_option_id (``int``, *optional*):
                0-based identifier of the correct answer option, required for polls in quiz mode.

            question_parse_mode (:obj:`~pyrogram.enums.ParseMode`, *optional*):
                By default, texts are parsed using both Markdown and HTML styles.
                You can combine both syntaxes together.

            question_entities (List of :obj:`~pyrogram.types.MessageEntity`):
                List of special entities that appear in the poll question, which can be specified instead of
                *parse_mode*.

            explanation (``str``, *optional*):
                Text that is shown when a user chooses an incorrect answer or taps on the lamp icon in a quiz-style
                poll, 0-200 characters with at most 2 line feeds after entities parsing.

            explanation_parse_mode (:obj:`~pyrogram.enums.ParseMode`, *optional*):
                By default, texts are parsed using both Markdown and HTML styles.
                You can combine both syntaxes together.

            explanation_entities (List of :obj:`~pyrogram.types.MessageEntity`):
                List of special entities that appear in the poll explanation, which can be specified instead of
                *parse_mode*.

            open_period (``int``, *optional*):
                Amount of time in seconds the poll will be active after creation, 5-600.
                Can't be used together with *close_date*.

            close_date (:py:obj:`~datetime.datetime`, *optional*):
                Point in time when the poll will be automatically closed.
                Must be at least 5 and no more than 600 seconds in the future.
                Can't be used together with *open_period*.

            is_closed (``bool``, *optional*):
                Pass True, if the poll needs to be immediately closed.
                This can be useful for poll preview.

            quote (``bool``, *optional*):
                If ``True``, the message will be sent as a reply to this message.
                If *reply_parameters* is passed, this parameter will be ignored.
                Defaults to ``True`` in group chats and ``False`` in private chats.

            disable_notification (``bool``, *optional*):
                Sends the message silently.
                Users will receive a notification with no sound.

            protect_content (``bool``, *optional*):
                Protects the contents of the sent message from forwarding and saving.

            message_thread_id (``int``, *optional*):
                Unique identifier of a message thread to which the message belongs.
                For supergroups only.

            effect_id (``int``, *optional*):
                Unique identifier of the message effect.
                For private chats only.

            reply_parameters (:obj:`~pyrogram.types.ReplyParameters`, *optional*):
                Describes reply parameters for the message that is being sent.

            schedule_date (:py:obj:`~datetime.datetime`, *optional*):
                Date when the message will be automatically sent.

            business_connection_id (``str``, *optional*):
                Unique identifier of the business connection on behalf of which the message will be sent.

            options_parse_mode (:obj:`~pyrogram.enums.ParseMode`, *optional*):
                By default, texts are parsed using both Markdown and HTML styles.
                You can combine both syntaxes together.

            allow_paid_broadcast (``bool``, *optional*):
                If True, you will be allowed to send up to 1000 messages per second.
                Ignoring broadcasting limits for a fee of 0.1 Telegram Stars per message.
                The relevant Stars will be withdrawn from the bot's balance.
                For bots only.

            paid_message_star_count (``int``, *optional*):
                The number of Telegram Stars the user agreed to pay to send the messages.

            reply_markup (:obj:`~pyrogram.types.InlineKeyboardMarkup` | :obj:`~pyrogram.types.ReplyKeyboardMarkup` | :obj:`~pyrogram.types.ReplyKeyboardRemove` | :obj:`~pyrogram.types.ForceReply`, *optional*):
                Additional interface options. An object for an inline keyboard, custom reply keyboard,
                instructions to remove reply keyboard or to force a reply from the user.

        Returns:
            On success, the sent :obj:`~pyrogram.types.Message` is returned.

        Raises:
            RPCError: In case of a Telegram RPC error.
        """
        if quote is None:
            quote = self.chat.type != enums.ChatType.PRIVATE

        if reply_parameters is None and quote:
            reply_parameters = types.ReplyParameters(
                message_id=self.id
            )

        if message_thread_id is None:
            message_thread_id = self.message_thread_id

        if business_connection_id is None:
            business_connection_id = self.business_connection_id

        return await self._client.send_poll(
            chat_id=self.chat.id,
            question=question,
            options=options,
            is_anonymous=is_anonymous,
            type=type,
            allows_multiple_answers=allows_multiple_answers,
            correct_option_id=correct_option_id,
            question_parse_mode=question_parse_mode,
            question_entities=question_entities,
            explanation=explanation,
            explanation_parse_mode=explanation_parse_mode,
            explanation_entities=explanation_entities,
            open_period=open_period,
            close_date=close_date,
            is_closed=is_closed,
            disable_notification=disable_notification,
            protect_content=protect_content,
            message_thread_id=message_thread_id,
            effect_id=effect_id,
            reply_parameters=reply_parameters,
            schedule_date=schedule_date,
            business_connection_id=business_connection_id,
            options_parse_mode=options_parse_mode,
            allow_paid_broadcast=allow_paid_broadcast,
            paid_message_star_count=paid_message_star_count,
            reply_markup=reply_markup,

            reply_to_message_id=reply_to_message_id,
            quote_text=quote_text,
            quote_parse_mode=quote_parse_mode,
            quote_entities=quote_entities,
            quote_offset=quote_offset,
        )

    async def reply_sticker(
        self,
        sticker: Union[str, BinaryIO],
        quote: bool = None,
        emoji: str = "",
        caption: str = "",
        parse_mode: Optional["enums.ParseMode"] = None,
        caption_entities: List["types.MessageEntity"] = None,
        disable_notification: bool = None,
        message_thread_id: int = None,
        direct_messages_chat_topic_id: int = None,
        effect_id: int = None,
        reply_parameters: "types.ReplyParameters" = None,
        business_connection_id: str = None,
        allow_paid_broadcast: bool = None,
        paid_message_star_count: int = None,
        reply_markup: Union[
            "types.InlineKeyboardMarkup",
            "types.ReplyKeyboardMarkup",
            "types.ReplyKeyboardRemove",
            "types.ForceReply"
        ] = None,
        progress: Callable = None,
        progress_args: tuple = (),

        reply_to_message_id: int = None,
        quote_text: str = None,
        quote_entities: List["types.MessageEntity"] = None,
    ) -> "Message":
        """Bound method *reply_sticker* of :obj:`~pyrogram.types.Message`.

        Use as a shortcut for:

        .. code-block:: python

            await client.send_sticker(
                chat_id=message.chat.id,
                sticker=sticker
            )

        Example:
            .. code-block:: python

                await message.reply_sticker(sticker)

        Parameters:
            sticker (``str``):
                Sticker to send.
                Pass a file_id as string to send a sticker that exists on the Telegram servers,
                pass an HTTP URL as a string for Telegram to get a .webp sticker file from the Internet, or
                pass a file path as string to upload a new sticker that exists on your local machine.

            quote (``bool``, *optional*):
                If ``True``, the message will be sent as a reply to this message.
                If *reply_parameters* is passed, this parameter will be ignored.
                Defaults to ``True`` in group chats and ``False`` in private chats.

            emoji (``str``, *optional*):
                Emoji associated with this sticker.

            caption (``str``, *optional*):
                Sticker caption, 0-1024 characters.

            parse_mode (:obj:`~pyrogram.enums.ParseMode`, *optional*):
                By default, texts are parsed using both Markdown and HTML styles.
                You can combine both syntaxes together.

            caption_entities (List of :obj:`~pyrogram.types.MessageEntity`):
                List of special entities that appear in the caption, which can be specified instead of *parse_mode*.

            disable_notification (``bool``, *optional*):
                Sends the message silently.
                Users will receive a notification with no sound.

            message_thread_id (``int``, *optional*):
                Unique identifier of a message thread to which the message belongs.
                For forums only.

            direct_messages_chat_topic_id (``int``, *optional*):
                Unique identifier of the topic in a channel direct messages chat administered by the current user.
                For directs only.

            effect_id (``int``, *optional*):
                Unique identifier of the message effect.
                For private chats only.

            reply_parameters (:obj:`~pyrogram.types.ReplyParameters`, *optional*):
                Describes reply parameters for the message that is being sent.

            business_connection_id (``str``, *optional*):
                Unique identifier of the business connection on behalf of which the message will be sent.

            allow_paid_broadcast (``bool``, *optional*):
                If True, you will be allowed to send up to 1000 messages per second.
                Ignoring broadcasting limits for a fee of 0.1 Telegram Stars per message.
                The relevant Stars will be withdrawn from the bot's balance.
                For bots only.

            paid_message_star_count (``int``, *optional*):
                The number of Telegram Stars the user agreed to pay to send the messages.

            reply_markup (:obj:`~pyrogram.types.InlineKeyboardMarkup` | :obj:`~pyrogram.types.ReplyKeyboardMarkup` | :obj:`~pyrogram.types.ReplyKeyboardRemove` | :obj:`~pyrogram.types.ForceReply`, *optional*):
                Additional interface options. An object for an inline keyboard, custom reply keyboard,
                instructions to remove reply keyboard or to force a reply from the user.

            progress (``Callable``, *optional*):
                Pass a callback function to view the file transmission progress.
                The function must take *(current, total)* as positional arguments (look at Other Parameters below for a
                detailed description) and will be called back each time a new file chunk has been successfully
                transmitted.

            progress_args (``tuple``, *optional*):
                Extra custom arguments for the progress callback function.
                You can pass anything you need to be available in the progress callback scope; for example, a Message
                object or a Client instance in order to edit the message with the updated progress status.

        Other Parameters:
            current (``int``):
                The amount of bytes transmitted so far.

            total (``int``):
                The total size of the file.

            *args (``tuple``, *optional*):
                Extra custom arguments as defined in the ``progress_args`` parameter.
                You can either keep ``*args`` or add every single extra argument in your function signature.

        Returns:
            On success, the sent :obj:`~pyrogram.types.Message` is returned.
            In case the upload is deliberately stopped with :meth:`~pyrogram.Client.stop_transmission`, None is returned
            instead.

        Raises:
            RPCError: In case of a Telegram RPC error.
        """
        if quote is None:
            quote = self.chat.type != enums.ChatType.PRIVATE

        if reply_parameters is None and quote:
            reply_parameters = types.ReplyParameters(
                message_id=self.id
            )

        if message_thread_id is None:
            message_thread_id = self.message_thread_id

        if direct_messages_chat_topic_id is None:
            direct_messages_chat_topic_id = self.direct_messages_chat_topic_id

        if business_connection_id is None:
            business_connection_id = self.business_connection_id

        return await self._client.send_sticker(
            chat_id=self.chat.id,
            sticker=sticker,
            emoji=emoji,
            caption=caption,
            parse_mode=parse_mode,
            caption_entities=caption_entities,
            disable_notification=disable_notification,
            message_thread_id=message_thread_id,
            direct_messages_chat_topic_id=direct_messages_chat_topic_id,
            effect_id=effect_id,
            reply_parameters=reply_parameters,
            business_connection_id=business_connection_id,
            allow_paid_broadcast=allow_paid_broadcast,
            paid_message_star_count=paid_message_star_count,
            reply_markup=reply_markup,
            progress=progress,
            progress_args=progress_args,

            reply_to_message_id=reply_to_message_id,
            quote_text=quote_text,
            quote_entities=quote_entities,
        )

    async def reply_venue(
        self,
        latitude: float,
        longitude: float,
        title: str,
        address: str,
        quote: bool = None,
        foursquare_id: str = "",
        foursquare_type: str = "",
        disable_notification: bool = None,
        message_thread_id: int = None,
        direct_messages_chat_topic_id: int = None,
        effect_id: int = None,
        reply_parameters: "types.ReplyParameters" = None,
        business_connection_id: str = None,
        allow_paid_broadcast: bool = None,
        paid_message_star_count: int = None,
        reply_markup: Union[
            "types.InlineKeyboardMarkup",
            "types.ReplyKeyboardMarkup",
            "types.ReplyKeyboardRemove",
            "types.ForceReply"
        ] = None,

        reply_to_message_id: int = None,
        quote_text: str = None,
        parse_mode: Optional["enums.ParseMode"] = None,
        quote_entities: List["types.MessageEntity"] = None,
    ) -> "Message":
        """Bound method *reply_venue* of :obj:`~pyrogram.types.Message`.

        Use as a shortcut for:

        .. code-block:: python

            await client.send_venue(
                chat_id=message.chat.id,
                latitude=latitude,
                longitude=longitude,
                title="Venue title",
                address="Venue address"
            )

        Example:
            .. code-block:: python

                await message.reply_venue(latitude, longitude, "Venue title", "Venue address")

        Parameters:
            latitude (``float``):
                Latitude of the venue.

            longitude (``float``):
                Longitude of the venue.

            title (``str``):
                Name of the venue.

            address (``str``):
                Address of the venue.

            quote (``bool``, *optional*):
                If ``True``, the message will be sent as a reply to this message.
                If *reply_parameters* is passed, this parameter will be ignored.
                Defaults to ``True`` in group chats and ``False`` in private chats.

            foursquare_id (``str``, *optional*):
                Foursquare identifier of the venue.

            foursquare_type (``str``, *optional*):
                Foursquare type of the venue, if known.
                (For example, "arts_entertainment/default", "arts_entertainment/aquarium" or "food/icecream".)

            disable_notification (``bool``, *optional*):
                Sends the message silently.
                Users will receive a notification with no sound.

            message_thread_id (``int``, *optional*):
                Unique identifier of a message thread to which the message belongs.
                For forums only.

            direct_messages_chat_topic_id (``int``, *optional*):
                Unique identifier of the topic in a channel direct messages chat administered by the current user.
                For directs only.

            effect_id (``int``, *optional*):
                Unique identifier of the message effect.
                For private chats only.

            reply_parameters (:obj:`~pyrogram.types.ReplyParameters`, *optional*):
                Describes reply parameters for the message that is being sent.

            business_connection_id (``str``, *optional*):
                Unique identifier of the business connection on behalf of which the message will be sent.

            allow_paid_broadcast (``bool``, *optional*):
                If True, you will be allowed to send up to 1000 messages per second.
                Ignoring broadcasting limits for a fee of 0.1 Telegram Stars per message.
                The relevant Stars will be withdrawn from the bot's balance.
                For bots only.

            paid_message_star_count (``int``, *optional*):
                The number of Telegram Stars the user agreed to pay to send the messages.

            reply_markup (:obj:`~pyrogram.types.InlineKeyboardMarkup` | :obj:`~pyrogram.types.ReplyKeyboardMarkup` | :obj:`~pyrogram.types.ReplyKeyboardRemove` | :obj:`~pyrogram.types.ForceReply`, *optional*):
                Additional interface options. An object for an inline keyboard, custom reply keyboard,
                instructions to remove reply keyboard or to force a reply from the user.

        Returns:
            On success, the sent :obj:`~pyrogram.types.Message` is returned.

        Raises:
            RPCError: In case of a Telegram RPC error.
        """
        if quote is None:
            quote = self.chat.type != enums.ChatType.PRIVATE

        if reply_parameters is None and quote:
            reply_parameters = types.ReplyParameters(
                message_id=self.id
            )

        if message_thread_id is None:
            message_thread_id = self.message_thread_id

        if direct_messages_chat_topic_id is None:
            direct_messages_chat_topic_id = self.direct_messages_chat_topic_id

        if business_connection_id is None:
            business_connection_id = self.business_connection_id

        return await self._client.send_venue(
            chat_id=self.chat.id,
            latitude=latitude,
            longitude=longitude,
            title=title,
            address=address,
            foursquare_id=foursquare_id,
            foursquare_type=foursquare_type,
            disable_notification=disable_notification,
            message_thread_id=message_thread_id,
            direct_messages_chat_topic_id=direct_messages_chat_topic_id,
            effect_id=effect_id,
            reply_parameters=reply_parameters,
            business_connection_id=business_connection_id,
            allow_paid_broadcast=allow_paid_broadcast,
            paid_message_star_count=paid_message_star_count,
            reply_markup=reply_markup,

            reply_to_message_id=reply_to_message_id,
            quote_text=quote_text,
            parse_mode=parse_mode,
            quote_entities=quote_entities,
        )

    async def reply_video(
        self,
        video: Union[str, BinaryIO],
        quote: bool = None,
        caption: str = "",
        parse_mode: Optional["enums.ParseMode"] = None,
        caption_entities: List["types.MessageEntity"] = None,
        has_spoiler: bool = None,
        show_caption_above_media: bool = None,
        ttl_seconds: int = None,
        duration: int = 0,
        width: int = 0,
        height: int = 0,
        video_start_timestamp: int = None,
        video_cover: Union[str, BinaryIO] = None,
        thumb: Union[str, BinaryIO] = None,
        supports_streaming: bool = True,
        disable_notification: bool = None,
        message_thread_id: int = None,
        direct_messages_chat_topic_id: int = None,
        effect_id: int = None,
        reply_parameters: "types.ReplyParameters" = None,
        no_sound: bool = None,
        business_connection_id: str = None,
        allow_paid_broadcast: bool = None,
        paid_message_star_count: int = None,
        reply_markup: Union[
            "types.InlineKeyboardMarkup",
            "types.ReplyKeyboardMarkup",
            "types.ReplyKeyboardRemove",
            "types.ForceReply"
        ] = None,
        progress: Callable = None,
        progress_args: tuple = (),

        reply_to_message_id: int = None,
        quote_text: str = None,
        quote_entities: List["types.MessageEntity"] = None,
    ) -> "Message":
        """Bound method *reply_video* of :obj:`~pyrogram.types.Message`.

        Use as a shortcut for:

        .. code-block:: python

            await client.send_video(
                chat_id=message.chat.id,
                video=video
            )

        Example:
            .. code-block:: python

                await message.reply_video(video)

        Parameters:
            video (``str``):
                Video to send.
                Pass a file_id as string to send a video that exists on the Telegram servers,
                pass an HTTP URL as a string for Telegram to get a video from the Internet, or
                pass a file path as string to upload a new video that exists on your local machine.

            quote (``bool``, *optional*):
                If ``True``, the message will be sent as a reply to this message.
                If *reply_parameters* is passed, this parameter will be ignored.
                Defaults to ``True`` in group chats and ``False`` in private chats.

            caption (``str``, *optional*):
                Video caption, 0-1024 characters.

            parse_mode (:obj:`~pyrogram.enums.ParseMode`, *optional*):
                By default, texts are parsed using both Markdown and HTML styles.
                You can combine both syntaxes together.

            caption_entities (List of :obj:`~pyrogram.types.MessageEntity`):
                List of special entities that appear in the caption, which can be specified instead of *parse_mode*.

            has_spoiler (``bool``, *optional*):
                Pass True if the video needs to be covered with a spoiler animation.

            show_caption_above_media (``bool``, *optional*):
                Pass True to show the video caption above the video.

            ttl_seconds (``int``, *optional*):
                Self-Destruct Timer.
                If you set a timer, the video will self-destruct in *ttl_seconds*
                seconds after it was viewed.

            duration (``int``, *optional*):
                Duration of sent video in seconds.

            width (``int``, *optional*):
                Video width.

            height (``int``, *optional*):
                Video height.

            video_start_timestamp (``int``, *optional*):
                Video startpoint, in seconds.

            video_cover (``str`` | ``BinaryIO``, *optional*):
                Video cover.
                Pass a file_id as string to attach a photo that exists on the Telegram servers,
                pass an HTTP URL as a string for Telegram to get a photo from the Internet,
                pass a file path as string to upload a new photo that exists on your local machine, or
                pass a binary file-like object with its attribute ".name" set for in-memory uploads.

            thumb (``str`` | ``BinaryIO``, *optional*):
                Thumbnail of the video sent.
                The thumbnail should be in JPEG format and less than 200 KB in size.
                A thumbnail's width and height should not exceed 320 pixels.
                Thumbnails can't be reused and can be only uploaded as a new file.

            supports_streaming (``bool``, *optional*):
                Pass True, if the uploaded video is suitable for streaming.

            disable_notification (``bool``, *optional*):
                Sends the message silently.
                Users will receive a notification with no sound.

            message_thread_id (``int``, *optional*):
                Unique identifier of a message thread to which the message belongs.
                For forums only.

            direct_messages_chat_topic_id (``int``, *optional*):
                Unique identifier of the topic in a channel direct messages chat administered by the current user.
                For directs only.

            effect_id (``int``, *optional*):
                Unique identifier of the message effect.
                For private chats only.

            reply_parameters (:obj:`~pyrogram.types.ReplyParameters`, *optional*):
                Describes reply parameters for the message that is being sent.

            no_sound (``bool``, *optional*):
                Pass True, if the uploaded video is a video message with no sound.
                Doesn't work for external links.

            business_connection_id (``str``, *optional*):
                Unique identifier of the business connection on behalf of which the message will be sent.

            allow_paid_broadcast (``bool``, *optional*):
                If True, you will be allowed to send up to 1000 messages per second.
                Ignoring broadcasting limits for a fee of 0.1 Telegram Stars per message.
                The relevant Stars will be withdrawn from the bot's balance.
                For bots only.

            paid_message_star_count (``int``, *optional*):
                The number of Telegram Stars the user agreed to pay to send the messages.

            reply_markup (:obj:`~pyrogram.types.InlineKeyboardMarkup` | :obj:`~pyrogram.types.ReplyKeyboardMarkup` | :obj:`~pyrogram.types.ReplyKeyboardRemove` | :obj:`~pyrogram.types.ForceReply`, *optional*):
                Additional interface options. An object for an inline keyboard, custom reply keyboard,
                instructions to remove reply keyboard or to force a reply from the user.

            progress (``Callable``, *optional*):
                Pass a callback function to view the file transmission progress.
                The function must take *(current, total)* as positional arguments (look at Other Parameters below for a
                detailed description) and will be called back each time a new file chunk has been successfully
                transmitted.

            progress_args (``tuple``, *optional*):
                Extra custom arguments for the progress callback function.
                You can pass anything you need to be available in the progress callback scope; for example, a Message
                object or a Client instance in order to edit the message with the updated progress status.

        Other Parameters:
            current (``int``):
                The amount of bytes transmitted so far.

            total (``int``):
                The total size of the file.

            *args (``tuple``, *optional*):
                Extra custom arguments as defined in the ``progress_args`` parameter.
                You can either keep ``*args`` or add every single extra argument in your function signature.

        Returns:
            On success, the sent :obj:`~pyrogram.types.Message` is returned.
            In case the upload is deliberately stopped with :meth:`~pyrogram.Client.stop_transmission`, None is returned
            instead.

        Raises:
            RPCError: In case of a Telegram RPC error.
        """
        if quote is None:
            quote = self.chat.type != enums.ChatType.PRIVATE

        if reply_parameters is None and quote:
            reply_parameters = types.ReplyParameters(
                message_id=self.id
            )

        if message_thread_id is None:
            message_thread_id = self.message_thread_id

        if direct_messages_chat_topic_id is None:
            direct_messages_chat_topic_id = self.direct_messages_chat_topic_id

        if business_connection_id is None:
            business_connection_id = self.business_connection_id

        return await self._client.send_video(
            chat_id=self.chat.id,
            video=video,
            caption=caption,
            parse_mode=parse_mode,
            caption_entities=caption_entities,
            has_spoiler=has_spoiler,
            show_caption_above_media=show_caption_above_media,
            ttl_seconds=ttl_seconds,
            duration=duration,
            width=width,
            height=height,
            video_start_timestamp=video_start_timestamp,
            video_cover=video_cover,
            thumb=thumb,
            supports_streaming=supports_streaming,
            disable_notification=disable_notification,
            message_thread_id=message_thread_id,
            direct_messages_chat_topic_id=direct_messages_chat_topic_id,
            effect_id=effect_id,
            reply_parameters=reply_parameters,
            no_sound=no_sound,
            business_connection_id=business_connection_id,
            allow_paid_broadcast=allow_paid_broadcast,
            paid_message_star_count=paid_message_star_count,
            reply_markup=reply_markup,
            progress=progress,
            progress_args=progress_args,

            reply_to_message_id=reply_to_message_id,
            quote_text=quote_text,
            quote_entities=quote_entities,
        )

    async def reply_video_note(
        self,
        video_note: Union[str, BinaryIO],
        quote: bool = None,
        duration: int = 0,
        length: int = 1,
        thumb: Union[str, BinaryIO] = None,
        disable_notification: bool = None,
        message_thread_id: int = None,
        direct_messages_chat_topic_id: int = None,
        effect_id: int = None,
        reply_parameters: "types.ReplyParameters" = None,
        protect_content: bool = None,
        view_once: bool = None,
        business_connection_id: str = None,
        allow_paid_broadcast: bool = None,
        paid_message_star_count: int = None,
        reply_markup: Union[
            "types.InlineKeyboardMarkup",
            "types.ReplyKeyboardMarkup",
            "types.ReplyKeyboardRemove",
            "types.ForceReply"
        ] = None,
        progress: Callable = None,
        progress_args: tuple = (),

        reply_to_message_id: int = None,
        quote_text: str = None,
        parse_mode: Optional["enums.ParseMode"] = None,
        quote_entities: List["types.MessageEntity"] = None,
    ) -> "Message":
        """Bound method *reply_video_note* of :obj:`~pyrogram.types.Message`.

        Use as a shortcut for:

        .. code-block:: python

            await client.send_video_note(
                chat_id=message.chat.id,
                video_note=video_note
            )

        Example:
            .. code-block:: python

                await message.reply_video_note(video_note)

        Parameters:
            video_note (``str``):
                Video note to send.
                Pass a file_id as string to send a video note that exists on the Telegram servers, or
                pass a file path as string to upload a new video note that exists on your local machine.
                Sending video notes by a URL is currently unsupported.

            quote (``bool``, *optional*):
                If ``True``, the message will be sent as a reply to this message.
                If *reply_parameters* is passed, this parameter will be ignored.
                Defaults to ``True`` in group chats and ``False`` in private chats.

            duration (``int``, *optional*):
                Duration of sent video in seconds.

            length (``int``, *optional*):
                Video width and height.

            thumb (``str`` | ``BinaryIO``, *optional*):
                Thumbnail of the video sent.
                The thumbnail should be in JPEG format and less than 200 KB in size.
                A thumbnail's width and height should not exceed 320 pixels.
                Thumbnails can't be reused and can be only uploaded as a new file.

            disable_notification (``bool``, *optional*):
                Sends the message silently.
                Users will receive a notification with no sound.

            message_thread_id (``int``, *optional*):
                Unique identifier of a message thread to which the message belongs.
                For forums only.

            direct_messages_chat_topic_id (``int``, *optional*):
                Unique identifier of the topic in a channel direct messages chat administered by the current user.
                For directs only.

            effect_id (``int``, *optional*):
                Unique identifier of the message effect.
                For private chats only.

            reply_parameters (:obj:`~pyrogram.types.ReplyParameters`, *optional*):
                Describes reply parameters for the message that is being sent.

            protect_content (``bool``, *optional*):
                Protects the contents of the sent message from forwarding and saving.

            view_once (``bool``, *optional*):
                Self-Destruct Timer.
                If True, the video note will self-destruct after it was viewed.

            business_connection_id (``str``, *optional*):
                Unique identifier of the business connection on behalf of which the message will be sent.

            allow_paid_broadcast (``bool``, *optional*):
                If True, you will be allowed to send up to 1000 messages per second.
                Ignoring broadcasting limits for a fee of 0.1 Telegram Stars per message.
                The relevant Stars will be withdrawn from the bot's balance.
                For bots only.

            paid_message_star_count (``int``, *optional*):
                The number of Telegram Stars the user agreed to pay to send the messages.

            reply_markup (:obj:`~pyrogram.types.InlineKeyboardMarkup` | :obj:`~pyrogram.types.ReplyKeyboardMarkup` | :obj:`~pyrogram.types.ReplyKeyboardRemove` | :obj:`~pyrogram.types.ForceReply`, *optional*):
                Additional interface options. An object for an inline keyboard, custom reply keyboard,
                instructions to remove reply keyboard or to force a reply from the user.

            progress (``Callable``, *optional*):
                Pass a callback function to view the file transmission progress.
                The function must take *(current, total)* as positional arguments (look at Other Parameters below for a
                detailed description) and will be called back each time a new file chunk has been successfully
                transmitted.

            progress_args (``tuple``, *optional*):
                Extra custom arguments for the progress callback function.
                You can pass anything you need to be available in the progress callback scope; for example, a Message
                object or a Client instance in order to edit the message with the updated progress status.

        Other Parameters:
            current (``int``):
                The amount of bytes transmitted so far.

            total (``int``):
                The total size of the file.

            *args (``tuple``, *optional*):
                Extra custom arguments as defined in the ``progress_args`` parameter.
                You can either keep ``*args`` or add every single extra argument in your function signature.

        Returns:
            On success, the sent :obj:`~pyrogram.types.Message` is returned.
            In case the upload is deliberately stopped with :meth:`~pyrogram.Client.stop_transmission`, None is returned
            instead.

        Raises:
            RPCError: In case of a Telegram RPC error.
        """
        if quote is None:
            quote = self.chat.type != enums.ChatType.PRIVATE

        if reply_parameters is None and quote:
            reply_parameters = types.ReplyParameters(
                message_id=self.id
            )

        if message_thread_id is None:
            message_thread_id = self.message_thread_id

        if direct_messages_chat_topic_id is None:
            direct_messages_chat_topic_id = self.direct_messages_chat_topic_id

        if business_connection_id is None:
            business_connection_id = self.business_connection_id

        return await self._client.send_video_note(
            chat_id=self.chat.id,
            video_note=video_note,
            duration=duration,
            length=length,
            thumb=thumb,
            disable_notification=disable_notification,
            message_thread_id=message_thread_id,
            direct_messages_chat_topic_id=direct_messages_chat_topic_id,
            effect_id=effect_id,
            reply_parameters=reply_parameters,
            protect_content=protect_content,
            view_once=view_once,
            business_connection_id=business_connection_id,
            allow_paid_broadcast=allow_paid_broadcast,
            paid_message_star_count=paid_message_star_count,
            reply_markup=reply_markup,
            progress=progress,
            progress_args=progress_args,

            reply_to_message_id=reply_to_message_id,
            quote_text=quote_text,
            parse_mode=parse_mode,
            quote_entities=quote_entities,
        )

    async def reply_voice(
        self,
        voice: Union[str, BinaryIO],
        quote: bool = None,
        caption: str = "",
        parse_mode: Optional["enums.ParseMode"] = None,
        caption_entities: List["types.MessageEntity"] = None,
        duration: int = 0,
        disable_notification: bool = None,
        message_thread_id: int = None,
        direct_messages_chat_topic_id: int = None,
        effect_id: int = None,
        reply_parameters: "types.ReplyParameters" = None,
        view_once: bool = None,
        business_connection_id: str = None,
        allow_paid_broadcast: bool = None,
        paid_message_star_count: int = None,
        reply_markup: Union[
            "types.InlineKeyboardMarkup",
            "types.ReplyKeyboardMarkup",
            "types.ReplyKeyboardRemove",
            "types.ForceReply"
        ] = None,
        progress: Callable = None,
        progress_args: tuple = (),

        reply_to_message_id: int = None,
        quote_text: str = None,
        quote_entities: List["types.MessageEntity"] = None,
    ) -> "Message":
        """Bound method *reply_voice* of :obj:`~pyrogram.types.Message`.

        Use as a shortcut for:

        .. code-block:: python

            await client.send_voice(
                chat_id=message.chat.id,
                voice=voice
            )

        Example:
            .. code-block:: python

                await message.reply_voice(voice)

        Parameters:
            voice (``str``):
                Audio file to send.
                Pass a file_id as string to send an audio that exists on the Telegram servers,
                pass an HTTP URL as a string for Telegram to get an audio from the Internet, or
                pass a file path as string to upload a new audio that exists on your local machine.

            quote (``bool``, *optional*):
                If ``True``, the message will be sent as a reply to this message.
                If *reply_parameters* is passed, this parameter will be ignored.
                Defaults to ``True`` in group chats and ``False`` in private chats.

            caption (``str``, *optional*):
                Voice message caption, 0-1024 characters.

            parse_mode (:obj:`~pyrogram.enums.ParseMode`, *optional*):
                By default, texts are parsed using both Markdown and HTML styles.
                You can combine both syntaxes together.

            caption_entities (List of :obj:`~pyrogram.types.MessageEntity`):
                List of special entities that appear in the caption, which can be specified instead of *parse_mode*.

            duration (``int``, *optional*):
                Duration of the voice message in seconds.

            disable_notification (``bool``, *optional*):
                Sends the message silently.
                Users will receive a notification with no sound.

            message_thread_id (``int``, *optional*):
                Unique identifier of a message thread to which the message belongs.
                For forums only.

            direct_messages_chat_topic_id (``int``, *optional*):
                Unique identifier of the topic in a channel direct messages chat administered by the current user.
                For directs only.

            effect_id (``int``, *optional*):
                Unique identifier of the message effect.
                For private chats only.

            reply_parameters (:obj:`~pyrogram.types.ReplyParameters`, *optional*):
                Describes reply parameters for the message that is being sent.

            view_once (``bool``, *optional*):
                Self-Destruct Timer.
                If True, the voice note will self-destruct after it was listened.

            business_connection_id (``str``, *optional*):
                Unique identifier of the business connection on behalf of which the message will be sent.

            allow_paid_broadcast (``bool``, *optional*):
                If True, you will be allowed to send up to 1000 messages per second.
                Ignoring broadcasting limits for a fee of 0.1 Telegram Stars per message.
                The relevant Stars will be withdrawn from the bot's balance.
                For bots only.

            paid_message_star_count (``int``, *optional*):
                The number of Telegram Stars the user agreed to pay to send the messages.

            reply_markup (:obj:`~pyrogram.types.InlineKeyboardMarkup` | :obj:`~pyrogram.types.ReplyKeyboardMarkup` | :obj:`~pyrogram.types.ReplyKeyboardRemove` | :obj:`~pyrogram.types.ForceReply`, *optional*):
                Additional interface options. An object for an inline keyboard, custom reply keyboard,
                instructions to remove reply keyboard or to force a reply from the user.

            progress (``Callable``, *optional*):
                Pass a callback function to view the file transmission progress.
                The function must take *(current, total)* as positional arguments (look at Other Parameters below for a
                detailed description) and will be called back each time a new file chunk has been successfully
                transmitted.

            progress_args (``tuple``, *optional*):
                Extra custom arguments for the progress callback function.
                You can pass anything you need to be available in the progress callback scope; for example, a Message
                object or a Client instance in order to edit the message with the updated progress status.

        Other Parameters:
            current (``int``):
                The amount of bytes transmitted so far.

            total (``int``):
                The total size of the file.

            *args (``tuple``, *optional*):
                Extra custom arguments as defined in the ``progress_args`` parameter.
                You can either keep ``*args`` or add every single extra argument in your function signature.

        Returns:
            On success, the sent :obj:`~pyrogram.types.Message` is returned.
            In case the upload is deliberately stopped with :meth:`~pyrogram.Client.stop_transmission`, None is returned
            instead.

        Raises:
            RPCError: In case of a Telegram RPC error.
        """
        if quote is None:
            quote = self.chat.type != enums.ChatType.PRIVATE

        if reply_parameters is None and quote:
            reply_parameters = types.ReplyParameters(
                message_id=self.id
            )

        if message_thread_id is None:
            message_thread_id = self.message_thread_id

        if direct_messages_chat_topic_id is None:
            direct_messages_chat_topic_id = self.direct_messages_chat_topic_id

        if business_connection_id is None:
            business_connection_id = self.business_connection_id

        return await self._client.send_voice(
            chat_id=self.chat.id,
            voice=voice,
            caption=caption,
            parse_mode=parse_mode,
            caption_entities=caption_entities,
            duration=duration,
            disable_notification=disable_notification,
            message_thread_id=message_thread_id,
            direct_messages_chat_topic_id=direct_messages_chat_topic_id,
            effect_id=effect_id,
            reply_parameters=reply_parameters,
            view_once=view_once,
            business_connection_id=business_connection_id,
            allow_paid_broadcast=allow_paid_broadcast,
            paid_message_star_count=paid_message_star_count,
            reply_markup=reply_markup,
            progress=progress,
            progress_args=progress_args,

            reply_to_message_id=reply_to_message_id,
            quote_text=quote_text,
            quote_entities=quote_entities,
        )

    async def reply_web_page(
        self,
        text: str = None,
        quote: bool = None,
        url: str = None,
        prefer_large_media: bool = None,
        prefer_small_media: bool = None,
        parse_mode: Optional["enums.ParseMode"] = None,
        entities: List["types.MessageEntity"] = None,
        disable_notification: bool = None,
        message_thread_id: int = None,
        direct_messages_chat_topic_id: int = None,
        effect_id: int = None,
        show_caption_above_media: bool = None,
        reply_parameters: "types.ReplyParameters" = None,
        schedule_date: datetime = None,
        protect_content: bool = None,
        business_connection_id: str = None,
        allow_paid_broadcast: bool = None,
        paid_message_star_count: int = None,
        reply_markup: Union[
            "types.InlineKeyboardMarkup",
            "types.ReplyKeyboardMarkup",
            "types.ReplyKeyboardRemove",
            "types.ForceReply"
        ] = None,

        reply_to_message_id: int = None,
        reply_to_chat_id: Union[int, str] = None,
        reply_to_story_id: int = None,
        quote_text: str = None,
        quote_entities: List["types.MessageEntity"] = None,
        quote_offset: int = None,
    ) -> "types.Message":
        """Bound method *reply_web_page* of :obj:`~pyrogram.types.Message`.

        Use as a shortcut for:

        .. code-block:: python

            await client.send_web_page(
                chat_id=message.chat.id,
                url="https://docs.pyrogram.org"
            )

        Example:
            .. code-block:: python

                await message.reply_web_page("https://docs.pyrogram.org")

        Parameters:
            text (``str``, *optional*):
                Text of the message to be sent.

            quote (``bool``, *optional*):
                If ``True``, the message will be sent as a reply to this message.
                If *reply_parameters* is passed, this parameter will be ignored.
                Defaults to ``True`` in group chats and ``False`` in private chats.

            url (``str``, *optional*):
                Link that will be previewed.
                If url not specified, the first URL found in the text will be used.

            parse_mode (:obj:`~pyrogram.enums.ParseMode`, *optional*):
                By default, texts are parsed using both Markdown and HTML styles.
                You can combine both syntaxes together.

            entities (List of :obj:`~pyrogram.types.MessageEntity`):
                List of special entities that appear in message text, which can be specified instead of *parse_mode*.

            prefer_large_media (``bool``, *optional*):
                If True, media in the link preview will be larger.
                Ignored if the URL isn't explicitly specified or media size change isn't supported for the preview.

            prefer_small_media (``bool``, *optional*):
                If True, media in the link preview will be smaller.
                Ignored if the URL isn't explicitly specified or media size change isn't supported for the preview.

            show_caption_above_media (``bool``, *optional*):
                Pass True, if the caption must be shown above the message media.

            disable_notification (``bool``, *optional*):
                Sends the message silently.
                Users will receive a notification with no sound.

            message_thread_id (``int``, *optional*):
                Unique identifier of a message thread to which the message belongs.
                For forums only.

            direct_messages_chat_topic_id (``int``, *optional*):
                Unique identifier of the topic in a channel direct messages chat administered by the current user.
                For directs only.

            effect_id (``int``, *optional*):
                Unique identifier of the message effect.
                For private chats only.

            reply_parameters (:obj:`~pyrogram.types.ReplyParameters`, *optional*):
                Describes reply parameters for the message that is being sent.

            schedule_date (:py:obj:`~datetime.datetime`, *optional*):
                Date when the message will be automatically sent.

            protect_content (``bool``, *optional*):
                Protects the contents of the sent message from forwarding and saving.

            business_connection_id (``str``, *optional*):
                Unique identifier of the business connection on behalf of which the message will be sent.

            allow_paid_broadcast (``bool``, *optional*):
                If True, you will be allowed to send up to 1000 messages per second.
                Ignoring broadcasting limits for a fee of 0.1 Telegram Stars per message.
                The relevant Stars will be withdrawn from the bot's balance.
                For bots only.

            paid_message_star_count (``int``, *optional*):
                The number of Telegram Stars the user agreed to pay to send the messages.

            reply_markup (:obj:`~pyrogram.types.InlineKeyboardMarkup` | :obj:`~pyrogram.types.ReplyKeyboardMarkup` | :obj:`~pyrogram.types.ReplyKeyboardRemove` | :obj:`~pyrogram.types.ForceReply`, *optional*):
                Additional interface options. An object for an inline keyboard, custom reply keyboard,
                instructions to remove reply keyboard or to force a reply from the user.

        Returns:
            :obj:`~pyrogram.types.Message`: On success, the sent message is returned.
        """
        if quote is None:
            quote = self.chat.type != enums.ChatType.PRIVATE

        if reply_parameters is None and quote:
            reply_parameters = types.ReplyParameters(
                message_id=self.id
            )

        if message_thread_id is None:
            message_thread_id = self.message_thread_id

        if direct_messages_chat_topic_id is None:
            direct_messages_chat_topic_id = self.direct_messages_chat_topic_id

        if business_connection_id is None:
            business_connection_id = self.business_connection_id

        return await self._client.send_web_page(
            chat_id=self.chat.id,
            text=text,
            url=url,
            prefer_large_media=prefer_large_media,
            prefer_small_media=prefer_small_media,
            parse_mode=parse_mode,
            entities=entities,
            disable_notification=disable_notification,
            message_thread_id=message_thread_id,
            effect_id=effect_id,
            show_caption_above_media=show_caption_above_media,
            reply_parameters=reply_parameters,
            schedule_date=schedule_date,
            protect_content=protect_content,
            business_connection_id=business_connection_id,
            allow_paid_broadcast=allow_paid_broadcast,
            paid_message_star_count=paid_message_star_count,
            reply_markup=reply_markup,

            reply_to_message_id=reply_to_message_id,
            reply_to_chat_id=reply_to_chat_id,
            reply_to_story_id=reply_to_story_id,
            quote_text=quote_text,
            quote_entities=quote_entities,
            quote_offset=quote_offset,
        )

    async def reply_checklist(
        self,
        checklist: "types.InputChecklist",
        quote: bool = None,
        disable_notification: Optional[bool] = None,
        protect_content: Optional[bool] = None,
        message_thread_id: Optional[int] = None,
        effect_id: Optional[int] = None,
        reply_parameters: Optional["types.ReplyParameters"] = None,
        schedule_date: Optional[datetime] = None,
        business_connection_id: Optional[str] = None,
        paid_message_star_count: int = None,
        reply_markup: Optional[
            Union[
                "types.InlineKeyboardMarkup",
                "types.ReplyKeyboardMarkup",
                "types.ReplyKeyboardRemove",
                "types.ForceReply"
            ]
        ] = None,
    ) -> "Message":
        """Bound method *reply_checklist* of :obj:`~pyrogram.types.Message`.

        Use as a shortcut for:

        .. code-block:: python

            await client.send_checklist(
                chat_id=message.chat.id,
                title="To do",
                tasks=[
                    types.InputChecklistTask(id=1, text="Task 1"),
                    types.InputChecklistTask(id=2, text="Task 2")
                ]
            )

        Example:
            .. code-block:: python

                await message.reply_checklist("To do", [
                    types.InputChecklistTask(id=1, text="Task 1"),
                    types.InputChecklistTask(id=2, text="Task 2")
                ])

        Parameters:
            checklist (:obj:`~pyrogram.types.InputChecklist`):
                Checklist to send.

            quote (``bool``, *optional*):
                If ``True``, the message will be sent as a reply to this message.
                If *reply_parameters* is passed, this parameter will be ignored.
                Defaults to ``True`` in group chats and ``False`` in private chats.

            disable_notification (``bool``, *optional*):
                Sends the message silently.
                Users will receive a notification with no sound.

            protect_content (``bool``, *optional*):
                Protects the contents of the sent message from forwarding and saving.

            message_thread_id (``int``, *optional*):
                Unique identifier for the target message thread (topic) of the forum.
                For supergroups only.

            effect_id (``int``, *optional*):
                Unique identifier of the message effect.
                For private chats only.

            reply_parameters (:obj:`~pyrogram.types.ReplyParameters`, *optional*):
                Describes reply parameters for the message that is being sent.

            schedule_date (:py:obj:`~datetime.datetime`, *optional*):
                Date when the message will be automatically sent.

            business_connection_id (``str``, *optional*):
                Unique identifier of the business connection on behalf of which the message will be sent.

            paid_message_star_count (``int``, *optional*):
                The number of Telegram Stars the user agreed to pay to send the messages.

            reply_markup (:obj:`~pyrogram.types.InlineKeyboardMarkup` | :obj:`~pyrogram.types.ReplyKeyboardMarkup` | :obj:`~pyrogram.types.ReplyKeyboardRemove` | :obj:`~pyrogram.types.ForceReply`, *optional*):
                Additional interface options. An object for an inline keyboard, custom reply keyboard,
                instructions to remove reply keyboard or to force a reply from the user.

        Returns:
            On success, the sent :obj:`~pyrogram.types.Message` is returned.

        Raises:
            RPCError: In case of a Telegram RPC error.
        """
        if quote is None:
            quote = self.chat.type != enums.ChatType.PRIVATE

        if reply_parameters is None and quote:
            reply_parameters = types.ReplyParameters(
                message_id=self.id
            )

        if message_thread_id is None:
            message_thread_id = self.message_thread_id

        if business_connection_id is None:
            business_connection_id = self.business_connection_id

        return await self._client.send_checklist(
            chat_id=self.chat.id,
            checklist=checklist,
            disable_notification=disable_notification,
            protect_content=protect_content,
            message_thread_id=message_thread_id,
            effect_id=effect_id,
            reply_parameters=reply_parameters,
            schedule_date=schedule_date,
            business_connection_id=business_connection_id,
            paid_message_star_count=paid_message_star_count,
            reply_markup=reply_markup,
        )

    async def edit_text(
        self,
        text: str,
        parse_mode: Optional["enums.ParseMode"] = None,
        entities: List["types.MessageEntity"] = None,
        link_preview_options: "types.LinkPreviewOptions" = None,
        show_caption_above_media: bool = None,
        reply_markup: "types.InlineKeyboardMarkup" = None,

        disable_web_page_preview: bool = None,
    ) -> "Message":
        """Bound method *edit_text* of :obj:`~pyrogram.types.Message`.

        An alias exists as *edit*.

        Use as a shortcut for:

        .. code-block:: python

            await client.edit_message_text(
                chat_id=message.chat.id,
                message_id=message.id,
                text="hello"
            )

        Example:
            .. code-block:: python

                await message.edit_text("hello")

        Parameters:
            text (``str``):
                New text of the message.

            parse_mode (:obj:`~pyrogram.enums.ParseMode`, *optional*):
                By default, texts are parsed using both Markdown and HTML styles.
                You can combine both syntaxes together.

            entities (List of :obj:`~pyrogram.types.MessageEntity`):
                List of special entities that appear in message text, which can be specified instead of *parse_mode*.

            link_preview_options (:obj:`~pyrogram.types.LinkPreviewOptions`, *optional*):
                Options used for link preview generation for the message.

            show_caption_above_media (``bool``, *optional*):
                Pass True, if the caption must be shown above the message media.

            reply_markup (:obj:`~pyrogram.types.InlineKeyboardMarkup`, *optional*):
                An InlineKeyboardMarkup object.

        Returns:
            On success, the edited :obj:`~pyrogram.types.Message` is returned.

        Raises:
            RPCError: In case of a Telegram RPC error.
        """
        return await self._client.edit_message_text(
            chat_id=self.chat.id,
            message_id=self.id,
            text=text,
            parse_mode=parse_mode,
            entities=entities,
            link_preview_options=link_preview_options,
            show_caption_above_media=show_caption_above_media,
            reply_markup=reply_markup,

            disable_web_page_preview=disable_web_page_preview,
        )

    edit = edit_text

    async def edit_caption(
        self,
        caption: str,
        parse_mode: Optional["enums.ParseMode"] = None,
        caption_entities: List["types.MessageEntity"] = None,
        reply_markup: "types.InlineKeyboardMarkup" = None
    ) -> "Message":
        """Bound method *edit_caption* of :obj:`~pyrogram.types.Message`.

        Use as a shortcut for:

        .. code-block:: python

            await client.edit_message_caption(
                chat_id=message.chat.id,
                message_id=message.id,
                caption="hello"
            )

        Example:
            .. code-block:: python

                await message.edit_caption("hello")

        Parameters:
            caption (``str``):
                New caption of the message.

            parse_mode (:obj:`~pyrogram.enums.ParseMode`, *optional*):
                By default, texts are parsed using both Markdown and HTML styles.
                You can combine both syntaxes together.

            caption_entities (List of :obj:`~pyrogram.types.MessageEntity`):
                List of special entities that appear in the caption, which can be specified instead of *parse_mode*.

            reply_markup (:obj:`~pyrogram.types.InlineKeyboardMarkup`, *optional*):
                An InlineKeyboardMarkup object.

        Returns:
            On success, the edited :obj:`~pyrogram.types.Message` is returned.

        Raises:
            RPCError: In case of a Telegram RPC error.
        """
        return await self._client.edit_message_caption(
            chat_id=self.chat.id,
            message_id=self.id,
            caption=caption,
            parse_mode=parse_mode,
            caption_entities=caption_entities,
            reply_markup=reply_markup
        )

    async def edit_media(
        self,
        media: "types.InputMedia",
        reply_markup: "types.InlineKeyboardMarkup" = None
    ) -> "Message":
        """Bound method *edit_media* of :obj:`~pyrogram.types.Message`.

        Use as a shortcut for:

        .. code-block:: python

            await client.edit_message_media(
                chat_id=message.chat.id,
                message_id=message.id,
                media=media
            )

        Example:
            .. code-block:: python

                await message.edit_media(media)

        Parameters:
            media (:obj:`~pyrogram.types.InputMedia`):
                One of the InputMedia objects describing an animation, audio, document, photo or video.

            reply_markup (:obj:`~pyrogram.types.InlineKeyboardMarkup`, *optional*):
                An InlineKeyboardMarkup object.

        Returns:
            On success, the edited :obj:`~pyrogram.types.Message` is returned.

        Raises:
            RPCError: In case of a Telegram RPC error.
        """
        return await self._client.edit_message_media(
            chat_id=self.chat.id,
            message_id=self.id,
            media=media,
            reply_markup=reply_markup
        )

    async def edit_checklist(
        self,
        checklist: "types.InputChecklist",
        business_connection_id: Optional[str] = None,
        reply_markup: Optional["types.InlineKeyboardMarkup"] = None
    ) -> "Message":
        """Bound method *edit_checklist* of :obj:`~pyrogram.types.Message`.

        Use as a shortcut for:

        .. code-block:: python

            await app.edit_message_checklist(
                chat_id=chat_id,
                message_id=message_id,
                checklist=types.InputChecklist(
                    title="Checklist",
                    tasks=[
                        types.InputChecklistTask(id=1, text="Task 1"),
                        types.InputChecklistTask(id=2, text="Task 2")
                    ]
                )
            )

        Example:
            .. code-block:: python

                await message.edit_checklist(checklist)

        Parameters:
            checklist (:obj:`~pyrogram.types.InputChecklist`):
                New checklist.

            business_connection_id (``str``, *optional*):
                Unique identifier of the business connection on behalf of which the message will be sent.

            reply_markup (:obj:`~pyrogram.types.InlineKeyboardMarkup`, *optional*):
                An InlineKeyboardMarkup object.

        Returns:
            On success, the edited :obj:`~pyrogram.types.Message` is returned.

        Raises:
            RPCError: In case of a Telegram RPC error.
        """
        if business_connection_id is None:
            business_connection_id = self.business_connection_id

        return await self._client.edit_message_checklist(
            chat_id=self.chat.id,
            message_id=self.id,
            checklist=checklist,
            business_connection_id=business_connection_id,
            reply_markup=reply_markup
        )

    async def edit_reply_markup(self, reply_markup: "types.InlineKeyboardMarkup" = None) -> "Message":
        """Bound method *edit_reply_markup* of :obj:`~pyrogram.types.Message`.

        Use as a shortcut for:

        .. code-block:: python

            await client.edit_message_reply_markup(
                chat_id=message.chat.id,
                message_id=message.id,
                reply_markup=inline_reply_markup
            )

        Example:
            .. code-block:: python

                await message.edit_reply_markup(inline_reply_markup)

        Parameters:
            reply_markup (:obj:`~pyrogram.types.InlineKeyboardMarkup`):
                An InlineKeyboardMarkup object.

        Returns:
            On success, if edited message is sent by the bot, the edited
            :obj:`~pyrogram.types.Message` is returned, otherwise True is returned.

        Raises:
            RPCError: In case of a Telegram RPC error.
        """
        return await self._client.edit_message_reply_markup(
            chat_id=self.chat.id,
            message_id=self.id,
            reply_markup=reply_markup
        )

    async def forward(
        self,
        chat_id: Union[int, str],
        message_thread_id: int = None,
        disable_notification: bool = None,
        hide_sender_name: bool = None,
        hide_captions: bool = None,
        schedule_date: datetime = None,
        allow_paid_broadcast: bool = None,
        video_start_timestamp: int = None,
        paid_message_star_count: int = None
    ) -> Union["types.Message", List["types.Message"]]:
        """Bound method *forward* of :obj:`~pyrogram.types.Message`.

        Use as a shortcut for:

        .. code-block:: python

            await client.forward_messages(
                chat_id=chat_id,
                from_chat_id=message.chat.id,
                message_ids=message.id
            )

        Example:
            .. code-block:: python

                await message.forward(chat_id)

        Parameters:
            chat_id (``int`` | ``str``):
                Unique identifier (int) or username (str) of the target chat.
                For your personal cloud (Saved Messages) you can simply use "me" or "self".
                For a contact that exists in your Telegram address book you can use his phone number (str).

            message_thread_id (``int``, *optional*):
                Unique identifier of a message thread to which the message belongs.
                For supergroups only.

            disable_notification (``bool``, *optional*):
                Sends the message silently.
                Users will receive a notification with no sound.

            schedule_date (:py:obj:`~datetime.datetime`, *optional*):
                Date when the message will be automatically sent.

            hide_sender_name (``bool``, *optional*):
                If True, the original author of the message will not be shown.

            hide_captions (``bool``, *optional*):
                If True, the original media captions will be removed.

            allow_paid_broadcast (``bool``, *optional*):
                If True, you will be allowed to send up to 1000 messages per second.
                Ignoring broadcasting limits for a fee of 0.1 Telegram Stars per message.
                The relevant Stars will be withdrawn from the bot's balance.
                For bots only.

            video_start_timestamp (``int``, *optional*):
                Video startpoint, in seconds.

            paid_message_star_count (``int``, *optional*):
                The number of Telegram Stars the user agreed to pay to send the messages.

        Returns:
            On success, the forwarded Message is returned.

        Raises:
            RPCError: In case of a Telegram RPC error.
        """
        return await self._client.forward_messages(
            chat_id=chat_id,
            from_chat_id=self.chat.id,
            message_ids=self.id,
            message_thread_id=message_thread_id,
            disable_notification=disable_notification,
            schedule_date=schedule_date,
            hide_sender_name=hide_sender_name,
            hide_captions=hide_captions,
            allow_paid_broadcast=allow_paid_broadcast,
            video_start_timestamp=video_start_timestamp,
            paid_message_star_count=paid_message_star_count
        )

    async def copy(
        self,
        chat_id: Union[int, str],
        caption: str = None,
        parse_mode: Optional["enums.ParseMode"] = None,
        caption_entities: List["types.MessageEntity"] = None,
        disable_notification: bool = None,
        message_thread_id: int = None,
        reply_parameters: "types.ReplyParameters" = None,
        schedule_date: datetime = None,
        protect_content: bool = None,
        has_spoiler: bool = None,
        show_caption_above_media: bool = None,
        business_connection_id: str = None,
        allow_paid_broadcast: bool = None,
        paid_message_star_count: int = None,
        reply_markup: Union[
            "types.InlineKeyboardMarkup",
            "types.ReplyKeyboardMarkup",
            "types.ReplyKeyboardRemove",
            "types.ForceReply"
        ] = object,

        reply_to_chat_id: Union[int, str] = None,
        reply_to_message_id: int = None,
        quote_text: str = None,
        quote_entities: List["types.MessageEntity"] = None,
    ) -> Union["types.Message", List["types.Message"]]:
        """Bound method *copy* of :obj:`~pyrogram.types.Message`.

        Use as a shortcut for:

        .. code-block:: python

            await client.copy_message(
                chat_id=chat_id,
                from_chat_id=message.chat.id,
                message_id=message.id
            )

        Example:
            .. code-block:: python

                await message.copy(chat_id)

        Parameters:
            chat_id (``int`` | ``str``):
                Unique identifier (int) or username (str) of the target chat.
                For your personal cloud (Saved Messages) you can simply use "me" or "self".
                For a contact that exists in your Telegram address book you can use his phone number (str).

            caption (``string``, *optional*):
                New caption for media, 0-1024 characters after entities parsing.
                If not specified, the original caption is kept.
                Pass "" (empty string) to remove the caption.

            parse_mode (:obj:`~pyrogram.enums.ParseMode`, *optional*):
                By default, texts are parsed using both Markdown and HTML styles.
                You can combine both syntaxes together.

            caption_entities (List of :obj:`~pyrogram.types.MessageEntity`):
                List of special entities that appear in the new caption, which can be specified instead of *parse_mode*.

            disable_notification (``bool``, *optional*):
                Sends the message silently.
                Users will receive a notification with no sound.

            message_thread_id (``int``, *optional*):
                Unique identifier for the target message thread (topic) of the forum.
                For supergroups only.

            reply_parameters (:obj:`~pyrogram.types.ReplyParameters`, *optional*):
                Describes reply parameters for the message that is being sent.

            schedule_date (:py:obj:`~datetime.datetime`, *optional*):
                Date when the message will be automatically sent.

            protect_content (``bool``, *optional*):
                Protects the contents of the sent message from forwarding and saving.

            show_caption_above_media (``bool``, *optional*):
                Pass True, if the caption must be shown above the message media.

            business_connection_id (``str``, *optional*):
                Unique identifier of the business connection on behalf of which the message will be sent.

            allow_paid_broadcast (``bool``, *optional*):
                If True, you will be allowed to send up to 1000 messages per second.
                Ignoring broadcasting limits for a fee of 0.1 Telegram Stars per message.
                The relevant Stars will be withdrawn from the bot's balance.
                For bots only.

            paid_message_star_count (``int``, *optional*):
                The number of Telegram Stars the user agreed to pay to send the messages.

            reply_markup (:obj:`~pyrogram.types.InlineKeyboardMarkup` | :obj:`~pyrogram.types.ReplyKeyboardMarkup` | :obj:`~pyrogram.types.ReplyKeyboardRemove` | :obj:`~pyrogram.types.ForceReply`, *optional*):
                Additional interface options. An object for an inline keyboard, custom reply keyboard,
                instructions to remove reply keyboard or to force a reply from the user.
                If not specified, the original reply markup is kept.
                Pass None to remove the reply markup.

        Returns:
            :obj:`~pyrogram.types.Message`: On success, the copied message is returned.

        Raises:
            RPCError: In case of a Telegram RPC error.
        """
        if self.service:
            log.warning("Service messages cannot be copied. chat_id: %s, message_id: %s",
                        self.chat.id, self.id)
        elif self.game and not await self._client.storage.is_bot():
            log.warning("Users cannot send messages with Game media type. chat_id: %s, message_id: %s",
                        self.chat.id, self.id)
        elif self.empty:
            log.warning("Empty messages cannot be copied.")
        elif self.text:
            return await self._client.send_message(
                chat_id,
                text=self.text,
                entities=self.entities,
                parse_mode=enums.ParseMode.DISABLED,
                link_preview_options=types.LinkPreviewOptions(is_disabled=not self.web_page),
                disable_notification=disable_notification,
                message_thread_id=message_thread_id,
                reply_parameters=reply_parameters,
                reply_to_chat_id=reply_to_chat_id,
                reply_to_message_id=reply_to_message_id,
                quote_text=quote_text,
                quote_entities=quote_entities,
                schedule_date=schedule_date,
                protect_content=protect_content,
                business_connection_id=business_connection_id,
                allow_paid_broadcast=allow_paid_broadcast,
                paid_message_star_count=paid_message_star_count,
                reply_markup=self.reply_markup if reply_markup is object else reply_markup
            )
        elif self.media:
            send_media = partial(
                self._client.send_cached_media,
                chat_id=chat_id,
                disable_notification=disable_notification,
                message_thread_id=message_thread_id,
                reply_parameters=reply_parameters,
                reply_to_message_id=reply_to_message_id,
                reply_to_chat_id=reply_to_chat_id,
                quote_text=quote_text,
                quote_entities=quote_entities,
                schedule_date=schedule_date,
                protect_content=protect_content,
                has_spoiler=self.has_media_spoiler if has_spoiler is None else has_spoiler,
                show_caption_above_media=self.show_caption_above_media if show_caption_above_media is None else show_caption_above_media,
                business_connection_id=business_connection_id,
                allow_paid_broadcast=allow_paid_broadcast,
                paid_message_star_count=paid_message_star_count,
                reply_markup=self.reply_markup if reply_markup is object else reply_markup
            )

            if self.photo:
                file_id = self.photo.file_id
            elif self.audio:
                file_id = self.audio.file_id
            elif self.document:
                file_id = self.document.file_id
            elif self.video:
                file_id = self.video.file_id
            elif self.animation:
                file_id = self.animation.file_id
            elif self.voice:
                file_id = self.voice.file_id
            elif self.sticker:
                file_id = self.sticker.file_id
            elif self.video_note:
                file_id = self.video_note.file_id
            elif self.contact:
                return await self._client.send_contact(
                    chat_id,
                    phone_number=self.contact.phone_number,
                    first_name=self.contact.first_name,
                    last_name=self.contact.last_name,
                    vcard=self.contact.vcard,
                    disable_notification=disable_notification,
                    reply_parameters=reply_parameters,
                    message_thread_id=message_thread_id,
                    schedule_date=schedule_date,
                    allow_paid_broadcast=allow_paid_broadcast,
                    paid_message_star_count=paid_message_star_count,
                    business_connection_id=business_connection_id
                )
            elif self.location:
                return await self._client.send_location(
                    chat_id,
                    latitude=self.location.latitude,
                    longitude=self.location.longitude,
                    disable_notification=disable_notification,
                    message_thread_id=message_thread_id,
                    reply_parameters=reply_parameters,
                    schedule_date=schedule_date,
                    allow_paid_broadcast=allow_paid_broadcast,
                    paid_message_star_count=paid_message_star_count,
                    business_connection_id=business_connection_id
                )
            elif self.venue:
                return await self._client.send_venue(
                    chat_id,
                    latitude=self.venue.location.latitude,
                    longitude=self.venue.location.longitude,
                    title=self.venue.title,
                    address=self.venue.address,
                    foursquare_id=self.venue.foursquare_id,
                    foursquare_type=self.venue.foursquare_type,
                    disable_notification=disable_notification,
                    message_thread_id=message_thread_id,
                    reply_parameters=reply_parameters,
                    schedule_date=schedule_date,
                    allow_paid_broadcast=allow_paid_broadcast,
                    paid_message_star_count=paid_message_star_count,
                    business_connection_id=business_connection_id
                )
            elif self.poll:
                return await self._client.send_poll(
                    chat_id,
                    question=self.poll.question,
                    options=[opt.text for opt in self.poll.options],
                    disable_notification=disable_notification,
                    message_thread_id=message_thread_id,
                    reply_parameters=reply_parameters,
                    schedule_date=schedule_date,
                    allow_paid_broadcast=allow_paid_broadcast,
                    paid_message_star_count=paid_message_star_count,
                    business_connection_id=business_connection_id
                )
            elif self.game:
                return await self._client.send_game(
                    chat_id,
                    game_short_name=self.game.short_name,
                    disable_notification=disable_notification,
                    allow_paid_broadcast=allow_paid_broadcast,
                    message_thread_id=message_thread_id
                )
            else:
                raise ValueError("Unknown media type")

            if self.sticker or self.video_note:  # Sticker and VideoNote should have no caption
                return await send_media(
                    file_id=file_id,
                    message_thread_id=message_thread_id
                )
            else:
                if caption is None:
                    caption = self.caption or ""
                    caption_entities = self.caption_entities

                return await send_media(
                    file_id=file_id,
                    caption=caption,
                    parse_mode=parse_mode,
                    caption_entities=caption_entities,
                    message_thread_id=message_thread_id
                )
        else:
            raise ValueError("Can't copy this message")

    async def copy_media_group(
        self,
        chat_id: Union[int, str],
        captions: Union[List[str], str] = None,
        has_spoilers: Union[List[bool], bool] = None,
        disable_notification: bool = None,
        message_thread_id: int = None,
        reply_parameters: "types.ReplyParameters" = None,
        schedule_date: datetime = None,
        show_caption_above_media: bool = None,
        allow_paid_broadcast: bool = None,
        paid_message_star_count: int = None,

        reply_to_message_id: int = None,
        reply_to_chat_id: Union[int, str] = None,
        reply_to_story_id: int = None,
        quote_text: str = None,
        parse_mode: Optional["enums.ParseMode"] = None,
        quote_entities: List["types.MessageEntity"] = None,
        quote_offset: int = None,
    ) -> List["types.Message"]:
        """Bound method *copy_media_group* of :obj:`~pyrogram.types.Message`.

        Use as a shortcut for:

        .. code-block:: python

            await client.copy_media_group(
                chat_id=chat_id,
                from_chat_id=from_chat_id,
                message_ids=message.id
            )

        Example:
            .. code-block:: python

                await message.copy_media_group("me")

        Parameters:
            chat_id (``int`` | ``str``):
                Unique identifier (int) or username (str) of the target chat.
                For your personal cloud (Saved Messages) you can simply use "me" or "self".
                For a contact that exists in your Telegram address book you can use his phone number (str).

            captions (``str`` | List of ``str`` , *optional*):
                New caption for media, 0-1024 characters after entities parsing for each media.
                If not specified, the original caption is kept.
                Pass "" (empty string) to remove the caption.

                If a ``string`` is passed, it becomes a caption only for the first media.
                If a list of ``string`` passed, each element becomes caption for each media element.
                You can pass ``None`` in list to keep the original caption.

            disable_notification (``bool``, *optional*):
                Sends the message silently.
                Users will receive a notification with no sound.

            message_thread_id (``int``, *optional*):
                Unique identifier for the target message thread (topic) of the forum.
                For supergroups only.

            reply_parameters (:obj:`~pyrogram.types.ReplyParameters`, *optional*):
                Describes reply parameters for the message that is being sent.

            schedule_date (:py:obj:`~datetime.datetime`, *optional*):
                Date when the message will be automatically sent.

            show_caption_above_media (``bool``, *optional*):
                Pass True, if the caption must be shown above the message media.

            allow_paid_broadcast (``bool``, *optional*):
                If True, you will be allowed to send up to 1000 messages per second.
                Ignoring broadcasting limits for a fee of 0.1 Telegram Stars per message.
                The relevant Stars will be withdrawn from the bot's balance.
                For bots only.

            paid_message_star_count (``int``, *optional*):
                The number of Telegram Stars the user agreed to pay to send the messages.

        Returns:
            List of :obj:`~pyrogram.types.Message`: On success, a list of copied messages is returned.
        """
        return await self._client.copy_media_group(
            chat_id=chat_id,
            from_chat_id=self.chat.id,
            message_id=self.id,
            captions=captions,
            has_spoilers=has_spoilers,
            disable_notification=disable_notification,
            message_thread_id=message_thread_id,
            reply_parameters=reply_parameters,
            schedule_date=schedule_date,
            show_caption_above_media=show_caption_above_media,
            allow_paid_broadcast=allow_paid_broadcast,
            paid_message_star_count=paid_message_star_count,

            reply_to_message_id=reply_to_message_id,
            reply_to_chat_id=reply_to_chat_id,
            reply_to_story_id=reply_to_story_id,
            quote_text=quote_text,
            parse_mode=parse_mode,
            quote_entities=quote_entities,
            quote_offset=quote_offset,
        )

    async def delete(self, revoke: bool = True):
        """Bound method *delete* of :obj:`~pyrogram.types.Message`.

        Use as a shortcut for:

        .. code-block:: python

            await client.delete_messages(
                chat_id=chat_id,
                message_ids=message.id
            )

        Example:
            .. code-block:: python

                await message.delete()

        Parameters:
            revoke (``bool``, *optional*):
                Deletes messages on both parts.
                This is only for private cloud chats and normal groups, messages on
                channels and supergroups are always revoked (i.e.: deleted for everyone).
                Defaults to True.

        Returns:
            ``bool``: True on success, False otherwise.

        Raises:
            RPCError: In case of a Telegram RPC error.
        """
        r = await self._client.delete_messages(
            chat_id=self.chat.id,
            message_ids=self.id,
            revoke=revoke
        )

        return bool(r)

    async def click(
        self,
        x: Union[int, str] = 0,
        y: int = None,
        quote: bool = None,
        timeout: int = 10,
        request_write_access: bool = True,
        password: str = None
    ):
        """Bound method *click* of :obj:`~pyrogram.types.Message`.

        Use as a shortcut for clicking a button attached to the message instead of:

        - Clicking inline buttons:

        .. code-block:: python

            await client.request_callback_answer(
                chat_id=message.chat.id,
                message_id=message.id,
                callback_data=message.reply_markup[i][j].callback_data
            )

        - Clicking normal buttons:

        .. code-block:: python

            await client.send_message(
                chat_id=message.chat.id,
                text=message.reply_markup[i][j].text
            )

        Example:
            This method can be used in three different ways:

            1.  Pass one integer argument only (e.g.: ``.click(2)``, to click a button at index 2).
                Buttons are counted left to right, starting from the top.

            2.  Pass two integer arguments (e.g.: ``.click(1, 0)``, to click a button at position (1, 0)).
                The origin (0, 0) is top-left.

            3.  Pass one string argument only (e.g.: ``.click("Settings")``, to click a button by using its label).
                Only the first matching button will be pressed.

        Parameters:
            x (``int`` | ``str``):
                Used as integer index, integer abscissa (in pair with y) or as string label.
                Defaults to 0 (first button).

            y (``int``, *optional*):
                Used as ordinate only (in pair with x).

            quote (``bool``, *optional*):
                Useful for normal buttons only, where pressing it will result in a new message sent.
                If ``True``, the message will be sent as a reply to this message.
                Defaults to ``True`` in group chats and ``False`` in private chats.

            timeout (``int``, *optional*):
                Timeout in seconds.

            request_write_access (``bool``, *optional*):
                Only used in case of :obj:`~pyrogram.types.LoginUrl` button.
                True, if the bot can send messages to the user.
                Defaults to ``True``.

            password (``str``, *optional*):
                When clicking certain buttons (such as BotFather's confirmation button to transfer ownership), if your account has 2FA enabled, you need to provide your account's password.
                The 2-step verification password for the current user. Only applicable, if the :obj:`~pyrogram.types.InlineKeyboardButton` contains ``requires_password``.

        Returns:
            -   The result of :meth:`~pyrogram.Client.request_callback_answer` in case of inline callback button clicks.
            -   The result of :meth:`~Message.reply()` in case of normal button clicks.
            -   A string in case the inline button is a URL, a *switch_inline_query* or a
                *switch_inline_query_current_chat* button.
            -   A string URL with the user details, in case of a WebApp button.
            -   A :obj:`~pyrogram.types.Chat` object in case of a ``KeyboardButtonUserProfile`` button.

        Raises:
            RPCError: In case of a Telegram RPC error.
            ValueError: In case the provided index or position is out of range or the button label was not found.
            TimeoutError: In case, after clicking an inline button, the bot fails to answer within the timeout.
        """

        if isinstance(self.reply_markup, types.ReplyKeyboardMarkup):
            keyboard = self.reply_markup.keyboard
            is_inline = False
        elif isinstance(self.reply_markup, types.InlineKeyboardMarkup):
            keyboard = self.reply_markup.inline_keyboard
            is_inline = True
        else:
            raise ValueError("The message doesn't contain any keyboard")

        if isinstance(x, int) and y is None:
            try:
                button = [
                    button
                    for row in keyboard
                    for button in row
                ][x]
            except IndexError:
                raise ValueError(f"The button at index {x} doesn't exist")
        elif isinstance(x, int) and isinstance(y, int):
            try:
                button = keyboard[y][x]
            except IndexError:
                raise ValueError(f"The button at position ({x}, {y}) doesn't exist")
        elif isinstance(x, str) and y is None:
            label = x.encode("utf-16", "surrogatepass").decode("utf-16")

            try:
                button = [
                    button
                    for row in keyboard
                    for button in row
                    if label == button.text
                ][0]
            except IndexError:
                raise ValueError(f"The button with label '{x}' doesn't exists")
        else:
            raise ValueError("Invalid arguments")

        if is_inline:
            if button.callback_data:
                return await self._client.request_callback_answer(
                    chat_id=self.chat.id,
                    message_id=self.id,
                    callback_data=button.callback_data,
                    timeout=timeout
                )
            elif button.requires_password:
                if password is None:
                    raise ValueError(
                        "This button requires a password"
                    )

                return await self._client.request_callback_answer(
                    chat_id=self.chat.id,
                    message_id=self.id,
                    callback_data=button.callback_data,
                    password=password,
                    timeout=timeout
                )
            elif button.url:
                return button.url
            elif button.web_app:
                web_app = button.web_app

                bot_peer_id = (
                    self.via_bot and
                    self.via_bot.id
                ) or (
                    self.from_user and
                    self.from_user.is_bot and
                    self.from_user.id
                ) or None

                if not bot_peer_id:
                    raise ValueError(
                        "This button requires a bot as the sender"
                    )

                r = await self._client.invoke(
                    raw.functions.messages.RequestWebView(
                        peer=await self._client.resolve_peer(self.chat.id),
                        bot=await self._client.resolve_peer(bot_peer_id),
                        url=web_app.url,
                        platform=self._client.client_platform.value,
                        # TODO
                    )
                )
                return r.url
            elif button.user_id:
                return await self._client.get_chat(
                    button.user_id,
                    force_full=False
                )
            elif button.switch_inline_query:
                return button.switch_inline_query
            elif button.switch_inline_query_current_chat:
                return button.switch_inline_query_current_chat
            else:
                raise ValueError("This button is not supported yet")
        else:
            await self.reply(text=button, quote=quote)

    async def react(self, emoji: Union[int, str, List[Union[int, str]]] = None, big: bool = False) -> bool:
        """Bound method *react* of :obj:`~pyrogram.types.Message`.

        Use as a shortcut for:

        .. code-block:: python

            await client.send_reaction(
                chat_id=chat_id,
                message_id=message.id,
                emoji="🔥"
            )

        Example:
            .. code-block:: python

                await message.react(emoji="🔥")

        Parameters:
            emoji (``int`` | ``str`` | List of ``int`` | ``str``, *optional*):
                Reaction emoji.
                Pass None as emoji (default) to retract the reaction.
                Pass list of int or str to react multiple emojis.

            big (``bool``, *optional*):
                Pass True to show a bigger and longer reaction.
                Defaults to False.

        Returns:
            ``bool``: On success, True is returned.

        Raises:
            RPCError: In case of a Telegram RPC error.
        """

        return await self._client.send_reaction(
            chat_id=self.chat.id,
            message_id=self.id,
            emoji=emoji,
            big=big
        )

    async def retract_vote(
        self,
    ) -> "types.Poll":
        """Bound method *retract_vote* of :obj:`~pyrogram.types.Message`.

        Use as a shortcut for:

        .. code-block:: python

            client.retract_vote(
                chat_id=message.chat.id,
                message_id=message_id,
            )

        Example:
            .. code-block:: python

                message.retract_vote()

        Returns:
            :obj:`~pyrogram.types.Poll`: On success, the poll with the retracted vote is returned.

        Raises:
            RPCError: In case of a Telegram RPC error.
        """

        return await self._client.retract_vote(
            chat_id=self.chat.id,
            message_id=self.id
        )

    async def download(
        self,
        file_name: str = "",
        in_memory: bool = False,
        block: bool = True,
        progress: Callable = None,
        progress_args: tuple = ()
    ) -> str:
        """Bound method *download* of :obj:`~pyrogram.types.Message`.

        Use as a shortcut for:

        .. code-block:: python

            await client.download_media(message)

        Example:
            .. code-block:: python

                await message.download()

        Parameters:
            file_name (``str``, *optional*):
                A custom *file_name* to be used instead of the one provided by Telegram.
                By default, all files are downloaded in the *downloads* folder in your working directory.
                You can also specify a path for downloading files in a custom location: paths that end with "/"
                are considered directories. All non-existent folders will be created automatically.

            in_memory (``bool``, *optional*):
                Pass True to download the media in-memory.
                A binary file-like object with its attribute ".name" set will be returned.
                Defaults to False.

            block (``bool``, *optional*):
                Blocks the code execution until the file has been downloaded.
                Defaults to True.

            progress (``Callable``, *optional*):
                Pass a callback function to view the file transmission progress.
                The function must take *(current, total)* as positional arguments (look at Other Parameters below for a
                detailed description) and will be called back each time a new file chunk has been successfully
                transmitted.

            progress_args (``tuple``, *optional*):
                Extra custom arguments for the progress callback function.
                You can pass anything you need to be available in the progress callback scope; for example, a Message
                object or a Client instance in order to edit the message with the updated progress status.

        Other Parameters:
            current (``int``):
                The amount of bytes transmitted so far.

            total (``int``):
                The total size of the file.

            *args (``tuple``, *optional*):
                Extra custom arguments as defined in the ``progress_args`` parameter.
                You can either keep ``*args`` or add every single extra argument in your function signature.

        Returns:
            On success, the absolute path of the downloaded file as string is returned, None otherwise.

        Raises:
            RPCError: In case of a Telegram RPC error.
            ``ValueError``: If the message doesn't contain any downloadable media
        """
        return await self._client.download_media(
            message=self,
            file_name=file_name,
            in_memory=in_memory,
            block=block,
            progress=progress,
            progress_args=progress_args,
        )

    async def vote(
        self,
        option: int,
    ) -> "types.Poll":
        """Bound method *vote* of :obj:`~pyrogram.types.Message`.

        Use as a shortcut for:

        .. code-block:: python

            client.vote_poll(
                chat_id=message.chat.id,
                message_id=message.id,
                option=1
            )

        Example:
            .. code-block:: python

                message.vote(6)

        Parameters:
            option (``int``):
                Index of the poll option you want to vote for (0 to 9).

        Returns:
            :obj:`~pyrogram.types.Poll`: On success, the poll with the chosen option is returned.

        Raises:
            RPCError: In case of a Telegram RPC error.
        """

        return await self._client.vote_poll(
            chat_id=self.chat.id,
            message_id=self.id,
            options=option
        )

    async def pin(self, disable_notification: bool = False, both_sides: bool = False) -> "types.Message":
        """Bound method *pin* of :obj:`~pyrogram.types.Message`.

        Use as a shortcut for:

        .. code-block:: python

            await client.pin_chat_message(
                chat_id=message.chat.id,
                message_id=message_id
            )

        Example:
            .. code-block:: python

                await message.pin()

        Parameters:
            disable_notification (``bool``):
                Pass True, if it is not necessary to send a notification to all chat members about the new pinned
                message. Notifications are always disabled in channels.

            both_sides (``bool``, *optional*):
                Pass True to pin the message for both sides (you and recipient).
                Applicable to private chats only. Defaults to False.

        Returns:
            :obj:`~pyrogram.types.Message`: On success, the service message is returned.

        Raises:
            RPCError: In case of a Telegram RPC error.
        """
        return await self._client.pin_chat_message(
            chat_id=self.chat.id,
            message_id=self.id,
            disable_notification=disable_notification,
            both_sides=both_sides
        )

    async def unpin(self) -> bool:
        """Bound method *unpin* of :obj:`~pyrogram.types.Message`.

        Use as a shortcut for:

        .. code-block:: python

            await client.unpin_chat_message(
                chat_id=message.chat.id,
                message_id=message_id
            )

        Example:
            .. code-block:: python

                await message.unpin()

        Returns:
            True on success.

        Raises:
            RPCError: In case of a Telegram RPC error.
        """
        return await self._client.unpin_chat_message(
            chat_id=self.chat.id,
            message_id=self.id
        )

    async def read(self) -> bool:
        """Bound method *read* of :obj:`~pyrogram.types.Message`.

        Use as a shortcut for:

        .. code-block:: python

            await client.read_chat_history(
                chat_id=message.chat.id,
                max_id=message_id
            )

        Example:
            .. code-block:: python

                await message.read()

        Returns:
            True on success.

        Raises:
            RPCError: In case of a Telegram RPC error.
        """
        return await self._client.read_chat_history(
            chat_id=self.chat.id,
            max_id=self.id
        )

    async def view(self) -> bool:
        """Bound method *view* of :obj:`~pyrogram.types.Message`.

        Use as a shortcut for:

        .. code-block:: python

            await client.view_messages(
                chat_id=message.chat.id,
                message_id=message_id
            )

        Example:
            .. code-block:: python

                await message.view()

        Returns:
            True on success.

        Raises:
            RPCError: In case of a Telegram RPC error.
        """
        return await self._client.view_messages(
            chat_id=self.chat.id,
            message_id=self.id
        )

    async def pay(self) -> "types.PaymentResult":
        """Bound method *pay* of :obj:`~pyrogram.types.Message`.

        Use as a shortcut for:

        .. code-block:: python

            invoice = types.InputInvoiceMessage(
                    chat_id=chat_id,
                    message_id=123
                )

            form = await app.get_payment_form(invoice)

            await app.send_payment_form(
                payment_form_id=form.id,
                input_invoice=invoice
            )

        Example:
            .. code-block:: python

                await message.pay()

        Returns:
            :obj:`~pyrogram.types.PaymentResult`: On success, the payment result is returned.
        """
        invoice = types.InputInvoiceMessage(
            chat_id=self.chat.id,
            message_id=self.id
        )

        form = await self._client.get_payment_form(invoice)

        return await self._client.send_payment_form(
            payment_form_id=form.id,
            input_invoice=invoice
        )
