# CHANGE THIS TO AUTOQUEUE NEW CACHES
CACHEVERSION = 100
    #####
    #
    # Todo
    # Web hosting
    # Sync budgeted amount
    # Support for Tracking accounts
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
import copy
import logging
from logging.handlers import RotatingFileHandler

class YNABLog:
    def debug(self, msg):
        for x in self.logs:
            x.debug(msg)
    def info(self, msg):
        for x in self.logs:
            x.info(msg)
    def warn(self, msg):
        for x in self.logs:
            x.warn(msg)
    def error(self, msg):
        for x in self.logs:
            x.error(msg)
    def critical(self, msg):
        for x in self.logs:
            x.critical(msg)
    def verbose(self, log, bool):
        if bool:
            log.setLevel(logging.DEBUG)
        else:
            log.setLevel(logging.INFO)
    def enable(self, bool):
        if bool:
            # Filelog
            fileloghandler = RotatingFileHandler('YNAB.log', mode='a', maxBytes=5*1024*1024, backupCount=2, encoding=None, delay=0)
            fileloghandler.setFormatter(self.logformat)
            self.filelog.addHandler(fileloghandler)
            self.streamlog.enabled = False
            self.logs.add(self.filelog)
    def __init__(self):
        self.logformat = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        # Streamlog
        self.streamlog = logging.getLogger('STREAM')
        streamloghandler = logging.StreamHandler()
        streamloghandler.setFormatter(self.logformat)
        self.streamlog.addHandler(streamloghandler)
        
        self.filelog = logging.getLogger('YNAB')
        # Dict
        self.logs = {self.streamlog}

def getCachePath(param):
    '''
    Takes the YNAB API parameter (param)
    Returns a string of the corresponding budget's cache file path
    '''
    if '?last_knowledge_of_server=' in param:
        param = param.split('?')[0]
    if '/' in param:
        return 'caches/'+(param).replace('/','.')
    if '.cache.backup' in param:
        return 'caches/'+param
    return 'caches/'+(param+'.cache').replace('/','.')

def getURL(param, accesstoken):
    '''
    Takes the YNAB API Parameter (param), and accesstoken (Use getAccessTokenByBudgetID()).
    Returns a string: URL path
    '''  
    if '?last_knowledge_of_server=' in param:
        return ('https://api.youneedabudget.com/v1/budgets/' + str(param) + '&access_token=' + str(accesstoken))
    else:
        return ('https://api.youneedabudget.com/v1/budgets/' + str(param) + '?access_token=' + str(accesstoken))

def YNAB(param, accesstoken):
    '''
    Takes the YNAB API Parameter (param), and accesstoken (getAccessTokenByBudgetID()).
    Creates a cache file if none exist
    Returns json data
    '''
    path = getCachePath(param)
    if os.path.isfile(path):
        return YNAB_ParseCache(param)
    return YNAB_Fetch(param, accesstoken=accesstoken)

def YNAB_ParseCache(param):
    '''
    Reads cache file based on YNAB API Parameter (param) as if it's from the YNAB servers.
    Cache reconstructs itself if corrupt or if cacheversion is invalid
    Returns json data
    '''
    path = getCachePath(param)
    i = 0
    attempts = 10
    while i < attempts:
        i = i+1
        with open(path) as f:
            try:
                data = json.load(f)
            except ValueError:
                logger.error('[ERROR] Corrupt file ' + path + '. Fetching new from YNAB.')
                x = param.split('?')[0]
                data = YNAB_Fetch(x)
                logger.error('[CACHE] Cache restored. Retrying.')
                continue
            if data['cacheversion'] != CACHEVERSION and path.endswith('.cache'):
                logger.error('[CACHE] Cache version incorrect. Fetching new cache from YNAB')
                x = param.split('?')[0]
                data = YNAB_Fetch(x)
                logger.error('[CACHE] Cache updated. Retrying.')
                continue
        return data
    logger.critical('[CACHE] Cache failed to load / repair itself')
    sys.exit('CACHE Failed to load / repair itself')

def removekey(d, key):
    '''
    Removes a key from dictionary nondestructively
    Returns modified dictionary
    '''
    r = dict(d)
    del r[key]
    return r

