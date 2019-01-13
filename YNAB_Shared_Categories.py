    #####
    #
    # Todo
    # Web hosting
    # Sync budgeted amount
    # Handle edited transactions (currently show up as new)
    #
    #####

import urllib2
import urllib
import httplib
import json
import os
import sys
import time
from shutil import copyfile
import ConfigParser

# Gets the file path for caches
def getCachePath(param):
    if '?last_knowledge_of_server=' in param:
        param = param.split('?')[0]
    if '/' in param:
        return 'caches/'+(param).replace('/','.')
    if param == '': 
        return 'caches/main-json.cache'
    return 'caches/'+(param+'.cache').replace('/','.')

# Delta commands have a slightly different URL, this one returns the correct one
def getURL(param, accesstoken):  
    if '?last_knowledge_of_server=' in param:
        return ('https://api.youneedabudget.com/v1/budgets/' + str(param) + '&access_token=' + str(accesstoken))
    else:
        return ('https://api.youneedabudget.com/v1/budgets/' + str(param) + '?access_token=' + str(accesstoken))

# Checks the cache data. If there is no no cache it will call YNAB_Fetch for first time launch
def YNAB(param, accesstoken):
    path = getCachePath(param)
    if os.path.isfile(path):
        return YNAB_ParseCache(param)
    return YNAB_Fetch(param, accesstoken=accesstoken)

# Reads the cache and returns it as if it was from the server.
def YNAB_ParseCache(param):
    path = getCachePath(param)
    with open(path) as f:
        try:
            data = json.load(f)
        except ValueError:
            x = (path.split('/')[1]).split('.')[0]
            print 'Corrupt file ' + path + '. Fetching new from YNAB.'
            data = YNAB_Fetch(x)
            writeCache(data,x)
    return data

# Remove key from dictionary nondestructively
def removekey(d, key):
    r = dict(d)
    del r[key]
    return r

def requestData(url, data, header):
    i = 0
    attempts = 10
    while i < attempts:
        i = i+1
        try:
            req = urllib2.Request(url, data, header)
            break
        except urllib2.HTTPError, e:
            if i == attempts:
                print 'HTTP Request Failed too many times (' + str(i) + ') times. Recovering backed up transactions.'
                recoverTransactions()
                sys.exit(e) 
            print('HTTP Request '+e+' Failed ' + str(i) + ' times.')
        except urllib2.URLError, e:
            if i == attempts:
                print 'URL Failed too many times (' + str(i) + ') times. Recovering backed up transactions.'
                recoverTransactions()
                sys.exit(e)
            print('URL Failed '+e+' ' + str(i) + ' times.')
        time.sleep(1)
    return req

# fetchData returns the data from an URL, but doesn't write cache
xratemet = 0
def fetchData(url):
    global xratemet
    i = 0
    attempts = 10
    while i < attempts:
        i = i+1
        try:
            data = urllib2.urlopen(url)
            break
        except urllib2.HTTPError, e:
            if e.code == 400:
                i = attempts
                f = ('HTTP Error 400: Bad request, did you add a valid Access Token to the config file?')
            if e.code == 401:
                i = attempts
                f = ('HTTP Error 401: Missing/Invalid/Revoked/Expired access token')
            if e.code == 403:
                i = attempts
                f = ('HTTP Error 403: YNAB subscription expired')
            if e.code == 404:
                i = attempts
                f = ('HTTP Error 404: Not found, Wrong parameter given')
            if e.code == 409:
                f = ('HTTP Error 409: Conflicts with an existing resource')
            if e.code == 429:
                i = attempts
                f = ('HTTP Error 429: Too many requests, need to wait between 0-59 minutes to try again :(')
            if e.code == 500:
                f = ('HTTP Error 500: Internal Server Error, unexpected error')
            if i == attempts:
                print 'HTTP Request Failed too many times (' + str(i) + ') times. Recovering backed up transactions.'
                recoverTransactions()
                sys.exit(f) 
            print('HTTP Request Failed ' + str(i) + ' times.')
        except urllib2.URLError, e:
            if i == attempts:
                print 'URL Failed too many times (' + str(i) + ') times. Recovering backed up transactions.'
                recoverTransactions()
                sys.exit(e)
            print('URL Failed ' + str(i) + ' times.')
        except httplib.BadStatusLine as e:
            if i == attempts:
                print 'Failed too many times (' + str(i) + ') times. Recovering backed up transactions.'
                recoverTransactions()
                sys.exit(e)
        time.sleep(1)

    xrate = data.info().get('X-Rate-Limit')
    if int(xrate.split('/')[0]) >= (int(xrate.split('/')[1])-int(XRateTreshold)) and xratemet == 0: #Safety Treshold, incase there isn't enough X-Rates to complete the script.
        sys.exit('Surpassed X-Rate-Limit Safety treshold ' + xrate +', will run once more is available')
    xratemet += 1
    return data

