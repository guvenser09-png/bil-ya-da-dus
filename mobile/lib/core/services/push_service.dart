import 'dart:async';

import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart' show defaultTargetPlatform, TargetPlatform;
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:quizroyale/core/network/api_client.dart';
import 'package:quizroyale/core/router/app_router.dart';
import 'package:quizroyale/core/storage/secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Arka planda (uygulama kapalı/askıdayken) gelen bildirimleri işleyen
/// TOP-LEVEL handler. Firebase bunu ayrı bir izolatta çalıştırır → sınıf üyesi
/// olamaz ve `@pragma('vm:entry-point')` ŞART (release derlemesinde tree-shake
/// edilmesin diye).
///
/// Burada AĞIR İŞ YAPILMAZ: bildirimi zaten sistem gösterir; kullanıcı
/// dokununca yönlendirmeyi `onMessageOpenedApp` / `getInitialMessage` yapar.
@pragma('vm:entry-point')
Future<void> _firebaseBackgroundHandler(RemoteMessage message) async {
  // Bilinçli olarak boş: ileride sessiz (data-only) bildirimlerle önbellek
  // tazelemek istersek buraya eklenir. Hata fırlatmamalı.
}

/// Push bildirimi (FCM) altyapısı — Firebase kurulu DEĞİLSE zarifçe devre dışı.
///
/// ## Kimlik bilgisi yoksa ne olur?
/// `GoogleService-Info.plist` (iOS) / `google-services.json` (Android) yoksa
/// `Firebase.initializeApp()` istisna fırlatır. Bu istisna YUTULUR, [enabled]
/// false kalır ve TÜM push işlevleri sessizce no-op olur. Uygulama normal
/// çalışmaya devam eder. (Kurulum: docs/FIREBASE_KURULUM.md)
///
/// ## İzin NE ZAMAN istenir? (kritik retention kararı)
/// İlk açılışta İSTENMEZ. iOS'ta bildirim izni **tek şans**tır: kullanıcı bir
/// kez "İzin Verme" derse, uygulama içinden bir daha soramayız (yalnızca
/// Ayarlar'a yönlendirebiliriz). Uygulamayı henüz tanımayan birine soruşta
/// kabul oranı düşüktür.
///
/// Bu yüzden izin, oyuncu **ilk maçını bitirip sonuç ekranına düştüğünde**
/// istenir: oyunu tanımıştır, değer görmüştür, kabul oranı belirgin yüksektir.
/// Kanca noktası: `/result/:gameId` rotasını saran [PushPermissionGate]
/// (bkz. core/router/app_router.dart) → [onMatchFinished].
///
/// Sonuç ekranındaki NATIVE PUAN İSTEMİ ile çakışmaması özellikle gözetildi:
/// ReviewService en erken 2. maçtan sonra ve yalnızca KAZANINCA sorar; biz ise
/// İLK maç sonunda sorarız → iki sistem istemi asla üst üste binmez.
class PushService {
  PushService._();
  static final PushService instance = PushService._();

  // LAZY getter — ASLA alan başlatıcısı OLARAK erişme! `FirebaseMessaging.instance`
  // içeride `Firebase.app()` çağırır; Firebase.initializeApp() ÇALIŞMADAN önce
  // erişilirse istisna fırlatır. Alan başlatıcısı singleton kurulurken (main.dart
  // `PushService.instance` erişiminde) çalıştığından, bu istisna init()'in
  // try/catch'ine YAKALANMADAN main()'e sızıp runApp'tan önce uygulamayı ÇÖKERTİR
  // (BEYAZ EKRAN). Getter'la erişim ertelenir: tüm kullanım noktaları zaten
  // Firebase.initializeApp() başarıyla döndükten SONRA (init() içinde) veya
  // `_enabled` kontrolünün ardından çalışır.
  FirebaseMessaging get _messaging => FirebaseMessaging.instance;

  /// Firebase başarıyla başlatıldı mı? (plist yoksa false → her şey no-op)
  bool _enabled = false;
  bool get enabled => _enabled;

  bool _initialized = false;