def requestData(url, data, header):
    '''
    A more reliable version of urllib2.Request(). Attempts to Request multiple times before recovering backed up cache 
    '''
    i = 0
    attempts = 10
    while i < attempts:
        i = i+1
        try:
            req = urllib2.Request(url, data, header)
            break
        except urllib2.HTTPError, e:
            if i == attempts:
                logger.critical('[ERROR] HTTP Request Failed too many times (' + str(i) + ') times. Recovering backed up transactions.')
                logger.critical('[ERRORCODE]'+e)
                recoverTransactions()
                sys.exit(e) 
            logger.error('[ERROR] HTTP Request Failed ' + str(i) + ' times. (' + e +')')
        except urllib2.URLError, e:
            if i == attempts:
                logger.critical('[ERROR] URL Failed too many times (' + str(i) + ') times. Recovering backed up transactions.')
                logger.critical('[ERRORCODE]'+e)
                recoverTransactions()
                sys.exit(e)
            logger.error('[ERROR] URL Failed ' + str(i) + ' times. (' + e +')')
        time.sleep(1)
    return req

xratemet = 0
def fetchData(url):
    '''
    Returns raw urllib2 data from an URL (YNAB).
    Does multiple attempts before recovering backed up cache
    '''
    global xratemet
    i = 0
    attempts = 10
    while i < attempts:
        i = i+1
        try:
            data = urllib2.urlopen(url)
            break
        except urllib2.HTTPError, e:
            f = ''
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
                logger.critical('[ERROR] HTTP Request Failed too many times (' + str(i) + ') times. Recovering backed up transactions.')
                logger.critical('[ERRORCODE]'+e)
                recoverTransactions()
                sys.exit(f) 
            logger.error('[ERROR] HTTP Request Failed ' + str(i) + ' times. (' + e +')')
        except urllib2.URLError, e:
            if i == attempts:
                logger.critical('[ERROR] URL Failed too many times (' + str(i) + ') times. Recovering backed up transactions.')
                logger.critical('[ERRORCODE]'+e)
                recoverTransactions()
                sys.exit(e)
            logger.error('[ERROR] URL Failed ' + str(i) + ' times. (' + e +')')
        except httplib.BadStatusLine as e:
            if i == attempts:
                logger.critical('[ERROR] (BadStatusLine) Failed too many times (' + str(i) + ') times. Recovering backed up transactions.')
                logger.critical('[ERRORCODE]'+e)
                recoverTransactions()
                sys.exit(e)
            logger.error('[ERROR] BadStatusLine Failed ' + str(i) + ' times. (' + e +')')
        time.sleep(1)

    xrate = data.info().get('X-Rate-Limit')
    if int(xrate.split('/')[0]) >= (int(xrate.split('/')[1])-int(XRateTreshold)) and xratemet == 0: #Safety Treshold, incase there aren't enough X-Rates to complete the script.
        sys.exit('Surpassed X-Rate-Limit Safety treshold ' + xrate +', will run once more is available')
    xratemet += 1
    return data

def writeCache(data, param):
    '''
    Writes data to a cache filed based on the YNAB API Parameter (param) using getCachePath(param)
    Returns data
    '''
    path = getCachePath(param)
    if not os.path.exists('caches'):
        os.mkdir('caches')
    with open(path, 'w') as cache:
        json.dump(data,cache)
    return data

def YNAB_Fetch(param, accesstoken=None):
    '''
    Takes YNAB API Parameter (param) and an optional singular accesstoken (accesstoken=X)
    Grabs data from the YNAB server and writes it to cache.
    Also adds accesstoken to cache with key: 'token' and CACHEVERSION with key: 'cacheversion'
    Returns dictionaries of data (Single dictionary with specified accesstoken)
    '''
    O = []
    for Y in AccessToken:
        if accesstoken != None:
            Y = accesstoken
        url = getURL(param, Y)
        data = json.load(fetchData(url))
        data.update({'token':Y,
                    'cacheversion':CACHEVERSION})
        O.append(data)
        if param != '':
            writeCache(data,param)
        if accesstoken != None:
            return data
    return O

