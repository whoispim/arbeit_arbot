from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, ParseMode
from telegram.ext import Updater, CallbackContext, CommandHandler, ConversationHandler, MessageHandler, Filters
from configparser import SafeConfigParser
from datetime import datetime, date, timedelta
import logging
import math
import matplotlib.pyplot as plt
from operator import itemgetter

config = SafeConfigParser()
config.read("ident.ini")

updater = Updater(token=config.get("API","token"), use_context=True)
dispatcher = updater.dispatcher

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

DATUM, VONH, VONM, BISH, BISM, PAUSE, REMOVE, RAUS =range(8)
funfacts = {}

def start(update: Update, context: CallbackContext):
    context.bot.send_message(chat_id=update.effective_chat.id, text="He du!")
    user = update.message.from_user
    logger.info(user.first_name + ": Neue Anmeldung!")

def neuearbeit(update: Update, context: CallbackContext):
    reply_keyboard = [['Heute'],
                      ['Gestern', 'Vorgestern']]
    user = update.message.from_user
    logger.info(user.first_name + ": Neuer Eintrag gestartet")
    update.message.reply_text('Welcher Tag? (Button oder Eingabe nach art YYYY;MM;DD)',
                              reply_markup=ReplyKeyboardMarkup(reply_keyboard,
                                                               one_time_keyboard=True))
    return DATUM
    
def datum(update: Update, context: CallbackContext):
    datu = update.message.text
    if "Heute" in datu:
        funfacts["date"] = datetime.now().strftime("%Y;%m;%d")
    elif "Gestern" in datu:
        funfacts["date"] = (datetime.now() - timedelta(days=1)).strftime("%Y;%m;%d")
    elif "Vorgestern" in datu:
        funfacts["date"] = (datetime.now() - timedelta(days=2)).strftime("%Y;%m;%d")
    else:
        funfacts["date"] = datu
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
    funfacts["vonh"] = update.message.text
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
    funfacts["vonm"] = update.message.text
    reply_keyboard = [['01','02','03','04','05','06'],
                      ['07','08','09','10','11','12'],
                      ['13','14','15','16','17','18'],
                      ['19','20','21','22','23','24']]
    update.message.reply_text('kk.\nBis wann? (Stunde)',
                              reply_markup=ReplyKeyboardMarkup(reply_keyboard,
                                                               one_time_keyboard=True))
    return BISH

def bish(update: Update, context: CallbackContext):
    funfacts["bish"] = update.message.text
    reply_keyboard = [['05','10','15'],
                      ['20','25','30'],
                      ['35','40','45'],
                      ['50','55','00']]
    update.message.reply_text('kk.\nBis wann? (Minute)',
                              reply_markup=ReplyKeyboardMarkup(reply_keyboard,
                                                               one_time_keyboard=True))
    return BISM

def bism(update: Update, context: CallbackContext):
    funfacts["bism"] = update.message.text
    reply_keyboard = [['0'],['5','10','15'],['20','25','30'],
                      ['45','60','75','90']]
    update.message.reply_text('kk.\nWie lange pausiert? (Minuten)',
                              reply_markup=ReplyKeyboardMarkup(reply_keyboard,
                                                               one_time_keyboard=True))
    return PAUSE

def pause(update: Update, context: CallbackContext):
    user = update.message.from_user
    funfacts["pau"] = update.message.text
    zeit = zeitrechner(*list(map(int, [funfacts["vonh"], funfacts["vonm"], funfacts["bish"], funfacts["bism"], funfacts["pau"]])))
    update.message.reply_text(update.message.text + ' also. \nGuten Feierabend! Nochmal: ' + funfacts["vonh"] + ":" + funfacts["vonm"] + ", " + funfacts["bish"] + ":" + funfacts["bism"] + ", "+ funfacts["pau"] + ".\nDas macht " + "{:.2f}".format(zeit) + " Stunden.",)
    f = open("jdienstbuch.txt","a+")
