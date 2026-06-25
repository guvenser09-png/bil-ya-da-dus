import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:quizroyale/core/network/api_client.dart';
import 'package:quizroyale/core/storage/secure_storage.dart';

class AuthState {
  const AuthState({
    this.isLoading = false,
    this.error,
    this.user,
    this.isLoggedIn = false,
  });

  final bool isLoading;
  final String? error;
  final Map<String, dynamic>? user;
  final bool isLoggedIn;

  AuthState copyWith({
    bool? isLoading,
    String? error,
    Map<String, dynamic>? user,
    bool? isLoggedIn,
    bool clearError = false,
  }) {
    return AuthState(
      isLoading: isLoading ?? this.isLoading,
      error: clearError ? null : (error ?? this.error),
      user: user ?? this.user,
      isLoggedIn: isLoggedIn ?? this.isLoggedIn,
    );
  }
}

class AuthNotifier extends StateNotifier<AuthState> {
  AuthNotifier() : super(const AuthState()) {
    _checkLogin();
  }

  Future<void> _checkLogin() async {
    final loggedIn = await SecureStorage.instance.isLoggedIn();
    if (loggedIn) {
      state = state.copyWith(isLoggedIn: true);
      try {
        final user = await ApiClient.instance.get('/api/users/me');
        state = state.copyWith(user: user);
      } catch (_) {}
    }
  }

  Future<bool> login(String username, String password) async {
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      final data = await ApiClient.instance.post('/api/auth/login', body: {
        'username_or_email': username,
        'password': password,
      });
      try {
        await SecureStorage.instance.saveTokens(
          accessToken: data['access_token'] as String,
          refreshToken: data['refresh_token'] as String,
        );
        await SecureStorage.instance.saveUserInfo(
          userId: data['user']['id'].toString(),
          username: data['user']['username'] as String,
        );
      } catch (_) {}
      state = state.copyWith(
        isLoading: false,
        isLoggedIn: true,
        user: data['user'] as Map<String, dynamic>,
      );
      return true;
    } on DioException catch (e) {
      state = state.copyWith(
        isLoading: false,
        error: ApiClient.friendlyError(e),
      );
      return false;
    } catch (e) {
      state = state.copyWith(
        isLoading: false,
        error: 'Bir hata oluştu. Lütfen tekrar deneyin.',
      );
      return false;
    }
  }

  Future<bool> register(String username, String email, String password) async {
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      final data = await ApiClient.instance.post('/api/auth/register', body: {
        'username': username,
        'email': email,
        'password': password,
      });
      try {
        await SecureStorage.instance.saveTokens(
          accessToken: data['access_token'] as String,
          refreshToken: data['refresh_token'] as String,
        );
        await SecureStorage.instance.saveUserInfo(
          userId: data['user']['id'].toString(),
          username: data['user']['username'] as String,
        );
      } catch (_) {}
      state = state.copyWith(
        isLoading: false,
        isLoggedIn: true,
        user: data['user'] as Map<String, dynamic>,
      );
      return true;
    } on DioException catch (e) {
      state = state.copyWith(
        isLoading: false,
        error: ApiClient.friendlyError(e),
      );
      return false;
    } catch (e) {
      state = state.copyWith(
        isLoading: false,
        error: 'Bir hata oluştu. Lütfen tekrar deneyin.',
      );
      return false;
    }
  }

  Future<void> logout() async {
    try {
      await ApiClient.instance.post('/api/auth/logout');
    } catch (_) {}
    await SecureStorage.instance.clearAll();
    state = const AuthState();
  }

  /// Şifremi unuttum — e-postaya sıfırlama bağlantısı gönderir.
  /// Kullanıcı var olsa da olmasa da backend aynı yanıtı döner (güvenlik).
  /// DEBUG'da geliştirme kolaylığı için `debug_token` döndürülebilir;
  /// başarılıysa o token'ı (veya null) döndürürüz, hata varsa exception fırlatır.
  Future<String?> forgotPassword(String email) async {
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      final data = await ApiClient.instance.post(
        '/api/auth/forgot-password',
        body: {'email': email.trim()},
      );
      state = state.copyWith(isLoading: false);
      return data['debug_token'] as String?;
    } on DioException catch (e) {
      state = state.copyWith(isLoading: false, error: ApiClient.friendlyError(e));
      rethrow;
    } catch (e) {
      state = state.copyWith(
        isLoading: false,
        error: 'Bir hata oluştu. Lütfen tekrar deneyin.',
      );
      rethrow;
    }
  }

  /// Sıfırlama token'ı + yeni şifre ile şifreyi günceller.
  Future<bool> resetPassword(String token, String newPassword) async {
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      await ApiClient.instance.post(
        '/api/auth/reset-password',
        body: {'token': token.trim(), 'new_password': newPassword},
      );
      state = state.copyWith(isLoading: false);
      return true;
    } on DioException catch (e) {
      state = state.copyWith(isLoading: false, error: ApiClient.friendlyError(e));
      return false;
    } catch (e) {
      state = state.copyWith(
        isLoading: false,
        error: 'Bir hata oluştu. Lütfen tekrar deneyin.',
      );
      return false;
    }
  }

  /// Oturum açmış kullanıcıya e-posta doğrulama bağlantısı gönderir.
  Future<bool> sendVerification() async {
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      await ApiClient.instance.post('/api/auth/send-verification');
      state = state.copyWith(isLoading: false);
      return true;
    } on DioException catch (e) {
      state = state.copyWith(isLoading: false, error: ApiClient.friendlyError(e));
      return false;
    } catch (e) {
      state = state.copyWith(
        isLoading: false,
        error: 'Bir hata oluştu. Lütfen tekrar deneyin.',
      );
      return false;
    }
  }

  /// Hesabı kalıcı olarak siler/anonimleştirir (GERİ ALINAMAZ).
  /// Başarılı olursa local oturumu temizler ve state'i sıfırlar.
  Future<bool> deleteAccount() async {
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      await ApiClient.instance.delete('/api/users/me');
      await SecureStorage.instance.clearAll();
      state = const AuthState();
      return true;
    } on DioException catch (e) {
      state = state.copyWith(isLoading: false, error: ApiClient.friendlyError(e));
      return false;
    } catch (e) {
      state = state.copyWith(
        isLoading: false,
        error: 'Bir hata oluştu. Lütfen tekrar deneyin.',
      );
      return false;
    }
  }

  /// Kullanıcı profilini (bakiye/altın dâhil) backend'den tazeler.
  /// Üst bar bakiyesini güncel tutmak için satın alma/turnuva girişi sonrası
  /// çağrılır. Hata olursa mevcut state korunur.
  Future<void> refreshUser() async {
    try {
      final user = await ApiClient.instance.get('/api/users/me');
      state = state.copyWith(user: user);
    } catch (_) {}
  }

  void clearError() => state = state.copyWith(clearError: true);
}

final authProvider = StateNotifierProvider<AuthNotifier, AuthState>(
  (_) => AuthNotifier(),
);