def deleteBudgetCache(id):
    '''
    Takes a Budget ID and removes all relevant caches
    '''
    y = {('caches/' + id + '.cache'),
        ('caches/' + id + '.transactions'),
        ('caches/' + id + '.transactions.backup'),
        ('caches/' + id + '.queue'),
        ('caches/' + id + '.cache.backup')}
    for x in y:
        if os.path.exists(x):
            os.remove(x)

def removeDeletedBudgets():
    '''
    Detects deleted budgets by matching caches folder with MasterJSON.
    Sends unwanted caches to deleteBudgetCache(id)
    '''
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
                logger.warn('[CACHE] Budget ' + file.split('.')[0] + ' is no longer in MasterJSON. Deleting')
                deleteBudgetCache(file.split('.')[0])

# Creates a backup of every .transactions file, which can be recovered if the POST doesn't go through, so that the server_knowledge is reset.
# is run at the start of the script
def backupTransactionsCache():
    if not os.path.exists('caches'):
        os.mkdir('caches')
    for file in os.listdir('caches/'):
        if file.endswith('.cache') or file.endswith('.transactions'):
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
        logger.warn('[ERROR] No recovery made due to queued up transactions.')

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
                logger.debug(('[CATEGORY] Found Category: ' + index['name'] + ' using Note: ' + index['note'] + ' from budget: ' + index['budget_name']).encode('utf8'))
    return output

# Used to store all Delta Accounts in a dictionary
def getAllDeltaAccounts():
    output = []
    # Grabbing all Delta Account IDs
    updatecount = 0
    for M in MasterJSON:
        for item in M['data']['budgets']:
            if os.path.isfile(str('caches/' + item['id'] + '.cache')) == True:
                logger.debug(('[CACHE] Found existing cache in ' + item['name'] + ' checking for updates before proceeding').encode('utf8'))
                x = getBudgetUpdates(item['id'], M['token'])
                if x == False:
                    logger.debug(('[BUDGET] No updates in ' + item['name']).encode('utf8'))
                else:
                    updatecount += 1
            else:
                updatecount += 1

            json = YNAB(item['id'], M['token'])
            acc = findAccountByNote(AccountSyntax, json)
            if acc != None and acc['deleted'] == False:
                logger.info(('[ACCOUNT] Found Account: ' + acc['name'] + ' from budget: ' + item['name']).encode('utf8'))
                acc.update({'budget_name':item['name'], 'budget_id':item['id']})
                output.append(acc)
    if updatecount != 0:
        return output
    else:
        return False

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
        if i['id'] == id and i['on_budget']:
            return True
        if i['id'] == id and not i['on_budget']:
            logger.critical('[CRITICAL] Delta account is on a tracking account, change to a budget account!!')
            recoverTransactions()
            sys.exit('[CRITICAL] Delta account is on a tracking account!')
    return False

def isAccountOnBudget(category_id):
    if category_id != None:
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

def getAccountNameByID(id, budget_id):
    M = YNAB_ParseCache(budget_id)
    for x in M['data']['budget']['accounts']:
        if id == x['id']:
            return x['name']

def getBudgetIdByAccountId(account_id):
    for M in MasterJSON:
        for y in M['data']['budgets']:
            Y = YNAB_ParseCache(y['id'])
            for x in Y['data']['budget']['accounts']:
                if x['id'] == account_id:
                    return Y['data']['budget']['id']

def getBudgetInfoByAccountId(account_id):
    for M in MasterJSON:
        for y in M['data']['budgets']:
            Y = YNAB_ParseCache(y['id'])
            for x in Y['data']['budget']['accounts']:
                if x['id'] == account_id:
                    return Y['data']['budget']

def getNoteByCategoryId(id):
    for x in AllSharedCategories:
        if id == x['id']:
            return x['note']

