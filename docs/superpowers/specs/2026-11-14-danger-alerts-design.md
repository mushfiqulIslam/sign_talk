# Danger sound alerts on the lens: short design

Date: 2026-11-14 (Saturday). Demo freeze 20:00 today.

> **Status: dropped from the demo (Saturday 14:30).** Built and tested in the simulator, then removed: on the demo phone (Samsung, Google speech service) the alert recorder and speech-to-text could not share the microphone. Piping our recording into speech-to-text (`EXTRA_AUDIO_SOURCE`) heard speech but never returned text; a separate recorder made the speech service fail with a false permission error. Captions matter more, so alerts wait for the glasses microphone (`mwdat-speech`) or a laptop listener (approach B).

## Intent
A wearer with hearing loss can't hear a fire alarm, a siren or a car horn. When the phone hears one, the lens shows a clear warning straight away, whatever else is on screen. Demo: a fire-alarm sound plays from a laptop and the warning appears (`plan.md`, demo script step 3).

## Goals
- Recognise **fire / smoke alarm**, **siren** (emergency vehicle) and **car horn** from the phone microphone, on the phone, with no laptop or internet.
- Warning on the lens within about 1–2 seconds: big red-on-black words (`⚠ FIRE ALARM`), drawn as a picture like Extra-large captions, plus a phone vibration.
- The warning stays about 5 seconds, then the captions come back. A repeat of the same sound keeps it up rather than flashing.
- Captions keep working as today.

## Non-goals
- No other sound types (doorbell, baby crying, name called). Easy to add later; not now.
- No direction or distance of the sound.
- No home alert via Atech.

## Anti-goals
- **Captions silently stop** because the alert feature took the microphone.
- False alarms from speech or music often enough that the wearer ignores the warnings.
- A sign video or caption hiding an active warning.

## Approaches
- **A. On the phone (chosen by the user).** The app records the microphone itself once, and sends the same audio both to YAMNet and to Android speech-to-text (Android 13+ lets speech-to-text take audio from the app through `EXTRA_AUDIO_SOURCE`; the phone runs Android 17). Works anywhere; changes how captions get audio.
- B. On the laptop: laptop microphone → YAMNet in Python → phone over Wi-Fi. Captions untouched, but it needs the backend link and Wi-Fi, and it hears the room, not the wearer. Not chosen.

## How it works
```
phone mic ─ AudioRecord 16 kHz mono ─┬─> speech-to-text (EXTRA_AUDIO_SOURCE pipe) -> captions
                                     └─> YAMNet (on phone, ~1 s windows) -> alarm/siren/horn? -> lens warning + vibration
```
- **Sound model:** YAMNet (Google, 521 sound classes, Apache 2.0) through MediaPipe's on-device audio classifier (`com.google.mediapipe:tasks-audio`, `yamnet.tflite` about 4 MB in the app's assets).
- **Classes to warn on** (YAMNet names): *Fire alarm*, *Smoke detector, smoke alarm*, *Alarm* → **FIRE ALARM**; *Siren*, *Emergency vehicle*, *Police car (siren)*, *Ambulance (siren)*, *Fire engine, fire truck (siren)* → **SIREN**; *Vehicle horn, car horn, honking*, *Car alarm* → **CAR HORN**.
- **Avoiding false alarms:** warn only when a class scores at least 0.3 in **2 of the last 3** windows (about 1.5 s).
- **Lens priority:** warning > sign video > captions. A warning interrupts a playing video.
- **Phone screen:** an **Alerts: on/off** switch (on by default), the last alert and its score, and a **Test alert** button for the demo in case the room is noisy.

## Fallback (the anti-goal guard)
- First step is a **spike**: does this phone's speech service accept audio from the app (`EXTRA_AUDIO_SOURCE`)? Samsung phones may use Samsung's or Google's speech service, and not every one supports it.
- If it works: one shared recording, as above.
- If not: captions keep their current microphone path unchanged, and YAMNet is fed only **while no one is speaking**, i.e. between sentences when the recogniser restarts. That's weaker (it can miss an alarm during speech), and it would be said so in the pitch. The **Test alert** button still makes the demo safe.

## My calls (please check)
- Threshold 0.3, 2 of 3 windows, warning shown 5 s.
- Generic *Alarm* counts as FIRE ALARM (YAMNet often labels smoke alarms that way).
- Vibration on the phone; the glasses can't vibrate.
- Alerts on by default.

## Left to the builder
- Exact MediaPipe setup, buffer sizes, the pipe between the recorder and speech-to-text.
- The warning's picture layout.
