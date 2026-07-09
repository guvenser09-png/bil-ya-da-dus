import 'package:flutter/material.dart';
import 'package:quizroyale/core/services/haptic_service.dart';
import 'package:quizroyale/core/services/sound_service.dart';
import 'package:quizroyale/core/theme/app_theme.dart';
import 'package:quizroyale/shared/widgets/bilada_ui.dart';

class TrueFalseWidget extends StatelessWidget {
  const TrueFalseWidget({
    super.key,
    required this.question,
    required this.selectedAnswer,
    required this.onAnswer,
    this.correctAnswer,
  });

  final Map<String, dynamic> question;
  final int? selectedAnswer;
  final ValueChanged<dynamic> onAnswer;

  /// Reveal sırasında dolu gelir (0 = DOĞRU, 1 = YANLIŞ). Dolu olduğunda
  /// doğru şık yeşile, oyuncunun seçtiği yanlış şık kırmızıya boyanır.
  final int? correctAnswer;

  @override
  Widget build(BuildContext context) {
    final answered = selectedAnswer != null;
    final revealing = correctAnswer != null;
    final category = (question['kategori'] ?? question['category'] ?? 'Genel Kültür').toString();
    final text = (question['question'] ?? question['soru'] ?? '').toString();

    // KÖK NEDEN DÜZELTMESİ: Şık etiketleri ve indeksleri SORUNUN options
    // dizisinden gelmeli — sabit "DOĞRU=0 / YANLIŞ=1" varsayımından DEĞİL.
    // Sunucu `answer == correct_answer` ile skorlar ve correct_answer, options
    // dizisindeki indekstir. Bir dogru_yanlis sorusunun options'ı ters sırada
    // (['Yanlış','Doğru']) gelirse, sabit eşleme oyuncunun gördüğü doğru şıkkı
    // YANLIŞ indeksle gönderir → "doğru cevap verdim ama elendim". Artık
    // ekrandaki sıra options ile birebir aynı; gönderilen indeks her zaman
    // sunucunun beklediği indekstir.
    final options = List<String>.from(question['options'] as List? ?? const []);
    final String label0 = options.isNotEmpty ? options[0] : 'DOĞRU';
    final String label1 = options.length > 1 ? options[1] : 'YANLIŞ';

    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 8, 20, 16),
      child: Column(
        children: [
          Expanded(
            child: Center(
              child: GlassCard(
                padding: const EdgeInsets.all(28),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(category.toUpperCase(), style: BiladaText.label(color: AppTheme.cPrimary)),
                    const SizedBox(height: 16),
                    Text(text, textAlign: TextAlign.center, style: BiladaText.headline(size: 26)),
                  ],
                ),
              ),
            ),
          ),
          const SizedBox(height: 16),
          _option(
            index: 0,
            label: label0,
            icon: Icons.check_circle,
            baseColor: AppTheme.cTertiaryContainer,
            baseFg: AppTheme.cOnTertiaryContainer,
            baseShadow: AppTheme.cTertiaryShadow,
            answered: answered,
            revealing: revealing,
          ),
          const SizedBox(height: 14),
          _option(
            index: 1,
            label: label1,
            icon: Icons.cancel,
            baseColor: AppTheme.cErrorContainer,
            baseFg: AppTheme.cOnErrorContainer,
            baseShadow: AppTheme.cErrorShadow,
            answered: answered,
            revealing: revealing,
          ),
        ],
      ),
    );
  }

  Widget _option({
    required int index,
    required String label,
    required IconData icon,
    required Color baseColor,
    required Color baseFg,
    required Color baseShadow,
    required bool answered,
    required bool revealing,
  }) {
    final isSelected = selectedAnswer == index;
    Color color = baseColor;
    Color fg = baseFg;
    Color shadow = baseShadow;
    IconData displayIcon = icon;

    // Görsel durum bayrakları
    bool revealCorrect = false; // doğru şık (yeşil pop)
    bool revealWrong = false; // oyuncunun yanlış seçimi (kırmızı)

    if (revealing) {
      revealCorrect = correctAnswer == index;
      revealWrong = isSelected && correctAnswer != index;
      if (revealCorrect) {
        color = AppTheme.cTertiaryContainer;
        fg = AppTheme.cOnTertiaryContainer;
        shadow = AppTheme.cTertiaryShadow;
        displayIcon = Icons.check_circle;
      } else if (revealWrong) {
        color = AppTheme.cErrorContainer;
        fg = AppTheme.cOnErrorContainer;
        shadow = AppTheme.cErrorShadow;
        displayIcon = Icons.cancel;
      }
    }

    // Opacity: hiçbir zaman koyu griye boğmuyoruz.
    // - reveal: doğru/yanlış net (1.0), diğerleri yarı-soluk (0.5)
    // - sadece seçim yapıldı (reveal yok): seçilmeyen şık hafif soluk (0.85)
    double opacity = 1;
    if (revealing) {
      opacity = (revealCorrect || revealWrong) ? 1 : 0.5;
    } else if (answered && !isSelected) {
      opacity = 0.85;
    }

    // "Kilitlendi" hissi: seçim anında ya da reveal'da vurgulanan şık büyür.
    final highlighted = revealCorrect || revealWrong || (answered && !revealing && isSelected);
    final scale = highlighted ? 1.03 : 1.0;

    // Glow rengi: reveal'da yeşil/kırmızı, seçim anında pembe (vurgu).
    Color glow;
    if (revealCorrect) {
      glow = AppTheme.cTertiary;
    } else if (revealWrong) {
      glow = AppTheme.cError;
    } else {
      glow = Colors.white;
    }

    return AnimatedOpacity(
      duration: const Duration(milliseconds: 220),
      opacity: opacity,
      child: AnimatedScale(
        duration: const Duration(milliseconds: 220),
        curve: Curves.easeOutBack,
        scale: scale,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 220),
          curve: Curves.easeOut,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(24),
            boxShadow: highlighted
                ? [BoxShadow(color: glow.withValues(alpha: 0.55), blurRadius: 22, spreadRadius: 1)]
                : null,
          ),
          child: ChunkyButton(
            height: 74,
            depth: 8,
            color: color,
            foreground: fg,
            shadowColor: shadow,
            // Cevaplandıktan sonra onPressed'i null bırakmıyoruz; aksi halde
            // ChunkyButton disabled olup şıkkı griye boğuyor. No-op ile canlı
            // renk korunur, onAnswer yine tek sefer tetiklenir.
            // Şık kilitleme: yumuşak tık sesi + hafif haptik (ayara saygılı).
            onPressed: answered
                ? () {}
                : () {
                    SoundService().playSound(GameSound.click);
                    HapticService().buttonTap();
                    onAnswer(index);
                  },
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [Icon(displayIcon, size: 28), const SizedBox(width: 12), Text(label)],
            ),
          ),
        ),
      ),
    );
  }
}