# Updates new Accounts and Categories dictionaries to the old dictionary
def mergeDicts(old, changes, check=['accounts','categories','transactions','subtransactions']):
    updatecount = 0
    for x in check:
        if changes['data']['budget'][x] != []:
            updatecount += 1
            oldamount = 0
            newamount = 0
            for d1 in changes['data']['budget'][x]:
                n = True
                for i, d2 in enumerate(old['data']['budget'][x]):
                    if d1['id'] == d2['id']:
                        n = False
                        old['data']['budget'][x][i] = d1
                        oldamount += 1
                        break
                if n:
                    n = d1
                    old['data']['budget'][x].append(d1)
                    newamount += 1
            if oldamount >= 1 or newamount >= 1:
                logger.debug(('[CACHE] Updated ' + str(oldamount) + ' and added ' + str(newamount) + ' new ' + x).encode('utf8'))
    if updatecount == 0:
        return False
    old['data']['server_knowledge'] = changes['data']['server_knowledge']
    return old

# Fetches new data & adds it to the cache
def getBudgetUpdates(budget_id, accesstoken):
    check = ['accounts',
        'categories',
        'transactions',
        'subtransactions']
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
    data = mergeDicts(main,data,check=check)
    if data != False:
        writeCache(data, str(budget_id))
    else:
        return False

