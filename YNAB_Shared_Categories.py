    #####
    #
    # Todo
    # Web hosting
    # Sync budgeted amount
    # Cross YNAB account support
    #
    #####

import urllib2
import urllib
import json
import os
import sys
from shutil import copyfile

# Grabs the API key string from key.txt. Creates a file if there is none.
APIKey = None
def getAPIKey():
    global APIKey
    if APIKey == None:
        if os.path.isfile('key.txt'):
            with open('key.txt', 'r') as key:
                APIKey = key.read().replace('\n','')
        else:
            with open('key.txt', 'w') as key:
                key.write('<YOUR_API_KEY_HERE(https://app.youneedabudget.com/settings/developer)>')
                sys.exit('File: key.txt was created. Edit this and add your own API-key')
    return APIKey

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
def getURL(param):  
    if '?last_knowledge_of_server=' in param:
        return 'https://api.youneedabudget.com/v1/budgets/' + str(param) + '&access_token=' + str(getAPIKey())
    return 'https://api.youneedabudget.com/v1/budgets/' + str(param) + '?access_token=' + str(getAPIKey())

# Checks the cache data. If there is no no cache it will call YNAB_Fetch for first time launch
def YNAB(param):
    path = getCachePath(param)
    if os.path.isfile(path):
        return YNAB_ParseCache(param)
    return YNAB_Fetch(param)

# Reads the cache and returns it as if it was from the server.
def YNAB_ParseCache(param):
    path = getCachePath(param)
    with open(path) as f:
        data = json.load(f)
    return data

# Remove key from dictionary nondestructively
def removekey(d, key):
    r = dict(d)
    del r[key]
    return r

# fetchData returns the data from an URL, but doesn't write cache
xratemet = 0
def fetchData(url):
    global xratemet
    try:
        data = urllib2.urlopen(url)
    except urllib2.HTTPError, e:
        print 'HTTPError. Recovering backed up transactions.'
        recoverTransactions()
        if e.code == 400:
            sys.exit('HTTP Error 400: Bad request, did you add a valid API key to key.txt?')
        if e.code == 401:
            sys.exit('HTTP Error 401: Missing/Invalid/Revoked/Expired access token')
        if e.code == 403:
            sys.exit('HTTP Error 403: YNAB subscription expired')
        if e.code == 404:
            sys.exit('HTTP Error 404: Not found, Wrong parameter given')
        if e.code == 409:
            sys.exit('HTTP Error 409: Conflicts with an existing resource')
        if e.code == 429:
            sys.exit('HTTP Error 429: Too many requests, need to wait between 0-59 minutes to try again :(')
        if e.code == 500:
            sys.exit('HTTP Error 500: Internal Server Error, unexpected error')
        sys.exit(e) 
    except urllib2.URLError, e:
        print 'URL-ERROR. Recovering backed up transactions.'
        recoverTransactions()
        sys.exit(e)

    xrate = data.info().get('X-Rate-Limit')
    if int(xrate.split('/')[0]) >= (int(xrate.split('/')[1])-int(xrate_safetytreshold)) and xratemet == 0: #Safety Treshold, incase there isn't enough X-Rates to complete the script.
        sys.exit('Surpassed X-Rate-Limit Safety treshold ' + xrate +', will run once more is available')
    xratemet += 1
    return json.load(data)

def writeCache(data, param):
    path = getCachePath(param)
    if not os.path.exists('caches'):
        os.mkdir('caches')
    with open(path, 'w') as cache:
        json.dump(data,cache)
    return data

# Fetches data from the server and writes it to cache
def YNAB_Fetch(param):
    url = getURL(param)
    data = fetchData(url)
    return writeCache(data,param)

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

# Recovers the .transactions files back to the old version. This runs if a POST request fails
def recoverTransactions():
    for file in os.listdir('caches/'):
        if file.endswith('.backup'):
            src = 'caches/'+file
            dst = ('caches/'+file).split('.backup')[0]
            copyfile(src,dst)

