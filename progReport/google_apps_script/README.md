# Emailing progress reports to parents (Google Sheets + Apps Script)

Sends each student's progress-report PDF to their parent(s), matching on
the student id in the PDF's filename. One email per student -- if a
student has two parent addresses, both get the same email (parent1 as
To, parent2 as Cc).

## Setup

1. **Upload the PDFs to a Drive folder.** Drag the contents of your
   Python project's `output/` folder into a Google Drive folder
   dedicated to this (e.g. "Progress Reports - MP2 2026"). The files
   must keep the `studentId_LastName_FirstName.pdf` naming the Python
   script already produces -- that's what this matches on.

2. **Get the folder's ID.** Open the folder in Drive; the ID is the
   part of the URL after `/folders/`:
   `https://drive.google.com/drive/folders/`**`1AbCdEfGhIjKlmNoPQrs`**

3. **Create a Google Sheet** (or add a tab to an existing one) named
   exactly `Reports`, with a header row:

   | student_id | student_name | parent1_email | parent2_email |
   |---|---|---|---|

   `parent2_email` is optional per row (leave blank for a single
   parent). `student_name` is optional too, but makes the email
   greeting and the Reports tab itself easier to read -- otherwise the
   email just refers to "student {id}". Don't add a `status` column
   yourself; the script creates one the first time you run it and
   writes to it (see below).

   You can start from `parent_emails_template.csv` in this folder:
   File -> Import -> Upload, choose "Replace current sheet", then
   rename the tab to `Reports`.

4. **Open the Apps Script editor.** In the Sheet: Extensions -> Apps
   Script. Delete the default empty `Code.gs` content and paste in this
   folder's `Code.gs`.

5. **Fill in the `CONFIG` block** at the top of `Code.gs`:
   - `DRIVE_FOLDER_ID`: the folder ID from step 2.
   - `SCHOOL_NAME`, `EMAIL_SUBJECT`, `EMAIL_BODY`: edit to taste.
     `{{studentName}}` and `{{schoolName}}` get filled in per email.
   - `SHEET_NAME`: only change this if you named your tab something
     other than `Reports`.

   Save (Ctrl/Cmd+S).

6. **Reload the spreadsheet** (close and reopen the tab, or just
   refresh). A **Progress Reports** menu appears next to Extensions/Help.

7. **First run: authorize.** Click Progress Reports -> Preview (dry
   run). Google will prompt you to authorize the script (it needs
   permission to read the Drive folder and, later, send Gmail on your
   behalf). Review and accept -- this is normal for any script you
   write yourself; it's not published or reviewed by Google, so you'll
   see an "unverified app" warning. Click "Advanced" -> "Go to
   (project name)" to proceed.

## Using it

- **Progress Reports -> Preview (dry run)**: doesn't send anything.
  Writes to each row's `status` column what *would* happen -- who it'd
  email and which PDF it found, or an error (missing email, no PDF
  found for that student id, etc.). Always run this first, and fix any
  `ERROR:` rows before sending for real.

- **Progress Reports -> Send Reports**: shows a confirmation dialog
  with the exact count of emails about to go out, then sends. Rows
  already marked `SENT ...` are automatically skipped, so it's safe to
  run this again later (e.g. after adding a few late rows) without
  double-emailing anyone.

- **Progress Reports -> Reset status column**: clears every row's
  status so the next Send Reports run re-emails everyone. Use this at
  the start of a new reporting period, not to retry a few failed rows
  -- for those, just fix that row's data and re-run Send Reports; only
  non-`SENT` rows get processed anyway.

## Notes and limits

- **Sending quota**: a personal Gmail account can send about 100
  emails/day through Apps Script; a Google Workspace (school Google
  account) can send up to 1,500/day. The script checks your remaining
  quota before a real send and warns you if there isn't enough left
  for the whole batch, rather than sending half and failing partway
  through.
- **Matching logic**: a PDF is matched to a sheet row by the digits
  before the first underscore in its filename. If your Drive folder
  ever has two PDFs for the same student id (e.g. you re-generated one
  report), the more recently modified file wins.
- **This sends real email to real people.** Always run Preview first,
  and consider testing end-to-end with one row pointing at your own
  email address before running it against your full parent list.