def writeCache(data, param):
    path = getCachePath(param)
    if not os.path.exists('caches'):
        os.mkdir('caches')
    with open(path, 'w') as cache:
        json.dump(data,cache)
    return data

# Fetches data from the server and writes it to cache
def YNAB_Fetch(param, accesstoken=None):
    O = []
    global AccessToken
    for Y in AccessToken:
        if accesstoken != None:
            Y = accesstoken
        url = getURL(param, Y)
        data = json.load(fetchData(url))
        data.update({'token':Y})
        O.append(data)
        if param != '':
            writeCache(data,param)
        if accesstoken != None:
            return data
    return O

def deleteBudgetCache(id):
    a = 'caches/' + id + '.cache'
    b = 'caches/' + id + '.transactions'
    c = 'caches/' + id + '.transactions.backup'
    d = 'caches/' + id + '.queue'
    if os.path.exists(a):
        os.remove(a)
    if os.path.exists(b):
        os.remove(b)
    if os.path.exists(c):
        os.remove(c)
    if os.path.exists(d):
        os.remove(d)

# Detect deleted budgets and remove their associated caches
def removeDeletedBudgets():
    for file in os.listdir('caches/'):
        if file.endswith('.cache'):
            x = True
            for M in MasterJSON:
                for i in M['data']['budgets']:
                    if file.split('.')[0] == i['id']:
                        x = False
                        # Cache is correct
                        break
            if x == True:
                print 'Budget ' + file.split('.')[0] + ' is no longer in MasterJSON. Deleting'
                deleteBudgetCache(file.split('.')[0])

# Creates a backup of every .transactions file, which can be recovered if the POST doesn't go through, so that the server_knowledge is reset.
# is run at the start of the script
def backupTransactionsCache():
    if not os.path.exists('caches'):
        os.mkdir('caches')
    for file in os.listdir('caches/'):
        if file.endswith('.transactions'):
            src = 'caches/'+file
            dst = 'caches/'+file+'.backup'
            copyfile(src,dst)

# If Recover = false then no recovery of transactions is made. Set to False after .queue is made
recover = True
# Recovers the .transactions files back to the old version. This runs if a POST request fails
def recoverTransactions():
    if recover:
        for file in os.listdir('caches/'):
            if file.endswith('.backup'):
                src = 'caches/'+file
                dst = ('caches/'+file).split('.backup')[0]
                copyfile(src,dst)
    else:
        print 'No recovery made due to queued up transactions.'

# Used by getAllSharedCategories
# Searches every category for the string 'CombinedAffix' in notes, 
# adds the unique note id to the category and returns a list of all categories
def searchAllSharedCategories(syntax, json): # Might be redundant with caching?
    output = []
    for item in json['data']['budget']['categories']:
        if item['note'] != None:
            if str(syntax) in str(item['note']):
                note_id = item['note'].split(CategoryAffix)[1]
                item = removekey(item, 'note')
                item.update({'note':note_id})
                output.append(item)
    return output

# Used to store all Shared Categories in a dictionary
def getAllSharedCategories(): # Needs Caching & Delta
    output = []
    # Grabbing all Joint Category IDs
    for item in AllDeltaAccounts:
        data = searchAllSharedCategories(CombinedAffix, YNAB(item['budget_id'], AccessToken))
        for index in data:
            if index['deleted'] == False:
                index.update({'budget_name':item['budget_name'], 'budget_id':item['budget_id']})
                output.append(index)
                print ('Found Category: ' + index['name'] + ' With ID: ' + index['id'] + ' using Note: ' + index['note'] + ' from budget: ' + index['budget_name'] + ' with ID: ' + index['budget_id']).encode('utf8')
    return output

