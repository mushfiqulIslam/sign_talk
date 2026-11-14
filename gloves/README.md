# Gloves: Rokoko Smartgloves II -> signs as text -> spoken by the phone

## Glove backend (`signtalk-gloves`): signs -> sentence -> phone over Wi-Fi

One command on the laptop recognises signs, turns them into a Finnish/English sentence (Gemini,
`GEMMA_API_KEY` in `sign_talk/.env`; plain words without it) and sends it to the Sign Talk app,
which shows it and speaks it out loud. Laptop and phone must be on the same Wi-Fi (or the phone's hotspot).

Install once (Python 3.10+), from the `sign_talk` folder:
```
Windows:      py -m venv gloves\.venv   then   gloves\.venv\Scripts\pip install -e gloves
Mac / Linux:  python3 -m venv gloves/.venv   then   gloves/.venv/bin/pip install -e gloves
```
Then (`gloves\.venv\Scripts\signtalk-gloves` on Windows, `gloves/.venv/bin/signtalk-gloves` elsewhere):
```
signtalk-gloves train --data <folder with one CSV per sign>    once; prints accuracy on unseen repetitions
signtalk-gloves run                                            replays recorded signs (no gloves needed)
signtalk-gloves run --source file --file sentence.csv          signs in a new recording (same CSV export), played in real time
signtalk-gloves run --source udp                               live: any tool sends frames to UDP 9100, one JSON object
                                                               per packet with the CSV's column names (Timestamp not needed)
signtalk-gloves run --source studio                            live gloves from Rokoko Studio (record signs first, below)
signtalk-gloves eval                                           score on 200 random phrases of held-out signs
signtalk-gloves detect sentence.csv                            print the signs in a recording
```
How well it reads the 10 recorded signs (one signer, one session; expect lower with other people or days):
99% of single 1 s windows, and **98% of random 2-4 sign phrases read back exactly** (all signs found).
A sign counts after 3 windows in a row agree with confidence >= 0.45; a sentence ends 2 s after the
hands stop signing. There is no "hands resting" recording yet: one would make live use safer.
It prints the laptop's address. In the app: **Gloves** card -> type that address -> **Connect** ->
**Play glove demo** (replay mode) or sign with the gloves (studio mode).
- Windows asks to let Python through the firewall the first time: tick **Private and Public**.
- Find the address yourself with `ipconfig` (Windows, "IPv4 Address" under Wi-Fi) or `ip addr` / `ifconfig`.
- Anyone on the same Wi-Fi can connect to port 8765 and read the sentences: use a trusted network.
- The CSV recordings and the trained model (`~/.signtalk/gloves-model.joblib`) are not in the repo.
- Tests: `gloves/.venv/bin/pip install -e "gloves[dev]"` then `gloves/.venv/bin/pytest gloves`.

The live (`--source studio`) recogniser uses the recordings made with `record.py` below, in Studio's
live format; the CSV model can't read the live stream. Record each sign ~10 times plus `rest`.

---

Rokoko Studio (Windows or Apple-silicon Mac) streams the glove data to these scripts
on the same laptop. Python 3.10+ and two packages (`numpy`, `lz4`).

## Setup on Windows (once)
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
