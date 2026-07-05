import { Audio, InterruptionModeAndroid, InterruptionModeIOS } from 'expo-av';
import {
  AndroidAudioEncoder,
  AndroidOutputFormat,
  IOSAudioQuality,
  IOSOutputFormat,
} from 'expo-av/build/Audio/RecordingConstants';
import * as Speech from 'expo-speech';
// SDK 54 moved the classic file-system API (cacheDirectory, EncodingType,
// readAsStringAsync, ...) to the /legacy entry point. Use it here to keep the
// existing rolling-buffer/audio logic unchanged.
import * as FileSystem from 'expo-file-system/legacy';
import { AUDIO_BUFFER } from '../config';
import { breadcrumb, captureException } from '../sentry';

const delay = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

const LIVE_RECORDING_OPTIONS = {
  isMeteringEnabled: true,
  android: {
    extension: '.m4a',
    outputFormat: AndroidOutputFormat.MPEG_4,
    audioEncoder: AndroidAudioEncoder.AAC,
    sampleRate: 16000,
    numberOfChannels: 1,
    bitRate: 64000,
  },
  ios: {
    extension: '.wav',
    outputFormat: IOSOutputFormat.LINEARPCM,
    audioQuality: IOSAudioQuality.MAX,
    sampleRate: 16000,
    numberOfChannels: 1,
    bitRate: 256000,
    linearPCMBitDepth: 16,
    linearPCMIsBigEndian: false,
    linearPCMIsFloat: false,
  },
  web: {
    mimeType: 'audio/wav',
    bitsPerSecond: 256000,
  },
};

/**
 * AudioManager owns the microphone. It runs an always-on rolling ring buffer
 * (continuously recording short segments) so that when a trigger fires, the
 * audio sent is the few seconds BEFORE the event rather than silence recorded
 * after the fact. This is the "always-on = buffer, not continuous upload"
 * design: we record continuously but only ever upload a buffered clip on demand.
 *
 * Because expo-av allows only one active Recording (and iOS can't record while
 * playing), the manager serializes mic access: dedicated listen-recording and
 * playback both pause the ring buffer, do their work, then resume it.
 */
class AudioManager {
  private permissionGranted = false;
  private running = false;
  private paused = false;
  private current: Audio.Recording | null = null;
  // Active push-to-talk recording, held between startManualRecording() and
  // stopManualRecordingB64() so the user controls exactly what is captured.
  private manualRecording: Audio.Recording | null = null;
  // The in-flight start (pauseBuffer + prepare + start). stop() awaits this so
  // a quick press/release can't stop before the recorder has actually started.
  private manualStartPromise: Promise<void> | null = null;
  // True for the whole duration of a single rolling-buffer iteration (from
  // before the recorder is prepared until it is stopped + unloaded). pauseBuffer
  // waits on this so a dedicated listen-recording can never prepare a second
  // native recorder while the buffer is mid-prepare ("Recorder is already
  // prepared").
  private segmentBusy = false;
  // Serializes dedicated listen-recordings so two overlapping `listen` prompts
  // can't prepare concurrent recorders.
  private dedicatedLock: Promise<void> = Promise.resolve();
  private ring: string[] = [];
  private segmentListeners: Array<(b64: string) => void> = [];
  // Live mic-level (dBFS) listeners, fed during push-to-talk for diagnostics.
  private meterListeners: Array<(dbfs: number) => void> = [];
  // Resolvers used to interrupt the segment sleep early (on pause/stop).
  private wakeups: Array<() => void> = [];
  private loopPromise: Promise<void> | null = null;

  private async ensurePermission(): Promise<boolean> {
    if (this.permissionGranted) return true;
    const { granted } = await Audio.requestPermissionsAsync();
    this.permissionGranted = granted;
    return granted;
  }

  async requestMicrophoneAccess(): Promise<boolean> {
    return this.ensurePermission();
  }

  onAudioSegment(listener: (b64: string) => void): () => void {
    this.segmentListeners.push(listener);
    return () => {
      this.segmentListeners = this.segmentListeners.filter((l) => l !== listener);
    };
  }

  /** Subscribe to live mic level (dBFS, ~ -160 = silence, ~ -20..0 = loud). */
  onMeter(listener: (dbfs: number) => void): () => void {
    this.meterListeners.push(listener);
    return () => {
      this.meterListeners = this.meterListeners.filter((l) => l !== listener);
    };
  }

