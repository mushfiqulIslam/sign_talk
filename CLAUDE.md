# sign_talk: notes for Claude Code

Junction 2026 hackathon project (Espoo, 13–15 Nov 2026). Smart glasses for people with hearing loss on the Meta Ray-Ban Display: captions, only the station announcements about the wearer's own trip (Gemini filter), and visual warnings for alarms, sirens and horns (YAMNet).

## Deadlines
- Full demo working end to end: Saturday 14 Nov, 20:00. No new features after that.
- Final submission set to FINAL on the Junction Platform: Sunday 15 Nov, 09:30 (hard deadline 10:00). Needs a public repo with an MIT licence, a 2-minute video and a deck PDF.
- All code must be written during the event.

## Where things are
- This repo: `sign_talk/` (GitHub `mushfiqulIslam/sign_talk`, private for now, must be public with an MIT licence before submitting).
- Plan, schedule, roles, demo script: `../plan.md`. Challenge briefs: `../challenges.md`. Update `../plan.md` when decisions change.
- Architecture diagrams: `docs/architecture.md`.
- Meta's Android toolkit, cloned for reference only (do not commit it here): `../reference/meta-wearables-dat-android`. The `samples/DisplayAccess` app there builds.
- Glasses test page and small FastAPI server from Friday night: `../server.py`, `../static/`. Move into this repo only when needed.

## Current task: version 1 Android app
Listen and show, nothing else: phone microphone -> Android speech-to-text (`SpeechRecognizer`) in our app -> Meta display module (`mwdat-display`) -> lens. The real glasses are back with Meta, so use Meta's mock glasses (`mwdat-mockdevice`, `GlassesModel.META_RAYBAN_DISPLAY`) and view their lens in Chrome on the laptop. No backend, Gemini or alerts in version 1.

Done means: speak near the phone and the words appear in the mock lens within about a second.

Later steps: app connects to the laptop backend over WebSocket; Gemini announcement filter; YAMNet danger alerts; glasses microphone (`mwdat-speech`, experimental) instead of the phone's; real glasses.

## Android facts learned Friday night
- Android Studio is extracted in `~/Downloads/android-studio-rabbit2-patch1-linux/android-studio/`; start with `bin/studio.sh`. SDK at `~/Android/Sdk` (platform 37, build-tools 36). `adb` is `~/Android/Sdk/platform-tools/adb`.
- The only Java installed is Android Studio's bundled JBR, Java 25. Gradle 8.14 cannot run on Java 25. Use Gradle 9.2.0 in `gradle-wrapper.properties`; the DisplayAccess sample then builds with AGP 8.11.1 and Kotlin 2.2.21.
- Command-line build: `JAVA_HOME=~/Downloads/android-studio-rabbit2-patch1-linux/android-studio/jbr ./gradlew assembleDebug`.
- Toolkit packages come from Maven Central, group `com.meta.wearable`, version `1.0.1` (`mwdat-core`, `mwdat-display`, `mwdat-mockdevice`). No token needed.
- `local.properties` needs `sdk.dir=/home/mushfiqul/Android/Sdk`, and in Developer Mode `mwdat_application_id=0` and `mwdat_client_token=0`.
- Startup: request `BLUETOOTH` and `BLUETOOTH_CONNECT`, then `Wearables.initialize(context)`.
- `MockDeviceKit.enable()` fakes registration (state goes to REGISTERED) and initialises Wearables if needed, so the mock path needs no `startRegistration` and no Meta AI app. Pass `MockDeviceKitConfig(initiallyRegistered = false)` to test the registration flow.
- Mock glasses: `MockDeviceKit.getInstance(ctx).enable()`, `pairGlasses(GlassesModel.META_RAYBAN_DISPLAY)`, then `powerOn()` and `don()`. Chrome preview of the mock lens: `startTestServer(9000)`, then `adb forward tcp:9000 tcp:9000` and open `http://127.0.0.1:9000/` on the laptop.
- Display: `Wearables.createSession(SpecificDeviceSelector(mockGlasses.deviceIdentifier))` (or `AutoDeviceSelector(filter = { it.isDisplayCapable() })` for real glasses), `session.start()`, wait for `DeviceSessionState.STARTED`, then `session.addDisplay()`, wait for `DisplayState.STARTED`, then `display.sendContent { flexBox(...) { text(..., style = TextStyle.BODY) } }`.
- Meta's sample sets `minSdk = 31` (Android 12). Check the phone's real Android version with `adb shell getprop ro.build.version.release`; Chrome always reports "Android 10".
- Real glasses later: Developer Mode on in the Meta AI app (done), then the app appears under Meta AI app > App connections > Developer mode apps after `Wearables.startRegistration(activity)`.

## Working with the user
- Plain-language explanations that can be shared with teammates (one teammate has a health background, not a coding one).
- Keep each step working before starting the next.
- Commit or push only when the user asks.