# Checks if a transaction is in a shared category, and not in a delta account
# Also parses Split transactions as separate entries
def checkTransaction(item, cache='transactions'):
    checkAccount = isAccountDelta(item['account_id'])
    meta = getBudgetInfoByAccountId(item['account_id'])
    AccountOnBudget = isAccountOnBudget(item['category_id'])
    if cache == 'subtransactions' or item['subtransactions'] == []:
        logger.debug('[TRANSCATION] Checking new ' + cache[0:-1])
        checkCategory = isCategoryShared(item['category_id']) # Boolean if false. Dict if true
        if checkCategory != False or HandleEdits:
            if not checkAccount or HandleEdits:

                output = []

                ## HANDLE EDITS
                checkCachedCategory = False
                checkCachedAccount = True
                SkipTransaction = False
                amount = None
                exists = False
                # Check if ID is in transactions cache.
                # NEED TO CLEAN HANDLEEDITS!!!

                if (item['deleted'] and not checkCategory) or not AccountOnBudget:
                    logger.debug('[TRANSACTION] Deleted, but not in a shared category or in a tracking account')
                    SkipTransaction = True

                if HandleEdits:
                    for cache in (YNAB_ParseCache(meta['id']+'.cache.backup'))['data']['budget'][cache]:
                        if item['id'] == cache['id']:

                            exists = True
                            logger.debug('[TRANSACTION] Transaction already exists in cache. Adjusting values')

                            try:
                                checkCachedAccount = isAccountDelta(cache['account_id'])
                            except KeyError:
                                logger.error('[ERROR] CACHED TRANSACTION USES INVALID ACCOUNT ID. USING NEW TRANSACTION ACCOUNT ID INSTEAD. RESULTS MAY VARY')
                                cache.update({'account_id':item['account_id']})
                                checkCachedAccount = isAccountDelta(item['account_id'])

                            # Determine if old/new transaction is valid for progresesion
                            if checkCachedAccount and checkAccount:
                                logger.debug('[TRANSACTION] Invalid Transaction. Transaction is in Delta')
                                return
                            checkCachedCategory = isCategoryShared(cache['category_id']) # Boolean if false. Dict if true
                            if checkCachedCategory == False and not checkCategory:
                                logger.debug('[TRANSACTION] Invalid Transaction. Transaction is not in a Shared Category')
                                return
                            
                            # If both cached and new categories are shared, but not in the same category
                            if checkCachedCategory != False and checkCategory and not checkCachedAccount and not checkAccount:
                                if item['category_id'] != cache['category_id']:
                                    logger.debug('[TRANSACTION] Shared transction changed category. Adjusting amounts')
                                    amount = item['amount'] # For existing item
                                    olditem = cache
                                    olditem.update({'budget_id':meta['id'], 
                                                'budget_name':meta['name'], 
                                                'account_name':getAccountNameByID(cache['account_id'], meta['id']),
                                                'category_name':checkCachedCategory['name'],
                                                'note':checkCachedCategory['note'],
                                                'payee_name':'Delta',
                                                'date':item['date'],
                                                'amount':cache['amount']*-1})
                                    if olditem['amount'] != 0 and olditem['amount'] != None:
                                        output.append(olditem)
                                    else:
                                        logger.debug('[TRANSACTION] Transaction amount is 0. Skipping')

                            # If category is moved from a regular one to a shared one. Parsed as a normal transaction
                            if checkCachedCategory == False and checkCategory and not checkCachedAccount and not checkAccount and not item['deleted']:
                                logger.debug('[TRANSACTION] Transaction moved from a regular category to a shared category.')
                                amount = item['amount'] # For existing item

                            # If transaction is moved from Delta account to regular account (Parsed as normal transaction)
                            if checkCategory and not checkAccount and checkCachedAccount:
                                logger.debug('[TRANSACTION] Transaction moved from Delta account to other account')
                                amount = item['amount']

                            # If transaction is moved from regular account to delta account (Parsed as normal transaction)
                            if checkCachedCategory and checkAccount and not checkCachedAccount:
                                logger.critical('[TRANSACTION][ERROR] Transaction moved to a delta account!!! TODO')

                            # If a category is moved from a shared one to a regular one. Parsed as a deleted transaction
                            if checkCachedCategory != False and not checkCategory and not checkCachedAccount and not checkAccount:
                                logger.debug('[TRANSACTION] Transaction moved from a shared category to a regular one.')
                                olditem = cache
                                olditem.update({'budget_id':meta['id'], 
                                            'budget_name':meta['name'], 
                                            'account_name':getAccountNameByID(cache['account_id'], meta['id']),
                                            'category_name':checkCachedCategory['name'],
                                            'note':checkCachedCategory['note'],
                                            'payee_name':'Delta',
                                            'date':item['date'],
                                            'amount':cache['amount']*-1})
                                if olditem['amount'] != 0 and olditem['amount'] != None:
                                    output.append(olditem)
                                else:
                                    logger.debug('[TRANSACTION] Transaction amount is 0. Skipping')
                                SkipTransaction = True

                            ## Final touches before sending off
                            # If amount wasn't changed it means it was in cache but in the same category and 
                            if amount == None and not item['deleted']:
                                logger.debug('[TRANSACTION] Transaction changed but Category didnt. Changing amount.')
                                amount = item['amount'] - cache['amount']
                                logger.debug('[TRANSACTION] Amount changed. Old amount: ' + str(cache['amount']) + ' New: ' + str(item['amount']) + '. New sum: ' + str(amount))
                                item.update({'amount':amount})
                                if item['memo'] != None:
                                    item.update({'memo':item['memo'] + ' (Adjusted)'})
                                else:
                                    item.update({'memo':'(Adjusted)'})
                            # Break the loop after execution
                            break

                    # If it doesn't exist in the cache and isn't shared skip it
                    if not exists and (not checkCategory or checkAccount):
                        logger.debug('[TRANSACTION] Transaction is brand new, but not in a shared Category or might be in a Delta Account.')
                        return
                    ## END HANDLE EDITS

                parsebool = False
                if not checkAccount or not checkCachedAccount:
                    parsebool = True

                if not SkipTransaction and parsebool:
                    logger.debug('[TRANSCATION] Transaction is new.')
                    item.update({'budget_id':meta['id'],
                                'budget_name':meta['name'], 
                                'date':item['date'],
                                'note':getNoteByCategoryId(item['category_id'])})
                    if item['amount'] != 0 and item['amount'] != None: 
                        output.append(item)
                    else:
                        logger.debug('[TRANSACTION] Transaction amount is 0. Skipping')
                if output != []:
                    logger.debug('[TRANSCATION] Transaction check complete. Adding to output')
                    return output
    else:
        logger.debug('[TRANSACTION] Split Transaction detected. Attempting to parse as regular transaction')
        logger.warn('[WARNING] Split Transactions have limited support, especially when deleted')
        output = []
        for sub in item['subtransactions']:
            x = removekey(item, 'subtransactions')
            x.update({
                'budget_id':meta['id'], 
                'budget_name':meta['name'], 
                'note':getNoteByCategoryId(sub['category_id']),
                'category_id':sub['category_id'],
                'amount':sub['amount'],
                'id':sub['id'],
                'transaction_id':sub['transaction_id'],
                'deleted':sub['deleted'],
                'date':item['date'],
                'account_id':item['account_id'],
                'memo':sub['memo'] + ' (Split)'
            })
            try:
                output.extend(checkTransaction(x, cache='subtransactions'))
            except TypeError:
                logger.error('[ERROR] Prevented a null transaction from being added to transaction output.')
        if output != []:
            logger.debug('[TRANSCATION] Transaction check complete. Adding to output')
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

    if send == []:
        logger.info('[SCRIPT] 0 new transactions.')

    recover = False
    for i in send:
        req = requestData(i['url'], i['data'], {'Content-Type': 'application/json', 'Content-Length': len(i['data'])})
        response = fetchData(req)
        logger.info(response.read())

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
				'approved':AutoApprove
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
                    logger.debug(('[TRANSACTION] Found a match ' + tr['category_name'] + ' matches: ' + categories['name'] + ', In Budget ' + budgets['budget_name']).encode('utf8'))

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
                                            'memo': memosrcbudget,
                                            'approved':AutoApprove})

                    transactiondata.update ({'target_budget':targetbudget})

                    output.append(transactiondata) # For bulk transaction
                    break
    return output

