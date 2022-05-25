from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, ParseMode, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CallbackContext, CommandHandler, ConversationHandler, MessageHandler, Filters, CallbackQueryHandler
from configparser import SafeConfigParser
from datetime import datetime, date, timedelta, time
import pytz
import logging
import math
import matplotlib.pyplot as plt
from matplotlib import cm
import numpy as np
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

DATUM, VONH, VONM, BISH, BISM, PAUSE, REMOVE, RAUS, NEWUSERHOURS, NEWUSERDAYS, LOESCH_MICH, LOESCHER, INLINETEST, ERINNER_MICH2, ERINNERER =range(15)
funfacts = {}
hours_n_days = {}
reminders = {}
active_reminders = {}

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

def zeitrechner(von_h, von_m, bis_h, bis_m, paus):
    soviel = bis_h - von_h + (bis_m - von_m - paus) / 60
    return soviel

def nicetime(hours):
    hour = int(hours)
    minute = math.floor((hours * 60 % 60) + .5)
    if hours < 0:
        minute *= -1
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
    
def make_entry(user, newe, outstring):
    with open("dbs/" + str(user.id) + ".txt", "r") as f:
        buch = f.readlines()
        if "Urlaub" in newe:
            h, d = buch[0].rstrip("\n").split(";")
            hourperweek = int(h)
            workdays = int(d,2)
            daysperweek = bin(workdays).count("1")
            hourperday = hourperweek / daysperweek
            start = time(hour=1, minute=1)
            end = datetime.combine(date.today(), start)+ timedelta(hours = hourperday)
            newe = newe[:-6] + "00;01;" + end.strftime("%H;%M;0")
            outstring = "Urlaubs- bzw. Feiertagseintrag mit üblicher Tagesarbeitszeit.\n"

        buch[1:] = sorted(buch[1:])
        existed = False
        for i, line in enumerate(buch):
            if line[:11] == newe[:11]:
                existed = True
                outstring += ("Es existiert bereits ein Eintrag an diesem Tag:\n`" +
                              line.replace("\n","") + "`\n")
                vonbook = datetime(*list(map(int, [line[:4], line[5:7], line[8:10], line[11:13], line[14:16]])))
                bisbook = datetime(*list(map(int, [line[:4], line[5:7], line[8:10], line[17:19], line[20:22]])))
                vonnewe = datetime(*list(map(int, [newe[:4], newe[5:7], newe[8:10], newe[11:13], newe[14:16]])))
                bisnewe = datetime(*list(map(int, [newe[:4], newe[5:7], newe[8:10], newe[17:19], newe[20:22]])))
                if (vonbook <= vonnewe < bisbook) or (vonnewe <= vonbook < bisnewe):
                    log(user, "Neuer Eintrag überlappt vorhandenen Eintrag, Aktion abgebrochen")
                    outstring += "Neuer Eintrag überlappt vorhandenen Eintrag, Aktion abgebrochen!"
                    return outstring
                between = max(vonnewe, vonbook) - min(bisnewe,bisbook) 
                pause = between + timedelta(minutes = int(line[23:25]) + int(newe[23:25]))
                buch[i]  = (min(vonbook,vonnewe).strftime("%Y;%m;%d;%H;%M;") + 
                            max(bisbook,bisnewe).strftime("%H;%M;") + 
                            str(int(pause.seconds/60)) + "\n")
                outstring += ("Der neue Eintrag wurde zum vorhandenen hinzugefügt:\n`" + 
                              buch[i].replace("\n","") + "`\n")
                log(user, "Eintrag vereinigt zu " + buch[i].replace("\n",""))

    if not existed:
        buch.append(newe)
        buch[1:] = sorted(buch[1:])
        log(user, "Neuer Eintrag angelegt: " + newe.replace("\n",""))
        
    outstring += "Guten Feierabend!"
    with open("dbs/" + str(user.id) + ".txt", "w") as f:
        f.writelines(buch)
        
    return outstring

def escape_markdown(outstring):
    doof = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for dumm in doof:
        outstring = outstring.replace(dumm,"\\"+dumm)
    return outstring