  // --- SharedPreferences anahtarları ---
  static const String _prefAsked = 'push_permission_asked';
  static const String _prefMatchCount = 'push_match_count';
  static const String _prefLastAskMs = 'push_last_ask_ms';
  static const String _prefLastToken = 'push_last_synced_token';

  /// İzin isteği başarısız/atlanmışsa tekrar denemeden önce beklenecek gün.
  /// (Kullanıcı "İzin Verme" dediyse iOS zaten bir daha istem göstermez; bu
  /// throttle yalnızca "izin hiç sorulamadı" durumları içindir.)
  static const int _retryAfterDays = 7;

  /// Bildirim payload'ındaki `route` alanı yalnızca BU listede varsa kullanılır.
  /// Bilinmeyen rota gelirse '/home'a düşülür → go_router hata ekranı ASLA çıkmaz.
  /// (app_router.dart'taki rotalarla eşleşmeli.)
  static const Set<String> _knownRoutes = {
    '/home',
    '/daily',
    '/leaderboard',
    '/store',
    '/profile',
    '/friends',
    '/tournament',
    '/season',
    '/inventory',
    '/cosmetics',
    '/room',
  };

  /// Kampanya tipi → rota. Backend `data: {type, route}` gönderir; `route`
  /// tanınmazsa buraya, o da yoksa '/home'a düşeriz.
  ///
  /// • daily    → Günün Sorusu ekranı (tek dokunuşla oynasın).
  /// • streak   → günlük ödül ANA SAYFADA alınır (kart + dialog) → '/home'.
  /// • comeback → ana sayfa (oyuncu kendi seçsin).
  /// • game     → maça zorla sokmayız (matchmaking rızayla başlar) → '/home'.
  static const Map<String, String> _routeForType = {
    'streak': '/home',
    'daily': '/daily',
    'comeback': '/home',
    'game': '/home',
  };

  /// Uygulama açılışında ÇAĞRILIR (main.dart) — await EDİLMEZ.
  ///
  /// Açılışı yavaşlatmaz: ağ/izin işi yapmaz, yalnızca Firebase'i başlatıp
  /// dinleyicileri kurar. İzin İSTEMEZ (bkz. sınıf dokümantasyonu). Firebase
  /// yoksa sessizce devre dışı kalır.
  Future<void> init() async {
    if (_initialized) return;
    _initialized = true;

    try {
      await Firebase.initializeApp();
      _enabled = true;
    } catch (_) {
      // GoogleService-Info.plist yok / yapılandırma hatalı → push kapalı.
      _enabled = false;
      return;
    }

    try {
      FirebaseMessaging.onBackgroundMessage(_firebaseBackgroundHandler);

      // iOS: uygulama ÖN PLANDAYKEN de bildirim banner'ı görünsün.
      await _messaging.setForegroundNotificationPresentationOptions(
        alert: true,
        badge: true,
        sound: true,
      );

      // Bildirime dokunularak açıldı (uygulama arka plandaydı).
      FirebaseMessaging.onMessageOpenedApp.listen(_handleOpenedMessage);

      // Uygulama TAMAMEN KAPALIYKEN bildirime dokunuldu → açılış mesajı.
      final initialMessage = await _messaging.getInitialMessage();
      if (initialMessage != null) {
        _handleOpenedMessage(initialMessage);
      }

      // Token yenilenince backend'i güncelle (FCM token'ı zamanla değişebilir).
      _messaging.onTokenRefresh.listen((token) {
        _syncToken(token, force: true);
      });

      // İzin DAHA ÖNCE verilmişse (geri dönen kullanıcı) token'ı tazele.
      // Yeni izin İSTENMEZ — yalnızca mevcut durumu okuruz.
      final settings = await _messaging.getNotificationSettings();
      if (settings.authorizationStatus == AuthorizationStatus.authorized ||
          settings.authorizationStatus == AuthorizationStatus.provisional) {
        await _fetchAndSyncToken();
      }
    } catch (_) {
      // Dinleyici kurulumu asla açılışı bozmasın.
    }
  }