  private emitMeter(dbfs: number | undefined): void {
    if (typeof dbfs !== 'number') return;
    this.meterListeners.forEach((l) => {
      try {
        l(dbfs);
      } catch {
        // ignore listener errors
      }
    });
  }

  private wake(): void {
    const pending = this.wakeups;
    this.wakeups = [];
    pending.forEach((w) => w());
  }

  // Interruptible sleep: resolves after ms OR when wake() is called.
  private interruptibleSleep(ms: number): Promise<void> {
    return new Promise<void>((resolve) => {
      const timer = setTimeout(() => resolve(), ms);
      this.wakeups.push(() => {
        clearTimeout(timer);
        resolve();
      });
    });
  }

  // ---- Rolling buffer lifecycle ----

  startRollingBuffer(): void {
    if (!AUDIO_BUFFER.enabled || this.running) return;
    this.running = true;
    this.paused = false;
    this.loopPromise = this.loop();
  }

  async stopRollingBuffer(): Promise<void> {
    this.running = false;
    this.wake();
    await this.loopPromise?.catch(() => undefined);
    this.loopPromise = null;
    this.ring = [];
  }

  private async loop(): Promise<void> {
    const granted = await this.ensurePermission();
    if (!granted) {
      this.running = false;
      breadcrumb('audio', 'buffer:no_permission');
      return;
    }
    breadcrumb('audio', 'buffer:start', { segmentMs: AUDIO_BUFFER.segmentMs });

    while (this.running) {
      if (this.paused) {
        await this.interruptibleSleep(150);
        continue;
      }
      // Claim the mic for the entire iteration BEFORE any async work, so a
      // concurrent pauseBuffer() waits for us to fully release it.
      this.segmentBusy = true;
      let rec: Audio.Recording | null = null;
      try {
        await this.configureRecordingMode();
        rec = new Audio.Recording();
        this.current = rec;
        await rec.prepareToRecordAsync(LIVE_RECORDING_OPTIONS);
        await rec.startAsync();

        await this.interruptibleSleep(AUDIO_BUFFER.segmentMs);

        // Stop and harvest the segment.
        await rec.stopAndUnloadAsync();
        const uri = rec.getURI();
        if (uri) {
          const b64 = await FileSystem.readAsStringAsync(uri, {
            encoding: FileSystem.EncodingType.Base64,
          });
          await FileSystem.deleteAsync(uri, { idempotent: true });
          // Discard a segment that was cut short by a pause/stop.
          if (!this.paused && this.running) {
            this.pushSegment(b64);
          }
        }
      } catch (err) {
        captureException(err, { stage: 'rolling_buffer' });
        if (rec) {
          await rec.stopAndUnloadAsync().catch(() => undefined);
        }
        await this.interruptibleSleep(500);
      } finally {
        this.current = null;
        this.segmentBusy = false;
      }
    }
    breadcrumb('audio', 'buffer:stopped');
  }

  private pushSegment(b64: string): void {
    this.ring.push(b64);
    while (this.ring.length > AUDIO_BUFFER.ringSize) this.ring.shift();
    this.segmentListeners.forEach((listener) => {
      try {
        listener(b64);
      } catch (err) {
        captureException(err, { stage: 'audio_segment_listener' });
      }
    });
  }

  /** Most recent buffered segment (the pre-trigger audio), or null if empty. */
  getRecentAudioB64(): string | null {
    return this.ring.length > 0 ? this.ring[this.ring.length - 1] : null;
  }

  // ---- Mic arbitration ----

  private async configureRecordingMode(settleMs = 0): Promise<void> {
    await Audio.setIsEnabledAsync(true);
    await Audio.setAudioModeAsync({
      allowsRecordingIOS: true,
      playsInSilentModeIOS: true,
      staysActiveInBackground: true,
      interruptionModeIOS: InterruptionModeIOS.DuckOthers,
      interruptionModeAndroid: InterruptionModeAndroid.DuckOthers,
      shouldDuckAndroid: true,
      playThroughEarpieceAndroid: false,
    });
    // iOS needs a moment for the AVAudioSession to actually activate in record
    // mode after a playback->record switch; recording immediately captures
    // silence. The continuous rolling buffer passes 0 (already in record mode),
    // while dedicated post-playback recordings request a settle window.
    if (settleMs > 0) await delay(settleMs);
  }

