from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, ParseMode, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CallbackContext, CommandHandler, ConversationHandler, MessageHandler, Filters, CallbackQueryHandler
from configparser import SafeConfigParser
from datetime import datetime, date, timedelta, time
import logging
import math
import matplotlib.pyplot as plt
from operator import itemgetter
import os
import warnings # this warning is apparently normal..
warnings.filterwarnings("ignore", message="If 'per_message=False', 'CallbackQueryHandler' will not be tracked for every message.")

config = SafeConfigParser()
config.read("ident.ini")

updater = Updater(token=config.get("API","token"), use_context=True)
dispatcher = updater.dispatcher

logging.basicConfig(format='%(asctime)s - %(message)s',
                    level=logging.INFO,
                    handlers=[logging.FileHandler("log.log"),
                              logging.StreamHandler()])
logger = logging.getLogger(__name__)

DATUM, VONH, VONM, BISH, BISM, PAUSE, REMOVE, RAUS, NEWUSERHOURS, NEWUSERDAYS, LOESCH_MICH, LOESCHER, INLINETEST =range(13)
funfacts = {}
hours_n_days = {}

def log(user, text):
    logger.info(user.first_name + ", ID " + str(user.id) + ": " + text)

def db_ok(uid):
    if os.path.exists("dbs/" + str(uid) + ".txt"):
        with open("dbs/" + str(uid) + ".txt", "r") as f:
            f.readline()
            if f.readline() != "":
                return True
            else:
                return False
    else:
        return False

def nicetime(hours):
    hour = int(hours)
    minute = math.floor((hours * 60 % 60) + .5)
    if minute == 60:
        hour += 1
        minute = 0
    if minute != 0:
        return "%d h, %02d min" % (hour, minute)
    else:
        return "%d h" % hour

def strikedays(bitdays):
    outstring = ""
    days = [[0b1000000, "Mo"],
            [0b0100000, "Di"],
            [0b0010000, "Mi"],
            [0b0001000, "Do"],
            [0b0000100, "Fr"],
            [0b0000010, "Sa"],
            [0b0000001, "So"]]
    for day in days:
        if bitdays & day[0]:
            outstring += "*" + day[1] + "*, "
        else:
            outstring += "~" + day[1] + "~, "
    return outstring[:-2]

def is_workday(daydate, workdays): # bit shift by weekday and bitwise comparison
    if workdays & 1 << 6 - daydate.weekday():
        return True
    else:
        return False

def start(update: Update, context: CallbackContext):
    outstring = ("Hallo!\n"
                 "Dieser Bot ist ein Hobbyprojekt und aktiv in Entwicklung. "
                 "Bitte verlasse dich nicht darauf, dass alles immer korrekt "
                 "ausgegeben wird und sei dir bewusst, dass ich Einsicht in "
                 "alle gespeicherten Daten habe und diese zu Fehlerbehebung auch nutze.\n\n"
                 "Zur akkuraten Berechnung von Überstunden benötigt der Bot die Anzahl "
                 "deiner wöchentlichen Arbeitsstunden. Bitte gib sie nun ein.")
#    outstring = outstring.replace(".", "\.")
    context.bot.send_message(chat_id=update.effective_chat.id, text=outstring)
    user = update.message.from_user
    log(user, "Neue Anmeldung!")
    return NEWUSERHOURS