#    f.write(datetime.now().strftime("%Y;%m;%d"))
    f.write(funfacts["date"])
    f.write(";" + funfacts["vonh"] + ";" + funfacts["vonm"] + ";" + funfacts["bish"] + ";" + funfacts["bism"] + ";" + funfacts["pau"] + "\n")
    f.close
    logger.info(user.first_name + ": Neuer Eintrag angelegt: "+ funfacts["vonh"] + ":" + funfacts["vonm"] + ";" + funfacts["bish"] + ":" + funfacts["bism"] + ";" + funfacts["pau"])
    return ConversationHandler.END

def cancel(update: Update, context: CallbackContext):
    user = update.message.from_user
    logger.info(user.first_name + ": Aktion abgebrochen.")
    update.message.reply_text('OK, dann besser nicht.',
                              reply_markup = ReplyKeyboardRemove())
    return ConversationHandler.END

#def zeitrechner(fun):
#    soviel = int(fun["bish"]) - int(fun["vonh"]) + (int(fun["bism"]) - int(fun["vonm"]) - int(fun["pau"])) / 60
#    return soviel

def zeitrechner(von_h, von_m, bis_h, bis_m, paus):
    soviel = bis_h - von_h + (bis_m - von_m - paus) / 60
    return soviel

def stats(update: Update, context: CallbackContext):
    # context.bot.send_message(chat_id=timtimID,
    #                          text=":3",
    #                          parse_mode=ParseMode.MARKDOWN_V2)
    user = update.message.from_user
    logger.info(user.first_name + ": Stats abgerufen")
    with open("jdienstbuch.txt","r") as f:
        ndata = []
        for line in f:
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
    plt.savefig("plotto.png")
    plt.close(fig)
    
    with open("plotto.png","rb") as pho:
        context.bot.send_photo(chat_id=update.effective_chat.id,
                               photo = pho)
        
    update.message.reply_text(outstring, parse_mode=ParseMode.MARKDOWN_V2)
    
def raw(update: Update, context: CallbackContext):
    user = update.message.from_user
    logger.info(user.first_name + ": Rohdaten abgerufen")
    with open("jdienstbuch.txt","r") as f:
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text="`" + f.read() + "`",
                                 parse_mode=ParseMode.MARKDOWN_V2)
        
def remove(update: Update, context: CallbackContext):
    user = update.message.from_user
    logger.info(user.first_name + ": Eintrag entfernen!")
    outstring = "`"
    with open("jdienstbuch.txt", "r") as f:
        for i, line in enumerate(f.readlines()):
            outstring += "{0:04d}".format(i) + ": " + line
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text=outstring + "`\nWelcher Eintrag soll gelöscht werden? \(ID\)",
                             parse_mode=ParseMode.MARKDOWN_V2)
    return RAUS
    
def raus(update: Update, context: CallbackContext):
    user = update.message.from_user
    logger.info(user.first_name + ": Eintrag entfernt.")
    id = int(update.message.text)
    a = False
    with open("jdienstbuch.txt", "r") as f:
        lines = f.readlines()
    with open("jdienstbuch.txt", "w") as f:
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
        RAUS: [MessageHandler(Filters.regex('^[0-9]{4}$'), raus)],
    },
    fallbacks=[CommandHandler('cancel', cancel)],
)

start_handler = CommandHandler('start', start)
dispatcher.add_handler(start_handler)
dispatcher.add_handler(conv_handler)

neuearbeit_handler = CommandHandler('a', neuearbeit)
dispatcher.add_handler(neuearbeit_handler)

stats_handler = CommandHandler('stats', stats)
dispatcher.add_handler(stats_handler)
raw_handler = CommandHandler('raw', raw)
dispatcher.add_handler(raw_handler)

remove_handler = CommandHandler('remove', remove)
dispatcher.add_handler(conv_handler)
dispatcher.add_handler(remconv_handler)

updater.start_polling()
updater.idle()

