import { Audio } from 'expo-av';
import * as FileSystem from 'expo-file-system';
import { AUDIO_BUFFER } from '../config';
import { breadcrumb, captureException } from '../sentry';

const delay = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

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
  private ring: string[] = [];
  // Resolvers used to interrupt the segment sleep early (on pause/stop).
  private wakeups: Array<() => void> = [];
  private loopPromise: Promise<void> | null = null;

  private async ensurePermission(): Promise<boolean> {
    if (this.permissionGranted) return true;
    const { granted } = await Audio.requestPermissionsAsync();
    this.permissionGranted = granted;
    return granted;
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
      try {
        await Audio.setAudioModeAsync({
          allowsRecordingIOS: true,
          playsInSilentModeIOS: true,
        });
        const rec = new Audio.Recording();
        await rec.prepareToRecordAsync(Audio.RecordingOptionsPresets.HIGH_QUALITY);
        await rec.startAsync();
        this.current = rec;

        await this.interruptibleSleep(AUDIO_BUFFER.segmentMs);

        // Stop and harvest the segment.
        if (this.current === rec) {
          await rec.stopAndUnloadAsync();
          this.current = null;
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
        }
      } catch (err) {
        this.current = null;
        captureException(err, { stage: 'rolling_buffer' });
        await this.interruptibleSleep(500);
      }
    }
    breadcrumb('audio', 'buffer:stopped');
  }

  private pushSegment(b64: string): void {
    this.ring.push(b64);
    while (this.ring.length > AUDIO_BUFFER.ringSize) this.ring.shift();
  }

  /** Most recent buffered segment (the pre-trigger audio), or null if empty. */
  getRecentAudioB64(): string | null {
    return this.ring.length > 0 ? this.ring[this.ring.length - 1] : null;
  }

  // ---- Mic arbitration ----

  private async pauseBuffer(): Promise<void> {
    if (!this.running) return;
    this.paused = true;
    this.wake();
    // Wait until the loop has released the mic.
    let waited = 0;
    while (this.current !== null && waited < 5_000) {
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
      await Audio.setAudioModeAsync({
        allowsRecordingIOS: false,
        playsInSilentModeIOS: true,
      });

      const uri = `${FileSystem.cacheDirectory}qc-speak-${Date.now()}.wav`;
      await FileSystem.writeAsStringAsync(uri, audioB64, {
        encoding: FileSystem.EncodingType.Base64,
      });

      const { sound } = await Audio.Sound.createAsync(
        { uri },
        { shouldPlay: true },
      );

      await new Promise<void>((resolve) => {
        sound.setOnPlaybackStatusUpdate((status) => {
          if (status.isLoaded && status.didJustFinish) {
            resolve();
          } else if (!status.isLoaded && status.error) {
            captureException(new Error(`playback error: ${status.error}`));
            resolve();
          }
        });
      });

      await sound.unloadAsync();
      await FileSystem.deleteAsync(uri, { idempotent: true });
      breadcrumb('audio', 'speak:play_done');
    } finally {
      this.resumeBuffer();
    }
  }

  /** Record from the mic for `durationMs`, returning the clip as base64. */
  async recordAudioBase64(durationMs: number): Promise<string> {
    breadcrumb('audio', 'listen:record_start', { durationMs });
    const granted = await this.ensurePermission();
    if (!granted) throw new Error('Microphone permission denied');

    await this.pauseBuffer();
    try {
      await Audio.setAudioModeAsync({
        allowsRecordingIOS: true,
        playsInSilentModeIOS: true,
      });

      const recording = new Audio.Recording();
      await recording.prepareToRecordAsync(
        Audio.RecordingOptionsPresets.HIGH_QUALITY,
      );
      await recording.startAsync();

      await delay(durationMs);

      await recording.stopAndUnloadAsync();
      const uri = recording.getURI();
      if (!uri) throw new Error('Recording produced no file URI');

      const b64 = await FileSystem.readAsStringAsync(uri, {
        encoding: FileSystem.EncodingType.Base64,
      });
      await FileSystem.deleteAsync(uri, { idempotent: true });
      breadcrumb('audio', 'listen:record_done', { bytes: b64.length });
      return b64;
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