def parseWhitelist():
    O = copy.deepcopy(MasterJSON)
    for val, M in enumerate(O):
        i = 0
        for x in M['data']['budgets']:
            z = True
            for y in Whitelist:
                if x['id'] == y or x['name'] == y:
                    logger.debug('[WHITELIST] Whitelisted: ' + MasterJSON[val]['data']['budgets'][i]['name'])
                    z = False
                    break
            if z:
                logger.debug('[WHITELIST] Skipping: ' + MasterJSON[val]['data']['budgets'][i]['name'])
                del MasterJSON[val]['data']['budgets'][i]
                continue
            i += 1

# This currently does not handle edited transactions - not sure how to go about that
# parseTransactions prepares the main transaction to be sent out
def parseTransactions(jointTransactions):
    output = []
    # Check all Transactions
    for tr in jointTransactions:
        # Check if deleted, if yes change amount
        if tr != None:
            if tr['deleted']:
                if IncludeDeleted == True:
                    logger.debug('[TRANSACTION] Deleted Transaction Found. Parsing in negative amount')
                    tr.update({ 'amount':-1*(tr['amount']),
                                'memo':'DELETED TRANSACTION',
                                'payee_name':'Deleted'})
                    output.extend(verifyTransaction(tr))
                else:
                    logger.warn('[TRANSACTION] A transaction in a shared category ID was deleted, but Detect-Deleted is turned off.')
            else:
                logger.debug(('[TRANSACTION] Account: ' + tr['account_name'] + '. Category: ' + tr['category_name'] + '. From budget: ' + tr['budget_name']).encode('utf8'))
                output.extend(verifyTransaction(tr))
    sendBulkTransactions(output)

def createConfig(path):
    config = ConfigParser.RawConfigParser(allow_no_value=True)
    config.optionxform = str
    # Key
    config.add_section('Key')
    config.set('Key', '# For multiple YNAB accounts, separate tokens with a comma "Token1, Token2"')
    config.set('Key', 'Access-Token', 'YOUR_ACCESS_TOKEN_HERE(https://app.youneedabudget.com/settings/developer)')
    # User
    config.add_section('User')
    config.set('User', 'Account-Syntax', 'Shared_Delta')
    config.set('User', 'Category-Syntax', 'Shared_ID:')
    config.set('User', 'Category-Affix', '<!>')
    # Options
    config.add_section('Options')
    config.set('Options', '# Only whitelisted budgets are parsed. Parses every budget by default. Separate Budget IDs/Names with a comma "ID1, ID2"')
    config.set('Options', 'Whitelisted-Budgets', '')
    config.set('Options', 'Detect-Deleted', '1')
    config.set('Options', 'Handle-Edits', '1')
    config.set('Options', 'Automatic-Approval', '1')
    # Meta
    config.add_section('Meta')
    config.set('Meta', 'X-Rate-Treshold', 20)
    # Debug
    config.add_section('Debug')
    config.set('Debug', '# Verbose Output changes log from INFO to DEBUG')
    config.set('Debug', 'Verbose-File-Output', '1')
    config.set('Debug', 'Verbose-Stream-Output', '0')
    config.set('Debug', 'Enable-File-Log', '1')
    # Write config if empty
    if path != '':
        with open(path, 'wb') as configfile:
            config.write(configfile)
    return config