def start(update: Update, context: CallbackContext):
    outstring = ("Hallo!\n"
                 "Dieser Bot ist ein Hobbyprojekt und aktiv in Entwicklung. "
                 "Bitte verlasse dich nicht darauf, dass alles immer korrekt "
                 "ausgegeben wird und sei dir bewusst, dass ich Einsicht in "
                 "alle gespeicherten Daten habe und diese zu Fehlerbehebung auch nutze.\n"
                 "Erklärungen zu den Kommandos findest du unter /help\n\n"
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
    elif hours_n_days[user.id][1] == 0:
            reply_markup = InlineKeyboardMarkup(keyboard)
            query.edit_message_text(text="Bitte wähle mindestens einen Tag aus\.\nAusgewählt: " + strikedays(hours_n_days[user.id][1]),
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
                      ['19','20','21','22','23','24'],
                      ["Urlaubs- oder Feiertag"]
                     ]
    update.message.reply_text('Ab wann? (Stunde)',
                              reply_markup=ReplyKeyboardMarkup(reply_keyboard,
                                                               one_time_keyboard=True))
    return VONH

def vonh(update: Update, context: CallbackContext):
    user = update.message.from_user
    if update.message.text == "Urlaubs- oder Feiertag":
        newe = funfacts[user.id]["date"] + ";Urlaub"
        outstring = make_entry(user, newe, "")
        update.message.reply_text(escape_markdown(outstring),
                                  parse_mode=ParseMode.MARKDOWN_V2)
        return ConversationHandler.END

        
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
    outstring = (update.message.text + ' also. \nNochmal: ' +
                 funfacts[user.id]["vonh"] + ":" + funfacts[user.id]["vonm"] + ", " +
                 funfacts[user.id]["bish"] + ":" + funfacts[user.id]["bism"] + ", " +
                 funfacts[user.id]["pau"] + ".\nDas macht " + nicetime(zeit) + ".\n")
    if zeit <= 0:
        outstring += ("Dein Eintrag ist ist 0 oder weniger Stunden lang und wurde deswegen nicht angelegt. "
                      "Wenn du einen Tag frei machst musst du das übrigens nicht Eintragen!")
        log(user, "Eintrag war zu kurz, abgebrochen.")
        update.message.reply_text(escape_markdown(outstring), parse_mode=ParseMode.MARKDOWN_V2)
        return ConversationHandler.END
    newe = (funfacts[user.id]["date"] + ";" + funfacts[user.id]["vonh"] + ";" +
            funfacts[user.id]["vonm"] + ";" + funfacts[user.id]["bish"] + ";" +
            funfacts[user.id]["bism"] + ";" + funfacts[user.id]["pau"] + "\n")
    
    outstring = make_entry(user, newe, outstring)
    
    update.message.reply_text(escape_markdown(outstring),
                              parse_mode=ParseMode.MARKDOWN_V2)
    return ConversationHandler.END

def cancel(update: Update, context: CallbackContext):
    user = update.message.from_user
    log(user, "Aktion abgebrochen.")
    update.message.reply_text('OK, dann besser nicht.',
                              reply_markup = ReplyKeyboardRemove())
    return ConversationHandler.END

def stats(update: Update, context: CallbackContext):
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
        # irgendwas läuft hier schief... soll wird manchmal falsch berechnet..?
        
        ueber_unter = hourperday * alltime_workdays - sum(times)
        if ueber_unter == 0:
            outstring += "\n"
        elif ueber_unter > 0:
            outstring += "Du bist " + nicetime(ueber_unter) + " im Minus.\n\n"
        else:
            outstring += "Du bist " + nicetime(-ueber_unter) + " im Plus.\n\n"

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
            # find first and last day of week
            dayX = min(i[0] for i in days)
            day1 = dayX - timedelta(days = dayX.weekday())
            day7 = day1 + timedelta(days = 6)
            # fix for first and last
            if day1 < ndata[0][0]: day1 = ndata[0][0]
            if day7 > ndata[-1][0]: day7 = ndata[-1][0]
            datemin = datetime.combine(day1, time.min) - timedelta(hours = 12)
            datemax = datetime.combine(day7, time.min) + timedelta(hours = 12)
            weeklyavg[week] = [[[datemin, datemax], [avg, avg]], numdays]
            totalOT = [[],[]]
            run_tot = hourperday
            for key in sorted(weeklyavg.keys()):
                totalOT[0].extend(weeklyavg[key][0][0])
                run_tot += (weeklyavg[key][0][1][0] - hourperday) * weeklyavg[key][1] / daysperweek
                totalOT[1].extend([run_tot,run_tot])
            totalOT[1][0] = weeklyavg[min(weeklyavg.keys())][0][1][0]# ~~aesthetics~~
            totalOT[1][1] = weeklyavg[min(weeklyavg.keys())][0][1][0]
            
            totaltest = [[],[]] # wonky redo to make weeklyOT are bit more palatable
            for i in range(0, len(totalOT[0]), 2):
                totaltest[0].append(totalOT[0][i] + (totalOT[0][i+1]-totalOT[0][i])/2)
                totaltest[1].append(totalOT[1][i])
        
        plt.style.use("ggplot")
        fig,ax = plt.subplots()
        fig.set_size_inches(11, 5, forward=True)
        bars = ax.bar(datelist,timelist, color="#2a9c48")
        weekday1 = datelist[0].weekday()
        colo = cm.Greens(np.linspace(0,1,30))[17:24][::-1]
        for bar in bars:
            bar.set_facecolor(colo[weekday1]) #daycolor(weekday1))
            weekday1 = (weekday1 + 1) % 7
        ax.plot(*totaltest, color="#b24720", linestyle="-", linewidth = 3, alpha = .15, solid_capstyle="round")
        for week in weeklyavg:
            ax.plot(*weeklyavg[week][0], color="#124720", linestyle=':')
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
            
        update.message.reply_text(escape_markdown(outstring),
                                  parse_mode=ParseMode.MARKDOWN_V2)
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

def helper(update: Update, context: CallbackContext):
    user = update.message.from_user
    log(user, "Hilfe..!")
    outstring = ("Hallo!\n"
                 "Dieser Bot ist ein Hobbyprojekt und aktiv in Entwicklung. "
                 "Bitte verlasse dich nicht darauf, dass alles immer korrekt "
                 "ausgegeben wird und sei dir bewusst, dass ich Einsicht in "
                 "alle gespeicherten Daten habe und diese zu Fehlerbehebung auch nutze.\n\n"
                 "Kommandoübersicht:\n"
                 "/a beginnt einen neuen Eintrag in dein Dienstbuch. Der Bot fragt dich nach Datum, "
                 "Start- und Endzeit und nach Pausenzeiten. Sollte bereits ein Eintrag an diesem Tag "
                 "vorhanden sein werden die Einträge zusammengeführt.\n"
                 "/start legt dein Dienstbuch an oder erlaubt dir, deine Basisinformationen "
                 "(Wochenstunden und Arbeitstage) zu ändern.\n"
                 "/cancel kann verwendet werden um jeden mehrstufigen Befehl abzubrechen.\n"
                 "/stats zeigt dir eine graphische Auswertung deines Dienstbuchs an sowie "
                 "Statistiken zu dieser und letzter Woche, diesem und letztem Monat und "
                 "deiner Gesamtarbeitszeit. Ganz wird dein aktuelles Überstundenkonto ausgegeben.\n"
                 "/raw gibt dein Dienstbuch in Rohform aus. So wird es vom Bot geschrieben und gelesen.\n"
                 "/remove erlaubt dir, einzelne Einträge aus deinem Dienstbuch zu löschen.\n"
                 "/erinner\_mich richtet eine Erinnerung ein. Der Bot wird dich an Arbeitstagen "
                 "zu einer von dir bestimmten Uhrzeit an das Eintragen erinnern. Diese Erinnerung wird nicht "
                 "durchgeführt falls du zu diesem Zeitpunkt bereits einen Eintrag angelegt hast.\n"
                 "/erinner\_mich\_nicht deaktiviert eine eingerichtete Erinnerung.\n"
                 "/loesch\_mich löscht dein gesamtes Dienstbuch.\n\n"
                 "Zusätzlich ist zu beachten, dass derzeit auch Feiertage manuell eingetragen werden müssen. "
                 "Lege dafür einen Eintrag für den entsprechenden Tag an, scrolle bei der Startzeit nach unten und "
                 "wähle den passenden Button aus. Es wird ein Eintrag erstellt, der deiner regulären Tagesarbeitszeit entspricht.")
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text=escape_markdown(outstring),
                             parse_mode=ParseMode.MARKDOWN_V2)    
        
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
    if os.path.exists("reminders/" + str(user.id) + ".txt"):
            os.remove("reminders/" + str(user.id) + ".txt")
            active_reminders[user.id].schedule_removal()
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
        psa_message = escape_markdown(update.message.text.replace("/psa ", ""))
        for userid in ids:
            try:
                context.bot.send_message(chat_id=userid,
                                         text=psa_message,
                                         parse_mode=ParseMode.MARKDOWN_V2)
                log(user, "PSA sent to " + str(userid) + ".")
            except Exception as e:
                print(e)
                log(user, "PSA Error! Bot may be blocked by " + str(userid) + ".")
    
