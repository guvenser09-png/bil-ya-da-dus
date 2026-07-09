import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';

class HapticService {
  static final HapticService _i = HapticService._();
  factory HapticService() => _i;
  HapticService._();

  static bool _enabled = true;
  static const String _prefKey = 'haptic_enabled';

  bool get enabled => _enabled;

  /// Tembel başlatma — ilk titreşim çağrısında ayar prefs'ten okunur; init
  /// unutulsa bile kullanıcının titreşim tercihi her zaman uygulanır.
  bool _initialized = false;
  Future<void>? _initFuture;

  Future<void> init() async {
    if (_initialized) return;
    _initFuture ??= _doInit();
    await _initFuture;
  }

  Future<void> _doInit() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      _enabled = prefs.getBool(_prefKey) ?? true;
    } catch (_) {}
    _initialized = true;
  }

  Future<void> setEnabled(bool value) async {
    _enabled = value;
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setBool(_prefKey, value);
    } catch (_) {}
  }

  Future<void> correctAnswer() async {
    await init();
    if (!_enabled) return;
    try {
      await HapticFeedback.lightImpact();
    } catch (_) {}
  }

  Future<void> wrongAnswer() async {
    await init();
    if (!_enabled) return;
    try {
      // Orta şiddet — yanlış cevap can sıkıcı ama cezalandırıcı olmasın.
      await HapticFeedback.mediumImpact();
    } catch (_) {}
  }

  Future<void> elimination() async {
    await init();
    if (!_enabled) return;
    try {
      // Güçlü his: tam titreşim + ağır darbe (trapdoor düşüşü).
      await HapticFeedback.vibrate();
      await HapticFeedback.heavyImpact();
    } catch (_) {}
  }

  Future<void> sliderTick() async {
    await init();
    if (!_enabled) return;
    try {
      await HapticFeedback.selectionClick();
    } catch (_) {}
  }

  Future<void> buttonTap() async {
    await init();
    if (!_enabled) return;
    try {
      await HapticFeedback.selectionClick();
    } catch (_) {}
  }

  Future<void> win() async {
    await init();
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