def newuserhours(update: Update, context: CallbackContext):
    user = update.message.from_user
    hours = int(update.message.text)
    hours_n_days[user.id] = [hours,0b0000000]
    outstring= (str(hours) + " Stunden sollen es sein.")
    update.message.reply_text(outstring)
    
    keyboard = [[InlineKeyboardButton("Mo", callback_data=64),
                 InlineKeyboardButton("Di", callback_data=32),
                 InlineKeyboardButton("Mi", callback_data=16),
                 InlineKeyboardButton("Do", callback_data=8),
                 InlineKeyboardButton("Fr", callback_data=4),
                 InlineKeyboardButton("Sa", callback_data=2),
                 InlineKeyboardButton("So", callback_data=1)],
                 [InlineKeyboardButton("Fertig", callback_data="fertig")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    context.bot.send_message(chat_id=update.effective_chat.id, 
                             text="An welchen Tagen arbeitest du?\nAusgewählt: " + strikedays(hours_n_days[user.id][1]),
                             reply_markup=reply_markup,
                             parse_mode=ParseMode.MARKDOWN_V2)
    return NEWUSERDAYS

def newuserdays(update: Update, context: CallbackContext):
    query = update.callback_query
    user = query.from_user
    query.answer()
    keyboard = [[InlineKeyboardButton("Mo", callback_data=64),
                 InlineKeyboardButton("Di", callback_data=32),
                 InlineKeyboardButton("Mi", callback_data=16),
                 InlineKeyboardButton("Do", callback_data=8),
                 InlineKeyboardButton("Fr", callback_data=4),
                 InlineKeyboardButton("Sa", callback_data=2),
                 InlineKeyboardButton("So", callback_data=1)],
                 [InlineKeyboardButton("Fertig", callback_data="fertig")]]
    if query.data != "fertig":
        hours_n_days[user.id][1] = hours_n_days[user.id][1] ^ int(query.data)
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text(text="An welchen Tagen arbeitest du?\nAusgewählt: " + strikedays(hours_n_days[user.id][1]),
                                reply_markup=reply_markup,
                                parse_mode=ParseMode.MARKDOWN_V2)
    else:
        if os.path.exists("dbs/" + str(user.id) + ".txt"):
            with open("dbs/" + str(user.id) + ".txt", "r") as f:
                lines = f.readlines()
            with open("dbs/" + str(user.id) + ".txt", "w") as f:
                f.write(str(hours_n_days[user.id][0]) + ";" + "{:07b}".format(hours_n_days[user.id][1]) + "\n")
                for i, line in enumerate(lines):
                    if i > 0:
                        f.write(line)
            log(user, "Gibbet schon, nun mit " + str(hours_n_days[user.id][0]) + " Stunden und " + 
                "{:07b}".format(hours_n_days[user.id][1]) + " Tagen.")
            query.edit_message_text(text="An welchen Tagen arbeitest du?\nAusgewählt: " + strikedays(hours_n_days[user.id][1]) + 
                                    "\nAuswahl beendet\. Der User war bereits angelegt\. Seine Einstellungen wurden aktualisiert\.",
                                    parse_mode=ParseMode.MARKDOWN_V2)
        else:
            with open("dbs/" + str(user.id) + ".txt", "a+") as f:
                f.write(str(hours_n_days[user.id][0]) + ";" + "{:07b}".format(hours_n_days[user.id][1]) + "\n")
            log(user, "User angelegt mit " + str(hours_n_days[user.id][0]) + " Stunden und " + 
                "{:07b}".format(hours_n_days[user.id][1]) + " Tagen.")        
            query.edit_message_text(text="An welchen Tagen arbeitest du?\nAusgewählt: " + strikedays(hours_n_days[user.id][1]) + 
                                    "\nAuswahl beendet\. Der Bot ist nun einsatzbereit\.\n" + 
                                    "Bitte lege nun mit \/a deinen ersten Eintrag an\.",
                                    parse_mode=ParseMode.MARKDOWN_V2)
        return ConversationHandler.END
        

def neuearbeit(update: Update, context: CallbackContext):
    user = update.message.from_user
    if os.path.exists("dbs/" + str(user.id) + ".txt"):
        funfacts[user.id] = {}
        reply_keyboard = [['Heute'],
                          ['Gestern', 'Vorgestern']]
        user = update.message.from_user
        log(user, "Neuer Eintrag gestartet")
        update.message.reply_text('Welcher Tag? (Button oder Eingabe nach art YYYY;MM;DD)',
                                  reply_markup=ReplyKeyboardMarkup(reply_keyboard,
                                                                   one_time_keyboard=True))
        return DATUM
    else:
        log(user, "Error! Neuer Eintrag konne nicht angelegt werden, Datei existiert nicht.")
        context.bot.send_message(chat_id=update.effective_chat.id,
                                         text="Error! Bitte erst über /start ein Dienstbuch anlegen.")
        return ConversationHandler.END
    
def datum(update: Update, context: CallbackContext):
    user = update.message.from_user
    datu = update.message.text
    if "Heute" in datu:
        funfacts[user.id]["date"] = datetime.now().strftime("%Y;%m;%d")
    elif "Gestern" in datu:
        funfacts[user.id]["date"] = (datetime.now() - timedelta(days=1)).strftime("%Y;%m;%d")
    elif "Vorgestern" in datu:
        funfacts[user.id]["date"] = (datetime.now() - timedelta(days=2)).strftime("%Y;%m;%d")
    else:
        funfacts[user.id]["date"] = datu
    reply_keyboard = [['01','02','03','04','05','06'],
                      ['07','08','09','10','11','12'],
                      ['13','14','15','16','17','18'],
                      ['19','20','21','22','23','24']
                     ]
    update.message.reply_text('Ab wann? (Stunde)',
                              reply_markup=ReplyKeyboardMarkup(reply_keyboard,
                                                               one_time_keyboard=True))
    return VONH

def vonh(update: Update, context: CallbackContext):
    user = update.message.from_user
    funfacts[user.id]["vonh"] = update.message.text
    reply_keyboard = [['05','10','15'],
                      ['20','25','30'],
                      ['35','40','45'],
                      ['50','55','00']
                     ]
    update.message.reply_text('kk.\nAb wann? (Minute)',
                              reply_markup=ReplyKeyboardMarkup(reply_keyboard,
                                                               one_time_keyboard=True))
    return VONM

def vonm(update: Update, context: CallbackContext):
    user = update.message.from_user
    funfacts[user.id]["vonm"] = update.message.text
    reply_keyboard = [['01','02','03','04','05','06'],
                      ['07','08','09','10','11','12'],
                      ['13','14','15','16','17','18'],
                      ['19','20','21','22','23','24']]
    update.message.reply_text('kk.\nBis wann? (Stunde)',
                              reply_markup=ReplyKeyboardMarkup(reply_keyboard,
                                                               one_time_keyboard=True))
    return BISH

def bish(update: Update, context: CallbackContext):
    user = update.message.from_user
    funfacts[user.id]["bish"] = update.message.text
    reply_keyboard = [['05','10','15'],
                      ['20','25','30'],
                      ['35','40','45'],
                      ['50','55','00']]
    update.message.reply_text('kk.\nBis wann? (Minute)',
                              reply_markup=ReplyKeyboardMarkup(reply_keyboard,
                                                               one_time_keyboard=True))
    return BISM

def bism(update: Update, context: CallbackContext):
    user = update.message.from_user
    funfacts[user.id]["bism"] = update.message.text
    reply_keyboard = [['0'],['5','10','15'],['20','25','30'],
                      ['45','60','75','90']]
    update.message.reply_text('kk.\nWie lange pausiert? (Minuten)',
                              reply_markup=ReplyKeyboardMarkup(reply_keyboard,
                                                               one_time_keyboard=True))
    return PAUSE

def pause(update: Update, context: CallbackContext):
    user = update.message.from_user
    funfacts[user.id]["pau"] = update.message.text
    zeit = zeitrechner(*list(map(int, [funfacts[user.id]["vonh"],
                                       funfacts[user.id]["vonm"],
                                       funfacts[user.id]["bish"],
                                       funfacts[user.id]["bism"],
                                       funfacts[user.id]["pau"]])))
    update.message.reply_text(update.message.text + ' also. \nGuten Feierabend! Nochmal: ' +
                              funfacts[user.id]["vonh"] + ":" + funfacts[user.id]["vonm"] + ", " +
                              funfacts[user.id]["bish"] + ":" + funfacts[user.id]["bism"] + ", " +
                              funfacts[user.id]["pau"] + ".\nDas macht " + nicetime(zeit) + ".",)
    f = open("dbs/" + str(user.id) + ".txt", "a+")

    f.write(funfacts[user.id]["date"] + ";" + funfacts[user.id]["vonh"] + ";" +
            funfacts[user.id]["vonm"] + ";" + funfacts[user.id]["bish"] + ";" +
            funfacts[user.id]["bism"] + ";" + funfacts[user.id]["pau"] + "\n")
    f.close
    log(user, "Neuer Eintrag angelegt: " +
        funfacts[user.id]["vonh"] + ":" + funfacts[user.id]["vonm"] + ";" +
        funfacts[user.id]["bish"] + ":" + funfacts[user.id]["bism"] + ";" +
        funfacts[user.id]["pau"])
    return ConversationHandler.END

def cancel(update: Update, context: CallbackContext):
    user = update.message.from_user
    log(user, "Aktion abgebrochen.")
    update.message.reply_text('OK, dann besser nicht.',
                              reply_markup = ReplyKeyboardRemove())
    return ConversationHandler.END

def zeitrechner(von_h, von_m, bis_h, bis_m, paus):
    soviel = bis_h - von_h + (bis_m - von_m - paus) / 60
    return soviel

def stats(update: Update, context: CallbackContext):
    # context.bot.send_message(chat_id=timtimID,
    #                          text=":3",
    #                          parse_mode=ParseMode.MARKDOWN_V2)
    user = update.message.from_user
    if db_ok(user.id):
        log(user, "Stats abgerufen")
        with open("dbs/" + str(user.id) + ".txt", "r") as f:
            ndata = []
            for i, line in enumerate(f):
                if i == 0:
                    h, d = line.rstrip("\n").split(";")
                    hourperweek = int(h)
                    workdays = int(d,2)
                    daysperweek = bin(workdays).count("1")
                    hourperday = hourperweek / daysperweek
                else:
                    el = list(map(int, line.rstrip("\n").split(";")))
                    tag = date(*el[0:3])
                    # datestring, year, month, day, week, worktime
                    ndata.append([tag,
                                  *el[0:3],
                                  tag.isocalendar()[1],
                                  zeitrechner(*list(map(int, el[3:])))])
        ndata = sorted(ndata, key=itemgetter(0))
        outstring = ""
        week = date.today().isocalendar()[1]
        times = []
        for line in ndata:
            if line[4] == week:
                times.append(line[5])
        if len(times) > 0:
            outstring += "*__Diese Woche:__*\n"
            outstring += ("Tage gearbeitet: " + str(len(times)) + "\n" +
                         "Durchschn. Zeit: " + nicetime(sum(times)/len(times)) + "\n" +
                         "Arbeitszeit ges.: " + nicetime(sum(times)) + "\n\n")
        week = (week - 2)%52 + 1
        times = []
        for line in ndata:
            if line[4] == week:
                times.append(line[5])
        if len(times) > 0:
            outstring += "*__Letzte Woche:__*\n"
            outstring += ("Tage gearbeitet: " + str(len(times)) + "\n" +
                         "Durchschn. Zeit: " + nicetime(sum(times)/len(times)) + "\n" +
                         "Arbeitszeit ges.: " + nicetime(sum(times)) + "\n\n")
    
        month = date.today().month
        times = []
        for line in ndata:
            if line[2] == month:
                times.append(line[5])
        if len(times) > 0:
            outstring += "*__Diesen Monat:__*\n"
            outstring += ("Tage gearbeitet: " + str(len(times)) + "\n" +
                         "Durchschn. Zeit: " + nicetime(sum(times)/len(times)) + "\n" +
                         "Arbeitszeit ges.: " + nicetime(sum(times)) + "\n\n")
        month = (month - 2)%12 + 1
        month_last = date.today().replace(day=1) - timedelta(days=1)
        month_list = [month_last - timedelta(days = x) for x in range(month_last.day)]
        if ndata[0][0] in month_list: # wenn monat unvollständig
            month_list = month_list[:month_list.index(ndata[0][0])+1] # kürzen aller früheren tage (hinten in liste)
        month_workdays = 0
        for day in month_list:
            if is_workday(day, workdays):
                month_workdays += 1
        times = []
        for line in ndata:
            if line[2] == month:
                times.append(line[5])
        if len(times) > 0:
            outstring += "*__Letzten Monat:__*\n"
            outstring += ("Tage gearbeitet: " + str(len(times)) + "\n" +
                         "Durchschn. Zeit: " + nicetime(sum(times)/len(times)) + "\n" +
                         "Soll: " + nicetime(hourperday * month_workdays) + "\n" +
                         "Arbeitszeit ges.: " + nicetime(sum(times)) + "\n\n")
      
        day1 = ndata[0][0]
        dayrange = date.today() - day1
        datelist = [day1 + timedelta(days = x) for x in range(dayrange.days + 1)]
        alltime_workdays = 0
        for day in datelist:
            if is_workday(day, workdays):
                alltime_workdays += 1
        
        if date.today() not in [a[0] for a in ndata]: # dont count today if there isnt an entry already
            alltime_workdays -= 1
        
        times = [row[5] for row in ndata]
        outstring += "*__Insgesamt:__*\n"
        outstring += ("Anzahl an Einträgen: " + str(len(ndata)) + "\n" +
                     "Durchschn. Zeit: " + nicetime(sum(times)/len(times)) + "\n" +
                     "Soll: " + nicetime(hourperday * alltime_workdays) + "\n" +
                     "Arbeitszeit ges.: " + nicetime(sum(times)) + "\n")
        
        ueber_unter = hourperday * alltime_workdays - sum(times)
        if ueber_unter == 0:
            outstring += "\n"
        elif ueber_unter > 0:
            outstring += "Du bist " + nicetime(ueber_unter) + " im Minus.\n\n"
        else:
            outstring += "Du bist " + nicetime(-ueber_unter) + " im Plus.\n\n"
        
        outstring = outstring.replace(".", "\.")

        timelist = [0] * (dayrange.days+1)
        for i, dat in enumerate(datelist):
            if is_workday(dat, workdays): # show zeros
                timelist[i] = 0.1
            for line in ndata:
                if line[0] == dat:
                    timelist[i] = line[5] 
        
        # weekly averages
        weeklyavg = {}
        weeks = set(line[4] for line in ndata)
        for week in weeks:
            days = [i for i in ndata if i[4] == week]
            # für aktuelle und erste woche nicht alle tage rechnen
            if week == date.today().isocalendar()[1]: 
                numdays = len(days)
                numdays = 0
                for day in [date.today()-timedelta(days = x) for x in range(date.today().weekday()+1)]:
                    if is_workday(day, workdays):
                        numdays += 1
                if date.today() not in [a[0] for a in ndata]: # dont count today if there isnt an entry already
                    numdays -= 1
            elif week == min(weeks):
                numdays = 0
                daysleft = 6 - days[0][0].weekday()
                for day in [days[0][0]+timedelta(days = x) for x in range(daysleft+1)]:
                    if is_workday(day, workdays):
                        numdays += 1
            else:
                numdays = daysperweek
            avg = sum(i[5] for i in days) / numdays
            datemin = datetime.combine(min(i[0] for i in days), time.min) - timedelta(hours = 12)
            datemax = datetime.combine(max(i[0] for i in days), time.min) + timedelta(hours = 12)
            weeklyavg[week] = [[datemin, datemax], [avg, avg]]
        
        plt.style.use("ggplot")
        fig,ax = plt.subplots()
        fig.set_size_inches(11, 5, forward=True)
        ax.bar(datelist,timelist, color="#2a9c48")
        for week in weeklyavg:
            ax.plot(*weeklyavg[week], color='#124720', linestyle='dotted')
        ax.autoscale(enable=True, axis='x', tight=True)
        ax.set_yticks(range(math.ceil(max(timelist))))
        ax.set_xticks(datelist)
        ax.set_xticklabels(datelist,rotation=90)
        ax.axhline(y = hourperday, color='k', linestyle='--')
        plt.tight_layout()
        plt.savefig("plots/" + str(user.id) + ".png")
        plt.close(fig)
        
        with open("plots/" + str(user.id) + ".png","rb") as pho:
            context.bot.send_photo(chat_id=update.effective_chat.id,
                                   photo = pho)
            
        update.message.reply_text(outstring, parse_mode=ParseMode.MARKDOWN_V2)
    else:
        log(user, "Error! Stats konnten nicht erstellt werden, Datei existiert nicht.")
        context.bot.send_message(chat_id=update.effective_chat.id,
                                         text="Error! Bitte erst über /start ein Dienstbuch anlegen und mit /a einen Eintrag anlegen.")
    
def raw(update: Update, context: CallbackContext):
    user = update.message.from_user
    if db_ok(user.id):
        log(user, "Rohdaten abgerufen.")
        with open("dbs/" + str(user.id) + ".txt", "r") as f:
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text="`" + f.read() + "`",
                                     parse_mode=ParseMode.MARKDOWN_V2)
    else:
        log(user, "Error! Rohdaten konnten nicht abgerufen werden, Datei existiert nicht.")
        context.bot.send_message(chat_id=update.effective_chat.id,
                                         text="Error! Bitte erst über /start ein Dienstbuch anlegen und mit /a einen Eintrag anlegen.")
        
def remove(update: Update, context: CallbackContext):
    user = update.message.from_user
    if db_ok(user.id):
        log(user, "Eintrag entfernen!")
        outstring = "`"
        with open("dbs/" + str(user.id) + ".txt", "r") as f:
            for i, line in enumerate(f.readlines()):
                if i == 0:
                    pass
                else:
                    outstring += "{0:04d}".format(i) + ": " + line
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text=outstring + "`\nWelcher Eintrag soll gelöscht werden? \(ID\)",
                                 parse_mode=ParseMode.MARKDOWN_V2)
        return RAUS
    else:
        log(user, "Error! Eintrag konnte nicht entfernt werden, Datei existiert nicht.")
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text="Error! Bitte erst über /start ein Dienstbuch anlegen und mit /a einen Eintrag anlegen.")
        return ConversationHandler.END
    
