import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:quizroyale/core/theme/app_theme.dart';
import 'package:quizroyale/shared/widgets/bilada_ui.dart';

class ComparisonWidget extends StatelessWidget {
  const ComparisonWidget({
    super.key,
    required this.question,
    required this.selectedAnswer,
    required this.onAnswer,
    this.correctAnswer,
  });

  final Map<String, dynamic> question;
  final int? selectedAnswer;
  final ValueChanged<dynamic> onAnswer;

  /// Reveal sırasında dolu gelir (doğru kartın index'i). Dolu olduğunda
  /// doğru kart yeşile, oyuncunun seçtiği yanlış kart kırmızıya boyanır.
  final int? correctAnswer;

  @override
  Widget build(BuildContext context) {
    final options = List<String>.from(question['options'] as List? ?? const ['', '']);
    final answered = selectedAnswer != null;

    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 8, 20, 16),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          GlassCard(
            padding: const EdgeInsets.all(24),
            child: Text(
              (question['question'] ?? question['soru'] ?? '').toString(),
              textAlign: TextAlign.center,
              style: BiladaText.headline(size: 22),
            ),
          ),
          const SizedBox(height: 28),
          IntrinsicHeight(
            child: Row(
              children: [
                Expanded(
                  child: _card(options.isNotEmpty ? options[0] : '', 0, AppTheme.cPrimaryContainer,
                      AppTheme.cOnPrimaryContainer, AppTheme.cPrimaryShadow, answered),
                ),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 10),
                  child: Container(
                    width: 40,
                    height: 40,
                    decoration: const BoxDecoration(gradient: AppTheme.primaryGradient, shape: BoxShape.circle),
                    alignment: Alignment.center,
                    child: Text('VS', style: BiladaText.label(color: Colors.white, size: 12)),
                  ),
                ),
                Expanded(
                  child: _card(options.length > 1 ? options[1] : '', 1, AppTheme.cSecondaryContainer,
                      Colors.white, AppTheme.cSecondaryShadow, answered),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _card(String text, int index, Color color, Color fg, Color shadow, bool answered) {
    final revealing = correctAnswer != null;
    final isSelected = selectedAnswer == index;
    IconData? icon;

    bool revealCorrect = false; // doğru kart (yeşil pop)
    bool revealWrong = false; // oyuncunun yanlış seçimi (kırmızı)

    if (revealing) {
      revealCorrect = correctAnswer == index;
      revealWrong = isSelected && correctAnswer != index;
      if (revealCorrect) {
        color = AppTheme.cTertiaryContainer;
        fg = AppTheme.cOnTertiaryContainer;
        shadow = AppTheme.cTertiaryShadow;
        icon = Icons.check_circle;
      } else if (revealWrong) {
        color = AppTheme.cErrorContainer;
        fg = AppTheme.cOnErrorContainer;
        shadow = AppTheme.cErrorShadow;
        icon = Icons.cancel;
      }
    }

    // Opacity: griye boğmadan hafif soluk.
    double opacity = 1;
    if (revealing) {
      opacity = (revealCorrect || revealWrong) ? 1 : 0.5;
    } else if (answered && !isSelected) {
      opacity = 0.85;
    }

    final highlighted = revealCorrect || revealWrong || (answered && !revealing && isSelected);
    final scale = highlighted ? 1.04 : 1.0;
    final Color glow = revealCorrect
        ? AppTheme.cTertiary
        : revealWrong
            ? AppTheme.cError
            : Colors.white;

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
            borderRadius: BorderRadius.circular(20),
            boxShadow: highlighted
                ? [BoxShadow(color: glow.withValues(alpha: 0.5), blurRadius: 20, spreadRadius: 1)]
                : null,
          ),
          child: ChunkyButton(
            height: 140,
            depth: 6,
            color: color,
            foreground: fg,
            shadowColor: shadow,
            padding: const EdgeInsets.all(12),
            // Cevaptan sonra null yerine no-op: ChunkyButton griye boğmasın.
            onPressed: answered ? () {} : () { HapticFeedback.lightImpact(); onAnswer(index); },
            child: Column(
              mainAxisSize: MainAxisSize.min,
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                if (icon != null) ...[
                  Icon(icon, color: fg, size: 28),
                  const SizedBox(height: 8),
                ],
                Text(text, textAlign: TextAlign.center, style: BiladaText.title(color: fg, size: 17)),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