  /// Maç bitti (sonuç ekranına düşüldü) — izin isteme kancası.
  ///
  /// İlk maçtan sonra izni ister. Sonraki maçlarda: izin zaten sorulduysa
  /// hiçbir şey yapmaz; sorulamadıysa [_retryAfterDays] günde bir tekrar dener.
  Future<void> onMatchFinished() async {
    if (!_enabled) return;
    try {
      final prefs = await SharedPreferences.getInstance();
      final count = (prefs.getInt(_prefMatchCount) ?? 0) + 1;
      await prefs.setInt(_prefMatchCount, count);

      // Daha önce sorduysak bir daha sorma (iOS zaten ikinci kez göstermez).
      if (prefs.getBool(_prefAsked) ?? false) {
        return;
      }

      // Throttle: art arda denemeyelim.
      final lastAsk = prefs.getInt(_prefLastAskMs) ?? 0;
      if (lastAsk > 0) {
        final elapsed = DateTime.now().millisecondsSinceEpoch - lastAsk;
        if (elapsed < _retryAfterDays * 24 * 60 * 60 * 1000) return;
      }

      // Sonuç ekranı otursun, kutlama animasyonunun üstüne sistem istemi
      // bindirmeyelim; kullanıcı skorunu görsün, sonra soralım.
      await Future<void>.delayed(const Duration(milliseconds: 1800));

      await requestPermission();
    } catch (_) {
      // İzin akışı asla oyunu bozmasın.
    }
  }

