import 'dart:async';
import 'dart:math';

import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:google_mobile_ads/google_mobile_ads.dart';
import 'package:quizroyale/core/network/api_client.dart';

/// Ödüllü reklam gösterim sonucu — çağıran akış (kalkan/altın) buna göre
/// karar verir.
enum AdRewardStatus {
  /// Kullanıcı reklamı sonuna kadar izledi ve ödülü HAK ETTİ. Ödül backend'e
  /// (`POST /api/ads/reward`) bildirildi.
  earned,

  /// Reklam gösterildi ama kullanıcı ödülü hak etmeden (erken) kapattı.
  dismissed,

  /// Reklam yüklü değildi / gösterilemedi / platform desteklemiyor (web).
  /// Çağıran taraf kullanıcıya nazikçe "reklam şu an yok" diyebilir.
  unavailable,
}

/// Ödüllü (rewarded) reklam servisi.
///
/// Yalnızca ÖDÜLLÜ reklam kullanılır (banner/geçiş YOK). Reklam önden yüklenir
/// (preload); [showRewarded] ile gösterilir; kullanıcı ödülü hak ederse ödül
/// backend'e bildirilir ve bir sonraki reklam yeniden yüklenir. Reklam
/// yüklenemezse/başarısızsa servis zarafetle döner — ASLA çökmez.
///
/// Web'de google_mobile_ads no-op'tur; tüm giriş noktaları [kIsWeb] ile
/// korunur, böylece web derlemesi/çalışması bozulmaz.
class AdService {
  AdService._();
  static final AdService instance = AdService._();

  // ───────────────────────────────────────────────────────────────────────
  // GERÇEK AdMob kimlikleri (üretim). AdMob hesabından alındı.
  //   - iOS App ID (Info.plist → GADApplicationIdentifier):
  //       ca-app-pub-1508388843514752~2964435608
  //   - iOS ödüllü birim kimliği (aşağıda):
  //       ca-app-pub-1508388843514752/4497009123
  // (Referans için Google test kimlikleri:
  //   App ID  test: ca-app-pub-3940256099942544~1458002511
  //   Rewarded test: ca-app-pub-3940256099942544/1712485313)
  // ───────────────────────────────────────────────────────────────────────
  static const String _rewardedAdUnitId =
      'ca-app-pub-1508388843514752/4497009123';

  RewardedAd? _rewardedAd;
  bool _isLoading = false;
  bool _isShowing = false;

  // ── GRANT SONUCU SÖZLEŞMESİ ────────────────────────────────────────────
  // showRewarded [AdRewardStatus.earned] dönse bile backend ödülü REDDETMİŞ
  // olabilir (ör. günlük cap → 400 "Bu reklam türü için günlük limite
  // ulaştınız"). Eskiden bu hata sessizce yutuluyor, UI "eklendi!" diyordu ama
  // bakiye değişmiyordu. Artık her showRewarded çağrısının POST sonucu bu iki
  // alanda yayınlanır; çağıran taraf earned SONRASI bunlara bakarak GERÇEĞİ
  // gösterir:
  //   - [lastGrantError] != null → backend reddetti; mesajı kullanıcıya göster,
  //     "+eklendi" DEME. (Backend'in Türkçe `detail` mesajı, yoksa genel hata.)
  //   - [lastGrantError] == null → grant başarılı; [lastGrantedCoins] backend'in
  //     verdiği coin miktarı (response.reward.coins). POST atlanan yerleşimlerde
  //     (shield) veya parse edilemezse null kalabilir.
  // Her showRewarded BAŞINDA ikisi de sıfırlanır (bayat değer taşınmaz).

  /// Son showRewarded çağrısında backend grant'i reddettiyse hata mesajı.
  String? lastGrantError;

  /// Son başarılı grant'te backend'in verdiği coin miktarı.
  int? lastGrantedCoins;

  /// Reklam gösterime hazır mı? (UI önceden buton durumu/etiketi ayarlayabilir.)
  bool get isReady => _rewardedAd != null;