# Used to store all Delta Accounts in a dictionary
def getAllDeltaAccounts():
    output = []
    # Grabbing all Delta Account IDs
    for M in MasterJSON:
        for item in M['data']['budgets']:
            if os.path.isfile(str('caches/' + item['id'] + '.cache')) == True:
                print ('Checking for updates in ' + item['name']).encode('utf8')
                getBudgetUpdates(item['id'], M['token'])

            print ('Checking for Delta Accounts in ' + item['name']).encode('utf8')
            json = YNAB(item['id'], M['token'])
            acc = findAccountByNote(AccountSyntax, json)
            if acc != None and acc['deleted'] == False:
                print ('Found Account: ' + acc['name'] + ' With ID: ' + acc['id'] + ' from budget: ' + item['name'] + ' with ID: ' + item['id']).encode('utf8')
                acc.update({'budget_name':item['name'], 'budget_id':item['id']})
                output.append(acc)
    return output

# Used by newTransactions parser to see if the new transaction is from a shared category
# Checks if the Category ID is in the SharedCategories list
def isCategoryShared(id):
    for i in AllSharedCategories:
        if i['id'] == id:
            return i
    return False

# Used by newTransactions parser to see if the new transaction is from a delta account
# Checks if the Account ID is in the DeltaAccounts list
def isAccountDelta(id): # Works
    for i in AllDeltaAccounts:
        if i['id'] == id:
            return True
    return False

# Returns the account data if note is found in string. Used to find all entities with the AccountModifier
def findAccountByNote(note, json): # FINISHED
    for item in json['data']['budget']['accounts']:
        if item['note'] != None and note in item['note']:
            return item

# Gets the ID of the default category by name. Used to grab 'To be Budgeted' in parseDeltas
def fetchCategoryIdByName(budget_id, name):
    accesstoken = getAccessTokenFromBudget(budget_id)
    json = YNAB(str(budget_id), accesstoken)
    for item in json['data']['budget']['categories']:
        if item['name'] == name:
            return item['id']

# Updates new Accounts and Categories dictionaries to the old dictionary
def mergeDicts(old, changes):
    # Accounts
    a = changes['data']['budget']['accounts']
    b = changes['data']['budget']['categories']
    c = changes['data']['budget']['transactions']
    d = changes['data']['budget']['subtransactions']
    if a != [] or b != [] or c != [] or d != []:
        # Accounts
        oldamount = 0
        newamount = 0
        for d1 in a:
            n = True
            for i, d2 in enumerate(old['data']['budget']['accounts']):
                if d1['id'] == d2['id']:
                    n = False
                    old['data']['budget']['accounts'][i] = d1
                    oldamount += 1
                    break
            if n:
                n = d1
                old['data']['budget']['accounts'].append(d1)
                newamount += 1
        if oldamount >= 1:
            print ('Updated ' + str(oldamount) + ' existing accounts.').encode('utf8')
        if newamount >= 1:
            print ('Cached ' + str(oldamount) + ' new accounts.').encode('utf8')
            
        # Categories
        oldamount = 0
        newamount = 0
        for d1 in b:
            n = True
            for i, d2 in enumerate(old['data']['budget']['categories']):
                if d1['id'] == d2['id']:
                    n = False
                    old['data']['budget']['categories'][i] = d1
                    oldamount += 1
                    break
            if n:
                n = d1
                old['data']['budget']['categories'].append(d1)
                newamount += 1
        if oldamount >= 1:
            print ('Updated ' + str(oldamount) + ' existing categories.').encode('utf8')
        if newamount >= 1:
            print ('Cached ' + str(oldamount) + ' new categories.').encode('utf8')

        # Transactions
        oldamount = 0
        newamount = 0
        for d1 in c:
            n = True
            for i, d2 in enumerate(old['data']['budget']['transactions']):
                if d1['id'] == d2['id']:
                    n = False
                    old['data']['budget']['transactions'][i] = d1
                    oldamount += 1
                    break
            if n:
                n = d1
                old['data']['budget']['transactions'].append(d1)
                newamount += 1
        if oldamount >= 1:
            print ('Updated ' + str(oldamount) + ' existing transactions.').encode('utf8')
        if newamount >= 1:
            print ('Cached ' + str(oldamount) + ' new transactions.').encode('utf8')
        # Subtransactions
        oldamount = 0
        newamount = 0
        for d1 in d:
            n = True
            for i, d2 in enumerate(old['data']['budget']['subtransactions']):
                if d1['id'] == d2['id']:
                    n = False
                    old['data']['budget']['subtransactions'][i] = d1
                    oldamount += 1
                    break
            if n:
                n = d1
                old['data']['budget']['subtransactions'].append(d1)
                newamount += 1
        if oldamount >= 1:
            print ('Updated ' + str(oldamount) + ' existing subtransactions.').encode('utf8')
        if newamount >= 1:
            print ('Cached ' + str(oldamount) + ' new subtransactions.').encode('utf8')
        # Server knowledge
        old['data']['server_knowledge'] = changes['data']['server_knowledge']
        return old
    return False

