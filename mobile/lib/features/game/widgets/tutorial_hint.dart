import 'dart:async';
import 'package:flutter/material.dart';
import 'package:quizroyale/core/theme/app_theme.dart';

/// İlk-maç mini tutorial ipucu balonu.
///
/// Non-blocking: oyunu engellemez (IgnorePointer + dokununca kapanır).
/// ~3sn sonra otomatik solup kaybolur. Tasarımla uyumlu, abartısız.
///
/// Her yeni tur tipi geldiğinde [message]/[type] değiştirilerek tekrar
/// tetiklenir (didUpdateWidget).
class TutorialHint extends StatefulWidget {
  const TutorialHint({
    super.key,
    required this.type,
    required this.message,
    this.onDismiss,
  });

  /// İpucunun ait olduğu tur tipi (anahtar). Değişince yeniden gösterilir.
  final String type;
  final String message;
  final VoidCallback? onDismiss;

  @override
  State<TutorialHint> createState() => _TutorialHintState();
}

class _TutorialHintState extends State<TutorialHint>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;
  late final Animation<double> _fade;
  late final Animation<double> _slide;
  Timer? _autoHide;
  bool _hidden = false;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 320),
    );
    _fade = CurvedAnimation(parent: _ctrl, curve: Curves.easeOut);
    _slide = Tween<double>(begin: 14, end: 0).animate(
      CurvedAnimation(parent: _ctrl, curve: Curves.easeOutBack),
    );
    _start();
  }

  void _start() {
    _hidden = false;
    _ctrl.forward(from: 0);
    _autoHide?.cancel();
    // ~3sn görünür kalsın (en kritik "KİLİTLE" ipucu kaçırılmasın).
    _autoHide = Timer(const Duration(milliseconds: 3000), _dismiss);
  }

  @override
  void didUpdateWidget(TutorialHint old) {
    super.didUpdateWidget(old);
    // Yeni tur tipi → ipucu yeniden gösterilsin.
    if (old.type != widget.type || old.message != widget.message) {
      _start();
    }
  }

  Future<void> _dismiss() async {
    if (_hidden || !mounted) return;
    _hidden = true;
    _autoHide?.cancel();
    try {
      await _ctrl.reverse();
    } catch (_) {
      // Controller dispose edilmiş olabilir.
    }
    if (mounted) widget.onDismiss?.call();
  }

  @override
  void dispose() {
    _autoHide?.cancel();
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Positioned(
      left: 16,
      right: 16,
      top: 8,
      child: SafeArea(
        bottom: false,
        child: AnimatedBuilder(
          animation: _ctrl,
          builder: (_, child) => Opacity(
            opacity: _fade.value,
            child: Transform.translate(
              offset: Offset(0, _slide.value),
              child: child,
            ),
          ),
          child: GestureDetector(
            onTap: _dismiss,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              decoration: BoxDecoration(
                color: AppTheme.card.withValues(alpha: 0.96),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(
                    color: AppTheme.cTertiary.withValues(alpha: 0.55),
                    width: 1.5),
                boxShadow: [
                  BoxShadow(
                    color: AppTheme.cTertiary.withValues(alpha: 0.25),
                    blurRadius: 18,
                    spreadRadius: -2,
                  ),
                ],
              ),
              child: Row(
                children: [
                  Container(
                    width: 30,
                    height: 30,
                    decoration: BoxDecoration(
                      color: AppTheme.cTertiary.withValues(alpha: 0.2),
                      shape: BoxShape.circle,
                    ),
                    child: const Center(
                      child: Text('💡', style: TextStyle(fontSize: 16)),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      widget.message,
                      style: const TextStyle(
                        color: AppTheme.textPrimary,
                        fontSize: 13.5,
                        fontWeight: FontWeight.w600,
                        height: 1.25,
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Icon(Icons.close_rounded,
                      size: 16,
                      color: AppTheme.textSecondary.withValues(alpha: 0.7)),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// Tur tipine göre ipucu metni. Bilinmeyen tip → null (gösterme).
String? tutorialMessageFor(String type) {
  switch (type) {
    case 'dogru_yanlis':
      return 'Doğru mu yanlış mı? En hızlı doğru cevap avantaj!';
    case 'gorsel':
      return 'Görseldeki doğru cevabı seç.';
    case 'karsilastirma':
      return 'Hangisi daha büyük/çok? Birini seç.';
    case 'coktan_secmeli':
      return 'Doğru şıkkı seç.';
    case 'tahmin':
      return 'Kaydırıcıyı sürükle ve CEVABI GÖNDER butonuna bas!';
    default:
      return null;
  }
}