  /// SDK başlatıldıktan sonra çağrılır: ilk ödüllü reklamı önden yükler.
  /// Web'de no-op. (MobileAds.instance.initialize main.dart'ta yapılır.)
  void init() {
    if (kIsWeb) return;
    _preload();
  }

  /// Bir sonraki ödüllü reklamı arka planda yükler. Zaten yükleniyor/yüklüyse
  /// tekrar denemez. Hata sessizce yutulur (sonraki showRewarded tekrar dener).
  void _preload() {
    if (kIsWeb || _isLoading || _rewardedAd != null) return;
    _isLoading = true;
    RewardedAd.load(
      adUnitId: _rewardedAdUnitId,
      // İZLEMESİZ (non-personalized) reklam iste: IDFA/kişiselleştirme yok →
      // App Tracking Transparency (ATT) izni İSTEMEYE GEREK KALMAZ ve App
      // Store gizlilik beyanında "Tracking: No" kalır. (Gelir bir miktar düşer
      // ama uyum + kullanıcı gizliliği önce gelir.)
      request: const AdRequest(nonPersonalizedAds: true),
      rewardedAdLoadCallback: RewardedAdLoadCallback(
        onAdLoaded: (ad) {
          _rewardedAd = ad;
          _isLoading = false;
        },
        onAdFailedToLoad: (error) {
          _rewardedAd = null;
          _isLoading = false;
          // Sessizce yut — reklam envanteri geçici olarak boş olabilir.
        },
      ),
    );
  }

