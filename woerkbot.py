from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, ParseMode
from telegram.ext import Updater, CallbackContext, CommandHandler, ConversationHandler, MessageHandler, Filters
from configparser import SafeConfigParser
from datetime import datetime, date, timedelta
import logging
import math
import matplotlib.pyplot as plt
from operator import itemgetter
from os.path import exists

config = SafeConfigParser()
config.read("ident.ini")

updater = Updater(token=config.get("API","token"), use_context=True)
dispatcher = updater.dispatcher

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

DATUM, VONH, VONM, BISH, BISM, PAUSE, REMOVE, RAUS, NEWUSER =range(9)
funfacts = {}

def log(user, text):
    logger.info(user.first_name + ", ID " + str(user.id) + ": " + text)

def start(update: Update, context: CallbackContext):
    outstring = ("Hallo!\n"
                 "Dieser Bot ist ein Hobbyprojekt und aktiv in Entwicklung. "
                 "Bitte verlasse dich nicht darauf, dass alles immer korrekt "
                 "ausgegeben wird und sei dir bewusst, dass ich Einsicht in "
                 "alle gespeicherten Daten habe und diese zu Fehlerbehebung auch nutze.\n\n"
                 "Der Bot geht aktuell davon aus, dass sich deine Arbeitszeit im "
                 "Normalfall auf 5 Tage verteilt. Zur akkuraten Berechnung von benötigt "
                 "er deine wöchentlichen Arbeitsstunden. Bitte gib sie nun ein.")
#    outstring = outstring.replace(".", "\.")
    context.bot.send_message(chat_id=update.effective_chat.id, text=outstring)
    user = update.message.from_user
    log(user, "Neue Anmeldung!")
    return NEWUSER

def newuser(update: Update, context: CallbackContext):
    user = update.message.from_user
    hours = int(update.message.text)
    if exists("dbs/" + str(user.id) + ".txt"):
        with open("dbs/" + str(user.id) + ".txt", "r") as f:
            lines = f.readlines()
        with open("dbs/" + str(user.id) + ".txt", "w") as f:
            f.write(str(hours) + "\n")
            for i, line in enumerate(lines):
                if i > 0:
                    f.write(line)
        log(user, "Gibbet schon, nun mit " + str(hours) + " Stunden.")
        update.message.reply_text("User war bereits angelegt, Wochenstundenzahl wurde mit " + 
                                  str(hours) + " h überschrieben.")
    else:
        with open("dbs/" + str(user.id) + ".txt", "a+") as f:
            f.write(str(hours) + "\n")
            log(user, "User mit " + str(hours) + " Wochenstunden angelegt.")
            update.message.reply_text(str(hours) + " sollen es sein.")
    return ConversationHandler.END

