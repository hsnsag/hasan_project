# PillBox v2 – Developer Guide

This document is for **developers** who want to understand, maintain, or extend the PillBox application.  
End users should start with the main `ReadMe.md` user guide.


## 1. Overview

PillBox is a small **Tkinter**-based desktop application that helps users manage daily medications:

- Add medications with:
  - name
  - dose
  - one or more times per day
  - selected days of the week
  - active / inactive flag
- Show a **weekly pillbox grid** (Mon–Sun × AM / Noon / PM / Bed).
- Trigger “dose due” popups that allow users to:
  - Take
  - Snooze
  - Skip
- Log all actions to CSV files.
- Show a **7-day summary** of taken / snoozed / skipped actions.

Everything is built around a single main script:

- `run_app.py` – entry point and main GUI logic.

Data is stored in CSV files in the project root:

- `med_schedule.csv`
- `dose_log.csv`
- `snoozes.csv`



## 2. Implemented vs. Planned Features
### 2.1 Implemented

- **Medication schedule management**
  - Add new meds with multiple times per day.
  - Select active days via checkboxes (Mon–Sun).
  - Mark meds active/inactive.
  - Edit existing meds from the “Current Medications” table.
  - Soft-delete meds (mark inactive) via “Delete selected”.

- **Weekly pillbox view**
  - Mon–Sun columns.
  - AM / Noon / PM / Bed rows.
  - Each cell can display med name, dose, time.
  - Color-coded for taken / skipped / snoozed / due soon / idle.

- **Reminders & Snoozes**
  - Scheduler loop checks for doses due today.
  - Popup for doses within ±60 seconds.
  - Snooze durations via dropdown (5–60 minutes).
  - Snoozed times override today’s schedule.
  - Snoozes persisted in `snoozes.csv` with basic cleanup.

- **Logging and Summary**
  - All actions logged to `dose_log.csv`.
  - 7-day summary chart using matplotlib (if installed).
  - Chart shows counts of taken / snoozed / skipped.

- **User-facing documentation**
  - `ReadMe.md` as a user guide.

### 2.2 Not (fully) implemented

- Multiple users / profiles.
- Background reminders outside the app (only works while app is open).
- Time-travel / simulation mode for testing.
- Automatic nightly cleanup of snoozes (currently manual/limited).
- Advanced error handling and log files (console-based print for now).


## 3. Install, Deployment, Admin Notes

Assumptions:

- Developer can run using this statment :

  ```bash
  python run_app.py

3.1 Dependencies
Python 3.10+ (tested on 3.13).
Required packages:
pip install pandas matplotlib
tkinter is typically included on Windows Python installs (official python.org installer).

3.2 Project Structure (developer view)
Typical structure:

hasan_project/
├─ run_app.py              # Main app (entry point)
├─ med_schedule.csv        # Schedule data
├─ dose_log.csv            # Action logs
├─ snoozes.csv             # Snoozed doses
├─ ReadMe.md               # User guide
├─ LICENSE
├─ bugs.md                 # Known bugs and issues (developer notes)
├─ docs/
│  ├─ DEVELOPER.md         # This developer guide
│  ├─ <project-spec>.pdf
│  ├─ <review-docs>.pdf

Entry point: run_app.py (a future refactor could rename to main.py, but run_app.py is explicit enough).

3.3 Data and admin considerations
Data files (*.csv) are stored next to run_app.py.
There is no separate config file; everything is hard-coded in constants at the top of run_app.py.
No API keys or external services are used.
No database server is required.
If you deploy this for end users:
Consider moving data files into a dedicated directory (e.g., data/) and updating paths.
Consider a simple installer or shortcut that runs python run_app.py or wraps it with a packaged executable (e.g., PyInstaller), if non-technical users will use it.

## 4. User Flow and Code Walkthrough
This section connects user actions to the relevant code (functions / classes / methods).
### 4.1 High-level user flow
  1.	User starts the app (python run_app.py).
  2.	On start:
	CSV files are ensured.
	Snoozes older than a few days are cleaned.
	Tabs are created: Pillbox, Add/Edit, Summary.
  3.	User typically:
	Goes to Add/Edit to add one or more medications.
	Returns to Pillbox to see the weekly grid.
	Waits for reminders/popups while the app runs.
	Uses Summary tab to see recent actions.

### 4.2 Key modules / classes
Everything lives in run_app.py.

#### 4.2.1 Helper functions (top-level)
*	CSV utilities
	ensure_csv(path, headers)
	read_rows(path)
	append_row(path, headers, row)
	write_all(path, headers, rows)
These functions provide a thin wrapper over csv.DictReader/Writer.
  
*	Schedule helpers
	days_mask_to_names(mask)
Converts '1010100' style masks into day names ("Mon Wed Fri").
	coerce_days_mask_from_bools(day_bools)
Maps list of 7 booleans to string mask.
	is_day_active(mask, d)
Returns whether date d is active for that mask.
	bucket_for_hour(h)
Maps an hour (0–23) to AM/Noon/PM/Bed.
  
*	IDs and logging
	next_med_id(rows)
Scans existing rows to compute the next ID.
	log_action(med_id, sched_dt, action, actual_dt=None)
Appends a log entry to dose_log.csv.
	is_already_logged(med_id, sched_dt)
Used by scheduler to avoid double-popups/logs.

#### 4.2.2 SnoozeManager class
*	File: run_app.py
*	Purpose: Manage all snooze entries in snoozes.csv.
Key methods:
*	__init__(path=SNOOZE_CSV)
Ensures the file exists.
*	add(med_id, scheduled_dt, new_dt)
Called when user snoozes a dose.
Writes (med_id, original scheduled time, new time) to CSV.
*	get_today()
Returns a dictionary mapping (med_id, scheduled_iso) to new_dt (datetime) for snoozes where the new date is today.
This mapping is used in _build_week_schedule() to override times for today.
*	cleanup_old(keep_days=1)
Purges snoozes older than keep_days days (based on new_dt).

#### 4.2.3 PillBoxApp class (Tk root window)
Main responsibilities:
*	Create UI tabs and widgets.
*	Tie together schedule data, snoozes, and logs.
*	Periodically check for due doses.
*	Handle add/edit/delete and popups.
Key methods grouped by tab:

A. Weekly grid (Pillbox tab)
*	_build_grid_tab()
Creates:
	Title label.
	Weekly grid labels (self.grid_labels[(bucket, weekday_index)]).
	Color legend.
	Action buttons (Refresh, Clear old snoozes).
*	_build_week_schedule()
Returns a list of dose dicts:
{
    "med_id": str,
    "med_name": str,
    "dose": str,
    "scheduled_dt": datetime,
    "scheduled_iso": str
}
For the current week (Mon–Sun), applying today’s snoozes from SnoozeManager.get_today().
*	_update_grid_colors()
	Resets all cells to idle.
	Loops over week = _build_week_schedule() and logs from dose_log.csv.
	Applies colors according to action:
	taken → green
	skipped → red
	snoozed → blue (and shows “(snoozed)”)
	due soon today → yellow
	otherwise → gray/normal.
	Relies on bucket_for_hour() and the BUCKETS map.
*	_clear_old_snoozes(keep_days) and _refresh_ui()
	Utility handlers for buttons.

B. Add/Edit tab
*	_build_edit_tab()
Builds the form:
	self.ent_name, self.ent_dose
	Time pickers: self.cb_hour, self.cb_minute, and "Add time" → _add_time_to_list()
	Times list: self.times_listbox and "Remove selected" → _remove_selected_time()
	Day checkboxes: self.day_vars
	Active checkbox: self.var_active
	"Save Medication" → _save_medication()
	Current Medications table: self.tree using a simplified view of schedule.
	"Reload list", "Edit selected", "Delete selected" buttons.

*	_add_time_to_list()
Adds HH:MM from dropdowns to self.current_times, sorted, and repopulates listbox.

*	_remove_selected_time()
Removes a selected time from the list.

*	_reload_schedule_view()
Reads med_schedule.csv and populates the table with human-readable day names.

*	_load_med_into_form(med_row)
Loads a row into the form so user can edit.

*	_edit_selected_med()
	Gets med_id from selected row.
	Finds row in schedule.
	Calls _load_med_into_form.
	Sets self.current_edit_med_id so _save_medication() knows to update, not insert.

*	_delete_selected_med()
	Mark active = "0" in the schedule for that med_id.
	Rewrites the CSV.
	Refreshes table and grid.

*	_save_medication()
	If self.current_edit_med_id is None → new med (compute ID via next_med_id() and append row).
	Else → find row with that med_id, update fields, rewrite entire schedule via write_all().

C. Summary tab
*	_build_summary_tab()
Sets up self.summary_container and a "Refresh summary" button.

*	_draw_summary()
	Reads dose_log.csv, counts actions in last 7 days.
	If matplotlib is available, draws a simple bar chart in self.summary_container.
	Otherwise shows a “chart disabled” label.

D. Scheduler and popups
*	_scheduler_loop()
	Called once at start, then re-schedules itself every 10 seconds.
	Builds week using _build_week_schedule().
	Filters to today’s doses only.
	If any dose is within ±60 seconds of now and not yet logged (is_already_logged()), shows _show_due_popup(item) and breaks (only one popup per pass).
	Always calls _update_grid_colors() afterward.

*	_show_due_popup(item)
	Creates a modal Toplevel window with med name, dose, time.
	Offers buttons:
	do_take() → logs "taken".
	do_snooze() → calls SnoozeManager.add() and logs "snoozed".
	do_skip() → logs "skipped".
	Each handler updates the grid and shows a confirmation messagebox.

## 5. Known Issues
### 5.1 Minor issues (non-breaking)
*	Scheduler resolution
	Checks every 10 seconds; if the app is paused or OS is busy, popups may be slightly delayed.
	Time comparison window (±60 seconds) is a simple heuristic.

*	Fixed window size
	self.geometry("1200x720") is hard-coded.
	On very small screens, widgets may not fully fit.

*	CSV robustness
	CSV parsing ignores malformed rows silently in several places (try/except with bare pass).
	If someone manually edits the CSV incorrectly, it may cause subtle issues.

*	UI refresh logic
	UI updates are sometimes triggered in multiple places (_scheduler_loop, _refresh_ui, after save/delete).
	This is fine for this scale but could be tightened for clarity.

### 5.2 Major issues (breaking or potentially breaking)
*	Single-user assumption
	No support for multiple users or profiles.
	All meds go into one global schedule.

*	No persistent configuration
	No config file for controlling behavior (e.g., grid buckets, snooze window).
	All constants are in the code.

*	No unit tests
	There is no automated test suite.
	Changes must be tested manually by running the GUI.

### 5.3 Computational inefficiencies (optional note)
*	For the current scale (a few meds), the app is fine.
*	Inefficiencies:
	_build_week_schedule() is called often and re-parses the CSV each time.
	Logs and schedules are always read from disk instead of being cached.

*	For a realistic deployment with many entries, consider:
	In-memory caching with explicit invalidation on change.
	Using a lightweight database (e.g., SQLite) instead of CSV.

## 6. Future Work
Some directions for future development:
1.	Multi-user support
	Add a concept of “profile” or “patient”.
	Store a user_id column in CSV (or new DB schema).
	Add UI to switch users.

2.	Time-travel / simulation mode
	Allow developer to fake “current time” for testing.
	Could be a hidden developer control in the Summary tab or a CLI flag.

3.	Editing log entries
	Allow the user (or admin) to correct mistaken actions (e.g., clicked “skipped” instead of “taken”).

4.	Config file
	Move constants (file paths, buckets, etc.) into a simple config module or JSON file.

5.	Improved error handling
	Introduce a lightweight logging framework (logging module) instead of print().
	Surface serious errors via a dedicated error dialog.

6.	Packaging / deployment
	Wrap the app as a pip package or use PyInstaller to build a standalone executable.

## 7. Ongoing Development & Maintenance
If this project continues beyond the course, here are some suggestions:
*	Version control discipline
	Keep run_app.py as the main entry point.
	If the code grows, consider splitting into modules: model.py, view.py, controller.py, etc.

*	Unit tests
	Add tests for:
	days_mask_to_names, coerce_days_mask_from_bools.
	next_med_id.
	SnoozeManager behavior (especially get_today and cleanup_old).
	Use plain unittest or pytest.

*	Extensibility guidelines
	New UI features should ideally:
	Reuse existing helpers for CSV I/O.
	Respect the current data model: med_schedule.csv, dose_log.csv, snoozes.csv.
	When adding new fields, keep CSV headers and docstrings in sync.
