# On-device ML fall model (SisFall CNN-LSTM via TFLite)

The accelerometer monitor runs **two detectors in parallel**:

1. **Threshold detector** (`src/sensors/detectFall.ts`) — always on, zero setup.
   Looks for an impact spike followed by stillness. This is the cheap, robust
   baseline and the default trigger source.
2. **ML confirmer** (`src/sensors/fallModel.ts`) — a SisFall-style CNN-LSTM
   exported to TFLite. It adds coverage for falls without a clean
   impact+stillness signature (e.g. a slow slump). It is a **graceful no-op**
   until you complete the steps below, so the app builds and runs without it.

The ML path only runs inference when a sample exceeds `FALL_MODEL.gateG`
(a cheap pre-gate), keeping the model off during quiet periods — the same
"cheap filter gates the expensive brain" principle used between device and cloud.

## What's already wired
- `react-native-fast-tflite` is in `package.json` + `app.json` plugins.
- `metro.config.js` registers `.tflite` as a bundlable asset.
- `prepareWindow()` resamples the 50 Hz stream to `FALL_MODEL.modelHz` (20 Hz),
  shapes it into a `Float32Array` of `windowSamples*3` ([x,y,z] per timestep),
  and is unit-tested in `fallModel.test.ts`.
- `AccelerometerMonitor.runModel()` calls the model and triggers on
  `prob >= FALL_MODEL.threshold`.

## Remaining setup (needs your device)
1. **Get a model.** Train/export a SisFall CNN-LSTM to TFLite, or use a public
   repo (e.g. `1saifj/Fall-Detection-System-SisFall`, `ankit1997/Fall-Detection-using-CNN`).
   The expected I/O: input `Float32Array` of length `windowSamples*3` (default
   `51*3 = 153`, row-major `[x,y,z]` per timestep at 20 Hz); output a single
   sigmoid fall probability. Adjust `FALL_MODEL.windowSamples` / `modelHz` to
   match your model, and add normalization in `prepareWindow` if your model
   expects it (SisFall raw is in g here).
2. **Add the asset.** Drop the file at `assets/models/fall_sisfall.tflite`.
3. **Inject it once at startup.** In `src/hooks/useQuietcare.ts` (before
   `accel.start()`), add:
   ```ts
   import { setFallModelSource } from '../sensors/fallModel';
   // @ts-expect-error — Metro resolves .tflite as an asset module
   setFallModelSource(require('../../assets/models/fall_sisfall.tflite'));
   ```
4. **Install + rebuild the dev client** (the native module isn't in Expo Go):
   ```bash
   npm install
   npx expo prebuild --clean   # or: eas build --profile development
   npm run ios   # or: npm run android
   ```

## Verifying
- Logic is unit-tested offline: `npm test` (covers `prepareWindow`/`decideFall`
  and the graceful no-op path).
- On-device: watch the debug log for `FALL DETECTED` after a simulated slump;
  tune `FALL_MODEL.threshold` / `gateG`. Inference + the native module can only
  be verified on a real build/device.