def erinner_mich(update: Update, context: CallbackContext):
    user = update.message.from_user
    if not db_ok(user.id):
        update.message.reply_text("Bitte erst mit /start ein Dienstbuch anlegen.")
        log(user, "Erinnerung ohne Useraccount anlegen?!")
        return ConversationHandler.END
        
    if os.path.exists("reminders/" + str(user.id) + ".txt"):
        update.message.reply_text("Es ist bereits eine Erinnerung vermerkt. Bitte entferne diese zuerst.")
        log(user, "Erinnerung bereits vermerkt.")
        return ConversationHandler.END
    else:
        reminders[user.id] = {}
        reply_keyboard = [['01','02','03','04','05','06'],
                          ['07','08','09','10','11','12'],
                          ['13','14','15','16','17','18'],
                          ['19','20','21','22','23','24']]
        update.message.reply_text("Diese Funktion erinnert dich an jedem Arbeitstag zur " + 
                                  "eingetragegen Uhrzeit wenn noch kein Eintrag vorhanden ist.\n" +
                                  "Wieviel Uhr? (Stunde)",
                                  reply_markup=ReplyKeyboardMarkup(reply_keyboard,
                                                                   one_time_keyboard=True))
        return ERINNER_MICH2
    
def erinner_mich2(update: Update, context: CallbackContext):
    user = update.message.from_user
    reminders[user.id]["hour"] = update.message.text
    reply_keyboard = [['05','10','15'],
                      ['20','25','30'],
                      ['35','40','45'],
                      ['50','55','00']]
    update.message.reply_text('Wieviel Uhr? (Minute)',
                              reply_markup=ReplyKeyboardMarkup(reply_keyboard,
                                                               one_time_keyboard=True))
    return ERINNERER

