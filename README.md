# YNAB-Shared-Categories
Currently in progress!

To use this application, run the script once, and edit the key.txt with your own access token from https://app.youneedabudget.com/settings/developer

In the budgets you wish to share categories with, create a checking account and name it Delta. 
Add "Joint_Delta" to the Notes of this account. Do this for every applicable budget.

In the categories you wish to share, add "<!>Joint_ID:XXX<!>" anywhere to the note of the category. Do so for every account you want synchronized
If you want to change the syntax to something else, replace it in the conf.txt file. Keep everything within the quotationmarks

Make sure to match the category name with the ID. For example: 
Groceries in BudgetA's note: My note! <!>Joint_ID:001<!>.
Groceries in BudgetB's note: Another note. <!>Joint_ID:001<!> <-- Shared Category ID.
You can also use letters, words or symbols for your ID, as long as the syntax is the same between accounts

The application kinda works, but still lacks some important features:
 - It only grabs and caches Accounts & Categories once, so if you've created a new joint category after running the app, 
 you need to delete the caches folder to reset.
 - The application needs to be manually executed whenever a new transaction is added (However you don't need to actively execute it, it recognizes every new transaction since last execution

Keep in mind this application does not work retroactively and only handles new transactions, and ignores everything before the cache was created/updated.
 
I'm not a programmer and have little experience with REST API's and Python, so things are probably not as optimized as they could be.

Transaction example: 
Budget A spends -100$ in Groceries, in the account Visa
Budget B receives a transaction of -100$ in Groceries, in the account Delta
Budget A and B both recieve +50$ in their Delta accounts in the category: To Be Budgeted.

If there are more than 2 accounts the share will be distributed evenly. For example with 1 person spending 100$ in a shared category with 4 people, the delta added is 75$. (Meaning only -25$ is deducted from To be Budgeted)

The delta will then display the differences in spending, or what the recievers Budget owes the source Budget.
This way you'll still be able to how much you have left to budget, regardless if you've received your share.

I've intended for this script to be run off a Raspberry Pi.

Any help in finishing this application will be appreciated!
Apologies for the awful formatting and unreadable script :)