# Used by getAllSharedCategories
# Searches every category for the string 'CombinedAffix' in notes, 
# adds the unique note id to the category and returns a list of all categories
def searchAllSharedCategories(syntax, json): # Might be redundant with caching?
    output = []
    for item in json['data']['budget']['categories']:
        if item['note'] != None:
            if str(syntax) in str(item['note']):
                note_id = item['note'].split(modSeparatorAffix)[1]
                item = removekey(item, 'note')
                item.update({'note':note_id})
                output.append(item)
    return output

# Used to store all Shared Categories in a dictionary
def getAllSharedCategories(): # Needs Caching & Delta
    output = []
    # Grabbing all Joint Category IDs
    for item in AllDeltaAccounts:
        data = searchAllSharedCategories(CombinedAffix, YNAB(item['budget_id']))
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
    for item in MasterJSON['data']['budgets']:
        json = YNAB(item['id'])
        acc = findAccountByNote(modNoteDeltaAccount, json)
        if acc != None and acc['deleted'] == False:
            print ('Found Account: ' + acc['name'] + ' With ID: ' + acc['id'] + ' from budget: ' + item['name'] + ' with ID: ' + item['id']).encode('utf8')
            acc.update({'budget_name':item['name'], 'budget_id':item['id']})
            output.append(acc)
        print ('Checking for updates in ' + item['name']).encode('utf8')
        getBudgetUpdates(item['id'])
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
    json = YNAB(str(budget_id))
    for item in json['data']['budget']['categories']:
        if item['name'] == name:
            return item['id']

# Updates new Accounts and Categories dictionaries to the old dictionary
def mergeDicts(old, changes):
    # Accounts
    if changes['data']['budget']['accounts'] != [] or changes['data']['budget']['categories'] != []:
        for d1 in changes['data']['budget']['accounts']:
            n = True
            for i, d2 in enumerate(old['data']['budget']['accounts']):
                if d1['id'] == d2['id']:
                    n = False
                    print ('Old account ' + d1['name'] + ' updated.').encode('utf8')
                    old['data']['budget']['accounts'][i] = d1
                    break
            if n:
                n = d1
                print ('New account ' + d1['name'] + ' added.').encode('utf8')
                old['data']['budget']['accounts'].append(d1)
                break
        # Categories
        for d1 in changes['data']['budget']['categories']:
            n = True
            for i, d2 in enumerate(old['data']['budget']['categories']):
                if d1['id'] == d2['id']:
                    n = False
                    print ('Old category ' + d1['name'] + ' updated').encode('utf8')
                    old['data']['budget']['categories'][i] = d1
                    break
            if n:
                n = d1
                print ('New category ' + d1['name'] + ' added.').encode('utf8')
                old['data']['budget']['categories'].append(d1)
                break
        # Server knowledge
        old['data']['server_knowledge'] = changes['data']['server_knowledge']
        return old
    return False

# Fetches new data & adds it to the cache
def getBudgetUpdates(budget_id):
    param = budget_id+'?last_knowledge_of_server='
    path = getCachePath(param)
    if os.path.isfile(path):
        json = YNAB(param)
        x = json['data']['server_knowledge']
    else: 
        json = YNAB(budget_id)
        x = json['data']['server_knowledge']
    param = param + str(x)
    url = getURL(param)
    data = fetchData(url)
    data = mergeDicts(json,data)
    if data == False:
        return None
    writeCache(data, str(budget_id))
    return data

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

