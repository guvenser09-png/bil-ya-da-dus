import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class SecureStorage {
  SecureStorage._();
  static final SecureStorage _instance = SecureStorage._();
  static SecureStorage get instance => _instance;

  static final _storage = FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
  );

  // In-memory fallback for web / environments where secure storage is unavailable
  static final Map<String, String> _memory = {};

  static const _keyAccess = 'access_token';
  static const _keyRefresh = 'refresh_token';
  static const _keyUserId = 'user_id';
  static const _keyUsername = 'username';

  Future<void> _write(String key, String value) async {
    _memory[key] = value;
    try {
      await _storage.write(key: key, value: value);
    } catch (_) {}
  }

  Future<String?> _read(String key) async {
    if (_memory.containsKey(key)) return _memory[key];
    try {
      final val = await _storage.read(key: key);
      if (val != null) _memory[key] = val;
      return val;
    } catch (_) {
      return null;
    }
  }

  Future<void> saveTokens({
    required String accessToken,
    required String refreshToken,
  }) async {
    await _write(_keyAccess, accessToken);
    await _write(_keyRefresh, refreshToken);
  }

  Future<String?> getAccessToken() => _read(_keyAccess);
  Future<String?> getRefreshToken() => _read(_keyRefresh);

  Future<void> saveUserInfo({required String userId, required String username}) async {
    await _write(_keyUserId, userId);
    await _write(_keyUsername, username);
  }

  Future<String?> getUserId() => _read(_keyUserId);
  Future<String?> getUsername() => _read(_keyUsername);

  Future<bool> isLoggedIn() async {
    final token = await _read(_keyAccess);
    return token != null && token.isNotEmpty;
  }

  Future<void> clearAll() async {
    _memory.clear();
    try {
      await _storage.deleteAll();
    } catch (_) {}
  }
}
