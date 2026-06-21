import React from 'react';
import { RootNavigator } from './src/app/RootNavigator';

// Native entry (Metro resolves App.native.tsx on iOS/Android). Renders the
// role-based demo: a login screen with one-tap Caretaker (Jack) and Elder
// (Margaret) accounts. Caretaker -> in-app dashboard; Elder -> the Halo
// companion with REAL on-device accelerometer fall detection (expo-sensors).
//
// Everything here uses Expo-Go-safe modules (no react-native-fast-tflite /
// camera), so it runs from the `expo start` QR with no custom dev client.
export default function App() {
  return <RootNavigator />;
}
