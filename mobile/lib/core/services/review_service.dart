import 'package:in_app_review/in_app_review.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Apple'ın onayladığı NATIVE "uygulamaya puan ver" istemini (iOS'ta
/// SKStoreReviewController; Android'de In-App Review API) DOĞRU ANDA tetikler.
///
/// KURAL (Apple): puan/yorum karşılığında ÖDÜL (altın vb.) VERİLMEZ — teşvikli
/// derecelendirme yasaktır. Biz yalnızca istemi göstermeyi isteriz; istemin
/// gerçekten çıkıp çıkmayacağına ve kaç kez çıkacağına (yılda ~3) iOS karar
/// verir. requestReview() sessizce hiçbir şey yapmayabilir — bu NORMALDİR,
/// hata değildir. Bu yüzden istemi yalnızca POZİTİF anlarda (maç kazanınca)
/// ve kendi kotamızla kısıtlayarak tetikleriz.
class ReviewService {
  static final ReviewService _i = ReviewService._();
  factory ReviewService() => _i;
  ReviewService._();

  final InAppReview _inAppReview = InAppReview.instance;

  // Prefs anahtarları.
  static const String _prefKeyMatchCount = 'review_match_count';
  static const String _prefKeyLastPrompt = 'review_last_prompt_ms';

  // Ayarlanabilir eşikler.
  static const int _minMatches = 2; // en az 2 maç oynamadan sorma
  static const int _throttleDays = 60; // iki istem arası minimum gün

  // Aynı OTURUMDA (uygulama açık kaldığı sürece) yalnızca bir kez sor.
  bool _askedThisSession = false;

  /// Bir maçın bittiğini kaydeder — oyuncunun toplam oynadığı maç sayısını
  /// artırır. Sonuç ekranı, kazansın kaybetsin her maç sonunda çağırmalı ki
  /// "en az 2 maç" koşulu doğru sayılsın.
  Future<void> recordMatchPlayed() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final count = prefs.getInt(_prefKeyMatchCount) ?? 0;
      await prefs.setInt(_prefKeyMatchCount, count + 1);
    } catch (_) {}
  }

  /// SADECE POZİTİF ANDA (maç kazanınca, kutlama oturduktan sonra) çağrılmalı.
  /// Tüm koşullar sağlanırsa native puan istemini talep eder. Kaybeden
  /// oyuncuda ASLA çağrılmaz (çağıran taraf bu kararı verir).
  ///
  /// Koşullar:
  ///  • Cihaz/mağaza istemi destekliyor olmalı (isAvailable).
  ///  • Oyuncu en az [_minMatches] maç oynamış olmalı (çok erken sorma).
  ///  • Son istemin üstünden en az [_throttleDays] gün geçmiş olmalı.
  ///  • Aynı oturumda daha önce sorulmamış olmalı.
  Future<void> maybeAskForReview() async {
    // Aynı oturumda tekrar deneme.
    if (_askedThisSession) return;

    try {
      // Native istem bu cihazda/mağazada mevcut mu? (Web'de no-op → false.)
      if (!await _inAppReview.isAvailable()) return;

      final prefs = await SharedPreferences.getInstance();

      // 1) En az _minMatches maç oynanmış olmalı.
      final matchCount = prefs.getInt(_prefKeyMatchCount) ?? 0;
      if (matchCount < _minMatches) return;

      // 2) Kendi throttle'ımız: son istemin üstünden yeterli gün geçti mi?
      //    (Apple zaten yılda ~3 ile sınırlar; biz de üstüne kendimiz kısarız.)
      final lastMs = prefs.getInt(_prefKeyLastPrompt) ?? 0;
      if (lastMs > 0) {
        final elapsed = DateTime.now().millisecondsSinceEpoch - lastMs;
        if (elapsed < _throttleDays * 24 * 60 * 60 * 1000) return;
      }

      // Bu oturumda artık sorduk say (istem çıkmasa da tekrar denemeyelim).
      _askedThisSession = true;

      // Native istemi talep et. iOS istemi GÖSTERMEYEBİLİR (kotayı kendisi
      // yönetir) — bu normal, hata sayma.
      await _inAppReview.requestReview();

      // Son gösterim tarihini kaydet (throttle için). requestReview'in gerçekte
      // istem gösterip göstermediğini API bildirmez; en güvenli varsayım "istendi
      // → tarihi güncelle" (aksi halde her kazançta tekrar tetiklenir).
      await prefs.setInt(
          _prefKeyLastPrompt, DateTime.now().millisecondsSinceEpoch);
    } catch (_) {
      // Sessizce yut — puan istemi asla oyunu bozacak bir hata fırlatmamalı.
    }
  }
}