def raus(update: Update, context: CallbackContext):
    user = update.message.from_user
    log(user, "Eintrag entfernt.")
    id = int(update.message.text)
    a = False
    with open("dbs/" + str(user.id) + ".txt", "r") as f:
        lines = f.readlines()
    with open("dbs/" + str(user.id) + ".txt", "w") as f:
        for i, line in enumerate(lines):
            if i != id:
                f.write(line)
            else:
                a = True
    if a:
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text="`" + lines[id] + "`\nwurde gelöscht\.",
                                 parse_mode=ParseMode.MARKDOWN_V2)
    else:
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text="Error!")
    return ConversationHandler.END
    
def loesch_mich(update: Update, context: CallbackContext):
    user = update.message.from_user
    if db_ok(user.id):
        log(user, "Dienstbuch löschen!")
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text="Sollen *alle* deine Einträge gelöscht werden?\n" +
                                 "Bitte bestätige indem du _Tschau_ schreibst oder breche die Operation mit \\cancel ab\.",
                                 parse_mode=ParseMode.MARKDOWN_V2)
        return LOESCHER
    else:
        log(user, "Error! Dienstbuch konnte nicht gelöscht werden, Datei existiert nicht.")
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text="Error! Dein Dienstbuch existiert nicht.")
        return ConversationHandler.END