# Config
# Creates a config file if it doesn't exist
if not os.path.exists('YNAB_Shared_Categories.cfg'):
        logger.info('[INITIALIZE] Creating YNAB_Shared_Categories.cfg')
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
AccessToken     = [x.strip() for x in config.get('Key', 'Access-Token').split(',')]
# User
AccountSyntax   = config.get('User', 'Account-Syntax')
CategorySyntax  = config.get('User', 'Category-Syntax')
CategoryAffix   = config.get('User', 'Category-Affix')
CombinedAffix   = CategoryAffix + CategorySyntax
# Options
Whitelist       = [x.strip() for x in config.get('Options', 'Whitelisted-Budgets').split(',')]
IncludeDeleted  = config.getboolean('Options', 'Detect-Deleted')
HandleEdits     = config.getboolean('Options', 'Handle-Edits')
AutoApprove     = config.getboolean('Options', 'Automatic-Approval')
# Meta
XRateTreshold   = config.getint('Meta', 'X-Rate-Treshold')
# Debug
logger = YNABLog()
logger.verbose(logger.filelog, config.getboolean('Debug', 'Verbose-File-Output'))
logger.verbose(logger.streamlog, config.getboolean('Debug', 'Verbose-Stream-Output'))
logger.enable(config.getboolean('Debug', 'Enable-File-Log'))

def main():
    logger.info('[SCRIPT] Backing up existing caches')
    backupTransactionsCache()
    logger.info('[SCRIPT] Done')

    logger.info('[SCRIPT] Grabbing MasterJSON')
    global MasterJSON
    MasterJSON = YNAB_Fetch('')
    logger.info('[SCRIPT] Grabbed MasterJSON')

    if Whitelist != ['']:
        logger.info('[SCRIPT][OPTIONAL] Whitelist found. Parsing Whitelist')
        parseWhitelist()
        logger.info('[SCRIPT][OPTIONAL] Done parsing Whitelist')

    logger.info('[SCRIPT] Grabbing Shared Delta Account IDs')
    global AllDeltaAccounts
    AllDeltaAccounts = getAllDeltaAccounts()
    if not AllDeltaAccounts:
        logger.info('[BUDGET] Zero updates were found. No reason to progress script.')
        return
    logger.info('[SCRIPT] All Shared Delta Account IDs grabbed.')

    logger.info('[SCRIPT] Grabbing Shared Category IDs')
    global AllSharedCategories
    AllSharedCategories = getAllSharedCategories()
    logger.info('[SCRIPT] All Shared Category IDs grabbed.')

    logger.info('[SCRIPT] Grabbing new transactions.')
    transactions = []
    for i, item in enumerate(AllDeltaAccounts, start=1):
        transactions.extend(getNewJointTransactions(item['budget_id']))
        logger.info(('[TRANSACTION] Finished grabbing transactions from ' + item['budget_name'] + ' (' + str(i) + '/' + str(len(AllDeltaAccounts)) + ')').encode('utf8'))
    logger.info('[SCRIPT] Finished grabbing transactions.')    

    logger.info('[SCRIPT] Sending new transactions to parser, if any')
    parseTransactions(transactions)
    logger.info('[SCRIPT] Completed parsing of transactions')

##############
# SCRIPT START
##############
start_time = time.time()
logger.info('------------------------------------------------------')
logger.info('[SCRIPT] Starting script')
main()
logger.info('[SCRIPT] Completed script. Cleaning up')
removeDeletedBudgets()
logger.info("[SCRIPT] Script finished execution after %s seconds " % round((time.time() - start_time),2))
logger.info('------------------------------------------------------')
