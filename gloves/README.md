# Gloves: Rokoko Smartgloves II -> signs as text

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