# Fetches new data & adds it to the cache
def getBudgetUpdates(budget_id, accesstoken):
    param = budget_id+'?last_knowledge_of_server='
    path = getCachePath(param)
    if os.path.isfile(path):
        main = YNAB(param, accesstoken)
        x = main['data']['server_knowledge']
    else: 
        main = YNAB(budget_id, accesstoken)
        x = main['data']['server_knowledge']
    param = param + str(x)
    url = getURL(param, accesstoken)
    data = json.load(fetchData(url))
    data = mergeDicts(main,data)
    if data != False:
        writeCache(data, str(budget_id))

# Checks if a transaction is in a shared category, and not in a delta account
# Also parses Split transactions as separate entries
def checkTransaction(item):
    if item['subtransactions'] == []:
        checkCategory = isCategoryShared(item['category_id'])
        if checkCategory != False:
            if not isAccountDelta(item['account_id']):
                item.update({'budget_id':checkCategory['budget_id'], 
                            'budget_name':checkCategory['budget_name'], 
                            'note':checkCategory['note']})
                output = []
                output.append(item)
                return output
    else:
        print 'Split Transaction detected'
        output = []
        for sub in item['subtransactions']:
            checkCategory = isCategoryShared(sub['category_id'])
            if checkCategory != False:
                if not isAccountDelta(item['account_id']):
                    x = removekey(item, 'subtransactions')
                    x.update({
                        'budget_id':checkCategory['budget_id'], 
                        'budget_name':checkCategory['budget_name'], 
                        'note':checkCategory['note'],
                        'category_id':sub['category_id'],
                        'amount':sub['amount'],
                        'id':sub['id'],
                        'transaction_id':sub['transaction_id'],
                        'deleted':sub['deleted'],
                        'memo':sub['memo'] + ' (Split)'
                    })
                    output.append(x)
        if output != []:
            return output

def getAccessTokenFromBudget(budget_id):
    path = getCachePath(budget_id)
    if os.path.isfile(path):
        with open(path) as f:
            data = json.load(f)
            return data['token']

# Fetches all new transactions in a budget & returns every transaction in a shared category
def getNewJointTransactions(budget_id):
    output = []
    accesstoken = getAccessTokenFromBudget(budget_id)
    param = budget_id+'/transactions'
    json = YNAB(param, accesstoken)
    server_knowledge = json['data']['server_knowledge']

    if server_knowledge != '':
        json = YNAB_Fetch(param + '?last_knowledge_of_server=' + str(server_knowledge), accesstoken=accesstoken)

    for item in json['data']['transactions']:
        x = checkTransaction(item)
        if x != None:
            for i in x:
                output.append(i)
    return output

# Get every Budget except the source of transaction for a transaction
def getTransactionReceivers(senders_budget):
    output = []
    for budgets in AllDeltaAccounts:
        if senders_budget != budgets['budget_id']:
            output.append(budgets)
    return output

