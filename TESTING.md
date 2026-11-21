# OGLOS: testing and walkthrough guide

Everything you need to test the prototype: where to open it, every login, and step-by-step walkthroughs for each
role with what you should see. All data is **made up** (the "Sunrise Multispeciality" demo hospital).

> These demo logins are fixed and public on purpose. They only exist in demo data, and the demo seed refuses to
> run in production. Never reuse them for a real hospital.

---

## 1. Open the app

Start it first if it isn't running (see `README.md`, section 3). The quickest way:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run-render-local.ps1
```

| App | Who | Render version (recommended) | Development version |
|---|---|---|---|
| **Admin site** | MD, admin, supervisor | **http://localhost:10000** | http://localhost:5173 |
| **Staff app** | housekeeping staff | **http://localhost:10000/staff/** | http://localhost:5174 |

Both versions have the same logins below.

**Tip:** to see the staff app as on a phone, press **F12** in Chrome, click the phone icon (top left of the panel),
and pick a phone size. Use a **private window** for a second person, so the two sign-ins don't replace each other.

---

## 2. All logins

**Hospital code (everyone): `SUNRISE`**
**Password (MD, admin, supervisor): `sunrise-demo-2026`**

### Admin site (http://localhost:10000)

| Role | Email | Password | 6-digit code | Can do |
|---|---|---|---|---|
| **MD** | `md@sunrise.example.org` | `sunrise-demo-2026` | `python scripts/demo-code.py md` | see everything: Today dashboard, attendance; read-only |
| **Admin** | `admin@sunrise.example.org` | `sunrise-demo-2026` | `python scripts/demo-code.py admin` | everything incl. setup: staff, desks, roster, daily tasks, entrance QR |
| **Supervisor** | `supervisor@sunrise.example.org` | `sunrise-demo-2026` | not needed | Housekeeping only: approvals, flags, attendance, roster |

**The 6-digit code** changes every 30 seconds. Run the command in PowerShell from the project folder, e.g.
`python scripts/demo-code.py md` → `MD code: 460157 (valid for 16 more seconds)`, and type it straight away.
To use a phone authenticator app instead (Google/Microsoft Authenticator → *enter a setup key*):

| Account | Authenticator secret |
|---|---|
| MD | `OGLOSMDSUNRISEDEMOKEYAAAAAAAAAAA` |
| Admin | `OGLOSADMINSUNRISEDEMOKEYAAAAAAAA` |

### Staff app (http://localhost:10000/staff/)

**Way 1, shared phone + PIN (no email needed):**
1. Tap **Use the shared phone and PIN**.
2. The first time on this browser, it asks to set up the phone: Hospital code `SUNRISE`, Device key
   **`SUNRISE-DEMO-SHARED-PHONE-01`** → *Continue*. (Remembered after that.)
3. Employee code from the table below, PIN **`4826`** → *Sign in*.

**Way 2, own email + code:** enter the email from the table → *Send sign-in code*. Codes aren't emailed in the
prototype; read the code from the server log:

```powershell
docker logs oglos-render-test --tail 15        # Render version
```
(Development version: it appears in the window running the server.) Look for `Your OGLOS sign-in code is ……`.

| Employee code | Name | Desk today (morning shift) | Email | App language |
|---|---|---|---|---|
| `HK-101` | Lakshmi R | Housekeeping Ground (HK-G) | `hk-101@sunrise.example.org` | Kannada |
| `HK-102` | Manjunath S | Housekeeping Floor 1 (HK-1) | `hk-102@sunrise.example.org` | Kannada |
| `HK-103` | Shabana B | Housekeeping Floor 2 (HK-2) | `hk-103@sunrise.example.org` | Hindi |
| `HK-104` | Ravi Kumar | Housekeeping Floor 3 (HK-3) | `hk-104@sunrise.example.org` | Kannada |
| `HK-105` | Geetha M | Housekeeping Floor 4 (HK-4) | `hk-105@sunrise.example.org` | Kannada |
| `HK-106` | Anil Yadav | Housekeeping Basement (HK-B1) | `hk-106@sunrise.example.org` | Hindi |

All PINs are `4826`. Each person opens in their own language; switch with **English / ಕನ್ನಡ / हिन्दी** on the sign-in
screen or the notice screen.

> **MD and admin can't use the staff app's email code.** For safety, high-access accounts must sign in on the
> admin site with password + 6-digit code. The staff app still says "We sent a code" (so outsiders can't tell which
> emails exist), but nothing is sent.

---

## 3. What's in the demo hospital

| Thing | Demo data |
|---|---|
| Branches | Jayanagar (main), Whitefield |
| Building | Main block, floors B1, G, 1, 2, 3, 4 |
| Desks | HK-B1, HK-G, HK-1 … HK-4 (housekeeping), W3-NS Ward 3 Nurse Station |
| Daily tasks per desk | Washroom cleaning at 08:00, 11:00, 14:00, 17:00 (45 min to finish); Corridor at 09:30, 15:30 (60 min) |
| Checklists | Washroom: floor mopped, toilets disinfected, soap refilled, bin emptied (with pictures) |
| Shifts | Morning 07–15, Evening 15–23, Night 23–07 |
| Already happened today | some tasks approved, some waiting for approval, one sent back for rework, some overdue, a few fake-work flags, 5 staff checked in |

Floor 3 washroom tasks have a "should take at least 6 minutes" rule, so finishing one quickly raises a
**"Finished much faster than expected"** flag. Good for testing flags.

---

## 4. Walkthroughs

Tick each box as you go. **Expected** is what you should see.

### A. Staff: do a cleaning task (5 min)

- [ ] Open the staff app, sign in as **`HK-101` / `4826`** (shared phone, see section 2).
- [ ] **Expected:** the *staff data notice* (what is collected, why, how long). Tap **I have read this**.
      It only appears the first time and again when the notice changes.
- [ ] **Expected:** home screen with your name, your desk (*Housekeeping Ground*), check-in box, and *My tasks today*.
      Late tasks are at the top with a red stripe and **Late by …**.
- [ ] Open a task with a dashed circle (due) or red triangle (overdue). Tap **Start task**.
- [ ] Tap **Take the before photo**. On a laptop pick any JPG/PNG; on a phone the camera opens.
      **Expected:** thumbnail + *Photo saved* with the time.
- [ ] Try **Send for approval** now. **Expected:** disabled until the checklist and after photo are done.
- [ ] Tick every checklist row (big rows with pictures).
- [ ] **Take the after photo**. (Trying the after photo before the before photo is refused.)
- [ ] **Send for approval**. **Expected:** back on home; the task shows **Awaiting approval** (purple).

### B. Supervisor: approve or send back (3 min)

- [ ] In a private window, open the admin site and sign in as **supervisor** (no code needed).
- [ ] Click **Approvals**. **Expected:** a queue on the left; the selected task shows **Before | After photos** side by
      side, each stamped with desk, time and staff code, plus the checklist ticks and any flags.
- [ ] Click **Approve**. **Expected:** "Approved", next task opens.
- [ ] On another task click **Send back**, type a reason (e.g. *Corner still wet*), confirm.
- [ ] Back in the staff app (as that worker): **Expected:** the task returns with your note and needs **new**
      photos and a fresh checklist (old photos don't count for rework).

### C. Supervisor: fake-work flags (2 min)

- [ ] Admin site → **Flags**. **Expected:** hints like *Finished much faster than expected* or *Same photo used before*,
      with "Flags are hints, not proof".
- [ ] Click **Open task** to review it, then **Dismiss** or **Confirm problem**.
- [ ] To create a new flag: as **`HK-104`** (Floor 3), start a washroom task and send it within a minute.

### D. MD: the dashboard (2 min)

- [ ] Sign in to the admin site as **MD**: email, password, then the code from `python scripts/demo-code.py md`.
- [ ] **Today** shows a plain sentence such as *"15 of 36 tasks done today"* with chips for overdue, awaiting approval and flags.
- [ ] **Building, by floor**: floors stacked 4 → B1, each desk a tile coloured by its worst status (red = overdue,
      purple = awaiting approval, green = all done). Click a tile: that desk's tasks appear on the right.
- [ ] **Attendance**: who checked in today and when.
- [ ] Note the MD has no setup menus (read-only).

### E. Admin: set up a new desk, person and daily task (5 min)

- [ ] Sign in as **admin** (code: `python scripts/demo-code.py admin`).
- [ ] **Desks** → add *Housekeeping Floor 5*, code `HK-5`, branch Jayanagar, floor 4, department Housekeeping.
- [ ] **Staff** → add a person: code `HK-107`, name *Test Worker*, role *Staff*, department Housekeeping, PIN `5917`.
- [ ] **Task templates** → add a daily task for `HK-5`: name *Lift lobby cleaning*, times `10:00, 16:00`,
      checklist lines like `Floor mopped | ನೆಲ ಒರೆಸಲಾಗಿದೆ | फ़र्श पोछा`.
- [ ] **Roster** → for today's Morning shift, assign *Test Worker* to `HK-5`.
- [ ] Staff app: sign in as **`HK-107` / `5917`**. **Expected:** the new desk and its two tasks.

### F. Entrance QR check-in (3 min)

- [ ] Admin → **Entrance QR**: a printable code for the branch entrance. (*Replace code* invalidates the old print.)
- [ ] Staff app → **Check in** opens the camera. Point it at the QR. On a laptop, show the QR on your phone screen
      (or open the admin site on the phone) and hold it to the webcam.
- [ ] **Expected:** a big green tick and *Checked in at HH:MM*; the home screen then offers **Check out**.
- [ ] Admin/supervisor → **Attendance** shows the check-in. No GPS or face data is collected.

### G. Languages (1 min)

- [ ] Staff app sign-in → switch **ಕನ್ನಡ** / **हिन्दी**. Every label, status and error changes language.
- [ ] Admin site → language menu (top right).
- [ ] Sign in as `HK-103` (Hindi) or `HK-101` (Kannada) on a fresh browser: the app opens in their language.

### H. Security checks (optional, 3 min)

- [ ] Staff app, email login with `md@sunrise.example.org` → says "code sent" but **no code** appears in the log.
- [ ] Wrong PIN 5 times for **`HK-106`** → *Too many wrong tries*; the account locks for 15 minutes.
      (Use HK-106 so your main demo user stays usable.)
- [ ] Admin site, wrong password → generic *Email or password is wrong* (doesn't reveal which part).

---

## 5. Reset the demo

Testing changes the data (approvals, check-ins, locks). To start clean:

```powershell
# Render version
powershell -ExecutionPolicy Bypass -File scripts\run-render-local.ps1 -Fresh

# Development version
$env:SEED_RESET=1; powershell -ExecutionPolicy Bypass -File scripts\dev.ps1 seed; Remove-Item Env:SEED_RESET
```

The logins stay exactly the same after a reset.

## 6. Good to know

- **Times are India time (IST).** Before ~09:00 the demo still shows a played-out morning (tasks done early).
- **Locked out after testing wrong PINs/codes?** Wait 15 minutes or reset the demo.
- **First page load says *Loading…*?** Refresh after a few seconds.
- **The 6-digit code was rejected?** It lasts 30 seconds; run the command again.
- **Not built yet:** offline mode, "Going out" desk cover, leave, reports export, a Devices screen in the admin site.
- **Kannada/Hindi text** is a first draft awaiting a native-speaker check.
- Problems starting the app: `README.md` section 8.
