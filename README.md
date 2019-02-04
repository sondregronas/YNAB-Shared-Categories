Lets you share specific categories with other people, perfect for keeping track of separate budgets for you and your SO! <br>
Requires Python 2.7.13 - https://www.python.org/downloads/release/python-2713/
<br>

## Usage
Change the Access-Token parameter in the config file with your access-token from YNAB. You can get this from: https://app.youneedabudget.com/settings/developer
<br>

In all of your desired budgets, create a Tracking account named Delta, and add the note ```Shared_Delta``` <br>
In your shared categories, add the note ```<!>Shared_ID: XX<!>```, where XX is a unique ID. Match the ID with the corresponding category on your other budgets. <br>

#### Example
Make sure to match the category name with the ID. For example: 
> Groceries in BudgetA's note: My note! <!>Shared_ID:001<!>. <br>
> Groceries in BudgetB's note: Another note. <!>Shared_ID:001<!> <-- Shared Category ID. 

Run the script once to create an initial cache. The script will tell you if you have mismatching category ID's. From now on, next time you run the script it will check every new transaction to see if it matches the shared category criteria, and send effectively an "IOU" to the other budget(s), aswell as updating the spent amount in their budget category. <br>

You may run it manually and it will parse every new transaction from when since it was last ran, but the suggested method is to create an automation rule for it to run every 5-10 minutes if you're on linux (Crontab). I may get around to setup a server for it at some point, then all you'd need to do is authenticate and add the notes as described above. <br>

Optionally you can also speed-up the script by whitelisting budgets, either by name or ID as explained in the Config file. <br>


## Transaction example: 
> Budget A spends -100$ in Groceries, in the account Visa <br>
> Budget B receives a transaction of -100$ in Groceries, in the account Delta <br>
> Budget A and B both recieve +50$ in their Delta accounts in the category: To Be Budgeted. <br>

If there are more than 2 accounts the share will be distributed evenly. For example with 1 person spending 100$ in a shared category with 4 people, the delta added is 75$. (Meaning only -25$ is deducted from To be Budgeted)

The delta will then display the differences in spending, or what the recievers Budget owes the source Budget.
This way you'll still be able to how much you have left to budget, regardless if you've received your share.
<br>

## Configuration file/options
```Access-Token``` - Your YNAB Access Token(s), separate the tokens with a comma if using separate YNAB accounts <br>
<br>

```Account-Syntax``` (Default: Shared_Delta) The string that needs to be added to every shared budget, in a Delta account. <br>
```Category-Syntax``` (Default: Shared_ID:) The string before an ID, within a categorys memo, in a Shared category. <br>
```Category-Affix``` (Default: <!>) A string that needs to be wrapped around the Category-Syntax + ID on both ends. <br>
<br>

```Whitelisted-Budgets``` (Default: blank) Separate budget ID's/Names by a comma. The script will only check the whitelisted budgets for updates. Checks all if blank. <br>
```Detect-Deleted``` (Default: 1) Will adjust for deleted transactions if selected (Parses a negative amount). Recommended to leave on 1. <br>
```Handle-Edits``` (Default: 1) Checks for edits within a transaction (edited amount, changed category, etc). Recommended to leave on 1. <br>
```Automatic-Approval``` (Default: 1) If this is set to 1, every transaction in a Delta account will be 'Approved' automatically <br>
<br>

```X-Rate-Treshold``` (Default: 20) Since the script communicates with the YNAB server multiple times each execution, a buffer is required to make sure we have enough "X-Rates" to finish the script. <br>
<br>

```Verbose-File-Output = 1``` (Default: 1) Sets the log level (YNAB.log) to verbose (Everything) if 1. <br>
```Verbose-Stream-Output = 0``` (Default: 0) Sets the log level for the script to Verbose if 1. <br>
```Enable-File-Log = 1``` (Default: 1) Enables the use of YNAB.log <br>
<br>


## Setup on a Raspberry Pi
###### Getting the script
EDIT: I haven't tested this in awhile after I've made some changes, hopefully it still works. <br>
1. Open Terminal on the Raspberry or access it using SSH<br>
2. Make sure to have git installed ```sudo apt-get install git```<br>
3. (Optional) Create a directory ```mkdir python_scripts``` and enter the directory ```cd python_scripts```<br>
4. Run the command: ```sudo git clone https://github.com/sondregronas/YNAB-Shared-Categories/```<br>
5. Enter the directory by using ```cd YNAB-Shared-Categories```<br>
6. Copy in your access-token to the config file named YNAB_Shared_Categories.cfg, where it says access-token with ```sudo nano YNAB_Shared_Categories.cfg```<br>
7. Exit with 'Ctrl+X' and hit 'Y' and then 'Enter' to confirm.<br>
8. Run the script again to create initial caches. <br>
Now everytime you run the script it will check for new transactions and send them to every shared account.<br>

###### Automate the script
We can use crontab to automatically run the script <br>
- Run ```sudo crontab -e``` and select nano - if this option comes up<br>
- Add the following line to the end of the document:
```*/10 * * * * cd /home/pi/python_scripts/YNAB-Shared-Categories/ && python /home/pi/python_scripts/YNAB-Shared-Categories/YNAB_Shared_Categories.py```<br>
- The */10 tells it to run every 10 minutes, you can change this if you want.<br>
- Exit with 'Ctrl+X' and hit 'Y' and then 'Enter' to confirm<br>

###### Update the git
To update the git simply go enter the directory ```cd python_scripts/YNAB-Shared-Categories/``` and run: ```sudo git pull```<br>


## Disclaimer
Keep in mind this application does NOT work retroactively and only handles new transactions, and ignores everything before its first run. So this will work with already established budgets :).

I'm not a programmer and have little experience with REST API's and Python, so things can probably be more optimized. I would appreciate any help in that department :P.