def erinnerer(update: Update, context: CallbackContext):
    user = update.message.from_user
    reminders[user.id]["minute"] = update.message.text
    with open("reminders/" + str(user.id) + ".txt", "w") as f:
        f.write(reminders[user.id]["hour"] + ";" + reminders[user.id]["minute"])
    thetime = time(int(reminders[user.id]["hour"]), int(reminders[user.id]["minute"]), tzinfo = pytz.timezone("Europe/Berlin"))

    thedays = ()
    with open("dbs/" + str(user.id) + ".txt") as f:
        workdays = int(f.readline().rstrip("\n").split(";")[1], 2)
    for i in range(7):
        if 64 >> i & workdays:
            thedays = thedays + (i,)
    
    active_reminders[user.id] = j.run_daily(die_erinnerung, context = (user.id),
                                            time = thetime, days = thedays)
    update.message.reply_text("Arbeitstägliche Erinnerung für " + 
                              reminders[user.id]["hour"] + ":" + reminders[user.id]["minute"] + 
                              " angelegt.")
    log(user, "Erinnerung eingerichtet (" + reminders[user.id]["hour"] + ":" +
              reminders[user.id]["minute"] + ", " + "{:07b}".format(workdays) + ").")
    return ConversationHandler.END

def erinner_mich_nicht(update: Update, context: CallbackContext):
    user = update.message.from_user
    if os.path.exists("reminders/" + str(user.id) + ".txt"):
            os.remove("reminders/" + str(user.id) + ".txt")
            active_reminders[user.id].schedule_removal()
            log(user, "Erinnerung gelöscht.")
            context.bot.send_message(chat_id=update.effective_chat.id, 
                                     text = "Erinnerung entfernt.")
    else:
        log(user, "Erinnerungslöschversuch misglückt.")
        context.bot.send_message(chat_id=update.effective_chat.id, 
                                     text = "Keine Erinnerung gefunden.")

