# YNAB-Shared-Categories
Currently in progress!

To use this application, run the script once, and edit the key.txt with your own access token from https://app.youneedabudget.com/settings/developer

In the budgets you wish to share categories with, create a checking account and name it Delta. 
Add "Joint_Delta" to the Notes of this account. Do this for every applicable budget.

In the categories you wish to share, add "Joint_ID:XXX" (where XXX is a number like 001) to the note of the category,
do for all applicable categories. Again do this for all applicable budgets.
Make sure to match the category name with the ID. For example: 
Groceries in BudgetA's note: Joint_ID:001. 
Groceries in BudgetB's note: Joint_ID:001

The application currently doesn't work as it should, heres why:
 - It only grabs and caches Accounts & Categories once, so if you've created a new joint category after running the app, 
 you need to delete the caches folder.
 - The application doesn't run continously, in the future it will check for new transactions every ~10 minutes (adjustable)
 - Currently it does not send any data back to the YNAB server, this will be fixed soon.

Keep in mind this application only handles new transactions, and ignores everything before the cache was created/updated.
 
I'm not a programmer and have little experience with REST API's and Python, so things are probably not as ideal as they should be.
 
In the function parseTransactions you can get every transaction data that needs to be sent to the YNAB server. All transaction data is stored in
'tr', and all the target account/category data is stored in 'categories' dictionaries.
 
In the function parseDeltas every transaction data is stored in the 'transaction' and 'delta' dictionaries, with the amount being deltaamount.
This is an amount that is going to be added to the "To Be Budgeted" category for every Delta account.

Transaction example (How it's supposed to be when its working): 
Budget A spends -100$ in Groceries, in the account Visa
Budget B receives a transaction of -100$ in Groceries, in the account Delta
Budget A and B both recieve +50$ in their Delta accounts in the category: To Be Budgeted.

The delta will then display the differences in spending, or what the recievers Budget owes the source Budget.
This way only your share of the spending disappears from the 'To be budgeted' amount.

I've intended for this script to be ran as a service in the background of a Raspberry Pi.

Any help in finishing this application will be appreciated!
Apologies for the awful formatting and unreadable script :)