  private async configurePlaybackMode(): Promise<void> {
    await Audio.setIsEnabledAsync(true);
    await Audio.setAudioModeAsync({
      allowsRecordingIOS: false,
      playsInSilentModeIOS: true,
      staysActiveInBackground: true,
      interruptionModeIOS: InterruptionModeIOS.DoNotMix,
      interruptionModeAndroid: InterruptionModeAndroid.DoNotMix,
      shouldDuckAndroid: false,
      playThroughEarpieceAndroid: false,
    });
    await delay(150);
  }

  private async pauseBuffer(): Promise<void> {
    if (!this.running) return;
    this.paused = true;
    this.wake();
    // Wait until the loop has fully released the mic (recorder created,
    // prepared, started, stopped AND unloaded). segmentBusy spans the whole
    // iteration, closing the prepare/start window that `this.current` alone
    // misses.
    let waited = 0;
    while ((this.segmentBusy || this.current !== null) && waited < 6_000) {
      await delay(50);
      waited += 50;
    }
  }

  private resumeBuffer(): void {
    if (!this.running) return;
    this.paused = false;
    this.wake();
  }

  // ---- Public play / record (used by the check-in flow) ----

  /** Play a base64 audio clip through the speaker. */
  async playBase64Audio(audioB64: string): Promise<void> {
    breadcrumb('audio', 'speak:play_start', { bytes: audioB64.length });
    await this.pauseBuffer();
    try {
      await this.configurePlaybackMode();

      const uri = `${FileSystem.cacheDirectory}qc-speak-${Date.now()}.wav`;
      await FileSystem.writeAsStringAsync(uri, audioB64, {
        encoding: FileSystem.EncodingType.Base64,
      });

      const sound = new Audio.Sound();
      try {
        await sound.loadAsync(
          { uri },
          { shouldPlay: false, volume: 1.0, isMuted: false, progressUpdateIntervalMillis: 100 },
        );

        await new Promise<void>((resolve) => {
          let settled = false;
          const settle = () => {
            if (settled) return;
            settled = true;
            resolve();
          };
          sound.setOnPlaybackStatusUpdate((status) => {
            if (status.isLoaded && status.didJustFinish) {
              settle();
            } else if (!status.isLoaded && status.error) {
              captureException(new Error(`playback error: ${status.error}`));
              settle();
            }
          });
          sound.playAsync().catch((err) => {
            captureException(err, { stage: 'playback' });
            settle();
          });
        });
      } finally {
        await sound.unloadAsync().catch(() => undefined);
        await FileSystem.deleteAsync(uri, { idempotent: true });
      }
      breadcrumb('audio', 'speak:play_done');
    } finally {
      this.resumeBuffer();
    }
  }

  async speakText(text: string): Promise<void> {
    breadcrumb('audio', 'speech:start');
    await this.pauseBuffer();
    try {
      await this.configurePlaybackMode();
      await Speech.stop().catch((err) => captureException(err, { stage: 'speech_stop' }));
      await delay(100);
      await new Promise<void>((resolve) => {
        let settled = false;
        const settle = () => {
          if (settled) return;
          settled = true;
          resolve();
        };
        Speech.speak(text, {
          rate: 0.95,
          pitch: 1.0,
          useApplicationAudioSession: true,
          onDone: settle,
          onStopped: settle,
          onError: (err) => {
            captureException(err, { stage: 'speech' });
            settle();
          },
        });
      });
      breadcrumb('audio', 'speech:done');
    } finally {
      this.resumeBuffer();
    }
  }

  /** Record from the mic for `durationMs`, returning the clip as base64. */
  async recordAudioBase64(durationMs: number): Promise<string> {
    // Serialize dedicated recordings: chain onto any in-flight one so two
    // overlapping `listen` prompts never prepare concurrent native recorders.
    const run = this.dedicatedLock.then(() => this._recordAudioBase64(durationMs));
    // Keep the lock chained but don't let its rejection poison the next caller.
    this.dedicatedLock = run.then(
      () => undefined,
      () => undefined,
    );
    return run;
  }

