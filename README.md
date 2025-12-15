# PillBox
PillBox is a simple desktop app that helps users manage daily medications. It shows a weekly “pillbox” grid (Mon–Sun × AM/Noon/PM/Bed), lets you add medications and schedules, snooze or log doses, and view a summary of recent actions.

## 1. Overview
PillBox is a Tkinter (desktop) application written in Python. It is designed for:
* Adding medications with name, dose, one or more times per day, and selected days of the week.
* Showing a weekly calendar grid of when each medication is due.
* Popping up reminders when a dose is due, with options to Take, Snooze, or Skip.
* Recording all actions in CSV files and summarizing them in a small chart.

This file is the user’s guide: how to install, run, and use the app. Technical / developer details (code structure, functions, etc.) belong in docs/DEVELOPER.md.

## 2. Requirements
- Operating system: Windows 10 or later (Tkinter is included with normal Python installs on Windows).
-	Python version: Python 3.10+
    - Tested with Python 3.13 on Windows.
-	Python packages:
    - Pandas.
    -	Matplotlib (optional but recommended for the Summary chart).
    -	Tkinter (usually included with Python on Windows).
No API keys or external web services are required.

## 3. Installation
1.	Clone or download the repository
git clone https://github.com/<your-username>/<your-repo-name>.git
cd <your-repo-name>
2.	Install required packages:
    -	From the project root folder: pip install pandas matplotlib
    -	If matplotlib is not installed, the app will still run, but the Summary chart will be disabled.
3.	Project Structure (for users): Your project folder will look roughly like: 
hasan_project/ 
    -	run_app.py 	    	-> Main program: start the app from here 
    -	med_schedule.csv	-> Medication schedule (auto-created if missing)
    -	dose_log.csv 	  	-> Logged actions: taken / skipped / snoozed (auto-created)
    - snoozes.csv 	  	-> Snoozed doses (auto-created) 
    -	ReadMe.md 	    	> This user guide 
    -	LICENSE 
    -	docs/ 
    -	DEVELOPER.md 	-> Developer documentation (technical details); (project spec, review docs, etc.);(other folders such as screenshots/, tmp/, data/ if you add them).

You do not need to manually create the .csv files; the app will create them the first time it runs.

## 4.	How to Run the Application
  1.	Open a terminal (PowerShell, Command Prompt, or VS Code terminal).
  2.	Change into the project folder, e.g.: cd C:\Users<your-name>\Desktop\hasan_project
  3.	Run the app: python run_app.py
  4.	A window titled “PillBox — Version 2 (Progress)” should appear.

If nothing happens or you see an error, see the Troubleshooting section below.

## 5.	Using PillBox (Step-by-Step) 
### 5.1. Main Screen: Weekly Pillbox When the app starts, you are on the Pillbox tab:
- The grid shows rows for time buckets: AM, Noon, PM, Bed.
- The columns are the days of the week: Mon–Sun.
- Each cell can show: medication name dose exact time (HH:MM) 
- Cells are color-coded: 
    - 🟩 Green – Taken,
    - 🟥 Red – Skipped,
    - 🟦 Blue – Snoozed,
    - 🟨 Yellow – Due soon (today, within ~15 minutes of the scheduled time), 
    - ⬜ Gray – Idle / empty

At the bottom of this tab you will also see: 
-	Refresh – Reloads schedule and logs and redraws the grid. 
-	Clear old snoozes – Removes snoozed entries older than a certain number of days.

### 5.2. Add a New Medication
Go to the “Add/Edit” tab, and you will see a form with fields.
1. Name
    -	Enter the medication name.
    -	Example: Vitamin D
2. Dose
    -	Enter the dose description.
    -	Example: 2000 IU or 500 mg.
3. Add Time (24h)
    -	Use the hour dropdown (00–23).
    -	Use the minute dropdown (increments of 5).
    -	Click “Add time” to add that time to the list.
    -	The times you add appear in the small list labeled “Times”. You can add multiple times per day (e.g., 08:00, 20:00).
4. Remove selected time
    -	Click on a time in the list to select it.
    -	Click “Remove selected” to delete it from the schedule.
5. Days
    -	Check the days of the week when you want this medication to be active.
    -	Example: Mon Tue Wed Thu Fri for weekdays only.
