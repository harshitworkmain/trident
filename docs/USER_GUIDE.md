# TRIDENT user guide

TRIDENT coordinates flood and water rescue in Chennai. It has four parts:

- a public web page where anyone can ask for rescue and follow the request
- a staff console (the control room) for dispatchers, responders, viewers and admins
- wearable bands that report vital signs and have an SOS button
- underwater ROV units that can be sent to a request and driven from the console

This guide explains how to use each part. It is written for the people who use the system, not for
developers. To install and start TRIDENT, see [GETTING_STARTED.md](GETTING_STARTED.md).

> **The wearable states are decision support, not a medical device.** The band and its models have
> not been clinically validated. A state such as "Cardiac arrest" means "the signals match this
> pattern; send someone to check", not a diagnosis. A STABLE band does not prove a person is safe.
> Always confirm by radio, phone or in person.

## Contents

1. [Quick reference](#1-quick-reference)
2. [Members of the public: asking for help](#2-members-of-the-public-asking-for-help)
3. [Wearers: using the band](#3-wearers-using-the-band)
4. [Staff: signing in and finding your way](#4-staff-signing-in-and-finding-your-way)
5. [Dispatchers: handling requests](#5-dispatchers-handling-requests)
6. [Alerts](#6-alerts)
7. [Responders and viewers](#7-responders-and-viewers)
8. [Wearables pages](#8-wearables-pages)
9. [ROV units and missions](#9-rov-units-and-missions)
10. [ROV station operator](#10-rov-station-operator)
11. [Weather](#11-weather)
12. [Analytics](#12-analytics)
13. [Admin](#13-admin)
14. [When things go wrong](#14-when-things-go-wrong)
15. [Known limitations in this version](#15-known-limitations-in-this-version)

---

## 1. Quick reference

### Roles and permissions

Staff accounts have one of four roles. The console hides or disables what your role cannot do,
but the server makes the final decision: if it refuses, you see an error message.

| Action | admin | dispatcher | responder | viewer |
|---|:-:|:-:|:-:|:-:|
| See every page except Admin | yes | yes | yes | yes |
| Assign a team to a request; move a team between requests | yes | yes | – | – |
| Change the status of a request | yes | yes | only requests assigned to their own team | – |
| Add a note to a request | yes | yes | yes | – |
| Confirm or remove a wearable link on a request | yes | yes | – | – |
| Acknowledge or resolve an alert | yes | yes | yes | – |
| Send a command to a wearable | yes | yes | – | – |
| Deploy, recall, reset an ROV; take manual control | yes | yes | – | – |
| Take over an ROV that someone else is driving | yes | – | – | – |
| STOP an ROV | yes | yes | yes | – |
| Admin page: users, devices, teams, SMS test | yes | – | – | – |
| Issue an ROV bridge key | yes | – | – | – |

### Request (SOS) statuses

| Status | Meaning | How it is reached |
|---|---|---|
| Pending | Received, not yet checked | Created by the web form, SMS or a band |
| Triaged | Checked by a dispatcher, no team yet | Dispatcher marks it triaged; also where a request returns when its team is moved away |
| Assigned | A team has been given the request | Dispatcher assigns a team, or automatic dispatch does |
| En route | The team is on its way | Dispatcher or the assigned team |
| On scene | The team has arrived | Dispatcher or the assigned team |
| Resolved | Rescue completed (closed) | Dispatcher or the assigned team |
| Cancelled | Closed without a rescue: duplicate, people already safe, false request | Dispatcher or the assigned team, from any open status |

Statuses move forward one step at a time: pending → triaged → assigned → en route → on scene →
resolved. Any open request can be cancelled. Resolved and cancelled requests cannot be reopened.

### Priorities

Every request gets a score from 0 to 100 and a priority from P1 to P5. **P1 is the most urgent.**

| Priority | Score | Typical example |
|---|---|---|
| P1 | 60 or more | Several injured people with a medical need, or a band in a critical state |
| P2 | 45–59 | A band SOS button press; flooding with an injured, elderly person |
| P3 | 30–44 | Flooding with several people and water running low |
| P4 | 15–29 | Flooding, everyone well, supplies adequate |
| P5 | under 15 | Coastal erosion or "other" with no added risk factors |

What raises the score (each factor is capped so no single answer dominates):

- the emergency type (tsunami and dam breach highest, then flood and medical, then storm and rising water)
- the number of injured people, and the number of people to rescue
- vulnerable people: medical need, pregnancy, disability, elderly, children
- drinking water and food running out
- age 70 or over, or 5 or under (web form only)
- a band SOS button press (+40, so at least P2)
- a **confirmed** linked wearable: +30 in a critical state, +5 in the advisory state, +3 if it is offline
- waiting time: +2 for every 5 minutes without a team, up to +20 ("waiting N min")

The score is recalculated every 10 seconds, so a request can move up while it waits. The reasons
are listed on each request ("Why this priority").

### Alert levels

| Level | Shown as | What happens |
|---|---|---|
| none | green | Nothing; the band is STABLE or its state is unknown |
| advisory | amber | Shown on the wearable; no alert is opened. Only ELEVATED_STRESS is advisory |
| critical | red | An alert opens in the Alerts panel, the band beeps, and a linked request is re-scored |

### Wearable states

"Basis" says how the state is detected (see
[WEARABLE_ML_ARCHITECTURE.md](WEARABLE_ML_ARCHITECTURE.md), section 9): **ml+rule** needs a
machine-learning model output and fixed rules; **rule** uses thresholds only; **ml** is a model
alone. When two states apply, the more severe one is shown.

| State (console label) | Level | Basis | What it suggests | What to do |
|---|---|---|---|---|
| STABLE (Stable) | none | – | No pattern of concern | Nothing. It does not prove the person is safe |
| ELEVATED_STRESS (Elevated stress) | advisory | ml | Sustained high stress while at rest. The stress model is known not to transfer well to new people | Keep an eye on it; never act on it alone |
| CONCUSSIVE_STASIS (Concussive stasis) | critical | ml+rule | A fall, then no movement for 30 s or more | Possible head injury or unconsciousness; contact or send help |
| CRUSH_ENTRAPMENT (Crush / entrapment) | critical | ml+rule | Not moving, heart rate well above the person's baseline, after an impact or 5 min of stillness | Possibly trapped under debris; send a team |
| CARDIAC_ARREST (Cardiac arrest) | critical | ml+rule | Sensor on the skin but no heartbeat for 10 s and no movement, or an extreme rhythm | Highest urgency; send help at once and confirm by any means |
| ASPIRATION_HYPOXIA (Aspiration / hypoxia) | critical | **rule** | Blood oxygen below 90 % for 15 s or falling fast; worse if submerged | Possible drowning or breathing problem |
| HEMORRHAGIC_SHOCK (Haemorrhagic shock) | critical | ml+rule | Fast, rising heart rate at rest, cooling skin, high sweat response | Possible serious bleeding |
| HYPOTHERMIA_RISK (Hypothermia risk) | critical | **rule** | Skin below 32 °C and falling, with a slow pulse or wet band | Person is getting cold; get them out of the water and warm |
| LOST_CONTACT (Lost contact) | critical | **rule** (alert only) | The band was not STABLE and then sent nothing for 30 s | Treat as an emergency: dead battery, submerged, crushed or out of range. Go to the last position |
| SOS_BUTTON (SOS button) | critical | – (alert only) | The wearer pressed the SOS button | A person is asking for help; a request was created automatically |
| UNKNOWN | none | – | The server has no models loaded, so it cannot assess the band | Vital signs still display; ask the admin to check the server |

Notes:

- LOST_CONTACT and SOS_BUTTON are alert types, not band states; they appear in the Alerts panel.
- A band whose finger sensor slips or whose battery is low is flagged as a sensor fault. Heart
  rules are suppressed while that lasts, so a cardiac state is not shown from bad readings.

### Keyboard shortcuts (staff console)

Press **?** on any staff page to show this list. Single-key shortcuts do nothing while you are
typing in a field, while a modifier key (Ctrl, Alt, Cmd) is held, or while a dialog is open.

| Key | Action |
|---|---|
| ? | Show the shortcut list |
| 1 – 7 | Go to Operations, Wearables, ROV missions, Weather, Analytics, ROV units, Admin (7 for admins only) |
| / | Jump to the SOS queue search box (Operations) |
| j / k | Select the next / previous request in the queue |
| Enter | Open the selected request |
| a | Acknowledge the oldest open alert |
| m | Show or hide the map (Operations) |
| Esc | Close a dialog; in the queue search box, clear the search |
| Ctrl+Enter (Cmd+Enter) | Add the note you are typing (request page) |
| W A S D | Drive an ROV forward, left, backward, right (mission panel focused, you have manual control) |
| R / F | ROV up / down |
| L | ROV lights on or off |
| Space | Emergency STOP of the ROV you are driving |
| Left / Right arrows | Previous / next tab (Analytics) |

---

## 2. Members of the public: asking for help

You do not need an account. Open the TRIDENT site and choose **Request help**. If you can make a
phone call, the page also lists **112** (national emergency), **1070** (Tamil Nadu State Emergency
Operation Centre) and **1913** (Greater Chennai Corporation).

### How to send a request on the website

The form has four short steps. Your answers are saved on your phone as you type, so you can close
the page and come back. "Start over" clears them.

1. **What and where.** Choose what is happening (flooding, water rising, medical, storm damage,
   dam or lake breach, tsunami, coastal erosion, something else). Press **Use my location** and
   allow location access, which is the fastest way for a boat to find you. Add an address and a
   landmark if you can. You need either your location or an address. The pincode is optional.
2. **Who is there.** How many people need rescue, how many are injured, and whether anyone is
   elderly, a child under 12, pregnant, unable to walk or climb, or needs medicine, oxygen or
   dialysis. These raise the priority.
3. **Food and water.** How much drinking water and food is left, and anything else the team
   should know (which floor, how to reach the building, pets, medicines).
4. **Your contact.** A name, a 10-digit mobile number the team can call, and optionally your age
   and email. If you were given a TRIDENT wristband, type its ID (for example `TRD-W00`).

Check the summary and press **Send request for help**.

On the confirmation screen you get:

- a **reference** such as `SOS-7K2Q9X`: write it down or take a screenshot
- a **tracking link** (copy it, or press **Open tracking page**)
- the **priority** your request was given (P1 is most urgent, P5 least)

Then stay where you said you are, keep your phone on and charged, and signal from a terrace or
window. If things get worse, send a new request or call 112.

### How to send a request with a weak or no connection

The top of the page shows **Online**, **Offline**, or how many requests are waiting to send.

- **Offline when you press Send:** the request is saved on your phone and the page says "Saved on
  this phone". It is sent automatically when a connection returns; the page retries every
  30 seconds and as soon as the phone reconnects. Some browsers can send it even after you close
  the page. **Try now** forces an attempt.
- **Sending twice is safe.** A saved request keeps the same identity, so retries never create a
  second request.
- **If the server refuses it** (for example a field it does not accept), the page says so; press
  **Edit and send again**.
- The site works offline once you have opened it at least once with a connection.

### How to send a request by SMS

An SMS often gets through when mobile data does not. When the control room has an SMS number
configured, the form shows **Send by SMS instead** while you are offline. It opens your messages
app with the text already written. The number is remembered from your last visit with a
connection, so open the site once while you still have data.

You can also type the message yourself. The format is:

```
SOS <lat>,<lng> P<people> I<injured> T<type> <note>
```

| Part | Meaning | Example |
|---|---|---|
| `SOS` | Start of the message | `SOS` |
| `<lat>,<lng>` | Your position in decimal degrees (optional but very helpful) | `13.0120,80.2410` |
| `P<n>` | People who need rescue | `P3` |
| `I<n>` | Of them, injured | `I1` |
| `T<type>` | `flood`, `water-level-rising`, `medical`, `storm`, `dam-breach`, `tsunami`, `coastal-erosion` or `other` | `Tflood` |
| note | Address, landmark, and words such as elderly, child, pregnant, wheelchair, bleeding, diabetic | `elderly, ground floor flooded` |

Example: `SOS 13.0120,80.2410 P3 I1 Tflood elderly, ground floor flooded`

Every part except `SOS` is optional, and spacing and capital letters do not matter
(`sos p 2 i 0 storm near anna nagar bus depot` also works). Keep it to 160 characters. You get a
reply with your reference, priority and a tracking link; if you did not send a position, the reply
asks for one.

### How to track a request

- Open the tracking link from the confirmation screen or SMS reply, or
- on the home page, enter the **reference number** and the **tracking code** under "Track a request".
  The home page also shows a **Track SOS-…** button for the last request sent from that phone.

The tracking page shows the current status in plain words, the team name once one is assigned,
and the time of each step. It refreshes every 30 seconds. "Closed by the control room" means the
request was cancelled, usually because it was a duplicate or the people were already safe.

---

## 3. Wearers: using the band

The band measures heart rate, blood oxygen, skin temperature, sweat response, movement, water
contact and position, and sends them to the control room every 1.5 seconds. Wear it snugly so the
sensor on the underside touches the skin. Keep it charged.

### How to call for help with the band

Use the recessed **SOS button**:

- **hold it for 1.5 seconds**, or
- **press it 3 times within 2 seconds**.

The band beeps twice at once. It keeps sending until the control room confirms, with a short beep
every 10 seconds while it is still trying. When the control room has received it, you hear **one
long beep** (about 1 second) and the reminders stop. A request is created automatically with your
band's position, at priority P2 or higher, and the control room sees a red SOS alert.

If there is no network, the band keeps trying (at least every 3 seconds) and sends as soon as it
reconnects.

### How to cancel an accidental SOS

Press and **hold the button for 5 seconds** (a new press, after the SOS was raised). You hear two
longer beeps. The control room sees that you cancelled, but **the request stays open until a
dispatcher checks on you**, because a cancel can also come from someone who is no longer able to
ask. Short presses while an SOS is active are ignored, and holding on after raising does not cancel.

### What the beeps mean

| Sound | Meaning |
|---|---|
| 2 short beeps | Your SOS was raised and is being sent |
| 1 very short beep every 10 s | Your SOS is still being sent (not yet confirmed) |
| 1 long beep (0.8 s) | The control room received your SOS |
| 2 longer beeps (0.4 s each) | Your SOS cancel was registered |
| 3 short beeps every 2 s, repeating | The control room's system rates your readings as critical. Stay still if you can; help is being alerted |
| Continuous tone | The band detected a fall, or you left your permitted area (geofence). It stops when staff reset the fall or you return inside the area |
| Continuous tone for a set time | Staff sent a "buzz" to get your attention |

The band also has a local status page at `http://<band-ip>/` on the same Wi-Fi network. Its SOS
line shows `none`, `sending`, `received SOS-…` or `cancelled`.

---

## 4. Staff: signing in and finding your way

### How to sign in

Go to **Staff sign-in** (`/login`) and enter the username and password your admin gave you. Your
session renews itself while you use the console; after 7 days without use you must sign in again.
On a shared computer, always press **Sign out** (top right). If an admin
deactivates your account or changes your role, your live connection is closed within 30 seconds.

### The layout

- **Left menu:** Operations (1), Wearables (2), ROV missions (3), Weather (4), Analytics (5),
  ROV units (6) and, for admins, Admin (7).
- **Top bar:** an **open alerts** counter (click it to jump to the Alerts panel), the real-time
  feed indicator, the local clock, the shortcut help (**?**), your name and role, and Sign out.
- **Real-time feed indicator:** **Live** means updates arrive within a second. **Reconnecting**
  or **Offline** means the page is showing the last data it has; click the indicator to retry at
  once. On reconnect the page reloads its data, so nothing is missed.

Screen-reader users hear new P1/P2 requests, new alerts, escalations and "No free teams" announced.

---

## 5. Dispatchers: handling requests

### The Operations page

The Operations page is the main working view. From top to bottom:

- **Weather strip:** current conditions and active weather hazards (click for the Weather page).
- **Key figures:** open requests (and how many await triage), open P1 requests, open alerts,
  free teams, wearables online (and how many are critical), and the average time from request to
  on scene.
- **Capacity banner:** only shown when teams are short (see below).
- **SOS queue** on the left; **Alerts** and the **Map** on the right.

The **map** shows open requests (coloured by priority), wearables, team bases and ROVs. Use the
layer buttons to hide any of them. Click a marker to open it. Press **m** or **Hide map** to give
the queue more room.

### How to read the SOS queue

The queue is sorted by priority (P1 first), then by score, then oldest first. Filters: **Open**
(default), **Pending** (not yet checked) and **All** (including closed). Search (press **/**)
matches the reference, name, address, area, emergency type, team and source.

Each row shows:

- **P**: the priority
- **Request**: the reference, type and area, plus flags:
  - **SMS** or **Wearable SOS**: where the request came from (web requests have no flag)
  - **Awaiting resources**: a P1 or P2 request with no team because none has capacity
  - **waiting N min**: time without a team; amber for P1/P2 after 15 minutes
  - **possible duplicate of SOS-…**: same phone, or within about 100 m of an earlier open
    request in the last 2 hours. Click it to compare
- **People**: number to rescue and injured
- **Why this priority**: the score and the main reasons
- **Status** and the assigned team
- **Age**: time since the request arrived

New rows are briefly highlighted.

### Automatic dispatch

Every 10 seconds the server re-scores open requests and **automatically assigns P1 and P2
requests** to a free team, most urgent first. It picks the team with the lowest relative load
(and, for P1, prefers teams set to deploy automatically), then the nearest. Requests marked as
possible duplicates are never assigned automatically, so one emergency cannot take two teams.
P3 to P5 requests wait for a dispatcher.

Automatic assignments appear in the request's history with the author `auto-dispatch`.

### How to work a request

Click a row (or select it with **j**/**k** and press **Enter**). The request page shows:

- **Request:** caller, phone (click to call), address, coordinates, people, vulnerable groups,
  water and food, the caller's own notes, and the priority reasons
- **Location** map with the request, its linked band and the assigned team's base
- **Notes**
- **Actions**, **Timeline**, **Linked wearable** and **Assignment history** on the right

**To move a request forward**, use the **Mark …** button in Actions. It always offers the next
step only: Mark triaged, Mark en route, Mark on scene, Mark resolved.

**To assign or reassign a team**, choose a team in **Assign team** and press **Assign**. Each team
shows its load (for example `2/3`). Full or unavailable teams cannot be chosen. You can assign
from pending, triaged or assigned; once a team is en route, the assignment is fixed.

**To cancel**, press **Cancel request**, give a reason (for example "Duplicate of SOS-…") and
confirm. The caller's tracking page then shows "Closed by the control room".

### If you see "Changed by someone else"

Two people may act on the same request at once. TRIDENT never overwrites silently. If someone
else changed the request after you opened it, your action is refused and a yellow banner says
**Changed by someone else**, with the new status, team and version. The page now shows the current
record.

- **Re-apply my change** sends your action again against the new version (it is disabled when the
  action no longer makes sense, for example marking en route a request that is now cancelled).
- **Discard** drops your change.

Read the new state first: often the other person already did what you intended.

### How to add notes

Type in **Notes** and press **Add** (or Ctrl+Enter). Notes are visible to everyone in the control
room and to responders, with author and time. Use them for call-backs, radio updates and anything
the next person needs. ROV deployment and arrival are added as notes automatically.

### How to link and confirm a wearable

A band ID typed into the public form or claimed in a request is **only a claim** and shows as
**claimed (not verified)**. Until it is confirmed, the band's readings do not change the request's
priority, do not link its alerts, and cannot trigger an automatic team move.

- After confirming with the caller (for example by calling back), press **Confirm wearable link**.
  The chip changes to **verified**, and the band's state now counts for triage.
- If the ID is wrong, press **Remove link**.

Requests raised by the band's own SOS button are verified automatically.

The panel shows the band's state, risk, online status, battery and the evidence for its state.
Click the band ID for its full page.

### SMS and wearable requests

- **SMS** requests are named `SMS` plus the last four digits of the phone. Water and food are
  unknown, so they are not scored up. If no coordinates were sent, the address field holds the
  message text. Call back to fill gaps.
- **Wearable SOS** requests are named after the band label, have no phone number, and use the
  band's GPS position. If the wearer later cancels on the band, a note says so: **check on the
  person before cancelling the request**.

### Capacity banner: how to move a team

When at most one team has free capacity, a banner appears above the queue:

- **Only N of M teams free** (strained), or **No free teams** (exhausted, with urgent requests
  waiting)
- the urgent requests waiting, with their priority and waiting time

When no team is free, the banner may suggest moves such as
**Move NDRF Alpha from SOS-AAA (P4) → SOS-BBB (P1)**. A move is only suggested from a request that
is at least two priority levels lower, is **assigned but not yet en route**.

To move a team:

1. Press the suggested move. Read the confirmation: the team leaves the lower-priority request,
   which goes back to the queue without a team (as Triaged) and keeps its place by priority and
   waiting time.
2. Press **Move team**.
3. **Tell the team by radio or phone.** TRIDENT does not contact the team for you.

Both requests are checked again when you confirm. If either changed in the meantime (for example
the team already left), the move is refused with **Not moved: changed by someone else** and the
suggestions refresh. Viewers and responders see the suggestions but cannot press them.

### Extreme-case automatic moves

Normally a team is only moved when a dispatcher confirms. There is one exception. The server moves
a team **on its own** when **all** of these are true:

- the request is P1 with a score of 80 or more
- its **verified** wearable has been in a critical state with risk 0.85 or more for at least 60 s
- the environment agrees: a water-disaster emergency type (flood, tsunami, dam breach, water
  rising), an active weather **warning**, or a rising river
- no team is free

The team is taken only from a **P4 or P5** request that is assigned and **not yet en route**.

How to recognise one:

- **On the request that lost its team:** it is back to **Triaged**, and the Triaged step in its
  Timeline reads `auto-dispatch · Auto-reallocated (extreme case): <team> moved to SOS-…; back in
  the queue`.
- **On the request that gained the team:** it becomes **Assigned**, the "Awaiting resources" flag
  disappears, and the team appears in Assignment history.
- **The full evidence** (score, band state, risk, duration and the environmental signals) is in
  the audit log under the action `sos.reallocate_extreme` (see [Admin](#13-admin)).

As with a manual move, **tell both teams by radio**: the system changes the records, not the
boat's direction.

---

## 6. Alerts

Alerts are opened automatically for a wearable in a **critical** state, for a **LOST_CONTACT**
(a non-stable band that went silent for 30 s) and for an **SOS_BUTTON** press. Advisory states do
not open alerts.

The Alerts panel on Operations lists unresolved alerts, open ones first and oldest first. Each
shows the state, how long ago it opened, the band and its label, the risk, the linked request (if
any) and up to three pieces of evidence.

### How to acknowledge an alert

Press **Ack** (or press **a** anywhere on the console for the oldest open alert). Acknowledging
means "I have seen this and someone is dealing with it". The alert stays in the list marked
**Acked** with your name.

### Escalation

An alert that is not acknowledged within **2 minutes** is marked **Escalated** in red and
announced again. Escalation does not page anyone outside the console: it is a signal to the control
room that an alert is being missed.

### How to resolve an alert

Press **Resolve**, add a note (for example "Reached by NDRF Alpha, conscious, moved to camp") and
confirm. Resolve when the person has been reached or the reading is confirmed false. Resolving
closes the alert for everyone; it also counts as acknowledged if nobody had acknowledged it.

Resolving an alert does **not** change the request. Update the request separately.

---

## 7. Responders and viewers

### Responders

A responder account belongs to a team. Responders can:

- see everything on the console except Admin
- change the status of requests **assigned to their own team** (mark en route, on scene,
  resolved, or cancel); other requests show "You can view this request. Status changes need a
  dispatcher or the assigned team"
- add notes to any request
- acknowledge and resolve alerts
- press **STOP** on any ROV

Responders cannot assign teams, move teams, send band commands or drive ROVs.

### Viewers

Viewers can open every page except Admin and see everything live, but cannot change anything.

---

## 8. Wearables pages

### The Wearables list

Each band has a tile with its ID and label, online dot, state, risk bar, the latest heart rate,
SpO₂, skin temperature and EDA (sweat response) with a 2-minute trend, battery and time since the
last frame. Online bands come first, then by severity. Filters: **All**, **Needs attention**
(advisory or critical), **Online**, **Offline**.

A band is shown **offline** after 30 seconds without data.

### A band's page

Click a tile. The page shows:

- **Vitals** charts (heart rate, SpO₂, skin temperature, EDA, motion) over 2, 5 or 10 minutes
- **Fusion state**: the current state, risk and the evidence behind it
- **Tier-1 heads**: the individual model outputs (fall probability, stress, heart-rate trust,
  rhythm, activity). Stress is marked advisory. "HR trust" below 0.5 means the optical heart rate
  is unreliable at the moment
- **Commands** (dispatchers and admins)
- **State history**: every change of state, with time, risk and evidence

If the band is offline, a banner says so; the charts show the last data received.

### How to send a command to a band

Commands are queued and delivered with the band's next upload (normally within 1.5 seconds; when
it is offline, when it reconnects). The list under the buttons shows what you sent.

| Button | Effect on the band |
|---|---|
| Reset fall | Clears a fall latched on the band and stops its continuous alarm |
| Calibrate GSR | Re-baselines the sweat sensor. The wearer should sit still for about 2 minutes first |
| Set geofence | Sets a circle (centre and radius, defaulting to the band's position); the band sounds when it leaves it |
| Buzz | Sounds the band's buzzer to get the wearer's attention |

See [Known limitations](#15-known-limitations-in-this-version) for current problems with
**Set geofence** and **Buzz**.

---

## 9. ROV units and missions

ROVs are small underwater units used to search flooded areas. A unit is either **real** (connected
through a serial bridge at the station) or **simulated** (for training and demonstrations). The
console always shows which: a "simulated unit" chip, or the link status **online** / **offline**.

### ROV units page

The fleet table lists each unit's status, link, battery, depth and heading, and mission.

| ROV status | Meaning |
|---|---|
| Idle | At home, available |
| Deploying | Driving itself to the request's location |
| On mission | At the location, holding position and depth |
| Returning | Driving itself home |
| Stopped | Emergency-stopped; thrusters off; waits for a reset |

**How to deploy a unit** (dispatcher or admin):

1. Press **Deploy** on an idle unit with a working link.
2. Choose a request. Only open requests with coordinates are listed, most urgent first.
3. Press **Deploy to SOS-…**.

The unit needs at least 30 % battery. It drives itself there (**auto** mode); a note is added to
the request when it is deployed and when it arrives. On a mission, a unit whose battery falls
below 20 % returns home by itself.

Other actions in the table:

- **Recall**: the unit abandons the mission and drives home on autopilot; any manual control is released.
- **Stop** (anyone except viewers): thrusters stop at once; the unit holds position as **Stopped**.
- **Reset**: clears a stop. The unit then **returns home** on autopilot.
- **Open mission**: goes to the ROV missions page.

**Live cameras** lists units with an active camera, with a "Persons seen" badge and the nearest
face's approximate distance.

### ROV missions page

Each unit on a mission has a panel with:

- a **map** with the unit's position, its track over the last 30 minutes, a dashed line to its
  goal (target or home), the request and the victims' bands
- **telemetry**: depth, heading, water temperature, speed, battery (red below 20 %), lights, link
  and mode. Values turn grey and say "stale" when nothing has arrived for 5 seconds
- the **camera**
- **Mission SOS** and **Victim wearables**: the mission's request plus any other open request
  assigned to the same team, with each person's live band state and vitals. A red **victim
  critical** chip appears in the header when any of them is critical
- the **controls**

### Auto and manual mode

In **auto** the unit navigates itself. A dispatcher or admin can take **manual** control; then
only that person can drive it.

- **Take manual control**: the unit's thrust is stopped and you become the pilot ("You are
  driving"). Others see "<name> is driving".
- **Release to auto**: hands the unit back to its autopilot.
- If someone else is driving, you cannot take over. An **admin** can (**Take over (admin)**).

### How to drive

You must be the pilot. Either:

- **hold** the arrow and up/down buttons on screen, or
- **click the mission panel** (or Tab to it) so it has keyboard focus, then **hold** W/A/S/D to
  move and turn, R/F to go up and down, and press L for the lights.

Movement continues only while you hold the key or button. Releasing it, or moving focus out of the
panel, sends a stop. Set the thrust with the **Speed** slider (0–100 %, default 40 %).

**Dead-man stop:** if the pilot sends no command for **120 seconds**, the unit cuts its thrust and
holds position. This protects against a closed browser or lost connection. Real units also stop
their thrusters by themselves if the station bridge loses contact with the server for 5 seconds.

### STOP

The red **STOP** button (or **Space** while you are driving) is the emergency stop. Anyone except a
viewer can press it, at any time, even while someone else is driving. The unit goes to **Stopped**
and holds position.

To continue, a dispatcher presses **Clear stop · return home**. **This sends the unit home; it does
not resume the mission.** Deploy it again if needed. Use Space only for a real stop: to pause
movement, just release the movement key.

### Return home

**Return home** (dispatcher or admin) asks for confirmation, releases manual control and drives the
unit home on autopilot. It is disabled while someone else is driving.

### The camera panel

What you see depends on what the station runs:

| Camera panel | Meaning |
|---|---|
| Annotated stream with **LIVE**, model name and frame rate | The vision worker is running; boxes mark detections |
| **STALLED**, "last frame … ago" | No new frame for 5 seconds; the page reconnects by itself |
| Plain video | The unit has a camera stream but no vision worker |
| **No camera feed** | No camera for this unit. Nothing is ever faked |

With the vision worker running, the panel lists:

- **Persons in view**: the number of people the detector sees. A **Persons seen · N** badge also
  appears on the mission header and on the ROV units page.
- **Faces**: a name for a face that matches a registered person, otherwise "Unknown person",
  with the match confidence.
- **Objects**: up to six detections, nearest first, with the detector's confidence.

Distances are shown as **~2.1 m**. They are **approximate**: estimated from the size of the object
in the image (a pinhole-camera estimate, about ±30 %). Water clarity, partial views and unusual
sizes make them worse. Use them to judge "near or far", not to navigate precisely.

---

## 10. ROV station operator

The station operator runs the equipment beside a real ROV: the serial bridge and, optionally, the
vision worker. Setup commands are in [GETTING_STARTED.md](GETTING_STARTED.md).

1. **Get a bridge key.** An admin opens **ROV units**, presses **Bridge key** on the unit, optionally
   enters the camera's MJPEG stream URL, and presses **Issue key**. The key is shown once. Issuing a
   key turns the unit from simulated into real: it shows **offline** until the bridge connects, and
   any earlier key stops working.
2. **Start the bridge** (`src/rov/bridge.py`) with that key. The unit's link turns **online** and
   its telemetry becomes live.
3. **Optional: start the vision worker** (`python -m src.cv.vision --key … --source <camera|url|file|demo>`)
   with a vision key for the unit, issued by an admin (see [Admin](#13-admin)). The camera panel
   then shows the annotated stream and detections.

During a mission, keep the station laptop powered and connected. If the bridge loses contact with
the server for 5 seconds, it stops the thrusters. If the console shows the unit **offline**, check
the bridge and its serial cable first.

---

## 11. Weather

The Weather page is for planning: when to stage teams and where water may rise.

- **Current conditions:** temperature, humidity, rain, wind (with gusts), pressure, and when and
  where they were observed. The source is **Open-Meteo** (live) or **offline CSV fallback** when
  the internet is down; in that case the values may be old, so check the time.
- **Forecast, next 24 h or 48 h:** a chart for each variable. The line is the median (p50); the
  shaded band is the 10th to 90th percentile, meaning that in 8 cases out of 10 the real value
  falls inside it. Rain shows the total expected over the period.
- **Hazards:** heat, heavy rain, flood risk or high wind, each as a **watch** (be ready) or a
  **warning** (expected), with the time window and reason. Active hazards also appear in the
  Operations weather strip. A **warning** counts as an environmental signal for extreme-case
  automatic moves.
- **Forecast model:** the training data range, the candidate models and the backtest skill
  against "persistence" (assuming tomorrow equals today). Green means clearly better than
  persistence; red means worse.

The forecast is recomputed every 30 minutes.

---

## 12. Analytics

All figures are computed live from the database; each panel names its source. Use the tabs, or
the left/right arrow keys once a tab has focus.

| Tab | What it shows | Source |
|---|---|---|
| Overview | Open and critical requests, average response time, teams available, wearables online, open alerts; requests created vs resolved over 24 h; counts by type, status and priority | Database (all requests), hourly series |
| Sensors | Frames per minute; for each band: frames in the last 5 minutes, frame rate (expected 0.67 Hz), battery, how often each sensor gave usable data (PPG, SpO₂, EDA, temperature, IMU, GPS), share of time in each state over 24 h, and the share of sensor faults | Telemetry ingest, last 10 minutes and 24 hours |
| Trends | Any of: requests created, requests resolved, alerts opened, telemetry frames, wearable state changes, over the last hour, 24 hours or 14 days | Database time series |
| Geographic | Map of request density (about 1 km cells), open requests, bands, teams, ROVs and river gauges; table of the Adyar, Cooum and Kosasthalaiyar rivers: current discharge, 30-day median, ratio (amber above 1.3×, red above 2×), trend and forecast | Database; rivers from GloFAS via the Open-Meteo Flood API, refreshed every 3 hours |
| Performance | Alert acknowledgement time (p50, p90; escalation is at 120 s), ROV missions and median transit time, response time by priority (creation to on scene, p50/p90/p95), team utilisation | Database and live team loads |
| AI predictions | The measured quality of each wearable model (F1, confidence interval, AUROC, threshold, external test), false alarms per 8 hours for each critical state from replaying real recordings, the rhythm test on atrial fibrillation data, and the weather model card | Model registry and validation reports |

The AI predictions tab is the honest record of how reliable the wearable states are. Read it before
relying on a state.

---

## 13. Admin

The Admin page is visible only to admins. Every change made there (and every other write in
TRIDENT) is recorded in the audit log.

### Users and roles

- **Add user:** username (3–64 letters, digits, dots, dashes, underscores), display name, initial
  password (at least 10 characters; share it privately), role, and team (needed for responders).
- **Change a role or team** with the drop-downs in the table; it takes effect at once.
- **Deactivate** by unticking **active**. The person's console disconnects within 30 seconds and
  they cannot sign in.

### Teams

For each team: its load, its **capacity** (edit the number and leave the field to save) and
whether it is **available**. Untick available to stand a team down; it then receives no new
assignments, automatic or manual. Dispatchers can make the same changes from **Teams** in the
Operations header.

### How to register a wearable band

1. Press **Register device**. Enter the **Device ID**, which must match the ID the band sends, and
   a **Label** (for example "Rescuer · Kumar" or "Evacuee · camp 3").
2. Press **Register**. The band's **key is shown once**. Copy it and give it to whoever flashes the
   band (it goes in the band's `secrets.h`, never in a shared file). You must tick **I have stored
   this key** to close the dialog. TRIDENT keeps only a fingerprint of the key and cannot show it
   again.

### How to rotate a band key

Press **Rotate key** and confirm. The old key stops working **immediately**, so the band is rejected
until it is re-flashed with the new key. Rotate a key when a band is lost, a key may have leaked, or
a band's memory was erased. The new key is shown once, as above.

### ROV bridge and vision keys

The **ROV units** panel on the Admin page lists each unit with two buttons. Each key is shown once,
with a copy button and the command to run at the station. Issuing a new key invalidates the old one.

- **Issue bridge key:** for the serial bridge (`python -m src.rov.bridge --port COMx --key …`). This
  turns the unit from simulated into real: it shows offline, and **Deploy** stays disabled until a
  bridge connects. Admins can also issue it from **Bridge key** on the ROV units page (see
  [ROV station operator](#10-rov-station-operator)).
- **Issue vision key:** for the camera worker (`python -m src.cv.vision --key … --source <camera>`).

### How to test SMS intake

**SMS intake test** runs a message through the same parser the SMS gateway uses, without a phone or
provider. Enter a sender number and a message, then press **Send test SMS**. The result shows the
reference, priority, the reply the sender would receive, and how each part was read.

**This creates a real request** in the queue (source SMS). After a drill, cancel it with a note such
as "SMS intake test".

In production, an SMS gateway (a provider or an Android phone at the control room) forwards real
messages; that is configured on the server.

### Audit log

Every write is recorded with who did it, what, on which record, when and the request ID. This
covers sign-ins and failed sign-ins, status changes, assignments, team moves (manual `sos.reallocate` and automatic
`sos.reallocate_extreme`), notes, alert actions and escalations, band commands, key issues and
rotations, ROV actions and user changes. The **Audit log** table on the Admin page shows the most
recent entries, newest first, with a text filter. The same data is available from the API at
`GET /api/v1/audit?limit=200` (up to 1000 entries).

---

## 14. When things go wrong

| What you notice | What it means | What to do |
|---|---|---|
| Public page shows **Offline** | The phone has no data connection | Send anyway (it is saved and retried), or use **Send by SMS instead**, or call |
| Console shows **Reconnecting** or **Offline** | The live feed is interrupted; data may be old | Click the indicator to retry; check the network. Changes you make still go to the server when it is reachable |
| An action fails with "service unavailable" | The database is busy or unreachable; nothing was saved | Wait a few seconds and try again. Nothing half-saved is left behind |
| **Changed by someone else** | Another person changed the same request first | Read the new state, then Re-apply or Discard |
| A band shows **offline** | No data for 30 s | If it was not STABLE, a LOST_CONTACT alert opens. Go to its last position |
| A band's battery is low | Readings become unreliable; heart rules are suppressed | Replace or charge the band |
| Weather shows **offline data** | The internet is down; the last cached forecast is shown | Use with care; check the observation time |
| Map has no background | Map tiles cannot be loaded (no internet) | Markers still show; use addresses |
| ROV link **offline** | The station bridge is not connected | Check the station laptop and bridge; the unit stops itself after 5 s without contact |
| ROV stopped by itself | Dead-man stop after 120 s without a command, or low battery return | Take control again, or recall it |

---

## 15. Known limitations in this version

These are known gaps between what the console offers and what happens. They are listed so that no
one relies on a behaviour that does not exist yet.

- **Estimated arrival** is not calculated yet, so the public tracking page never shows one.
- **LOST_CONTACT** opens for any band that goes silent in a non-stable state. That includes the advisory
  ELEVATED_STRESS state, so a stressed wearer whose battery dies raises an alert (by design). It is not raised
  for STABLE bands, or for UNKNOWN bands when no models are loaded.
- **The band does not verify the server's TLS certificate** (the firmware uses an insecure TLS client),
  so a hostile network could impersonate the server. Planned for a future version.
- **Band readings are not validated on the wired hardware yet.** The models were trained and tested on
  public datasets, and the firmware is verified by compilation and emulated frames.

