# YNAB-Shared-Categories
Created with Python 2.7.13 - https://www.python.org/downloads/release/python-2713/
<br>

## Usage
To use this application, install Python from above and run the script once, and edit the key.txt with your own access token from https://app.youneedabudget.com/settings/developer

After you've added the Shared Delta Accounts and categories as described below, run it again to create initial caches (A /caches/ folder should appear). 

And you're done. Now everytime you want to synchronize the transactions run it again. I'm not sure how to automate the process on Windows/Mac, but I'll eventually try and set something up using a website if I can.

#### Budgets
In the budgets you wish to share categories with, create a checking account and name it Delta, or somethinge else. 
Add "Shared_Delta" to the Notes of this account. Do this for every budget you want to share categories with.

#### Categories
In the categories you wish to share, add "<!>Shared_ID:XXX<!>" anywhere to the note of the category. Do so for every account you want synchronized

Make sure to match the category name with the ID. For example: 
> Groceries in BudgetA's note: My note! <!>Shared_ID:001<!>. <br>
> Groceries in BudgetB's note: Another note. <!>Shared_ID:001<!> <-- Shared Category ID. 

You can also use letters, words or symbols for your ID, as long as the note affix and note modifier is the same between accounts

## Installation (Raspberry Pi)
Just thought I'd add this here if people want to have it running for themselves while I try to figure out how to add it on a website
###### Getting the script
1. Open Terminal on the Raspberry or access it using SSH<br>
2. Install git ```sudo apt-get install git```<br>
3. (Optional) Create a directory ```mkdir python_scripts``` and enter the directory ```cd python_scripts```<br>
4. Run the command: ```sudo git clone https://github.com/sondregronas/YNAB-Shared-Categories/```<br>
5. A directory "YNAB-Shared-Categories" was now added to this folder<br>
6. Copy in your access-token to a file named key.txt with ```sudo nano /YNAB-Shared-Categories/key.txt```<br>
7. Exit with 'Ctrl+X' and hit 'Y' and then 'Enter' to confirm.<br>
8. Run it once to create initial caches, it will only handle transactions after the initial run. ```sudo python /YNAB-Shared-Categories/YNAB-Shared-Categories.py```<br>
Now everytime you run the script it will check for new transactions and send them to every shared account.<br>

###### Automate the script
We can use crontab to automatically run the script
9. Run ```sudo crontab -e``` and select nano - if this option comes up<br>
10. Add the following line to the end of the document:
```*/10 * * * * cd /home/pi/python_scripts/YNAB-Shared-Categories/ && python /home/pi/python_scripts/YNAB-Shared-Categories/YNAB_Shared_Categories.py```<br>
11. The */10 tells it to run every 10 minutes, you can change this if you want.<br>
12. Exit with 'Ctrl+X' and hit 'Y' and then 'Enter' to confirm<br>

###### Update the git
To update the git simply go to the directory ```cd python_scripts/YNAB-Shared-Categories/``` and run: ```sudo git reset --hard master```

###### Clear cache
Unfortunately I still haven't worked out how to update the caches for categories / accounts, so if a category has been modified you will need to flush the cache. Do so by going to the directory and run ```sudo rm -r caches/```

## Configuration
If you want some of the syntaxes, do so in the conf.txt file.
> Shared Account Note (Shared_Delta) is required but can be set to whatever you'd like <br>
> Shared Category Note Modifier (Shared_ID:) is optional and can be set to whatever. <br>
> Shared Category Note Affix (<!>) is required and but be set to whatever you'd like. Please put this on both sides of the ID <br>
> Detect Deleted transactions (1) determines whether or not the script should handle deleted transactions (Same as a regular transaction but with negative amount) (Default 1).

## Status
The application works, but still lacks some important features:
 - It only grabs and caches Accounts & Categories once, so if you've created a new joint category after running the app, 
 you need to delete the caches folder to reset.
 - The application needs to be manually executed whenever a new transaction is added (However you don't need to actively execute it, it recognizes every new transaction since last execution

## Transaction example: 
> Budget A spends -100$ in Groceries, in the account Visa <br>
> Budget B receives a transaction of -100$ in Groceries, in the account Delta <br>
> Budget A and B both recieve +50$ in their Delta accounts in the category: To Be Budgeted. <br>

If there are more than 2 accounts the share will be distributed evenly. For example with 1 person spending 100$ in a shared category with 4 people, the delta added is 75$. (Meaning only -25$ is deducted from To be Budgeted)

The delta will then display the differences in spending, or what the recievers Budget owes the source Budget.
This way you'll still be able to how much you have left to budget, regardless if you've received your share.

## Disclaimer
Keep in mind this application does not work retroactively and only handles new transactions, and ignores everything before the cache was created/updated.

I'm not a programmer and have little experience with REST API's and Python, so things are probably not as optimized as they could be.
