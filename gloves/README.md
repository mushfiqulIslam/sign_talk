# Gloves: Rokoko Smartgloves II -> signs as text -> spoken by the phone

## Glove backend (`signtalk-gloves`): signs -> sentence -> phone over Wi-Fi

One command on the laptop recognises signs, turns them into a Finnish/English sentence (Gemini;
plain words without a key) and sends it to the Sign Talk app, which shows it and speaks it out loud.
The laptop and the phone must be on the **same Wi-Fi** (or the laptop on the phone's hotspot).

### The trained model is included
`gloves/gloves-model.joblib` (2.8 MB) is trained on the 10 signs the Sign Talk team recorded
(me, name, address, study, university, Aalto, nice, meet, good, day; one signer), shared under
the repo's MIT licence. It also holds held-out stretches of those recordings for the replay demo.
The raw CSV recordings are not in the repo. `start.bat` / `start.sh` and `signtalk-gloves run` use
this model automatically: **no training needed**. Run `train` only for new recordings.

### Easiest: the shared package (plug and play)
`signtalk-gloves bundle` writes `~/Downloads/SignTalk-Gloves.zip` (backend + trained model + start
scripts, no API keys), for people who don't use Git. The recipient unzips it and:
- Windows: double-click **`start.bat`** · Mac / Linux: **`./start.sh`**
- first start sets itself up (installs `uv`, which fetches Python if needed; about a minute)
- a page with a **QR code** opens: on the phone, **Sign Talk -> Gloves -> Scan QR on the laptop**
- `QUICKSTART.txt` in the zip says the same in five steps.
Without a Gemini key the demo phrases still come out as natural sentences (a small phrase book).
`start.bat` / `start.sh` also work straight from this folder of the repo, with the included model.

### Install on Windows (once)
1. Install **Python 3.10+** from python.org: in the installer tick **"Add python.exe to PATH"**.
   Install **Git** from git-scm.com (or download the repo as a ZIP).
2. In **Command Prompt**:
   ```bat
   git clone https://github.com/mushfiqulIslam/sign_talk.git
   cd sign_talk
   py -m venv gloves\.venv
   gloves\.venv\Scripts\pip install -e gloves
   ```
3. (Only with new recordings) train your own model:
   `gloves\.venv\Scripts\signtalk-gloves train --data C:\gestures` (one CSV per sign).
4. Run it, always from the `sign_talk` folder:
   ```bat
   gloves\.venv\Scripts\signtalk-gloves run --name "Anna's laptop"
   ```
   The first time, Windows asks to let Python through the firewall: tick **Private and Public**.
   Missed it? In an **administrator** Command Prompt:
   `netsh advfirewall firewall add rule name="Sign Talk gloves" dir=in action=allow protocol=TCP localport=8765`

**Update later:** `git pull` in `sign_talk`, then `gloves\.venv\Scripts\pip install -e gloves`.

### Install on Mac / Linux (once)
```
git clone https://github.com/mushfiqulIslam/sign_talk.git && cd sign_talk
python3 -m venv gloves/.venv && gloves/.venv/bin/pip install -e gloves
gloves/.venv/bin/signtalk-gloves run --name "My laptop"
```

### Phone
Install the Sign Talk APK (from the team), open it on the same Wi-Fi. The **Gloves** card lists
"Found on this Wi-Fi -> Anna's laptop" and connects by itself (tap a laptop if there are several).
Tap **Play glove demo**: the signs appear, then the sentence, spoken in the language picked on screen.
If no laptop appears (the Wi-Fi blocks announcements, or a VPN / virtual network adapter is on):
type the laptop's address in the Gloves card: `ipconfig` -> "IPv4 Address" under Wireless LAN
adapter Wi-Fi (Windows), `ip addr` or `ifconfig` (Mac / Linux). The phone's hotspot always works.

### Commands
(`gloves\.venv\Scripts\signtalk-gloves` on Windows, `gloves/.venv/bin/signtalk-gloves` elsewhere)
```
signtalk-gloves train --data <folder with one CSV per sign>    once; prints accuracy on unseen repetitions
signtalk-gloves run                                            replays recorded signs (no gloves needed)
signtalk-gloves run --source file --file sentence.csv          signs in a new recording (same CSV export), in real time
signtalk-gloves run --source udp                               live: any tool sends frames to UDP 9100, one JSON object
                                                               per packet with the CSV's column names (Timestamp not needed)
signtalk-gloves run --source studio                            live gloves from Rokoko Studio (record signs first, below)
signtalk-gloves eval                                           score on 200 random phrases of held-out signs (about 98%)
signtalk-gloves detect sentence.csv                            print the signs in a recording
```

### How well it works
On the 10 recorded signs (one signer, one session; expect lower with other people or days):
99% of single 1 s windows, and **98% of random 2-4 sign phrases read back exactly** (all signs found).
A sign counts after 3 windows in a row agree with confidence >= 0.45; a sentence ends 2 s after the
hands stop signing. There is no "hands resting" recording yet: one would make live use safer.

### Good to know
- Anyone on the same Wi-Fi can connect to port 8765 and read the sentences: use a trusted network.
- The model shipped in the repo is used unless you train your own (`train` saves to
  `~/.signtalk/gloves-model.joblib`, `%USERPROFILE%\.signtalk\` on Windows; delete the shipped
  file to use yours). The raw CSV recordings are not in the repo.
- Tests: `pip install -e "gloves[dev]"` into the same venv, then `pytest gloves`.

The live (`--source studio`) recogniser uses the recordings made with `record.py` below, in Studio's
live format; the CSV model can't read the live stream. Record each sign ~10 times plus `rest`.

---

Rokoko Studio (Windows or Apple-silicon Mac) streams the glove data to these scripts
on the same laptop. Python 3.10+ and two packages (`numpy`, `lz4`).

## Setup on Windows for the older Studio scripts only (record.py, recognise.py, inspect_stream.py)
Not needed if you installed `signtalk-gloves` above: it includes these packages.
```
cd sign_talk\gloves
py -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

## Rokoko Studio
1. Connect the gloves and check the hands move in Studio.
2. Livestreaming > add a **Custom** target: IP `127.0.0.1`, port `14043`, format **JSON**
   (v3), compression off if there is a choice. Switch the stream on.
3. Allow Python through Windows Firewall if Windows asks.

## 1. See what Studio sends
```
.venv\Scripts\python inspect_stream.py            layout, joint names, live finger bend
.venv\Scripts\python inspect_stream.py --raw      one full packet as JSON
.venv\Scripts\python inspect_stream.py --joints   every joint's numbers once
```
The live table shows each finger's bend in degrees (0 = straight). Bend a finger: its
number should change. If it says "Hand joints we understood: 0", send the `--raw` output
to Claude. The first packet is also saved to `first_packet.json`.

## 2. Record signs
```
.venv\Scripts\python record.py
```
Type a name, the number of repetitions (10 is good), then hold the sign each time it says
SIGN NOW (about half a second is recorded). Also record **`rest`** (hands relaxed): it is
never shown as a word, and stops random hand positions from being read as signs.
Recordings go to `sign_dataset/<sign>/`.

## 3. Recognise live
```
.venv\Scripts\python recognise.py           (add --verbose to see every guess)
```
Prints `>>> WORD` when a sign is held. If signs get mixed up, record a few more of each.

## Without gloves
`python fake_studio.py` pretends to be Studio (type a pose number to change the hand).
`python tests/test_pipeline.py` checks stream -> record -> recognise end to end.
