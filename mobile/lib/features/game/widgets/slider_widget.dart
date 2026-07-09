import 'package:flutter/material.dart';
import 'package:quizroyale/core/services/haptic_service.dart';
import 'package:quizroyale/core/services/sound_service.dart';
import 'package:quizroyale/core/theme/app_theme.dart';
import 'package:quizroyale/shared/widgets/bilada_ui.dart';

class SliderWidget extends StatefulWidget {
  const SliderWidget({
    super.key,
    required this.question,
    required this.currentValue,
    required this.isLocked,
    required this.onValueChanged,
    required this.onLock,
    this.correctValue,
  });

  final Map<String, dynamic> question;
  final double? currentValue;
  final bool isLocked;
  final ValueChanged<double> onValueChanged;
  final VoidCallback onLock;

  /// Reveal sırasında dolu gelir (doğru sayı). Dolu olduğunda doğru değer
  /// yeşil bir etiketle gösterilir.
  final double? correctValue;

  @override
  State<SliderWidget> createState() => _SliderWidgetState();
}

class _SliderWidgetState extends State<SliderWidget> {
  late double _value;
  double _lastTickValue = 0;

  @override
  void initState() {
    super.initState();
    final min = (widget.question['min_value'] as num?)?.toDouble() ?? 0;
    final max = (widget.question['max_value'] as num?)?.toDouble() ?? 100;
    _value = widget.currentValue ?? (min + (max - min) / 2);
  }

  @override
  Widget build(BuildContext context) {
    final min = (widget.question['min_value'] as num?)?.toDouble() ?? 0;
    final max = (widget.question['max_value'] as num?)?.toDouble() ?? 100;
    final unit = widget.question['unit'] as String? ?? '';
    final category = (widget.question['kategori'] ?? widget.question['category'] ?? '').toString();
    final tickInterval = (max - min) / 10;

    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(20, 8, 20, 16),
      child: Column(
        children: [
          GlassCard(
            padding: const EdgeInsets.all(28),
            child: Column(
              children: [
                if (category.isNotEmpty) ...[
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(999),
                      border: Border.all(color: AppTheme.cTertiary),
                      color: AppTheme.cTertiaryContainer.withValues(alpha: 0.15),
                    ),
                    child: Text(category.toUpperCase(), style: BiladaText.label(color: AppTheme.cTertiary)),
                  ),
                  const SizedBox(height: 16),
                ],
                Text((widget.question['question'] ?? widget.question['soru'] ?? '').toString(),
                    textAlign: TextAlign.center, style: BiladaText.headline(size: 24)),
                const SizedBox(height: 32),
                // Reveal: doğru sayıyı canlı yeşil etiketle, "pop" animasyonuyla göster.
                if (widget.correctValue != null) ...[
                  TweenAnimationBuilder<double>(
                    tween: Tween(begin: 0.6, end: 1),
                    duration: const Duration(milliseconds: 320),
                    curve: Curves.easeOutBack,
                    builder: (context, t, child) => Transform.scale(scale: t, child: child),
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 8),
                      decoration: BoxDecoration(
                        color: AppTheme.cTertiaryContainer,
                        borderRadius: BorderRadius.circular(16),
                        boxShadow: const [
                          BoxShadow(color: AppTheme.cTertiaryShadow, offset: Offset(0, 4), blurRadius: 0),
                          // Canlı yeşil glow
                          BoxShadow(color: AppTheme.cTertiary, blurRadius: 22, spreadRadius: -2),
                        ],
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const Icon(Icons.check_circle, color: AppTheme.cOnTertiaryContainer, size: 22),
                          const SizedBox(width: 8),
                          Text(
                            'DOĞRU: ${widget.correctValue!.toStringAsFixed(0)}${unit.isNotEmpty ? ' $unit' : ''}',
                            style: BiladaText.title(color: AppTheme.cOnTertiaryContainer, size: 18),
                          ),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),
                ],
                // Değer rozeti
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 8),
                  decoration: BoxDecoration(
                    color: AppTheme.cPrimary,
                    borderRadius: BorderRadius.circular(16),
                    boxShadow: const [BoxShadow(color: Color(0xFF8D004F), offset: Offset(0, 4), blurRadius: 0)],
                  ),
                  child: Text('${_value.toStringAsFixed(0)}${unit.isNotEmpty ? ' $unit' : ''}',
                      style: BiladaText.displayXl(color: AppTheme.cOnPrimary, size: 32)),
                ),
                const SizedBox(height: 16),
                SliderTheme(
                  data: SliderTheme.of(context).copyWith(
                    thumbColor: AppTheme.cPrimary,
                    activeTrackColor: AppTheme.cPrimaryContainer,
                    inactiveTrackColor: AppTheme.cSurfaceVariant,
                    thumbShape: const RoundSliderThumbShape(enabledThumbRadius: 16),
                    trackHeight: 16,
                    overlayColor: AppTheme.cPrimary.withValues(alpha: 0.2),
                  ),
                  child: Slider(
                    value: _value.clamp(min, max),
                    min: min,
                    max: max,
                    onChanged: widget.isLocked
                        ? null
                        : (v) {
                            setState(() => _value = v);
                            widget.onValueChanged(v);
                            final tick = (v / tickInterval).roundToDouble() * tickInterval;
                            if ((tick - _lastTickValue).abs() >= tickInterval * 0.9) {
                              // Ayara saygılı seçim tıkı (servis üzerinden).
                              HapticService().sliderTick();
                              _lastTickValue = tick;
                            }
                          },
                  ),
                ),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    _rangePill(min.toStringAsFixed(0)),
                    _rangePill(max.toStringAsFixed(0)),
                  ],
                ),
                const SizedBox(height: 24),
                ChunkyButton(
                  height: 60,
                  color: widget.isLocked ? AppTheme.cTertiaryContainer : AppTheme.cPrimaryContainer,
                  foreground: widget.isLocked ? AppTheme.cOnTertiaryContainer : AppTheme.cOnPrimaryContainer,
                  shadowColor: widget.isLocked ? AppTheme.cTertiaryShadow : AppTheme.cPrimaryShadow,
                  onPressed: widget.isLocked
                      ? null
                      : () {
                          // Cevabı kilitleme: tık sesi + hafif haptik (ayara saygılı).
                          SoundService().playSound(GameSound.click);
                          HapticService().buttonTap();
                          // Mevcut değeri (sürüklenmese bile) provider'a yaz, sonra kilitle+gönder.
                          widget.onValueChanged(_value);
                          widget.onLock();
                        },
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(widget.isLocked ? 'KİLİTLENDİ' : 'CEVABI GÖNDER'),
                      const SizedBox(width: 8),
                      Icon(widget.isLocked ? Icons.lock : Icons.send),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _rangePill(String text) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
      decoration: BoxDecoration(
        color: AppTheme.cSurfaceContainer,
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: AppTheme.cOutlineVariant),
      ),
      child: Text(text, style: BiladaText.label(color: AppTheme.cOnSurfaceVariant)),
    );
  }
}