  /// Ödüllü reklamı gösterir.
  ///
  /// Kullanıcı ödülü hak ederse (onUserEarnedReward) backend'e
  /// `POST /api/ads/reward {placement}` ile bildirir ve [AdRewardStatus.earned]
  /// döner. POST'un sonucu [lastGrantError]/[lastGrantedCoins] alanlarında
  /// yayınlanır (bkz. GRANT SONUCU SÖZLEŞMESİ) — earned dönmesi grant'in
  /// başarılı olduğu anlamına GELMEZ; çağıran bu alanları kontrol etmeli.
  /// Reklam yoksa/başarısızsa [AdRewardStatus.unavailable] döner
  /// (çağıran taraf kullanıcıyı bilgilendirebilir). Her durumda bir sonraki
  /// reklam yeniden yüklenir.
  ///
  /// [placement]: backend ödül türü — "gold" (+altın) veya "shield" (kalkan
  /// kredisi). Bakınız BACKEND SÖZLEŞMESİ.
  Future<AdRewardStatus> showRewarded({required String placement}) async {
    // Grant sonucu alanlarını sıfırla — önceki çağrının değeri taşınmasın
    // (bkz. GRANT SONUCU SÖZLEŞMESİ).
    lastGrantError = null;
    lastGrantedCoins = null;

    if (kIsWeb) return AdRewardStatus.unavailable;

    final ad = _rewardedAd;
    if (ad == null) {
      _preload(); // bir dahaki sefere hazır olsun
      return AdRewardStatus.unavailable;
    }
    if (_isShowing) return AdRewardStatus.unavailable;

    _isShowing = true;
    _rewardedAd = null; // tek kullanımlık — referansı hemen bırak

    final completer = Completer<AdRewardStatus>();
    var earned = false;

    ad.fullScreenContentCallback = FullScreenContentCallback(
      onAdDismissedFullScreenContent: (ad) {
        ad.dispose();
        _isShowing = false;
        if (!completer.isCompleted) {
          completer.complete(
              earned ? AdRewardStatus.earned : AdRewardStatus.dismissed);
        }
        _preload(); // sıradaki reklamı hazırla
      },
      onAdFailedToShowFullScreenContent: (ad, error) {
        ad.dispose();
        _isShowing = false;
        if (!completer.isCompleted) {
          completer.complete(AdRewardStatus.unavailable);
        }
        _preload();
      },
    );

    try {
      await ad.show(onUserEarnedReward: (_, __) {
        earned = true; // ödül hak edildi (bildirim dismiss sonrası yapılır)
      });
    } catch (_) {
      _isShowing = false;
      if (!completer.isCompleted) {
        completer.complete(AdRewardStatus.unavailable);
      }
      _preload();
    }

    final status = await completer.future;

    // Ödül hak edildiyse backend'e bildir. POST sonucu ARTIK YUTULMAZ:
    // başarı/başarısızlık [lastGrantedCoins]/[lastGrantError] üzerinden yayınlanır
    // (bkz. GRANT SONUCU SÖZLEŞMESİ) — çağıran taraf kullanıcıya gerçeği gösterir.
    // Eskiden `catch (_) {}` hatayı yutuyordu; kullanıcı reklamı izliyor, backend
    // (ör. günlük cap → 400) reddediyor, UI yine de "+altın eklendi!" diyordu.
    //
    // ⚠️ "shield" yerleşimini BURADAN bildirme: backend'de kalkan reklamı
    // /api/ads/reward'da DEĞİL, prepare-shield(source:"ad") içinden
    // verify_shield_ad ile doğrulanır (PLACEMENTS'te 'shield' yok → burada
    // 400 döner). Çağıran (shield_prompt_sheet) prepare-shield'ı zaten yapıyor.
    // Sadece coin veren yerleşimleri (gold vb.) bu uçtan bildiriyoruz.
    //
    // ÇİFT-GRANT KORUMASI (idempotency): her izleme için TEK bir nonce üret ve
    // gönder. Backend aynı nonce'u bir daha ödüllendirmez (Redis SET NX). Bu
    // nonce, POST tekrar gönderilse bile (Dio auth-interceptor'ı 401→token
    // yenileme sonrası aynı isteği YENİDEN atar; ağ tekrarları) aynı kaldığı
    // için ödül İKİ KEZ verilmez. Nonce OLMADAN backend'in idempotency guard'ı
    // atlanıyordu → özellikle oturumun İLK reklamında (bayat token → 401 →
    // retry) çift-grant oluyordu ("ilk sefer 2 katı" bug'ının kök nedeni).
    if (status == AdRewardStatus.earned && placement != 'shield') {
      try {
        final res = await ApiClient.instance.post(
          '/api/ads/reward',
          body: {'placement': placement, 'nonce': _newNonce()},
        );
        // Başarılı grant: backend'in verdiği miktarı yayınla
        // (response: {"granted": true, "reward": {"coins": N}, ...}).
        final reward = res['reward'];
        if (reward is Map && reward['coins'] is int) {
          lastGrantedCoins = reward['coins'] as int;
        }
      } on DioException catch (e) {
        // Backend reddetti (günlük cap, geçersiz placement, ağ hatası...).
        // Türkçe `detail` mesajını (varsa) çağırana taşı — UI gerçeği göstersin.
        lastGrantError = ApiClient.friendlyError(e);
      } catch (_) {
        lastGrantError = 'Ödül eklenemedi. Lütfen tekrar deneyin.';
      }
    }
    return status;
  }

  /// Ödüllü reklam ödülü için tek seferlik idempotency anahtarı (UUID v4).
  /// Kriptografik rastgelelikle üretilir; ek paket gerektirmez. Backend bu
  /// nonce'u Redis SET NX ile bir kez işler → aynı istek tekrar gelse bile
  /// altın İKİ KEZ eklenmez.
  static String _newNonce() {
    final rng = Random.secure();
    final bytes = List<int>.generate(16, (_) => rng.nextInt(256));
    // RFC 4122: sürüm 4 + variant bitleri.
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    String hex(int start, int end) => bytes
        .sublist(start, end)
        .map((b) => b.toRadixString(16).padLeft(2, '0'))
        .join();
    return '${hex(0, 4)}-${hex(4, 6)}-${hex(6, 8)}-${hex(8, 10)}-${hex(10, 16)}';
  }
}
