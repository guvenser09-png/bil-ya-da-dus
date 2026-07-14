import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:quizroyale/core/network/api_client.dart';
import 'package:quizroyale/core/services/push_service.dart';
import 'package:quizroyale/core/storage/device_id_store.dart';
import 'package:quizroyale/core/storage/secure_storage.dart';
import 'package:quizroyale/features/cosmetics/providers/cosmetics_provider.dart';
import 'package:quizroyale/features/daily/providers/daily_challenge_provider.dart';
import 'package:quizroyale/features/daily/providers/daily_provider.dart';
import 'package:quizroyale/features/friends/providers/friends_provider.dart';
import 'package:quizroyale/features/inventory/providers/inventory_provider.dart';
import 'package:quizroyale/features/leaderboard/providers/leaderboard_provider.dart';
import 'package:quizroyale/features/profile/providers/profile_provider.dart';
import 'package:quizroyale/features/quests/providers/quests_provider.dart';
import 'package:quizroyale/features/season/providers/season_provider.dart';
import 'package:quizroyale/features/store/providers/store_provider.dart';

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
  AuthNotifier(this._ref) : super(const AuthState()) {
    _checkLogin();
  }

  final Ref _ref;

  /// KÖK ÇÖZÜM (oturum sızıntısı): Kullanıcı-kapsamlı TÜM provider'ları
  /// geçersiz kıl. Bu provider'lar (profil, mağaza, sezon, sıralama, günlük
  /// ödül, kozmetik, envanter, arkadaşlar) constructor'larında bir kez veri
  /// yükleyip uygulama ömrü boyunca canlı kaldıkları için, çıkış yapıp farklı
  /// hesapla (veya misafir) girildiğinde ESKİ kullanıcının verisi ekranda
  /// kalıyordu. invalidate → notifier dispose edilir, bir sonraki watch'ta
  /// YENİ token ile sıfırdan yüklenir. Hem logout'ta hem her başarılı yeni
  /// girişte çağrılır (girişte de: önceki oturumun artığı kalmasın).
  void _resetUserScopedProviders() {
    _ref.invalidate(profileProvider);
    _ref.invalidate(otherProfileProvider);
    _ref.invalidate(storeProvider);
    _ref.invalidate(seasonProvider);
    _ref.invalidate(leaderboardProvider);
    _ref.invalidate(dailyProvider);
    // Günün 5 Sorusu + günlük görevler de kullanıcı-kapsamlı: hesap değişince
    // önceki oyuncunun serisi/ilerlemesi ekranda kalmasın.
    _ref.invalidate(dailyChallengeProvider);
    _ref.invalidate(questsProvider);
    _ref.invalidate(cosmeticsProvider);
    _ref.invalidate(inventoryProvider);
    _ref.invalidate(friendsProvider);
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
      // Yeni oturum: önceki kullanıcının cache'lenmiş state'i sızmasın.
      _resetUserScopedProviders();
      // Bildirim izni zaten verilmişse push token'ını YENİ hesaba bağla
      // (izin İSTEMEZ; izin ilk maç sonunda istenir). Girişi yavaşlatmasın.
      unawaited(PushService.instance.syncTokenAfterLogin());
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
      // Yeni oturum: önceki kullanıcının cache'lenmiş state'i sızmasın.
      _resetUserScopedProviders();
      // Bildirim izni zaten verilmişse push token'ını YENİ hesaba bağla
      // (izin İSTEMEZ; izin ilk maç sonunda istenir). Girişi yavaşlatmasın.
      unawaited(PushService.instance.syncTokenAfterLogin());
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

  /// Misafir olarak giriş: kalıcı device_id ile /api/auth/guest çağrılır.
  /// Aynı cihazdan tekrar girişte backend aynı hesabı döndürür; token
  /// saklama/oto-login akışı normal girişle birebir aynıdır.
  Future<bool> guestLogin() async {
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      final deviceId = await DeviceIdStore.getOrCreate();
      final data = await ApiClient.instance.post('/api/auth/guest', body: {
        'device_id': deviceId,
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
      // Yeni (misafir) oturum: önceki kullanıcının verisi ekranda kalmasın.
      _resetUserScopedProviders();
      // Bildirim izni zaten verilmişse push token'ını bu hesaba bağla.
      unawaited(PushService.instance.syncTokenAfterLogin());
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

  /// Misafir hesabı kalıcılaştır (email + şifre + opsiyonel yeni username).
  /// Başarıda user state'i backend yanıtıyla tazelenir (is_guest=false olur).
  Future<bool> claimAccount({
    required String email,
    required String password,
    String? username,
  }) async {
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      final body = <String, dynamic>{
        'email': email.trim(),
        'password': password,
      };
      if (username != null && username.trim().isNotEmpty) {
        body['username'] = username.trim();
      }
      final user = await ApiClient.instance.post('/api/auth/claim', body: body);
      try {
        await SecureStorage.instance.saveUserInfo(
          userId: user['id'].toString(),
          username: user['username'] as String,
        );
      } catch (_) {}
      state = state.copyWith(isLoading: false, user: user);
      // Hesap kalıcılaştı (is_guest=false): misafir olarak yüklenmiş
      // ekran verileri (sıralama guest_hidden vb.) tazelensin.
      _resetUserScopedProviders();
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

  Future<void> logout() async {
    // Push token'ını ÖNCE sil (auth token hâlâ geçerliyken): cihazı devralan
    // bir sonraki kullanıcıya eski hesabın bildirimi gitmesin.
    await PushService.instance.clearToken();
    try {
      await ApiClient.instance.post('/api/auth/logout');
    } catch (_) {}
    // Token + kullanıcı bilgisi (userId/username) tamamen silinir.
    await SecureStorage.instance.clearAll();
    state = const AuthState();
    // Çıkışta TÜM kullanıcı-kapsamlı state temizlenir — "çıkış yaptım ama
    // eski profil duruyor" hatasının kök çözümü.
    _resetUserScopedProviders();
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
      // Hesap silindi: kullanıcı-kapsamlı tüm state de temizlensin.
      _resetUserScopedProviders();
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
  (ref) => AuthNotifier(ref),
);