6. Active
    -	Leave this checked to make the medication active.
    -	If unchecked, the medication is stored but not shown in the weekly grid, and no reminders are triggered.
7. Save Medication
        When you’re done, click “Save Medication”, The app will:
    -	Validate that Name, Dose, and at least one time are provided.
    -	 Assign a new med_id.
    -	Save it in med_schedule.csv.
    - Refresh the Current Medications table.
    -	Refresh the weekly grid on the Pillbox tab.

### 5.3. Current Medications Table
At the bottom of the Add/Edit tab, you’ll see a table labeled “Current Medications”.
- Columns:
    -	med_id – Internal numeric ID
    -	med_name: Name you entered
    -	dose: Dose description
    -	times_csv: Comma-separated list of times (e.g., 08:00, 20:00)
    -	days – Human-readable days, e.g. Mon Wed Fri
    -	active: 1 for active, 0 for inactive
- Buttons below the table:
    -	Reload list: Reloads rows from med_schedule.csv.
    -	Edit selected: Loads the selected row into the form for editing.
    -	Delete selected: Marks the selected medication as inactive.

### 5.4. Edit an Existing Medication
1. Click a row in Current Medications to select it.
2. Click “Edit selected”.
3. The form at the top will be filled with that medication’s details:
        Name, Dose, Times, Days, Active flag.
4. Change whatever you need:
        Adjust times, change weekdays, rename the medication, etc.
5. Click “Save Medication”.
6. The app updates the existing entry instead of creating a new one.

### 5.5. Delete (Deactivate) a Medication
1. Click a row in Current Medications.
2. Click “Delete selected”.
3. Confirm when asked.
4. The app sets active = 0 for that med_id and rewrites med_schedule.csv.
5. The medication no longer appears in the weekly grid and is no longer used for reminders.

Note: The record is not physically removed; it is just marked inactive.

### 5.6. Reminders and Snooze Popups
While the app is running:

-	It checks periodically for doses scheduled for today.
-	If a dose is due (within about 1 minute of the scheduled time) and has not been logged yet, a popup appears, and popup options:
    - Take
      -	Logs the action as "taken" in dose_log.csv.
      -	Updates the weekly grid cell to green.
  
    -	Snooze
        -	Lets you choose a snooze time (5–60 minutes) from a dropdown.
        -	Adds an entry to snoozes.csv.
        -	Logs the action as "snoozed".
        -	Moves the dose to a new time later today.

 	  -	Skip
        -	Logs the action as "skipped" in dose_log.csv.
        -	Updates the weekly grid cell to red.

The grid is refreshed so you can see snoozed/ taken / skipped status.

### 5.7. Summary Tab
The Summary tab shows a simple bar chart of actions from the last 7 days:
Counts of:
    
-	taken
-	snoozed
-	skipped

If matplotlib is not installed, you will see a message that the chart is disabled.

## 6.	Errors and Troubleshooting Here are some common issues and how to fix them.
### 6.1. Module Not Found Error: 
-	No module named 'pandas' or 'matplotlib' 
-	Cause: Required packages are not installed. Fix: pip install pandas matplotlib Then run: python run_app.py

### 6.2. Window does not appear / Tkinter error 
-	On most Windows installs, Tkinter is included. 
-	If you see an error mentioning tkinter or TclError: Make sure you are using the official Python installer from python.org. 
-	Reinstall or modify your Python install and make sure “tk/tkinter” is included.

### 6.3. Nothing happens when I run python run_app.py 
-	Make sure you are in the correct folder (the one that contains run_app.py). 
-	Try: python run_app.py or py run_app.py depending on your Python setup.

### 6.4. The grid is empty 
Check that: 
-	You have added at least one medication on the Add/Edit tab. 
-	The medication is marked Active. 
-	Today’s day of the week is included in the Days checkboxes. 
-	The times you added are in the future (or at least today) so you can notice them. 
-	Click Refresh on the Pillbox tab to force an update.

## 7.	Limitations and Notes
-	The app is designed for one user and stores everything in CSV files in the project folder. 
-	The window size is fixed to keep layout simple. 
-	Reminders only work while the app is running; there is no background service. 
-	There is no password or user account system. 
-	Editing and deactivating medications works by updating the CSV file; this could be corrupted if edited manually. 
-	More technical limitations, bug lists, and future ideas are documented in docs/DEVELOPER.md and bugs.md.

