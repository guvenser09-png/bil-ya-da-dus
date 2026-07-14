import 'package:shared_preferences/shared_preferences.dart';

/// Maç sonu "hesabını kaydet" davetinin GÖSTERME KURALLARI.
///
/// Neden: oyuncuların çoğu misafir; misafirler sıralamada gizli olduğu için
/// oyunun en güçlü tutunma aracının (sıralamada yükselme hırsı) dışındalar.
/// Daveti maç sonunda göstermek dönüşümün en yüksek olduğu andır — AMA her
/// maçta göstermek rahatsız eder ve oyunu bıraktırır.
///
/// KURALLAR (öncelik sırasıyla):
///  1. Oyuncu bugün "şimdi değil" dediyse → o gün BİR DAHA sorulmaz.
///  2. Şampiyon olduysa → HER ZAMAN sorulur (kayıp aversiyonunun zirvesi:
///     "kazandın ama sıralamada görünmüyorsun").
///  3. Aksi hâlde → her [_everyNMatches] maçta bir (misafir olarak oynanan
///     maç sayacı üzerinden).
///
/// Kayıt ZORUNLU DEĞİLDİR: davet kapatılabilir, oyun misafir olarak sonsuza
/// kadar oynanabilir (Apple 5.1.1 + tasarım kararımız).
class ClaimPromptService {
  static final ClaimPromptService _i = ClaimPromptService._();
  factory ClaimPromptService() => _i;
  ClaimPromptService._();

  // Prefs anahtarları.
  static const String _prefKeyGuestMatches = 'claim_guest_match_count';
  static const String _prefKeyDismissedDay = 'claim_dismissed_day';

  /// Kaçta bir davet edilsin (şampiyonlukta bu kural atlanır).
  static const int _everyNMatches = 3;

  /// Misafir olarak bir maç daha bitti — sayacı artırır ve YENİ sayıyı döner.
  /// Sonuç ekranı, misafir oyuncu için maç başına BİR kez çağırmalı.
  Future<int> recordGuestMatch() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final count = (prefs.getInt(_prefKeyGuestMatches) ?? 0) + 1;
      await prefs.setInt(_prefKeyGuestMatches, count);
      return count;
    } catch (_) {
      return 0;
    }
  }

  /// Bu maçın sonunda davet gösterilsin mi? [recordGuestMatch] SONRASINDA,
  /// dönen sayaçla çağrılır.
  Future<bool> shouldPrompt({required bool isWinner, required int matchCount}) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      // 1) Bugün "şimdi değil" dendiyse bugün bir daha sorma.
      if (prefs.getString(_prefKeyDismissedDay) == _todayKey()) return false;
      // 2) Şampiyonluk: en ikna edici an — sıklık kuralını atla.
      if (isWinner) return true;
      // 3) Her _everyNMatches maçta bir.
      return matchCount > 0 && matchCount % _everyNMatches == 0;
    } catch (_) {
      return false;
    }
  }

  /// "Şimdi değil" — bugün tekrar sorulmaz (tercih cihazda saklanır).
  Future<void> dismissForToday() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_prefKeyDismissedDay, _todayKey());
    } catch (_) {}
  }

  /// Yerel gün anahtarı (YYYY-MM-DD) — "o gün tekrar sorma" için.
  String _todayKey() {
    final now = DateTime.now();
    final m = now.month.toString().padLeft(2, '0');
    final d = now.day.toString().padLeft(2, '0');
    return '${now.year}-$m-$d';
  }
}
