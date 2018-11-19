    #####
    #
    # Transaction logic: 
    # 1: Amount from Senders Account gets added to Delta Accounts of recipients in the category of the same ID
    # 2: Positive Amount / No. of Delta Accounts, is added to All Delta Accounts in "To Be Budgeted"
    #
    #####
    #
    # Todo
    # Sync Budgeted Amount in Joint Categories between all Budgets (If possible by date modified, or by highest number)
    # Verify budgets account & categories data without refreshing cache
    #
    #####
    #
    # Low priority
    # Be able to mark other transactions as "JOINT" that are not part of a joint category with memos, adding them to Delta without a category
    # Detected deleted or edited transactions & update all + delta if possible
    #
    ####

import urllib2
import urllib
import json
import os
import sys

# Grabs the API key string from file
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

# Checks for changes, writes to cache if any, fetches if there's no cache.
def YNAB(param):
    path = getCachePath(param)
    if os.path.isfile(path):
        return YNAB_ParseCache(param)
    return YNAB_Fetch(param)

# Fetches JSON
def YNAB_Fetch(param):
    path = getCachePath(param)

    url = 'https://api.youneedabudget.com/v1/budgets/' + str(param) + '?access_token=' + str(getAPIKey())
        
    if '?last_knowledge_of_server=' in param:
        url = 'https://api.youneedabudget.com/v1/budgets/' + str(param) + '&access_token=' + str(getAPIKey())
    
    # Request data
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
    # Fetch data if no errors

    # If it crashes here it's due to too many requests
    data = json.load(data)

    # Write Cache
    if not os.path.exists('caches'):
        os.mkdir('caches')
    with open(path, 'w') as cache:
        json.dump(data,cache)
    
    return data

# Parse the cache in param
def YNAB_ParseCache(param):
    path = getCachePath(param)
    with open(path) as f:
        data = json.load(f)
    return data

# Remove key from dictionary
def removekey(d, key):
    r = dict(d)
    del r[key]
    return r
    
# Returns All Account Info matching the Account Note Modifier. Takes the ID String & JSON in /budgets/-ID/
def findAccountByNote(note, json): # FINISHED
    for item in json['data']['budget']['accounts']:
        if(item['note'] == note):
            return item

# Used by getAllJointCategories - Searches every category for the string 'modNoteDeltaCategory' without ID in the Notes & Returns a dictionairy
# Takes the modNoteDeltaCategory syntax and the JSON from /budgets/-Budget_ID-/
def searchAllJointCategories(syntax, json): # Might be redundant with caching?
    output = []
    for item in json['data']['budget']['categories']:
        if item['note'] != None:
            if str(syntax) in str(item['note']):
                output.append(item)
    return output

# Grabs all JointCategoryIds to reduce fetching of JSON
def getAllJointCategories(AllDeltaAccounts): # Needs Caching & Delta
    output = []
    # Grabbing all Joint Category IDs
    for item in AllDeltaAccounts:
        data = searchAllJointCategories(modNoteDeltaCategory, YNAB(item['budget_id']))
        for index in data:
            index.update({'budget_name':item['budget_name'], 'budget_id':item['budget_id']})
            output.append(index)
            print str('Found Category: ' + index['name'] + ' With ID: ' + index['id'] + ' using Note: ' + index['note'] + ' from budget: ' + index['budget_name'] + ' with ID: ' + index['budget_id'])
    return output

# Grabs all DeltaAccountIds to reduce fetching of new JSON
def getAllDeltaAccounts(MasterJSON):
    output = []
    # Grabbing all Delta Account IDs
    for item in MasterJSON['data']['budgets']:
        acc = findAccountByNote(modNoteDeltaAccount, YNAB(item['id']))
        if acc != None:
            acc.update({'budget_name':item['name'], 'budget_id':item['id']})
            output.append(acc)
            print str('Found Account: ' + acc['name'] + ' With ID: ' + acc['id'] + ' from budget: ' + acc['budget_name'] + ' with ID: ' + acc['budget_id'])
    return output

# Checks if the Category ID matches the JointCategories list
def isCategoryJoint(id, AllJointCategories): # Works - Need to allow for more in memo (Contains id, skip if space?)
    for i in AllJointCategories:
        if i['id'] == id:
            return i
    return False

# Checks if the Account ID matches the DeltaAccounts list
def isAccountDelta(id, AllDeltaAccounts): # Works
    for i in AllDeltaAccounts:
        if i['id'] == id:
            return True
    return False

# Gets all the new Joint Transaction data
def getNewJointTransactionsBACKUP(json, AllJointCategories, AllDeltaAccounts, param):
    output = []
    server_knowledge = json['data']['server_knowledge']
    if server_knowledge != '':
        json = YNAB_Fetch(param + '?last_knowledge_of_server=' + str(server_knowledge))
    for item in json['data']['transactions']:
        checkCategory = isCategoryJoint(item['category_id'], AllJointCategories)
        if checkCategory != False:
            item.update({'budget_id':checkCategory['budget_id'], 'budget_name':checkCategory['budget_name'], 'note':checkCategory['note']})
            if not isAccountDelta(item['account_id'], AllDeltaAccounts):
                output.append(item)
    return output

