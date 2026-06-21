// Bridges the always-mounted CameraCapture component to the trigger flow.
// The component registers a capturer; the hook calls captureFrameB64() when a
// trigger fires to attach a snapshot (frame_b64) to the event.

type FrameCapturer = () => Promise<string | null>;

let capturer: FrameCapturer | null = null;

export const cameraManager = {
  /** Called by CameraCapture once the camera is ready (null to unregister). */
  register(fn: FrameCapturer | null): void {
    capturer = fn;
  },

  get isReady(): boolean {
    return capturer !== null;
  },

  /** Capture a single still as base64 JPEG, or null if unavailable. */
  async captureFrameB64(): Promise<string | null> {
    if (!capturer) return null;
    try {
      return await capturer();
    } catch {
      return null;
    }
  },
};
