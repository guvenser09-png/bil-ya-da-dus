import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:quizroyale/core/services/haptic_service.dart';
import 'package:quizroyale/core/services/sound_service.dart';
import 'package:quizroyale/core/theme/app_theme.dart';
import 'package:quizroyale/shared/widgets/bilada_ui.dart';

class MultipleChoiceWidget extends StatelessWidget {
  const MultipleChoiceWidget({
    super.key,
    required this.question,
    required this.selectedAnswer,
    required this.onAnswer,
    this.hasImage = false,
    this.correctAnswer,
    this.hiddenOptions = const [],
  });

  final Map<String, dynamic> question;
  final int? selectedAnswer;
  final ValueChanged<dynamic> onAnswer;
  final bool hasImage;

  /// Reveal sırasında dolu gelir (doğru şıkkın index'i). Dolu olduğunda
  /// doğru şık yeşile, oyuncunun seçtiği yanlış şık kırmızıya boyanır.
  final int? correctAnswer;

  /// %50 JOKER ile ELENEN şık indeksleri. Bu şıklar soluklaştırılır ve
  /// tıklanamaz olur (görsel olarak devre dışı).
  final List<int> hiddenOptions;

  static const _labels = ['A', 'B', 'C', 'D'];
  // pembe / mor / mint / nötr — Stitch çoktan seçmeli paleti
  static const _colors = [
    AppTheme.cPrimaryContainer,
    AppTheme.cSecondaryContainer,
    AppTheme.cTertiaryContainer,
    AppTheme.cSurfaceVariant,
  ];
  static const _fg = [
    AppTheme.cOnPrimaryContainer,
    Colors.white,
    AppTheme.cOnTertiaryContainer,
    AppTheme.cOnSurfaceVariant,
  ];
  static const _shadows = [
    AppTheme.cPrimaryShadow,
    AppTheme.cSecondaryShadow,
    AppTheme.cTertiaryShadow,
    Color(0xFF2B1B20),
  ];

  @override
  Widget build(BuildContext context) {
    final options = List<String>.from(question['options'] as List? ?? const []);
    final imageUrl = question['image_url'] as String?;
    final category = (question['kategori'] ?? question['category'] ?? '').toString();
    final answered = selectedAnswer != null;
    final revealing = correctAnswer != null;

    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(20, 8, 20, 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          GlassCard(
            padding: const EdgeInsets.all(24),
            child: Column(
              children: [
                if (category.isNotEmpty) ...[
                  Text(category.toUpperCase(), style: BiladaText.label(color: AppTheme.cPrimary)),
                  const SizedBox(height: 12),
                ],
                Text(
                  (question['question'] ?? question['soru'] ?? '').toString(),
                  textAlign: TextAlign.center,
                  style: BiladaText.headline(size: 24),
                ),
              ],
            ),
          ),
          if (hasImage && imageUrl != null) ...[
            const SizedBox(height: 14),
            ClipRRect(
              borderRadius: BorderRadius.circular(20),
              child: CachedNetworkImage(
                imageUrl: imageUrl,
                height: 150,
                width: double.infinity,
                fit: BoxFit.cover,
                placeholder: (_, __) => Container(
                  height: 150, color: AppTheme.cSurfaceContainerHighest,
                  child: const Center(child: CircularProgressIndicator(strokeWidth: 2)),
                ),
                errorWidget: (_, __, ___) => Container(
                  height: 150, color: AppTheme.cSurfaceContainerHighest,
                  child: const Icon(Icons.image_not_supported, color: AppTheme.cOutline),
                ),
              ),
            ),
          ],
          const SizedBox(height: 20),
          GridView.builder(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: 2,
              mainAxisSpacing: 16,
              crossAxisSpacing: 16,
              childAspectRatio: 1.5,
            ),
            itemCount: options.length,
            itemBuilder: (_, i) {
              final selected = selectedAnswer == i;
              // Joker ile elenmiş şık: reveal fazında görsel karar reveal'a
              // bırakılır (doğru/yanlış vurgusu bozulmasın); sadece cevap
              // verilmeden önce soluk+tıklanamaz gösterilir.
              final jokerHidden = hiddenOptions.contains(i) && !revealing;
              Color color = _colors[i % 4];
              Color fg = _fg[i % 4];
              Color shadow = _shadows[i % 4];
              IconData? badgeIcon;

              bool revealCorrect = false; // doğru şık (yeşil pop)
              bool revealWrong = false; // oyuncunun yanlış seçimi (kırmızı)

              if (revealing) {
                revealCorrect = correctAnswer == i;
                revealWrong = selected && correctAnswer != i;
                if (revealCorrect) {
                  color = AppTheme.cTertiaryContainer;
                  fg = AppTheme.cOnTertiaryContainer;
                  shadow = AppTheme.cTertiaryShadow;
                  badgeIcon = Icons.check_circle;
                } else if (revealWrong) {
                  color = AppTheme.cErrorContainer;
                  fg = AppTheme.cOnErrorContainer;
                  shadow = AppTheme.cErrorShadow;
                  badgeIcon = Icons.cancel;
                }
              }

              // Opacity: hiçbir zaman koyu griye boğmuyoruz.
              double opacity = 1;
              if (revealing) {
                opacity = (revealCorrect || revealWrong) ? 1 : 0.5;
              } else if (answered && !selected) {
                opacity = 0.85;
              }
              // Joker ile elenen şık belirgin şekilde soluk (devre dışı hissi)
              // ve harf rozeti yerine "engel" (½ eleme) ikonu gösterilir.
              if (jokerHidden) {
                opacity = 0.28;
                badgeIcon = Icons.block;
              }

              // "Kilitlendi" hissi / reveal pop'u.
              final highlighted =
                  revealCorrect || revealWrong || (answered && !revealing && selected);
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
                      height: double.infinity,
                      depth: 6,
                      color: color,
                      foreground: fg,
                      shadowColor: shadow,
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
                      // Cevaptan sonra null yerine no-op: ChunkyButton griye boğmasın.
                      // Joker ile elenmiş şık da no-op (tıklanamaz).
                      // Şık kilitleme: yumuşak tık sesi + hafif haptik (ayara saygılı).
                      onPressed: (answered || jokerHidden)
                          ? () {}
                          : () {
                              SoundService().playSound(GameSound.click);
                              HapticService().buttonTap();
                              onAnswer(i);
                            },
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          // Harf rozeti — reveal'da doğru/yanlış ikonu gösterir.
                          Container(
                            width: 30,
                            height: 30,
                            decoration: BoxDecoration(
                              color: fg.withValues(alpha: 0.2),
                              borderRadius: BorderRadius.circular(10),
                            ),
                            alignment: Alignment.center,
                            child: badgeIcon != null
                                ? Icon(badgeIcon, color: fg, size: 20)
                                : Text(_labels[i % 4], style: BiladaText.title(color: fg, size: 16)),
                          ),
                          const SizedBox(height: 10),
                          Flexible(
                            child: Text(
                              options[i],
                              textAlign: TextAlign.center,
                              maxLines: 3,
                              overflow: TextOverflow.ellipsis,
                              style: BiladaText.title(color: fg, size: 15),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              );
            },
          ),
        ],
      ),
    );
  }
}