  private async _recordAudioBase64(durationMs: number): Promise<string> {
    breadcrumb('audio', 'listen:record_start', { durationMs });
    const granted = await this.ensurePermission();
    if (!granted) throw new Error('Microphone permission denied');

    await this.pauseBuffer();
    let recording: Audio.Recording | null = null;
    try {
      // Settle the AVAudioSession in record mode before capturing; without this
      // a recording started right after playback captures pure silence on iOS.
      await this.configureRecordingMode(350);

      recording = new Audio.Recording();
      await recording.prepareToRecordAsync(LIVE_RECORDING_OPTIONS);
      await recording.startAsync();

      await delay(durationMs);

      const status = await recording.getStatusAsync().catch(() => null);
      if (status) {
        breadcrumb('audio', 'listen:record_status', {
          durationMs: status.durationMillis,
          metering: status.metering,
        });
      }

      await recording.stopAndUnloadAsync();
      const uri = recording.getURI();
      recording = null;
      if (!uri) throw new Error('Recording produced no file URI');

      const b64 = await FileSystem.readAsStringAsync(uri, {
        encoding: FileSystem.EncodingType.Base64,
      });
      await FileSystem.deleteAsync(uri, { idempotent: true });
      breadcrumb('audio', 'listen:record_done', { bytes: b64.length });
      return b64;
    } catch (err) {
      // Ensure a half-prepared recorder is released so the next attempt can
      // prepare cleanly instead of hitting "Recorder is already prepared".
      if (recording) {
        await recording.stopAndUnloadAsync().catch(() => undefined);
      }
      throw err;
    } finally {
      this.resumeBuffer();
    }
  }

  /**
   * Push-to-talk: begin recording and keep going until stopManualRecordingB64()
   * is called. The caller controls the exact capture window (press-and-hold),
   * which avoids the timing gap of a fixed-duration recording where the user's
   * speech can fall outside the window.
   */
  async startManualRecording(): Promise<void> {
    const granted = await this.ensurePermission();
    if (!granted) throw new Error('Microphone permission denied');
    const start = this.dedicatedLock.then(async () => {
      await this.pauseBuffer();
      try {
        await this.configureRecordingMode(350);
        const rec = new Audio.Recording();
        await rec.prepareToRecordAsync(LIVE_RECORDING_OPTIONS);
        // Stream live mic level to UI/diagnostics while the user holds.
        rec.setProgressUpdateInterval(150);
        rec.setOnRecordingStatusUpdate((s) => {
          if (s.isRecording) this.emitMeter(s.metering);
        });
        await rec.startAsync();
        this.manualRecording = rec;
        breadcrumb('audio', 'manual:record_start');
      } catch (err) {
        // Failed to start: release the mic so the buffer resumes.
        this.resumeBuffer();
        throw err;
      }
    });
    // stop() awaits this so a quick release can't stop before start finishes.
    this.manualStartPromise = start.then(
      () => undefined,
      () => undefined,
    );
    this.dedicatedLock = this.manualStartPromise;
    return start;
  }

  /** Stop the push-to-talk recording and return the clip as base64 ('' if none). */
  async stopManualRecordingB64(): Promise<string> {
    // The user may release before pauseBuffer + prepare + start finish; wait for
    // the in-flight start so we actually have a running recorder to stop.
    if (this.manualStartPromise) {
      await this.manualStartPromise;
      this.manualStartPromise = null;
    }
    const rec = this.manualRecording;
    this.manualRecording = null;
    if (!rec) {
      this.resumeBuffer();
      return '';
    }
    try {
      const status = await rec.getStatusAsync().catch(() => null);
      // If the start only just completed (quick press/release), capture a short
      // tail so the clip isn't empty.
      const recordedMs = status && 'durationMillis' in status ? status.durationMillis ?? 0 : 0;
      if (recordedMs < 600) await delay(600 - recordedMs);
      if (status) {
        breadcrumb('audio', 'manual:record_status', {
          durationMs: status.durationMillis,
          metering: status.metering,
        });
      }
      await rec.stopAndUnloadAsync();
      const uri = rec.getURI();
      if (!uri) return '';
      const b64 = await FileSystem.readAsStringAsync(uri, {
        encoding: FileSystem.EncodingType.Base64,
      });
      await FileSystem.deleteAsync(uri, { idempotent: true });
      breadcrumb('audio', 'manual:record_done', { bytes: b64.length });
      return b64;
    } catch (err) {
      captureException(err, { stage: 'manual_record_stop' });
      await rec.stopAndUnloadAsync().catch(() => undefined);
      return '';
    } finally {
      this.resumeBuffer();
    }
  }
}

export const audioManager = new AudioManager();

// Backwards-compatible function exports.
export const playBase64Audio = (b64: string): Promise<void> =>
  audioManager.playBase64Audio(b64);
export const recordAudioBase64 = (durationMs: number): Promise<string> =>
  audioManager.recordAudioBase64(durationMs);
export const speakText = (text: string): Promise<void> => audioManager.speakText(text);
