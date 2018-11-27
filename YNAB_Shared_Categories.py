    #####
    #
    # Todo
    # Verify budgets account & categories data without deleting
    #
    #####
    #
    # Low priority
    # Sync Budgeted Amount in Joint Categories between all Budgets (If possible by date modified, or by highest number)
    # Be able to mark other transactions as "JOINT" that are not part of a joint category with memos, adding them to Delta without a category
    # Detected deleted or edited transactions & update all + delta if possible
    # Have a neat conf.txt file with more options like "Standard Transaction text", "Standard Delta Text", etc.
    #
    ####

import urllib2
import urllib
import json
import os
import sys

######################################
# YNAB Related commands
######################################

# Grabs the API key string from key.txt. Creates a file if there is none.
def getAPIKey():
    if os.path.isfile('key.txt'):
        with open('key.txt', 'r') as key:
            apikey = key.read().replace('\n','')
    else:
        with open('key.txt', 'w') as key:
            key.write('<YOUR_API_KEY_HERE(https://app.youneedabudget.com/settings/developer)>')
            sys.exit('File: key.txt was created. Edit this and add your own API-key')
    return apikey

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

######################################
# Other useful functions
######################################

# Remove key from dictionary nondestructively
def removekey(d, key):
    r = dict(d)
    del r[key]
    return r

######################################
# Server Request commands - Limited to 200 runs per hour (1 user = usually 1 run each)
######################################

# fetchData returns the data from an URL, but doesn't write cache
def fetchData(url):
    try:
        data = urllib2.urlopen(url)
    except urllib2.HTTPError, e:
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
    return json.load(data)

# Fetches data from the server and writes it to cache
def YNAB_Fetch(param):
    path = getCachePath(param)
    url = getURL(param)
    data = fetchData(url)

    # Write Cache
    if not os.path.exists('caches'):
        os.mkdir('caches')
    with open(path, 'w') as cache:
        json.dump(data,cache)
    return data

######################################
# Used mainly only by other functions
######################################

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
            index.update({'budget_name':item['budget_name'], 'budget_id':item['budget_id']})
            output.append(index)
            print str('Found Category: ' + index['name'] + ' With ID: ' + index['id'] + ' using Note: ' + index['note'] + ' from budget: ' + index['budget_name'] + ' with ID: ' + index['budget_id'])
    return output

# Used to store all Delta Accounts in a dictionary
def getAllDeltaAccounts():
    output = []
    # Grabbing all Delta Account IDs
    for item in MasterJSON['data']['budgets']:
        acc = findAccountByNote(modNoteDeltaAccount, YNAB(item['id']))
        if acc != None:
            acc.update({'budget_name':item['name'], 'budget_id':item['id']})
            output.append(acc)
            print str('Found Account: ' + acc['name'] + ' With ID: ' + acc['id'] + ' from budget: ' + acc['budget_name'] + ' with ID: ' + acc['budget_id'])
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

######################################
# Data related functions
######################################

###############################################
###############################################
###############################################
###############################################

# Once these 2 are working, everything should be ready for use :)

### NEEDS WORK, TO DO
def mergeCache(budget_id, changes):
    print 'TO DO - mergeCache'
    # Main cache (<budget_id>.cache)
    #print YNAB_ParseCache(budget_id)
    # Merge with 'changes'
    #print changes

    # If matches ID:
    #   ifdeleted = true, 
    #       then remove key from main cache file ('caches/'+budget_id+'.cache')
    #   if items edited
    #       update main cache file with new values
    #   if item new
    #       add key to main cache file

### NEEDS WORK, DOES NOT WRITE TO CACHE
# Fetches new data NOT WORKING
def getBudgetUpdates(budget_id):
    param = budget_id+'?last_knowledge_of_server='
    path = getCachePath(param)
    if os.path.isfile(path): # THIS WILL NEVER BE TRUE SINCE THERE IS NO CACHE
        json = YNAB(param)
        x = json['data']['server_knowledge']
    else: 
        json = YNAB(budget_id)
        x = json['data']['server_knowledge']
    param = param + str(x)
    url = getURL(param)
    data = fetchData(url)
    # Write data to a cache file
    mergeCache(budget_id,data)
    return data