def loescher(update: Update, context: CallbackContext):
    user = update.message.from_user
    os.remove("dbs/" + str(user.id) + ".txt")
    log(user, "Dienstbuch gelöscht!")
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text="Okay. Machs gut!")
    return ConversationHandler.END

def logs(update: Update, context: CallbackContext):
    user = update.message.from_user
    if user.id == int(config.get("special_users","admin")):
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text="`" + os.popen("tail -n 20 log.log").read() + "`",
                                 parse_mode=ParseMode.MARKDOWN_V2)
        
def show_users(update: Update, context: CallbackContext):
    user = update.message.from_user
    if user.id == int(config.get("special_users","admin")):
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text="`" + os.popen("ls -lh dbs/").read() + "`",
                                 parse_mode=ParseMode.MARKDOWN_V2)
   
def psa(update: Update, context: CallbackContext):
    user = update.message.from_user
    if user.id == int(config.get("special_users","admin")):
        ids = [int(a.replace(".txt","")) for a in os.listdir("dbs") if "example" not in a]
        psa_message = update.message.text.replace("/psa ", "")
        for userid in ids:
            try:
                context.bot.send_message(chat_id=userid,
                                         text=psa_message,
                                         parse_mode=ParseMode.MARKDOWN_V2)
                log(user, "PSA sent to " + str(userid) + ".")
            except:
                log(user, "PSA Error! Bot may be blocked by " + str(userid) + ".")
                