def die_erinnerung(context: CallbackContext):
    id = context.job.context
    lookfor = date.today().strftime("%Y;%m;%d")
    erledigt = False
    with open("dbs/" + str(id) + ".txt", "r") as f:
        for line in f:
            if lookfor in line.rstrip("\n"): erledigt = True
    
    if erledigt:
        logger.info("User " + str(id) + " musste nicht erinnert werden.")
    else:
        try:
            context.bot.send_message(chat_id = id, 
                                     text = "Beep boop. Möchtest du heute noch einen Eintrag anlegen?\n" + 
                                     "Eintrag anlegen: /a\n" + 
                                     "Erinnerung deaktivieren: /erinner_mich_nicht")
            logger.info("User " + str(id) + " wurde erinnert.")
        except:
            logger.info("Erinnerung an User " + str(id) + " konnte nicht zugestellt werden.")

def requeue_reminders():
    ids = [int(a.replace(".txt","")) for a in os.listdir("reminders") if "example" not in a]
    for userid in ids:
        with open("reminders/" + str(userid) + ".txt", "r") as f:
            hour, minu = list(map(int, f.readline().split(";")))
        thetime = time(hour, minu, tzinfo = pytz.timezone("Europe/Berlin"))
        thedays = ()
        with open("dbs/" + str(userid) + ".txt") as f:
            workdays = int(f.readline().rstrip("\n").split(";")[1], 2)
        for i in range(7):
            if 64 >> i & workdays:
                thedays = thedays + (i,)
        
        active_reminders[userid] = j.run_daily(die_erinnerung, context = (userid),
                                                time = thetime, days = thedays)
        logger.info("Erinnerung wiedereingerichtet (" + str(userid) + ", " + str(hour) + ":" +
                  "{:02n}".format(minu) + ", " + "{:07b}".format(workdays) + ").")

conv_handler = ConversationHandler(
    entry_points=[CommandHandler('a',neuearbeit)],
    states={
        DATUM: [MessageHandler(Filters.regex('^([0-9;]+|Heute|Gestern|Vorgestern)$'), datum)],
        VONH: [MessageHandler(Filters.regex('^([0-9]+|Urlaubs- oder Feiertag)$'), vonh)],
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
        NEWUSERHOURS: [MessageHandler(Filters.regex('^[1-9][0-9]*$'), newuserhours)],
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

erinner_mich_handler = ConversationHandler(
    entry_points=[CommandHandler('erinner_mich',erinner_mich)],
    states={
        ERINNER_MICH2: [MessageHandler(Filters.regex('^[0-9]+$'), erinner_mich2)],
        ERINNERER: [MessageHandler(Filters.regex('^[0-9]+$'), erinnerer)],
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
help_handler = CommandHandler('help', helper)
dispatcher.add_handler(help_handler)

#remove_handler = CommandHandler('remove', remove)
#dispatcher.add_handler(conv_handler)
dispatcher.add_handler(remconv_handler)

logs_handler = CommandHandler('logs', logs)
dispatcher.add_handler(logs_handler)
show_users_handler = CommandHandler('show_users', show_users)
dispatcher.add_handler(show_users_handler)
psa_handler = CommandHandler('psa', psa)
dispatcher.add_handler(psa_handler)

dispatcher.add_handler(erinner_mich_handler)
erinner_mich_nicht_handler = CommandHandler('erinner_mich_nicht', erinner_mich_nicht)
dispatcher.add_handler(erinner_mich_nicht_handler)

j = updater.job_queue
requeue_reminders()

updater.start_polling()
updater.idle()

