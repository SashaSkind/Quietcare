import { Audio } from 'expo-av';
import * as FileSystem from 'expo-file-system';
import { breadcrumb, captureException } from '../sentry';

let permissionGranted = false;

async function ensurePermission(): Promise<boolean> {
  if (permissionGranted) return true;
  const { granted } = await Audio.requestPermissionsAsync();
  permissionGranted = granted;
  return granted;
}

/**
 * Play a base64-encoded audio clip (WAV/Opus) through the speaker.
 * Writes the payload to a cache file first because Android playback from
 * data: URIs is unreliable.
 */
export async function playBase64Audio(audioB64: string): Promise<void> {
  breadcrumb('audio', 'speak:play_start', { bytes: audioB64.length });
  await Audio.setAudioModeAsync({
    allowsRecordingIOS: false,
    playsInSilentModeIOS: true,
  });

  const uri = `${FileSystem.cacheDirectory}qc-speak-${Date.now()}.wav`;
  await FileSystem.writeAsStringAsync(uri, audioB64, {
    encoding: FileSystem.EncodingType.Base64,
  });

  const { sound } = await Audio.Sound.createAsync({ uri }, { shouldPlay: true });

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
}

/**
 * Record from the microphone for `durationMs`, returning the clip as base64.
 */
export async function recordAudioBase64(durationMs: number): Promise<string> {
  breadcrumb('audio', 'listen:record_start', { durationMs });
  const granted = await ensurePermission();
  if (!granted) {
    throw new Error('Microphone permission denied');
  }

  await Audio.setAudioModeAsync({
    allowsRecordingIOS: true,
    playsInSilentModeIOS: true,
  });

  const recording = new Audio.Recording();
  await recording.prepareToRecordAsync(
    Audio.RecordingOptionsPresets.HIGH_QUALITY,
  );
  await recording.startAsync();

  await new Promise<void>((resolve) => setTimeout(resolve, durationMs));

  await recording.stopAndUnloadAsync();
  const uri = recording.getURI();
  if (!uri) {
    throw new Error('Recording produced no file URI');
  }

  const b64 = await FileSystem.readAsStringAsync(uri, {
    encoding: FileSystem.EncodingType.Base64,
  });
  await FileSystem.deleteAsync(uri, { idempotent: true });
  breadcrumb('audio', 'listen:record_done', { bytes: b64.length });
  return b64;
}