def inlinetest(update: Update, context: CallbackContext):
    user = update.message.from_user
    hours_n_days[user.id] = [0,0b0000000]
    if user.id == int(config.get("special_users","admin")):
        keyboard = [[InlineKeyboardButton("Mo", callback_data=64),
                     InlineKeyboardButton("Di", callback_data=32),
                     InlineKeyboardButton("Mi", callback_data=16),
                     InlineKeyboardButton("Do", callback_data=8),
                     InlineKeyboardButton("Fr", callback_data=4),
                     InlineKeyboardButton("Sa", callback_data=2),
                     InlineKeyboardButton("So", callback_data=1)],
                     [InlineKeyboardButton("Fertig", callback_data="fertig")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        context.bot.send_message(chat_id=update.effective_chat.id, 
                                 text="Ausgewählt: " + strikedays(hours_n_days[user.id][1]),
                                 reply_markup=reply_markup,
                                 parse_mode=ParseMode.MARKDOWN_V2)
        
def button(update: Update, context: CallbackContext):
    query = update.callback_query
    user = query.from_user
    query.answer()
    keyboard = [[InlineKeyboardButton("Mo", callback_data=64),
                 InlineKeyboardButton("Di", callback_data=32),
                 InlineKeyboardButton("Mi", callback_data=16),
                 InlineKeyboardButton("Do", callback_data=8),
                 InlineKeyboardButton("Fr", callback_data=4),
                 InlineKeyboardButton("Sa", callback_data=2),
                 InlineKeyboardButton("So", callback_data=1)],
                 [InlineKeyboardButton("Fertig", callback_data="fertig")]]
    if query.data == "fertig":
        query.edit_message_text(text="Ausgewählt: " + strikedays(hours_n_days[user.id][1]) + 
                                "\nAuswahl beendet\. Der Bot ist nun einsatzbereit\.\n" + 
                                "Bitte lege nun mit \/a deinen ersten Eintrag an\.",
                                parse_mode=ParseMode.MARKDOWN_V2)
    else:
        hours_n_days[user.id][1] = hours_n_days[user.id][1] ^ int(query.data)
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text(text="Ausgewählt: " + strikedays(hours_n_days[user.id][1]),
                                reply_markup=reply_markup,
                                parse_mode=ParseMode.MARKDOWN_V2)

conv_handler = ConversationHandler(
    entry_points=[CommandHandler('a',neuearbeit)],
    states={
        DATUM: [MessageHandler(Filters.regex('^[0-9;]+$|Heute|Gestern|Vorgestern'), datum)],
        VONH: [MessageHandler(Filters.regex('^[0-9]+$'), vonh)],
        VONM: [MessageHandler(Filters.regex('^[0-9]+$'), vonm)],
        BISH: [MessageHandler(Filters.regex('^[0-9]+$'), bish)],
        BISM: [MessageHandler(Filters.regex('^[0-9]+$'), bism)],
        PAUSE: [MessageHandler(Filters.regex('^[0-9]+$'), pause)],
    },
    fallbacks=[CommandHandler('cancel', cancel)],
)

remconv_handler = ConversationHandler(
    entry_points=[CommandHandler('remove',remove)],
    states={
        RAUS: [MessageHandler(Filters.regex('^(?!0000)[0-9]{4}$'), raus)],
    },
    fallbacks=[CommandHandler('cancel', cancel)],
)

start_handler = ConversationHandler(
    entry_points=[CommandHandler('start',start)],
    states={
        NEWUSERHOURS: [MessageHandler(Filters.regex('^[0-9]+$'), newuserhours)],
        NEWUSERDAYS: [CallbackQueryHandler(newuserdays)],
    },
    fallbacks=[CommandHandler('cancel', cancel)],
)

loesch_mich_handler = ConversationHandler(
    entry_points=[CommandHandler('loesch_mich',loesch_mich)],
    states={
        LOESCHER: [MessageHandler(Filters.regex('^Tschau$'), loescher)],
    },
    fallbacks=[CommandHandler('cancel', cancel)],
)

#start_handler = CommandHandler('start', start)
dispatcher.add_handler(start_handler)
dispatcher.add_handler(conv_handler)
dispatcher.add_handler(loesch_mich_handler)

#neuearbeit_handler = CommandHandler('a', neuearbeit)
#dispatcher.add_handler(neuearbeit_handler)

stats_handler = CommandHandler('stats', stats)
dispatcher.add_handler(stats_handler)
raw_handler = CommandHandler('raw', raw)
dispatcher.add_handler(raw_handler)

#remove_handler = CommandHandler('remove', remove)
#dispatcher.add_handler(conv_handler)
dispatcher.add_handler(remconv_handler)

logs_handler = CommandHandler('logs', logs)
dispatcher.add_handler(logs_handler)
show_users_handler = CommandHandler('show_users', show_users)
dispatcher.add_handler(show_users_handler)
psa_handler = CommandHandler('psa', psa)
dispatcher.add_handler(psa_handler)

updater.start_polling()
updater.idle()

