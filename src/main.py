# -*- coding: utf-8 -*-
from utility import *
from telegram.ext import Updater
from telegram.ext import CommandHandler
from telegram.ext import MessageHandler, Filters
import logging
import sys
import json
import numpy as np
import os

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',level=logging.INFO)

filename = os.environ.get('STORE')
userGraph = []
userNames = []
with open(filename, 'r') as f:
    datastore = json.load(f)
    userNames = datastore['userNames']
    userGraph = datastore['userGraph']


updater = Updater(token=os.environ.get('BOT_TOKEN'))
dispatcher = updater.dispatcher

#Inizializzazione Bot
def start(bot, update):
    bot.send_message(chat_id=update.message.chat_id, text="I'm a bot, please talk to me!")
    
#Elenco comandi
def help(bot, update):
    bot.send_message(chat_id=update.message.chat_id, text="Elenco dei comandi: ")
    bot.send_message(chat_id=update.message.chat_id, text="/new [cifra] [persone] -> Aggiungere un pagamento a una o piu' persone")
    bot.send_message(chat_id=update.message.chat_id, text="/pay [cifra] [persona] -> Saldare un debito a una persona")
    bot.send_message(chat_id=update.message.chat_id, text="/balance -> Visualizza il saldo")    

def exit(bot, update):
    bot.send_message(chat_id=update.message.chat_id, text="Good bye!")
    updater.stop()
    sys.exit(0)

# def echo(bot, update):
#     bot.send_message(chat_id=update.message.chat_id, text=update.message.text)

#Aggiunge un utente alla lista utenti e alla matrice
def addUser(bot, update, name):
    if not name in userNames:
        # add new user in the user list 
        userNames.append(name)

        # add row and column for the new user
        for l in userGraph:
            l.append(0)
        userGraph.append([0] * len(userNames))

        bot.send_message(chat_id=update.message.chat_id, text='New user: ' + name)

#Crea un nuovo debito
def new(bot, update, args):
    if len(args) < 2 :
        bot.send_message(chat_id=update.message.chat_id, reply_to_message_id=update.message.message_id, text="/new cifra @persona [@persona] [...] [messaggio]")
        return

    buyerData = update.message.from_user
    buyerName = '@' + buyerData['username']
    addUser(bot, update, buyerName)

    
    messageIndex = len(args)
    for i in reversed(range(len(args))) :
        if '@' in args[i] :
            messageIndex = i + 1
            break
            
    message = ' '.join(args[messageIndex:])
    args = args[:messageIndex]
    users = [ name for name in args if '@' in name ]
    payments = [ cash for cash in args if is_number(cash)]
    print args
    print 'Users: ', users, 'Payments: ', payments, message

    for name in users: 
        addUser(bot, update, name)               
    
    if len(users) == 0 :
        bot.send_message(chat_id=update.message.chat_id, reply_to_message_id=update.message.message_id, text="Sembri aver dimenticato lo username.\nControlla di aver messo la @")
        return

    if len(payments) == 0 :
        bot.send_message(chat_id=update.message.chat_id, reply_to_message_id=update.message.message_id, text="Sembra che tu non abbia pagato nulla.\nPerche' non riprovi inserendo la cifra correttamente.")
        return

    if isRomana(args):
        cash = float(payments[0])
        updateRomana(cash, buyerName, users, message)
    else : 
        if len(users) != len(payments) :
            bot.send_message(chat_id=update.message.chat_id, reply_to_message_id=update.message.message_id, text="Se stai facendo conti separati, potresti aver messo un numero di persone diverso dal numero di cifre.")
            return
        
        updateIndividuale(buyerName, users, payments, message)

    updateDB()

    bot.send_message(chat_id=update.message.chat_id, text="Transizione registrata.\n{0} ha pagato per {1}\nCausale: {2}".format(buyerName, ' '.join(users), message))        

def userDebits (userName):
    userIndex = userNames.index(userName)
    return [ userGraph[userIndex][i] for i in range(len(userNames)) ]

def userCredits(userName):
    userIndex = userNames.index(userName)
    return [ userGraph[i][userIndex] for i in range(len(userNames)) ]

def moveDebitToUser(cash, fromUser, middleUser, toUser):
    userGraph[fromUser][toUser] += cash
    userGraph[middleUser][toUser] -= cash
    userGraph[fromUser][middleUser] -= cash

def minDebt(debtList):
    tmpList = filter(lambda a: a != 0, debtList)
    print debtList, tmpList
    return min(tmpList)

