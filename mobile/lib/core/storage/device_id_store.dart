import 'dart:math';

import 'package:shared_preferences/shared_preferences.dart';

/// Misafir girişi için kalıcı cihaz kimliği.
///
/// İlk çağrıda UUID v4 formatında bir kimlik üretir ve shared_preferences'a
/// yazar; sonraki çağrılar hep aynı değeri döndürür. Böylece aynı cihazdan
/// yapılan misafir girişleri backend'de aynı hesaba bağlanır.
class DeviceIdStore {
  DeviceIdStore._();

  static const _key = 'guest_device_id';
  static String? _cached;

  /// Kalıcı cihaz kimliğini döndürür (yoksa üretip saklar).
  static Future<String> getOrCreate() async {
    final cached = _cached;
    if (cached != null) return cached;
    final prefs = await SharedPreferences.getInstance();
    var id = prefs.getString(_key);
    if (id == null || id.isEmpty) {
      id = _generateUuidV4();
      await prefs.setString(_key, id);
    }
    _cached = id;
    return id;
  }

  /// Kriptografik rastgelelikle UUID v4 üretir (ek paket gerektirmez).
  static String _generateUuidV4() {
    final rng = Random.secure();
    final bytes = List<int>.generate(16, (_) => rng.nextInt(256));
    // RFC 4122: version 4 + variant bitleri
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    String hex(int start, int end) => bytes
        .sublist(start, end)
        .map((b) => b.toRadixString(16).padLeft(2, '0'))
        .join();
    return '${hex(0, 4)}-${hex(4, 6)}-${hex(6, 8)}-${hex(8, 10)}-${hex(10, 16)}';
  }
}
