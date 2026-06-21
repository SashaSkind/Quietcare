// Metro config extending Expo's defaults so the bundler treats `.tflite` model
// files as assets (required by react-native-fast-tflite). Without this, a
// `require('....tflite')` won't resolve.

const { getDefaultConfig } = require('expo/metro-config');

const config = getDefaultConfig(__dirname);

if (!config.resolver.assetExts.includes('tflite')) {
  config.resolver.assetExts.push('tflite');
}

module.exports = config;
