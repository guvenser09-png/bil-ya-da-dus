import 'package:flutter/material.dart';
import 'package:share_plus/share_plus.dart';
import 'package:quizroyale/features/daily/providers/daily_challenge_provider.dart';

/// Uygulamanın App Store bağlantısı — paylaşım metninin sonuna eklenir.
///
/// TODO(app-store-id): Uygulama App Store'da yayında; sayısal id öğrenilince
/// bunu doğrudan derin bağlantıyla değiştir:
///   https://apps.apple.com/tr/app/id<APP_ID>
/// O zamana kadar isimle arama bağlantısı kullanılıyor — çalışır, ama tıklama
/// sonrası bir adım fazladan atar (arama sonucu → uygulama).
const String kAppStoreUrl =
    'https://apps.apple.com/tr/search?term=Bil%20ya%20da%20D%C3%BC%C5%9F';

/// Wordle tarzı paylaşım metni — CEVAPLARI SIZDIRMAZ, sadece emoji ızgarası.
///
/// Örnek çıktı:
///   Bil ya da Düş — Günün 5 Sorusu
///   🟩🟩🟥🟩🟥 4/5
///   Sen kaç yaparsın?
///   https://apps.apple.com/...
///
/// Metnin gövdesini SUNUCU üretir (sonuçla birebir tutarlı olsun diye); ağ
/// yanıtı boş gelirse istemci aynı biçimi yerelde kurar.
String buildDailyShareText(DailyChallengeResult result) {
  final body = result.shareText.isNotEmpty
      ? result.shareText
      : 'Bil ya da Düş — Günün 5 Sorusu\n'
          '${result.grid} ${result.correctCount}/${result.questionCount}\n'
          'Sen kaç yaparsın?';
  return '$body\n$kAppStoreUrl';
}

/// Sistem paylaşım sayfasını açar (WhatsApp, Mesajlar, X, ...).
///
/// iPad'de paylaşım sayfası bir "popover" olarak açılır ve NEREDEN çıkacağını
/// bilmek zorundadır: sharePositionOrigin verilmezse iPad'de hata fırlatır.
/// Bu yüzden dokunulan widget'ın ekran dikdörtgenini hesaplayıp geçiyoruz.
Future<void> shareDailyResult(BuildContext context, DailyChallengeResult result) async {
  final box = context.findRenderObject() as RenderBox?;
  final origin = (box != null && box.hasSize)
      ? box.localToGlobal(Offset.zero) & box.size
      : null;

  try {
    await Share.share(
      buildDailyShareText(result),
      subject: 'Bil ya da Düş — Günün 5 Sorusu',
      sharePositionOrigin: origin,
    );
  } catch (_) {
    // Paylaşım sayfası açılamazsa oyuncuyu boşlukta bırakma.
    if (!context.mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Paylaşım açılamadı, tekrar dene.')),
    );
  }
}