# Used by sendBulkTransactions to minimize requests
# transactions is ALL transactions from every shared budget. This only returns the ones from a specific budget
def transactionSorter(transactions, account):
    output = []
    for index in transactions:
        if index['target_budget'] == account['budget_id']:
            output.append(index)
    return output

# Sends all parsed transactions to the correspdoing budget_id/transactions/bulk
def sendBulkTransactions(bulk):
    global recover
    send = []
    # Sort by budget - to prevent spamming the server with requests
    for acc in AllDeltaAccounts:
        tr = []
        transactiondata = []
        tr = transactionSorter(bulk, acc)

        if tr != []:
            # If there are transactions queued up, include them
            path = str('caches/' + tr[0]['target_budget'] + '.queue')
            if os.path.exists(path):
                with open(path, 'r') as cache:
                    tr.extend(json.load(cache))

            # Cache all transactions to queue in the event of failure
            with open(path, 'w') as cache:
                json.dump(tr,cache)
            
            for i in tr:
                data = removekey(i,'target_budget')
                transactiondata.append(data)

            targetbudget = str(tr[0]['target_budget'])
            accesstoken = getAccessTokenFromBudget(targetbudget)
            url = getURL(targetbudget+'/transactions/bulk', accesstoken)
            data = json.dumps({'transactions':transactiondata})

            send.append({'url':url, 'data':data, 'target':targetbudget})

    recover = False
    for i in send:
        req = requestData(i['url'], i['data'], {'Content-Type': 'application/json', 'Content-Length': len(i['data'])})
        response = fetchData(req)
        print response.read()

        # Remove queue on successful run
        path = str('caches/' + i['target'] + '.queue')
        if os.path.exists(path):
            os.remove(path)


# parseDeltas prepares the delta transaction to be sent out (Cleaning the old transaction data and replacing it with the target info)
def parseDeltas(transaction):
    output = []
    for delta in AllDeltaAccounts:
        x = transaction['amount']
        y = len(AllDeltaAccounts)
        payee = transaction['payee_name']
        if payee == None:
            payee = '(Payee Was Blank)'
        cat_id = str(fetchCategoryIdByName(str(delta['budget_id']), 'To be Budgeted'))
        data = {'category_id': cat_id,
                'category_name':'To be Budgeted', 
                'account_id':delta['id'], 
                'account_name':delta['name'],
                'amount':-1*(x-(x/y)),
                'memo': ('Split from ' + transaction['category_name'] + ', ' + payee + '. Source: ' + transaction['budget_name']),
                'date': transaction['date'],
                'target_budget':delta['budget_id'],
                'payee_name':'Delta',
				'approved':transaction['approved']
                }
        output.append(data) # For bulk transaction
    return output

# Targets the transaction to every other shared budget, and matches the shared categories between them.
# Also sends out the delta to all transactions.
def verifyTransaction(tr):
    output = []
    output.extend(parseDeltas(tr))
    for budgets in getTransactionReceivers(tr['budget_id']):
        for categories in AllSharedCategories:
            if tr['note'] == categories['note'] and tr['category_id'] != categories['id']:
                if categories['budget_id'] == budgets['budget_id']:
                    # Debug message
                    print ('Found a match ' + tr['category_name'] + ' matches: ' + categories['name'] + ', In Budget ' + budgets['budget_name'] + '. ID: ' + budgets['budget_id']).encode('utf8')

                    # Variables of necessary data
                    for delta in AllDeltaAccounts:
                        if budgets['budget_id'] == delta['budget_id']:
                            targetaccount = delta['id']
                            targetaccountname = delta['name']
                            break
                    targetcategoryid = categories['id']
                    targetcategoryname = categories['name']
                    targetbudget = budgets['budget_id']
                    if tr['memo'] != None:
                        memosrcbudget = 'Source: ' + tr['budget_name'] + '. ' + tr['memo']
                    else:
                        memosrcbudget = 'Source: ' + tr['budget_name']

                    # Remove unnecessary values
                    transactiondata = removekey(tr, 'note') 
                    transactiondata = removekey(transactiondata, 'budget_id')
                    transactiondata = removekey(transactiondata, 'budget_name')
                    transactiondata = removekey(transactiondata, 'payee_id')
                    transactiondata = removekey(transactiondata, 'id')

                    transactiondata.update({'category_id':targetcategoryid, 
                                            'category_name':targetcategoryname,
                                            'account_id':targetaccount,
                                            'account_name':targetaccountname,
                                            'memo': memosrcbudget})

                    transactiondata.update ({'target_budget':targetbudget})

                    output.append(transactiondata) # For bulk transaction
                    break
    return output

