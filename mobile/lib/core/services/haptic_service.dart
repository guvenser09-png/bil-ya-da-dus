import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';

class HapticService {
  static final HapticService _i = HapticService._();
  factory HapticService() => _i;
  HapticService._();

  static bool _enabled = true;
  static const String _prefKey = 'haptic_enabled';

  bool get enabled => _enabled;

  Future<void> init() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      _enabled = prefs.getBool(_prefKey) ?? true;
    } catch (_) {}
  }

  Future<void> setEnabled(bool value) async {
    _enabled = value;
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setBool(_prefKey, value);
    } catch (_) {}
  }

  Future<void> correctAnswer() async {
    if (!_enabled) return;
    try {
      await HapticFeedback.lightImpact();
    } catch (_) {}
  }

  Future<void> wrongAnswer() async {
    if (!_enabled) return;
    try {
      await HapticFeedback.heavyImpact();
    } catch (_) {}
  }

  Future<void> elimination() async {
    if (!_enabled) return;
    try {
      await HapticFeedback.vibrate();
    } catch (_) {}
  }

  Future<void> sliderTick() async {
    if (!_enabled) return;
    try {
      await HapticFeedback.selectionClick();
    } catch (_) {}
  }

  Future<void> buttonTap() async {
    if (!_enabled) return;
    try {
      await HapticFeedback.selectionClick();
    } catch (_) {}
  }

  Future<void> win() async {
    if (!_enabled) return;
    try {
      await HapticFeedback.vibrate();
      await Future.delayed(const Duration(milliseconds: 200));
      await HapticFeedback.vibrate();
      await Future.delayed(const Duration(milliseconds: 200));
      await HapticFeedback.vibrate();
    } catch (_) {}
  }
}
