import 'package:flutter/services.dart';

class ScreenSecurity {
  static const _channel = MethodChannel('com.quizroyale/security');

  static Future<void> enableSecureMode() async {
    try {
      await _channel.invokeMethod('enableSecure');
    } catch (_) {}
  }

  static Future<void> disableSecureMode() async {
    try {
      await _channel.invokeMethod('disableSecure');
    } catch (_) {}
  }
}