###############################################
###############################################
###############################################
###############################################

# Checks for new transactions and outputs their data, including budget_id, budget_name, and note (to find the category ID)
# This fetches both deleted and not deleted
def getNewJointTransactions(budget_id):
    output = []
    param = budget_id+'/transactions'
    json = YNAB(param)
    server_knowledge = json['data']['server_knowledge']

    if server_knowledge != '':
        json = YNAB_Fetch(param + '?last_knowledge_of_server=' + str(server_knowledge))

    for item in json['data']['transactions']:
        checkCategory = isCategoryShared(item['category_id'])
        if checkCategory != False:
            if not isAccountDelta(item['account_id']):
                item.update({'budget_id':checkCategory['budget_id'], 'budget_name':checkCategory['budget_name'], 'note':checkCategory['note']})
                output.append(item)
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
            clen = len(data)
            req = urllib2.Request(url, data, {'Content-Type': 'application/json', 'Content-Length': clen})
            try: 
                response = urllib2.urlopen(req)
            except urllib2.HTTPError as e:
                print e.code
                print e.read()
            print response.read()
    else:
        print 'No transactions sent. Transactiondata should be []: ' + str(bulk)

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
                'target_budget':delta['budget_id']
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
                    print 'Found a match ' + tr['category_name'] + ' matches: ' + categories['name'] + ', In Budget ' + budgets['budget_name'] + '. ID: ' + budgets['budget_id']

                    # Variables of necessary data
                    for delta in AllDeltaAccounts:
                        if budgets['budget_id'] == delta['budget_id']:
                            targetaccount = delta['id']
                            targetaccountname = delta['name']
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
    return output

# This currently does not handle edited transactions - not sure how to go about that
# parseTransactions prepares the main transaction to be sent out
def parseTransactions(jointTransactions):
    output = []
    # Check all Transactions
    for tr in jointTransactions:
        # Check if deleted, if yes change amount
        if tr['deleted'] == True:
            if IncludeDeleted == True:
                print 'Detected deleted transaction. Parsing in the negative amount'
                tr.update({ 'amount':-1*(tr['amount']),
                            'memo':'DELETED TRANSACTION',
                            'payee_name':'Deleted'})
                output.extend(verifyTransaction(tr))
        else:
            print 'Account: ' + tr['account_name'] + '. Category: ' + tr['category_name'] + '. From budget: ' + tr['budget_name'] + '. ID: ' + tr['budget_id']
            output.extend(verifyTransaction(tr))
    sendBulkTransactions(output)

######################################################
# GLOBALS
######################################################

if os.path.isfile('conf.txt') == False:
    with open('conf.txt', 'w') as f:
        f.write('# You can edit the modifier and affix to whatever you would like.\n')
        f.write('# Example Delta Account Note: "My delta account! (Shared_Delta)\n')
        f.write('# Example Category Note: Try to stay within budget! <!>Shared_ID: 01<!>\n')
        f.write('# VALUES:\n')
        f.write('Shared Account Note=Shared_Delta\n')
        f.write('Shared Category Note Modifier=Shared_ID:\n')
        f.write('Shared Category Note Affix=<!>\n')
        f.write('Detect Deleted transactions=1')
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
CombinedAffix = modSeparatorAffix+modNoteDeltaCategory


# SCRIPT START
MasterJSON = data = YNAB_Fetch('')
print 'Grabbed MasterJSON'
AllDeltaAccounts = getAllDeltaAccounts()
print 'All Joint Account IDs grabbed.'
AllSharedCategories = getAllSharedCategories()
print 'All Joint Category IDs grabbed.'
for item in AllDeltaAccounts:
    getBudgetUpdates(item['budget_id'])

transactions = []
for item in AllDeltaAccounts:
    print 'Checking new transactions in account: ' + item['budget_name'] + '. ID: ' + item['budget_id']
    transactions.extend(getNewJointTransactions(item['budget_id']))
parseTransactions(transactions)
