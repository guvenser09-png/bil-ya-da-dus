import 'dart:async';

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
  // TODO(admob): gerçek AdMob kimlikleriyle değiştir.
  // Aşağıdaki değer GOOGLE'IN RESMİ TEST ödüllü reklam birim kimliğidir.
  // App Store'a çıkmadan önce AdMob hesabından alınan GERÇEK ödüllü reklam
  // birim kimliğiyle değiştirilmeli. Ayrıca App ID de değiştirilmeli:
  //   - iOS App ID (Info.plist → GADApplicationIdentifier):
  //       test:   ca-app-pub-3940256099942544~1458002511
  //   - iOS ödüllü birim kimliği (aşağıda):
  //       test:   ca-app-pub-3940256099942544/1712485313
  // ───────────────────────────────────────────────────────────────────────
  static const String _rewardedAdUnitId =
      'ca-app-pub-3940256099942544/1712485313';

  RewardedAd? _rewardedAd;
  bool _isLoading = false;
  bool _isShowing = false;

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
  /// döner. Reklam yoksa/başarısızsa [AdRewardStatus.unavailable] döner
  /// (çağıran taraf kullanıcıyı bilgilendirebilir). Her durumda bir sonraki
  /// reklam yeniden yüklenir.
  ///
  /// [placement]: backend ödül türü — "gold" (+altın) veya "shield" (kalkan
  /// kredisi). Bakınız BACKEND SÖZLEŞMESİ.
  Future<AdRewardStatus> showRewarded({required String placement}) async {
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

    // Ödül hak edildiyse backend'e bildir. Ağ hatası olursa yut — kullanıcı
    // reklamı izledi; çağıran taraf bakiyeyi/prepare-shield'ı zaten tazeleyecek.
    //
    // ⚠️ "shield" yerleşimini BURADAN bildirme: backend'de kalkan reklamı
    // /api/ads/reward'da DEĞİL, prepare-shield(source:"ad") içinden
    // verify_shield_ad ile doğrulanır (PLACEMENTS'te 'shield' yok → burada
    // 400 döner). Çağıran (shield_prompt_sheet) prepare-shield'ı zaten yapıyor.
    // Sadece coin veren yerleşimleri (gold vb.) bu uçtan bildiriyoruz.
    if (status == AdRewardStatus.earned && placement != 'shield') {
      try {
        await ApiClient.instance
            .post('/api/ads/reward', body: {'placement': placement});
      } catch (_) {}
    }
    return status;
  }
}