  /// Bildirim iznini ister ve izin verilirse token'ı backend'e gönderir.
  /// Ayarlar ekranından da çağrılabilir. Firebase yoksa no-op → false.
  Future<bool> requestPermission() async {
    if (!_enabled) return false;
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setInt(_prefLastAskMs, DateTime.now().millisecondsSinceEpoch);

      final settings = await _messaging.requestPermission(
        alert: true,
        badge: true,
        sound: true,
      );

      // İstem gösterildi (kabul ya da ret) → bir daha sorma.
      await prefs.setBool(_prefAsked, true);

      final granted =
          settings.authorizationStatus == AuthorizationStatus.authorized ||
              settings.authorizationStatus == AuthorizationStatus.provisional;
      if (!granted) return false;

      await _fetchAndSyncToken();
      return true;
    } catch (_) {
      return false;
    }
  }

  /// Giriş (login / kayıt / misafir) BAŞARILI olduktan sonra çağrılır.
  ///
  /// Kullanıcı bildirimlere daha önce izin verdiyse (ör. cihazda başka bir
  /// hesapla oynadıysa) token'ı YENİ hesaba bağlar. İzin yoksa hiçbir şey
  /// yapmaz — burada izin İSTENMEZ (o iş ilk maç sonuna aittir).
  ///
  /// Bu olmasaydı: izin verilmiş ama oturum açılmamışken alınan token backend'e
  /// hiç ulaşmaz, kullanıcı bir sonraki açılışa kadar bildirim ALAMAZDI.
  Future<void> syncTokenAfterLogin() async {
    if (!_enabled) return;
    try {
      final settings = await _messaging.getNotificationSettings();
      final granted =
          settings.authorizationStatus == AuthorizationStatus.authorized ||
              settings.authorizationStatus == AuthorizationStatus.provisional;
      if (!granted) return;
      // force: token aynı olsa bile yeni kullanıcıya bağlanmalı.
      final token = await _messaging.getToken();
      if (token == null || token.isEmpty) return;
      await _syncToken(token, force: true);
    } catch (_) {}
  }

  /// FCM token'ını alıp backend'e kaydeder.
  Future<void> _fetchAndSyncToken() async {
    if (!_enabled) return;
    try {
      // iOS: APNs token'ı gelmeden getToken() null döner. Kısa bir bekleyişle
      // bir kez daha dene (uygulama yeni açıldıysa APNs kaydı sürüyor olabilir).
      var token = await _messaging.getToken();
      if (token == null) {
        await Future<void>.delayed(const Duration(seconds: 2));
        token = await _messaging.getToken();
      }
      if (token == null || token.isEmpty) return;
      await _syncToken(token);
    } catch (_) {}
  }

  /// Token'ı `POST /api/users/me/push-token` ile backend'e yazar.
  /// Aynı token tekrar tekrar gönderilmez ([force] ile zorlanabilir).
  Future<void> _syncToken(String token, {bool force = false}) async {
    try {
      // Oturum yoksa gönderme (uç auth'lu). Giriş sonrası init/izin akışı
      // token'ı zaten yeniden gönderir.
      if (!await SecureStorage.instance.isLoggedIn()) return;

      final prefs = await SharedPreferences.getInstance();
      if (!force && prefs.getString(_prefLastToken) == token) return;

      await ApiClient.instance.post(
        '/api/users/me/push-token',
        body: {
          'token': token,
          'platform': defaultTargetPlatform == TargetPlatform.android
              ? 'android'
              : 'ios',
        },
      );
      await prefs.setString(_prefLastToken, token);
    } catch (_) {
      // Ağ hatası → sessiz geç. Sonraki açılışta/yenilemede tekrar denenir.
    }
  }

  /// Çıkış (logout) akışında çağrılır: token'ı backend'den siler ki cihazı
  /// devralan bir sonraki kullanıcıya eski hesabın bildirimi gitmesin.
  /// (Hesap silmede sunucu zaten tüm token'ları temizler.)
  Future<void> clearToken() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final token = prefs.getString(_prefLastToken);
      await prefs.remove(_prefLastToken);
      if (token == null || token.isEmpty) return;

      await ApiClient.instance.delete(
        '/api/users/me/push-token',
        body: {
          'token': token,
          'platform': defaultTargetPlatform == TargetPlatform.android
              ? 'android'
              : 'ios',
        },
      );
    } catch (_) {
      // Çıkış akışı bu yüzden ASLA takılmasın.
    }
  }

  // --- Bildirime dokunma → yönlendirme (deep link) ---

  void _handleOpenedMessage(RemoteMessage message) {
    final route = _resolveRoute(message.data);
    _navigate(route);
  }

  /// Payload'dan güvenli bir rota çıkarır. Bilinmeyen her şey → '/home'.
  String _resolveRoute(Map<String, dynamic> data) {
    final route = (data['route'] ?? '').toString();
    if (_knownRoutes.contains(route)) return route;

    final type = (data['type'] ?? '').toString();
    return _routeForType[type] ?? '/home';
  }

  /// Router hazır olana kadar bekleyip yönlendirir.
  ///
  /// SOĞUK AÇILIŞ: uygulama kapalıyken bildirime dokunulursa navigator henüz
  /// kurulmamış olabilir (`currentContext == null`). Bu yüzden 300 ms aralıkla
  /// en fazla 10 kez (≈3 sn) yeniden denenir; olmazsa sessizce vazgeçilir
  /// (kullanıcı normal açılış ekranında kalır — hata YOK).
  void _navigate(String route, {int attempt = 0}) {
    final context = rootNavigatorKey.currentContext;
    if (context != null) {
      try {
        GoRouter.of(context).go(route);
      } catch (_) {}
      return;
    }
    if (attempt >= 10) return;
    Timer(
      const Duration(milliseconds: 300),
      () => _navigate(route, attempt: attempt + 1),
    );
  }
}

/// `/result/:gameId` rotasını saran görünmez kanca.
///
/// Sonuç ekranı dosyasına DOKUNMADAN "maç bitti" anını yakalar (o dosya başka
/// bir akışın sahipliğinde). Route bir kez kurulduğunda `initState` bir kez
/// çalışır → maç sayacı bir kez artar, ilk maçtan sonra bildirim izni istenir.
class PushPermissionGate extends StatefulWidget {
  const PushPermissionGate({super.key, required this.child});

  final Widget child;

  @override
  State<PushPermissionGate> createState() => _PushPermissionGateState();
}

class _PushPermissionGateState extends State<PushPermissionGate> {
  @override
  void initState() {
    super.initState();
    // Sonuç ekranının çizimini bloklamamak için ateşle-unut.
    unawaited(PushService.instance.onMatchFinished());
  }

  @override
  Widget build(BuildContext context) => widget.child;
}
