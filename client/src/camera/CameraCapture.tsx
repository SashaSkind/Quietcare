import { CameraView, useCameraPermissions } from 'expo-camera';
import { useEffect, useRef } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { cameraManager } from './cameraManager';
import { breadcrumb, captureException } from '../sentry';

/**
 * A small always-mounted front-facing camera. It keeps the camera ready so that
 * when a trigger fires we can grab a single still (frame_b64) for the caretaker.
 * Rendered as a tiny corner preview so it's visible that capture is live.
 */
export function CameraCapture() {
  const cameraRef = useRef<CameraView>(null);
  const readyRef = useRef(false);
  const [permission, requestPermission] = useCameraPermissions();

  useEffect(() => {
    if (permission && !permission.granted && permission.canAskAgain) {
      void requestPermission();
    }
  }, [permission, requestPermission]);

  useEffect(() => {
    cameraManager.register(async () => {
      if (!cameraRef.current || !readyRef.current) return null;
      breadcrumb('camera', 'capture_start');
      const photo = await cameraRef.current.takePictureAsync({
        base64: true,
        quality: 0.3,
        skipProcessing: true,
      });
      breadcrumb('camera', 'capture_done', {
        bytes: photo?.base64?.length ?? 0,
      });
      return photo?.base64 ?? null;
    });
    return () => cameraManager.register(null);
  }, []);

  if (!permission?.granted) {
    return null;
  }

  return (
    <View style={styles.wrap} pointerEvents="none">
      <CameraView
        ref={cameraRef}
        style={styles.cam}
        facing="front"
        onCameraReady={() => {
          readyRef.current = true;
          breadcrumb('camera', 'ready');
        }}
        onMountError={(e) =>
          captureException(new Error(`camera mount error: ${e.message}`))
        }
      />
      <Text style={styles.label}>cam</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    position: 'absolute',
    top: 8,
    right: 8,
    width: 56,
    height: 74,
    borderRadius: 8,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: '#334155',
    zIndex: 10,
  },
  cam: {
    flex: 1,
  },
  label: {
    position: 'absolute',
    bottom: 0,
    right: 2,
    color: '#e2e8f0',
    fontSize: 9,
  },
});