# Fetches all new transactions in a budget & returns every transaction in a shared category
def getNewJointTransactions(budget_id):
    output = []
    param = budget_id+'/transactions'
    json = YNAB(param)
    server_knowledge = json['data']['server_knowledge']

    if server_knowledge != '':
        json = YNAB_Fetch(param + '?last_knowledge_of_server=' + str(server_knowledge))

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
    # Only run if there are new transactions
    if bulk != []:
        # Sort by budget - to prevent spamming the server with requests
        for acc in AllDeltaAccounts:
            tr = []
            transactiondata = []
            tr = transactionSorter(bulk, acc)

            for i in tr:
                data = removekey(i,'target_budget')
                transactiondata.append(data)

            targetbudget = str(tr[0]['target_budget'])
            url = getURL(targetbudget+'/transactions/bulk')
            data = json.dumps({'transactions':transactiondata})
            req = urllib2.Request(url, data, {'Content-Type': 'application/json', 'Content-Length': len(data)})
            try: 
                response = urllib2.urlopen(req)
            except urllib2.HTTPError as e:
                print 'HTTPError. Recovering backed up transactions.'
                recoverTransactions()
                sys.exit(e.code)
                sys.exit(e.read())
            except urllib2.URLError, e:
                print 'URL-ERROR. Recovering backed up transactions.'
                recoverTransactions()
                sys.exit(e)
            print response.read()
    else:
        print 'No transactions sent. Transactiondata should be [], = ' + str(bulk)
        recoverTransactions()

# parseDeltas prepares the delta transaction to be sent out (Cleaning the old transaction data and replacing it with the target info)
def parseDeltas(transaction):
    output = []
    for delta in AllDeltaAccounts:
        x = transaction['amount']
        y = len(AllDeltaAccounts)
        cat_id = str(fetchCategoryIdByName(str(delta['budget_id']), 'To be Budgeted'))
        data = {'category_id': cat_id,
                'category_name':'To be Budgeted', 
                'account_id':delta['id'], 
                'account_name':delta['name'],
                'amount':-1*(x-(x/y)),
                'memo': 'Split from ' + transaction['category_name'] + ', ' + transaction['payee_name'] + '. Source: ' + transaction['budget_name'],
                'date': transaction['date'],
                'target_budget':delta['budget_id'],
                'payee_name':'Delta', # transaction['payee_name'], - Unless there's a way to prevent the standard categories/account for the given Payee then a static Payee is better to keep the default payee values
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
            if tr['deleted'] == True and IncludeDeleted == True:
                print 'Detected deleted transaction. Parsing in the negative amount'
                tr.update({ 'amount':-1*(tr['amount']),
                            'memo':'DELETED TRANSACTION',
                            'payee_name':'Deleted'})
                output.extend(verifyTransaction(tr))
            else:
                print ('Account: ' + tr['account_name'] + '. Category: ' + tr['category_name'] + '. From budget: ' + tr['budget_name'] + '. ID: ' + tr['budget_id']).encode('utf8')
                output.extend(verifyTransaction(tr))
    sendBulkTransactions(output)


#ConfigFile
if os.path.isfile('conf.txt') == False:
    with open('conf.txt', 'w') as f:
        f.write('# You can edit the modifier and affix to whatever you would like.\n')
        f.write('# Example Delta Account Note: "My delta account! (Shared_Delta)"\n')
        f.write('# Example Category Note: Try to stay within budget! <!>Shared_ID: 01<!>\n')
        f.write('# VALUES:\n')
        f.write('Shared Account Note=Shared_Delta\n')
        f.write('Shared Category Note Modifier=Shared_ID:\n')
        f.write('Shared Category Note Affix=<!>\n')
        f.write('Detect Deleted transactions=1\n')
        f.write('X-Rate-Limit Safe Treshold=20')
with open('conf.txt', 'r') as f:
    f.readline()
    f.readline()
    f.readline()
    f.readline()
    modNoteDeltaAccount = f.readline().split('=')[1].replace('\n','')
    modNoteDeltaCategory = f.readline().split('=')[1].replace('\n','')
    modSeparatorAffix = f.readline().split('=')[1].replace('\n','')
    if f.readline().split('=')[1].replace('\n','') == '1':
        IncludeDeleted = True
    else:
        IncludeDeleted = False
    xrate_safetytreshold = f.readline().split('=')[1].replace('\n','')
CombinedAffix = modSeparatorAffix+modNoteDeltaCategory

# SCRIPT START
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