def neuearbeit(update: Update, context: CallbackContext):
    user = update.message.from_user
    funfacts[user.id] = {}
    reply_keyboard = [['Heute'],
                      ['Gestern', 'Vorgestern']]
    user = update.message.from_user
    log(user, "Neuer Eintrag gestartet")
    update.message.reply_text('Welcher Tag? (Button oder Eingabe nach art YYYY;MM;DD)',
                              reply_markup=ReplyKeyboardMarkup(reply_keyboard,
                                                               one_time_keyboard=True))
    return DATUM
    
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
                              funfacts[user.id]["pau"] + ".\nDas macht " + "{:.2f}".format(zeit) + " Stunden.",)
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
    log(user, "Stats abgerufen")
    with open("dbs/" + str(user.id) + ".txt", "r") as f:
        ndata = []
        for i, line in enumerate(f):
            if i == 0:
                pass
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
                     "Durchschn. Zeit: " + "{:.2f}".format(sum(times)/len(times)) + " h\n" +
                     "Arbeitszeit ges.: " + "{:.2f}".format(sum(times)) + " h\n\n")
    week = (week - 2)%52 + 1
    times = []
    for line in ndata:
        if line[4] == week:
            times.append(line[5])
    if len(times) > 0:
        outstring += "*__Letzte Woche:__*\n"
        outstring += ("Tage gearbeitet: " + str(len(times)) + "\n" +
                     "Durchschn. Zeit: " + "{:.2f}".format(sum(times)/len(times)) + " h\n" +
                     "Arbeitszeit ges.: " + "{:.2f}".format(sum(times)) + " h\n\n")

    month = date.today().month
    times = []
    for line in ndata:
        if line[2] == month:
            times.append(line[5])
    if len(times) > 0:
        outstring += "*__Diesen Monat:__*\n"
        outstring += ("Tage gearbeitet: " + str(len(times)) + "\n" +
                     "Durchschn. Zeit: " + "{:.2f}".format(sum(times)/len(times)) + " h\n" +
                     "Arbeitszeit ges.: " + "{:.2f}".format(sum(times)) + " h\n\n")
    month = (month - 2)%12 + 1
    times = []
    for line in ndata:
        if line[2] == month:
            times.append(line[5])
    if len(times) > 0:
        outstring += "*__Letzten Monat:__*\n"
        outstring += ("Tage gearbeitet: " + str(len(times)) + "\n" +
                     "Durchschn. Zeit: " + "{:.2f}".format(sum(times)/len(times)) + " h\n" +
                     "Arbeitszeit ges.: " + "{:.2f}".format(sum(times)) + " h\n\n")
    
    times = [row[5] for row in ndata]
    ueber_unter = 6*len(times) - sum(times)
    outstring += "*__Insgesamt:__*\n"
    outstring += ("Anzahl an Einträgen: " + str(len(ndata)) + "\n" +
                 "Durchschn. Zeit: " + "{:.2f}".format(sum(times)/len(times)) + " h\n" +
                 "Soll: " + "{:.2f}".format(6*len(times)) + " h\n" +
                 "Arbeitszeit ges.: " + "{:.2f}".format(sum(times)) + " h\n")
    if ueber_unter == 0:
        outstring += "\n"
    elif ueber_unter > 0:
        outstring += "Du bist " + "{:.2f}".format(ueber_unter) + " h im Minus.\n\n"
    else:
        outstring += "Du bist " + "{:.2f}".format(-ueber_unter) + " h im Plus.\n\n"
    
    outstring = outstring.replace(".", "\.")
    
    day1 = ndata[0][0]
    dayrange = date.today() - day1
    datelist = [day1 + timedelta(days = x) for x in range(dayrange.days + 1)]
    timelist = [0] * (dayrange.days+1)
    for i, dat in enumerate(datelist):
        for line in ndata:
            if line[0] == dat:
                timelist[i] = max(line[5], 0.1) # show zeros
                
    # plt.style.use("ggplot")
    # fig,ax = plt.subplots()
    # ax.barh(datelist,timelist, color="#2a9c48")
    # ax.set_yticks(datelist)
    # ax.set_xticks(range(math.ceil(max(timelist))))
    # ax.invert_yaxis()
    # ax.axvline(x = 6, color='k', linestyle='--')
    
    plt.style.use("ggplot")
    fig,ax = plt.subplots()
    fig.set_size_inches(11, 5, forward=True)
    ax.bar(datelist,timelist, color="#2a9c48")
    ax.autoscale(enable=True, axis='x', tight=True)
    ax.set_yticks(range(math.ceil(max(timelist))))
    ax.set_xticks(datelist)
    ax.set_xticklabels(datelist,rotation=90)
    ax.axhline(y = 6, color='k', linestyle='--')
    plt.tight_layout()
    plt.savefig("plots/" + str(user.id) + ".png")
    plt.close(fig)
    
    with open("plots/" + str(user.id) + ".png","rb") as pho:
        context.bot.send_photo(chat_id=update.effective_chat.id,
                               photo = pho)
        
    update.message.reply_text(outstring, parse_mode=ParseMode.MARKDOWN_V2)
    
def raw(update: Update, context: CallbackContext):
    user = update.message.from_user
    log(user, "Rohdaten abgerufen.")
    with open("dbs/" + str(user.id) + ".txt", "r") as f:
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text="`" + f.read() + "`",
                                 parse_mode=ParseMode.MARKDOWN_V2)
        
def remove(update: Update, context: CallbackContext):
    user = update.message.from_user
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
        NEWUSER: [MessageHandler(Filters.regex('^[0-9]+$'), newuser)],
    },
    fallbacks=[CommandHandler('cancel', cancel)],
)

#start_handler = CommandHandler('start', start)
dispatcher.add_handler(start_handler)
dispatcher.add_handler(conv_handler)

#neuearbeit_handler = CommandHandler('a', neuearbeit)
#dispatcher.add_handler(neuearbeit_handler)

stats_handler = CommandHandler('stats', stats)
dispatcher.add_handler(stats_handler)
raw_handler = CommandHandler('raw', raw)
dispatcher.add_handler(raw_handler)

#remove_handler = CommandHandler('remove', remove)
#dispatcher.add_handler(conv_handler)
dispatcher.add_handler(remconv_handler)

updater.start_polling()
updater.idle()