# Checks for new transactions and outputs their data, including budget_id, budget_name, and note (to find the category ID)
def getNewJointTransactions(AllJointCategories, AllDeltaAccounts, budget_id):
    output = []

    param = budget_id+'/transactions'
    json = YNAB(param)
    server_knowledge = json['data']['server_knowledge']

    if server_knowledge != '':
        json = YNAB_Fetch(param + '?last_knowledge_of_server=' + str(server_knowledge))

    for item in json['data']['transactions']:
        checkCategory = isCategoryJoint(item['category_id'], AllJointCategories)
        if checkCategory != False:
            item.update({'budget_id':checkCategory['budget_id'], 'budget_name':checkCategory['budget_name'], 'note':checkCategory['note']})
            if not isAccountDelta(item['account_id'], AllDeltaAccounts):
                output.append(item)
    return output

# Get every Budget except the source of transaction for a transaction
def getTransactionReceivers(senders_budget, AllDeltaAccounts):
    output = []
    for budgets in AllDeltaAccounts:
        if senders_budget != budgets['budget_id']:
            output.append(budgets)
    #print 'OUTPUT'
    #print output
    return output

# Update the variable MasterJSON (Cache)
def UpdateMasterJSON(json):
    data = YNAB('')
    print 'Grabbed MasterJSON'
    #
    # NEED TO CHECK FOR UPDATES
    #
    return data

# Update the variable AllDeltaAccounts
def UpdateDeltaAccounts(json):
    data = getAllDeltaAccounts(MasterJSON)
    print 'All Joint Account IDs grabbed.'
    #
    # NEED TO CHECK FOR UPDATES
    #
    return data

# Update the variable AllJointCategories - needs to be made into a cache file
def UpdateJointCategories(json, AllDeltaAccounts):
    data = getAllJointCategories(AllDeltaAccounts)
    print 'All Joint Category IDs grabbed.'
    #
    # NEED TO CHECK FOR UPDATES
    #
    return data

####################################################
####################################################

def sendBulkTransactions(bulk):
    for index in bulk:
        targetbudget = index['target_budget']
        transactiondata = removekey(index,'target_budget')

        # Need to somehow sort by target_budget so to only send one request per budget - probably a really easy way to do this..
        # As for now it sends a request for every transaction which isn't ideal..
        url = 'https://api.youneedabudget.com/v1/budgets/' + targetbudget + '/transactions/bulk?access_token=' + str(getAPIKey())
        data = {'transactions':[transactiondata]}

        data = urllib.urlencode(data)
        req = urllib2.Request(url, data)
        #response = urllib2.urlopen(req) # Response 400?
        #print response.read() 

####################################################
####################################################

# Missing Category ID = To Be Budgeted
# Other than that I believe it is completed, unless payeeid or transactionid is required
# parseDeltas prepares the delta transaction to be sent out (Cleaning the old transaction data and replacing it with the target info)
def parseDeltas(transaction):
    output = []
    for delta in AllDeltaAccounts:
        # Variables of necessary data
        targetaccount = delta['id']
        targetaccountname = delta['name']
        targetcategoryid = '' # Not sure what the easiest way to retrieve this is, or if this is necessary
        targetcategoryname = 'To be Budgeted'
        targetbudget = delta['budget_id']
        targetpayeeid = '' # Not sure if this is needed
        transactionid = '' # Not sure if this is needed?
        memosrcbudget = 'Split delta for transaction at ' + transaction['payee_name'] + ' Source: ' + transaction['budget_name'] + '. Original Amount: ' + str(transaction['amount'])

        deltaamount = -1*(transaction['amount']/len(AllDeltaAccounts))

        # Remove 'note', 'budget_id', 'budget_name'. - These were only needed for budget verification and not part of the transactions originally.
        transactiondata = removekey(transaction, 'note') 
        transactiondata = removekey(transactiondata, 'budget_id')
        transactiondata = removekey(transactiondata, 'budget_name')

        # Update category & Account
        transactiondata = removekey(transactiondata, 'category_id')
        transactiondata = removekey(transactiondata, 'category_name')
        transactiondata = removekey(transactiondata, 'account_id')
        transactiondata = removekey(transactiondata, 'account_name')
        transactiondata = removekey(transactiondata, 'payee_id')
        transactiondata = removekey(transactiondata, 'id')
        transactiondata = removekey(transactiondata, 'amount')
        transactiondata = removekey(transactiondata, 'memo')

        transactiondata.update({'category_id':targetcategoryid, 
                                'category_name':targetcategoryname, 
                                'account_id':targetaccount, 
                                'account_name':targetaccountname,
                                'payee_id':targetpayeeid,
                                'id':transactionid,
                                'amount':deltaamount,
                                'memo': memosrcbudget})
        
        transactiondata.update ({'target_budget':targetbudget})
        output.append(transactiondata) # For bulk transaction
        
    return output


