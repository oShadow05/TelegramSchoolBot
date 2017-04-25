"""
Interact with your school website with telegram!

Copyright (c) 2016-2017 Paolo Barbolini <paolo@paolo565.org>
Released under the MIT license
"""

import botogram
import html
import pynamodb

from . import models
from . import utils


class Commands(botogram.components.Component):
    """All of the TelegramSchoolBot commands"""

    component_name = "tsb-commands"

    TABLES = {
        "Di quale classe vuoi sapere l'orario?": "class",
        "Qual'è il nome del prof di cui vuoi sapere l'orario?": "teacher",
        "Di quale aula vuoi sapere l'orario?": "classroom",
    }

    TABLE_MESSAGE = {
        "class": "Classe: %s",
        "teacher": "Prof: %s",
        "classroom": "Aula: %s",
    }

    def __init__(self):
        self.add_command("start", self.start_command, hidden=True)
        self.add_command("notifiche", self.notification_command, order=10)
        self.add_command("classe", self.class_command, order=20)
        self.add_command("prof", self.prof_command, order=30)
        self.add_command("aula", self.classroom_command, order=40)
        self.add_process_message_hook(self.message_received)
        self.add_chat_unavailable_hook(self.chat_unavailable)


    def start_command(self, bot, chat):
        lines = [
            bot.about,
            "",
            "Utilizza /help per ottenere la lista di tutti i comandi.",
            "Per ricevere una notifica quando esce un nuovo avviso fai /iscriviti"
        ]

        chat.send("\n".join(lines))


    def notification_command(self, bot, chat, message, args):
        """Abilita/Disabilita le notifiche per gli avvisi."""

        try:
            subscription = models.SubscriberModel.get(chat.id)
            subscription.delete()

            lines = [
                "Disiscrizione dalle notifiche completata con successo.",
                "Da ora non riceverai più notifiche riguardanti le nuove circolari pubblicate sul sito.",
                "Per riabilitarle fai /notifiche",
            ]

            message.reply("\n".join(lines))
            return
        except pynamodb.exceptions.DoesNotExist:
            pass

        lines = [
            "Iscrizione alle notifiche completata con successo.",
            "Ad ogni ora riceverai un messaggio con gli avvisi pubblicati nell'ultima ora se ce ne sono.",
            "Non bloccare il bot altrimenti sarai disiscritto automaticamente dalle notifiche."
        ]

        subscription = models.SubscriberModel(chat_id=chat.id)
        subscription.save()
        message.reply("\n".join(lines))


    def class_command(self, bot, chat, message, args):
        """Mostra gli orari di una classe."""

        if len(args) == 0:
            message.reply("Di quale classe vuoi sapere l'orario?", syntax="plain",
                          extra=botogram.ForceReply(data={
                              "force_reply": True,
                              "selective": True
                          }))
            return

        name = " ".join(args)
        try:
            page = models.PageModel.get("class", name.lower())
        except pynamodb.exceptions.DoesNotExist:
            message.reply("Non ho trovato la classe <b>%s</b>" % html.escape(name), syntax="html")
            return

        utils.send_page(bot, message, page, "Classe: %s" % page.display_name)


    def prof_command(self, bot, chat, message, args):
        """Mostra gli orari di un prof."""

        if len(args) == 0:
            message.reply("Qual'è il nome del prof di cui vuoi sapere l'orario?", syntax="plain",
                          extra=botogram.ForceReply(data={
                              "force_reply": True,
                              "selective": True
                          }))
            return

        name = " ".join(args)
        pages = models.PageModel.query("teacher", name__begins_with=name.lower(), limit=2)
        pages = list(pages)

        if len(pages) == 0:
            message.reply("Non ho trovato il prof <b>%s</b>" % html.escape(name), syntax="html")
            return
        if len(pages) > 1:
            message.reply("I criteri di ricerca inseriti coincidono con più di un risultato.")
            return

        utils.send_page(bot, message, pages[0], "Prof: %s" % pages[0].display_name)


    def classroom_command(self, bot, chat, message, args):
        """Mostra gli orari di un'aula."""

        if len(args) == 0:
            message.reply("Di quale aula vuoi sapere l'orario?", syntax="plain",
                          extra=botogram.ForceReply(data={
                              "force_reply": True,
                              "selective": True
                          }))
            return

        name = " ".join(args)
        pages = models.PageModel.query("classroom", name__begins_with=name.lower(), limit=2)
        pages = list(pages)

        if len(pages) == 0:
            message.reply("Non ho trovato l'aula <b>%s</b>" % html.escape(name), syntax="html")
            return
        if len(pages) > 1:
            message.reply("I criteri di ricerca inseriti coincidono con più di un risultato.")
            return

        utils.send_page(bot, message, pages[0], "Aula: %s" % pages[0].display_name)


    def message_received(self, bot, chat, message):
        query = message.text.lower()
        types = []

        if message.reply_to_message is not None and message.reply_to_message.text in self.TABLES:
            bot_text = message.reply_to_message.text
            types = [self.TABLES[bot_text]]
        else:
            types = self.TABLES.values()

        for type in types:
            if type == "class":
                # Small hack to prevent problems when there's a class like 1H and 1Hs
                try:
                    pages = [models.PageModel.get(type, query)]
                except pynamodb.exceptions.DoesNotExist:
                    continue
            else:
                pages = models.PageModel.query(type, name__begins_with=query, limit=2)
                pages = list(pages)

            if len(pages) == 0:
                continue

            if len(pages) > 1:
                message.reply("I criteri di ricerca inseriti coincidono con più di un risultato.")
                return

            utils.send_page(bot, message, pages[0], self.TABLE_MESSAGE[pages[0].type] % pages[0].display_name)
            return

        message.reply("Non ho trovato niente")


    def chat_unavailable(self, chat_id):
        try:
            subscription = models.SubscriberModel.get(chat_id)
        except pynamodb.exceptions.DoesNotExist:
            return

        subscription.delete()