# Bilancia il grafo dei debiti
# per ogni utente salda i debiti a partire da quelli piu' piccoli usando i crediti piu' grandi
def updateDB():
    for name in userNames:
        nameIndex = userNames.index(name)
        nameCredits = userCredits(name)
        nameDebits = userDebits(name)
        
        print "user", name, "debito: ", sum(nameDebits), "Tot crediti: ", sum(nameCredits)
        stop = False
        while not stop :
            if sum(nameCredits) == 0 or sum(nameDebits) == 0 :
                break

            # get the minimum debt
            debt = minDebt(nameDebits)
            creditorIndex = nameDebits.index(debt)

            # stop if the credits are less than the minimum debt
            if debt > sum(nameCredits) :
                break
            else :
                # if exist a debitor with a debit greater or eual than the considered debit move it to the creditor
                if max(nameCredits) > debt :
                    debitorIndex = nameCredits.index(max(nameCredits))
                    moveDebitToUser(debt, debitorIndex, nameIndex, creditorIndex)
                else :
                    while debt > 0 :
                        maxCredit = max(nameCredits)
                        debitorIndex = nameCredits.index(maxCredit)
                        
                        if maxCredit >= debt:
                            moveDebitToUser(debt,debitorIndex, nameIndex, creditorIndex)
                            debt = 0 
                        else : 
                            moveDebitToUser(maxCredit,debitorIndex, nameIndex, creditorIndex)
                            debt -= maxCredit
                            nameCredits[debitorIndex] = 0
            # update the debits and credits lists
            nameCredits = userCredits(name)
            nameDebits = userDebits(name)


    # store data to file
    data = {
        'userNames' : userNames,
        'userGraph' : userGraph
    }

    print data
    with open(filename, 'w') as file:
        file.write(json.dumps(data))    

#Controlla se un debito e' unico o multiplo
def isRomana(args):
    numbers = 0
    for arg in args:
        if is_number(arg): 
            numbers += 1
    return (numbers == 1)

#Aggiunge lo stesso debito a piu' utenti
def updateRomana(cash, buyer, users, message):
    #Contributo di ciascuno
    cashEach = cash / (len(users) + 1)
    buyerIndex = userNames.index(buyer)
    for user in users:
        userGraph[userNames.index(user)][buyerIndex] += cashEach
        # "{0} deve {1} a {2} per ".format(user, cashEach, buyer) + message"                
        

#Aggiunge un debito diverso a piu' utenti
def updateIndividuale(buyer, users, payments, message):
    buyerIndex = userNames.index(buyer)
    for i in range(0, len(users)):
        userGraph[userNames.index(users[i])][buyerIndex] += float(payments[i])

#Funz per estinguere i debiti
def pay(bot, update, args):
    if len(args) < 2 :
        bot.send_message(chat_id=update.message.chat_id, reply_to_message_id=update.message.message_id, text="/pay cifra @persona [messaggio]")
        return
    
    buyerData = update.message.from_user
    buyerName = '@' + buyerData['username']
    addUser(bot, update, buyerName)
    buyerIndex = userNames.index(buyerName)  

    cash = args[0]
    userName = args[1]
    message = ""
    if len(args) == 3:
        message = args[2]
    else :
        message = ' '.join(args[2:])

    if not is_number(cash) :
        bot.send_message(chat_id=update.message.chat_id, reply_to_message_id=update.message.message_id, text="Sembra che la cifra inserita non sia corretta")
        return 
    
    if not '@' in userName:
        bot.send_message(chat_id=update.message.chat_id, reply_to_message_id=update.message.message_id, text="Usa un username corretto per la persona scelta")
        return 

    userIndex = userNames.index(userName)
    userGraph[userIndex][buyerIndex] += float(cash)
    
    updateDB()
    bot.send_message(chat_id=update.message.chat_id, text="Transizione registrata.\n{0} --> {1}\nCausale: {2}".format(buyerName, userName, message))                 



def balance(bot, update):
    userData = update.message.from_user
    userName = '@' + userData['username']
    
    if not userName in userNames:
        bot.send_message(chat_id=update.message.chat_id, text="I have no idea who you are !!!")
        return
    
    userIndex = userNames.index(userName)
    userBalance = 0
    userCashIn = ''
    userCashOut = ''
    for i in range(len(userNames)):
        userBalance = userBalance + userGraph[i][userIndex] - userGraph[userIndex][i]

        if userGraph[i][userIndex] > 0:
            userCashIn += '{0} ti deve {1} euro'.format(userNames[i], round(userGraph[i][userIndex],0))
            userCashIn += '\n'
            # print '{0} ti deve {1} euro'.format(userNames[i], userGraph[i][userIndex])
        
        if userGraph[userIndex][i] > 0:
            userCashOut += 'Devi {1} euro a {0}'.format(userNames[i], round(userGraph[userIndex][i],0))
            userCashOut += '\n'
            # print 'Devi {1} euro a {0}'.format(userNames[i], userGraph[userIndex][i])


    bot.send_message(chat_id=update.message.chat_id, reply_to_message_id=update.message.message_id, text="Saldo: {0}\n{1}\n{2}".format(round(userBalance,0), userCashIn, userCashOut))

def showMatrix(bot, update):
    bot.send_message(chat_id=update.message.chat_id, text=userGraph)

start_handler = CommandHandler('start', start)
dispatcher.add_handler(start_handler)

help_handler = CommandHandler('help', help)
dispatcher.add_handler(help_handler)

exit_handler = CommandHandler('exit', exit)
dispatcher.add_handler(exit_handler)

# echo_handler = MessageHandler(Filters.text, echo)
# dispatcher.add_handler(echo_handler)

new_handler = CommandHandler('new', new, pass_args=True)
dispatcher.add_handler(new_handler)

pay_handler = CommandHandler('pay', pay, pass_args=True)
dispatcher.add_handler(pay_handler)

balance_handler = CommandHandler('balance', balance)
dispatcher.add_handler(balance_handler)

showMatrix_handler = CommandHandler('show', showMatrix)
dispatcher.add_handler(showMatrix_handler)

updater.start_polling()