# This should be complete AFAIK - Except it doesn't handle deleted or edited transactions. 
# It doesn't include deleted transactions however, edited transactions are treated as new transactions.
# Don't know if 'subtransactions' work either, but idk if it's necessary
# targetpayeeid and transactionid Might be needed - I don't know?
# parseTransactions prepares the main transaction to be sent out (Cleaning the old transaction data and replacing it with the target info)
def parseTransactions(jointTransactions):
    output = []
    # Check all Transactions
    for tr in jointTransactions:
        # Make sure transactions are new, and not deleted
        if not tr['deleted']:
            # Sends transaction data to parseDeltas
            output = parseDeltas(tr) # For bulk transaction
            print 'Account: ' + tr['account_name'] + '. Category: ' + tr['category_name'] + '. From budget: ' + tr['budget_name'] + '. ID: ' + tr['budget_id']
            # Get the receivers of the new transaction
            for budgets in getTransactionReceivers(tr['budget_id'], AllDeltaAccounts):
                for categories in AllJointCategories:
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
                            targetpayeeid = '' # Not sure if this is needed?
                            transactionid = '' # Not sure if this is needed?
                            memosrcbudget = tr['memo'] + ', Transaction From: ' + tr['budget_name']

                            # Remove 'note', 'budget_id', 'budget_name'. - These were only needed for budget verification and not part of the transactions originally.
                            transactiondata = removekey(tr, 'note') 
                            transactiondata = removekey(transactiondata, 'budget_id')
                            transactiondata = removekey(transactiondata, 'budget_name')

                            # Update category & Account
                            transactiondata = removekey(transactiondata, 'category_id')
                            transactiondata = removekey(transactiondata, 'category_name')
                            transactiondata = removekey(transactiondata, 'account_id')
                            transactiondata = removekey(transactiondata, 'account_name')
                            transactiondata = removekey(transactiondata, 'payee_id')
                            transactiondata = removekey(transactiondata, 'id')
                            transactiondata = removekey(transactiondata, 'memo')

                            transactiondata.update({'category_id':targetcategoryid, 
                                                    'category_name':targetcategoryname,
                                                    'account_id':targetaccount,
                                                    'account_name':targetaccountname,
                                                    'payee_id':targetpayeeid,
                                                    'id':transactionid,
                                                    'memo': memosrcbudget})

                            transactiondata.update ({'target_budget':targetbudget})
                            output.append(transactiondata) # For bulk transaction
    sendBulkTransactions(output)

def main():

    # Loop every X mins or something

    # Make a way to verify cache
    # if budgets / server_knowledge / accounts/categories changed, then 
        # Update caches with: 
        # MasterJSON = UpdateMasterJSON(MasterJSON)
        # AllDeltaAccounts = UpdateDeltaAccounts(AllDeltaAccounts)
        # AllJointCategories = UpdateJointCategories(AllJointCategories, AllDeltaAccounts)
    
    transactions = []
    for item in AllDeltaAccounts:
        print 'Checking new transactions in account: ' + item['budget_name'] + '. ID: ' + item['budget_id']
        transactions.extend(getNewJointTransactions(AllJointCategories, AllDeltaAccounts, item['budget_id']))
    parseTransactions(transactions)
    # End Loop

# END MAINSCRIPT

######################################################
# GLOBALS
######################################################

if os.path.isfile('conf.txt') == False:
    with open('conf.txt', 'w') as f:
        f.write('# You can edit the modifier to whatever you would like.\n')
        f.write('# Do not include any spaces or additional information in your notes on YNAB. Do not remove quotation marks\n')
        f.write('# VALUES:\n')
        f.write('Create a Delta account and put this in the Account Notes: "Joint_Delta"\n')
        f.write('DeltaCategoryNoteModifier: "Joint_ID:"\n')
        #f.write('SeparatorAffix:"<!>"')
with open('conf.txt', 'r') as f:
    f.readline()
    f.readline()
    f.readline()
    modNoteDeltaAccount = f.readline().split('"')[1]
    modNoteDeltaCategory = f.readline().split('"')[1]
    #modSeparatorAffix = f.readline().split('"')[1]


MasterJSON = ''
AllDeltaAccounts = []
AllJointCategories = []

MasterJSON = UpdateMasterJSON(MasterJSON)
AllDeltaAccounts = UpdateDeltaAccounts(AllDeltaAccounts)
AllJointCategories = UpdateJointCategories(AllJointCategories, AllDeltaAccounts)

######################################################
# END GLOBALS
######################################################

main()