# This currently does not handle edited transactions - not sure how to go about that
# parseTransactions prepares the main transaction to be sent out
def parseTransactions(jointTransactions):
    output = []
    # Check all Transactions
    for tr in jointTransactions:
        # Check if deleted, if yes change amount
        if tr != None:
            if tr['deleted'] == True:
                if IncludeDeleted == True:
                    print 'Deleted Transaction Found. Parsing in the negative amount'
                    tr.update({ 'amount':-1*(tr['amount']),
                                'memo':'DELETED TRANSACTION',
                                'payee_name':'Deleted'})
                    output.extend(verifyTransaction(tr))
            else:
                print ('Account: ' + tr['account_name'] + '. Category: ' + tr['category_name'] + '. From budget: ' + tr['budget_name'] + '. ID: ' + tr['budget_id']).encode('utf8')
                output.extend(verifyTransaction(tr))
    sendBulkTransactions(output)

def createConfig(path):
    config = ConfigParser.RawConfigParser(allow_no_value=True)

    config.optionxform = str

    config.add_section('Key')
    config.set('Key', '# For multiple YNAB accounts, separate tokens with a comma "Token1, Token2"')
    config.set('Key', 'Access-Token', 'YOUR_ACCESS_TOKEN_HERE(https://app.youneedabudget.com/settings/developer)')

    config.add_section('User')
    config.set('User', 'Account-Syntax', 'Shared_Delta')
    config.set('User', 'Category-Syntax', 'Shared_ID:')
    config.set('User', 'Category-Affix', '<!>')

    config.add_section('Options')
    config.set('Options', 'Detect-Deleted', '1')

    config.add_section('Meta')
    config.set('Meta', 'X-Rate-Treshold', 20)

    if path != '':
        with open(path, 'wb') as configfile:
            config.write(configfile)
    return config

# Config
# Creates a config file if it doesn't exist
if not os.path.exists('YNAB_Shared_Categories.cfg'):
        print 'Creating YNAB_Shared_Categories.cfg'
        createConfig('YNAB_Shared_Categories.cfg')
        sys.exit('YNAB_Shared_Categories.cfg was created. Add your Access Token to this file')

# Parse config
config = ConfigParser.SafeConfigParser()
# Make sure there are fallback values
config = createConfig('')
config.read('YNAB_Shared_Categories.cfg')

# Check if the access token value was changed
if 'youneedabudget' in config.get('Key', 'Access-Token'):
    sys.exit('Access Token needs to be added in YNAB_Shared_Categories.cfg.')

# Key
AccessToken     = config.get('Key', 'Access-Token').replace(' ','').split(',')

# User
AccountSyntax   = config.get('User', 'Account-Syntax')
CategorySyntax  = config.get('User', 'Category-Syntax')
CategoryAffix   = config.get('User', 'Category-Affix')
CombinedAffix   = CategoryAffix + CategorySyntax

# Options
IncludeDeleted  = config.getboolean('Options', 'Detect-Deleted')

# Meta
XRateTreshold   = config.getint('Meta', 'X-Rate-Treshold')


##############
# SCRIPT START
##############
backupTransactionsCache()
MasterJSON = YNAB_Fetch('')
print 'Grabbed MasterJSON'
AllDeltaAccounts = getAllDeltaAccounts()
print 'All Joint Account IDs grabbed.'
AllSharedCategories = getAllSharedCategories()
print 'All Joint Category IDs grabbed.'
transactions = []
for item in AllDeltaAccounts:
    print ('Checking new transactions in account: ' + item['budget_name'] + '. ID: ' + item['budget_id']).encode('utf8')
    transactions.extend(getNewJointTransactions(item['budget_id']))    
parseTransactions(transactions)
removeDeletedBudgets()
