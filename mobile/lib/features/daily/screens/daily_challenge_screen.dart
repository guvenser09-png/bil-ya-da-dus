import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:quizroyale/core/services/haptic_service.dart';
import 'package:quizroyale/core/theme/app_theme.dart';
import 'package:quizroyale/features/auth/providers/auth_provider.dart';
import 'package:quizroyale/features/daily/providers/daily_challenge_provider.dart';
import 'package:quizroyale/features/daily/widgets/daily_share_sheet.dart';
import 'package:quizroyale/features/game/widgets/comparison_widget.dart';
import 'package:quizroyale/features/game/widgets/multiple_choice_widget.dart';
import 'package:quizroyale/features/game/widgets/slider_widget.dart';
import 'package:quizroyale/features/game/widgets/true_false_widget.dart';
import 'package:quizroyale/features/quests/providers/quests_provider.dart';
import 'package:quizroyale/shared/widgets/bilada_ui.dart';

/// Günün 5 Sorusu — herkese AYNI 5 soru, ELEME YOK (hepsi cevaplanır).
///
/// Maçtan farkı: yanlış cevap elemez, sadece ızgarada 🟥 olur. Süre baskısı
/// HAFİF (soru başına 15 sn) — amaç stres değil, günlük alışkanlık.
class DailyChallengeScreen extends ConsumerStatefulWidget {
  const DailyChallengeScreen({super.key});

  @override
  ConsumerState<DailyChallengeScreen> createState() => _DailyChallengeScreenState();
}

/// Soru başına süre — maçtaki 5-8 sn'ye göre bilinçli olarak CÖMERT.
const int _kSecondsPerQuestion = 15;

class _DailyChallengeScreenState extends ConsumerState<DailyChallengeScreen> {
  List<Map<String, dynamic>>? _questions;
  bool _loading = true;
  String? _loadError;

  int _index = 0;

  /// Soru sırasıyla cevaplar (cevapsız → null). Sunucuya böyle gider.
  final List<dynamic> _answers = [];

  /// Doğruluk sunucuda hesaplandığı için istemci yalnızca HIZ bonusu üretir.
  int _speedBonus = 0;

  /// Slider (tahmin) turunda anlık değer.
  double? _sliderValue;
  bool _sliderLocked = false;

  Timer? _timer;
  int _remaining = _kSecondsPerQuestion;

  bool _submitting = false;
  DailyChallengeResult? _result;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _load() async {
    final questions =
        await ref.read(dailyChallengeProvider.notifier).fetchQuestions();
    if (!mounted) return;
    if (questions == null || questions.isEmpty) {
      // 403 (bugün oynanmış) ya da ağ hatası → kayıtlı sonucu göster.
      await ref.read(dailyChallengeProvider.notifier).load();
      if (!mounted) return;
      final saved = ref.read(dailyChallengeProvider).result;
      setState(() {
        _loading = false;
        _result = saved;
        _loadError = saved == null ? 'Sorular yüklenemedi. Sonra tekrar dene.' : null;
      });
      return;
    }
    setState(() {
      _questions = questions;
      _answers
        ..clear()
        ..addAll(List<dynamic>.filled(questions.length, null));
      _loading = false;
    });
    _startTimer();
  }

  void _startTimer() {
    _timer?.cancel();
    setState(() => _remaining = _kSecondsPerQuestion);
    _timer = Timer.periodic(const Duration(seconds: 1), (t) {
      if (!mounted) return;
      if (_remaining <= 1) {
        t.cancel();
        // Süre doldu: cevapsız (null) sayılır → ızgarada 🟥, ama ELENMEZ.
        _next();
        return;
      }
      setState(() => _remaining--);
    });
  }

  /// Şıklı cevap — dokununca kısa bir nefes payı bırakıp sıradaki soruya geçer.
  void _answer(dynamic value) {
    if (_answers[_index] != null) return; // çift dokunuş
    HapticService().buttonTap();
    setState(() {
      _answers[_index] = value;
      _speedBonus += _remaining * 2; // hız bonusu (sunucuda tavanlanır)
    });
    _timer?.cancel();
    Future.delayed(const Duration(milliseconds: 420), () {
      if (mounted) _next();
    });
  }

  void _next() {
    final questions = _questions;
    if (questions == null) return;
    if (_index >= questions.length - 1) {
      _submit();
      return;
    }
    setState(() {
      _index++;
      _sliderValue = null;
      _sliderLocked = false;
    });
    _startTimer();
  }

  Future<void> _submit() async {
    _timer?.cancel();
    if (_submitting) return;
    setState(() => _submitting = true);

    final result = await ref.read(dailyChallengeProvider.notifier).submit(
          answers: _answers,
          score: _speedBonus,
        );
    if (!mounted) return;

    if (result == null) {
      setState(() {
        _submitting = false;
        _loadError = 'Sonuç gönderilemedi. İnternetini kontrol et.';
      });
      return;
    }
    // Altın bakiyesi ve "Günün 5 Sorusu'nu oyna" görevi tazelensin.
    unawaited(ref.read(authProvider.notifier).refreshUser());
    unawaited(ref.read(questsProvider.notifier).load());
    HapticService().win();
    setState(() {
      _submitting = false;
      _result = result;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.transparent,
      body: Stack(
        children: [
          const Positioned.fill(child: BiladaBackground()),
          SafeArea(
            child: Column(
              children: [
                _header(),
                Expanded(child: _body()),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _header() {
    final total = _questions?.length ?? 5;
    final playing = _result == null && _questions != null && !_submitting;
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 4),
      child: Column(
        children: [
          Row(
            children: [
              IconButton(
                icon: const Icon(Icons.close_rounded, color: AppTheme.cOnSurfaceVariant),
                onPressed: () => context.go('/home'),
              ),
              Expanded(
                child: Text(
                  '🗓️ GÜNÜN 5 SORUSU',
                  textAlign: TextAlign.center,
                  style: BiladaText.label(color: AppTheme.cPrimary, size: 13),
                ),
              ),
              SizedBox(
                width: 48,
                child: playing
                    ? Center(
                        child: Text(
                          '${_index + 1}/$total',
                          style: BiladaText.label(color: AppTheme.cOnSurface, size: 13),
                        ),
                      )
                    : const SizedBox.shrink(),
              ),
            ],
          ),
          if (playing) ...[
            const SizedBox(height: 6),
            // Hafif süre baskısı: ince bir çubuk, geri sayım sesi/titreşimi YOK.
            ClipRRect(
              borderRadius: BorderRadius.circular(999),
              child: LinearProgressIndicator(
                value: _remaining / _kSecondsPerQuestion,
                minHeight: 6,
                backgroundColor: AppTheme.cSurfaceContainerHighest,
                valueColor: AlwaysStoppedAnimation(
                  _remaining <= 5 ? AppTheme.cError : AppTheme.cTertiary,
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _body() {
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_result != null) {
      return _DailyResultView(result: _result!);
    }
    if (_submitting) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_loadError != null || _questions == null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                _loadError ?? 'Bir şeyler ters gitti.',
                textAlign: TextAlign.center,
                style: BiladaText.body(),
              ),
              const SizedBox(height: 16),
              ChunkyButton(
                expand: false,
                onPressed: () => context.go('/home'),
                child: const Text('ANA EKRAN'),
              ),
            ],
          ),
        ),
      );
    }
    return _questionWidget(_questions![_index]);
  }

  Widget _questionWidget(Map<String, dynamic> q) {
    // Günlük sorularda tip 'type' alanında gelir (maçta 'tip'); ikisini de karşıla.
    final type = (q['type'] ?? q['tip'] ?? '').toString();
    final key = ValueKey('daily_${q['id'] ?? _index}');
    final selected = _answers[_index] is int ? _answers[_index] as int : null;
    final hasImage = q['image_url'] != null;

    switch (type) {
      case 'dogru_yanlis':
        return TrueFalseWidget(
          key: key,
          question: q,
          selectedAnswer: selected,
          onAnswer: _answer,
        );
      case 'karsilastirma':
        return ComparisonWidget(
          key: key,
          question: q,
          selectedAnswer: selected,
          onAnswer: _answer,
        );
      case 'gorsel':
      case 'coktan_secmeli':
        return MultipleChoiceWidget(
          key: key,
          question: q,
          selectedAnswer: selected,
          onAnswer: _answer,
          hasImage: hasImage,
        );
      case 'tahmin':
        return SliderWidget(
          key: key,
          question: q,
          currentValue: _sliderValue,
          isLocked: _sliderLocked,
          onValueChanged: (v) => setState(() => _sliderValue = v),
          onLock: () {
            if (_sliderLocked) return;
            setState(() => _sliderLocked = true);
            final min = (q['min_value'] as num?)?.toDouble() ?? 0;
            _answer(_sliderValue ?? min);
          },
        );
      default:
        // Bilinmeyen tip: oyuncuyu kilitleme, soruyu atla.
        return Center(
          child: TextButton(
            onPressed: _next,
            child: Text('Sonraki soru', style: BiladaText.body()),
          ),
        );
    }
  }
}

// ---------------------------------------------------------------------------
// Sonuç: 🟩🟩🟥🟩🟥 ızgarası + doğru sayısı + altın + günlük sıralama + PAYLAŞ
// ---------------------------------------------------------------------------

class _DailyResultView extends StatelessWidget {
  const _DailyResultView({required this.result});

  final DailyChallengeResult result;

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(20, 8, 20, 32),
      child: Column(
        children: [
          const SizedBox(height: 8),
          Text('BUGÜNKÜ SONUCUN', style: BiladaText.label(color: AppTheme.cPrimary)),
          const SizedBox(height: 12),

          // Izgara — paylaşım kartındakiyle BİREBİR aynı (cevap sızdırmaz).
          GlassCard(
            padding: const EdgeInsets.symmetric(vertical: 22, horizontal: 16),
            child: Column(
              children: [
                Text(result.grid, style: const TextStyle(fontSize: 34, letterSpacing: 4)),
                const SizedBox(height: 10),
                Text(
                  '${result.correctCount}/${result.questionCount} doğru',
                  style: BiladaText.headline(size: 26),
                ),
                if (result.streak > 1) ...[
                  const SizedBox(height: 6),
                  Text(
                    '🔥 ${result.streak} gün üst üste',
                    style: BiladaText.label(color: AppTheme.gold, size: 12),
                  ),
                ],
              ],
            ),
          ),
          const SizedBox(height: 14),

          Row(
            children: [
              Expanded(
                child: _tile(
                  emoji: '🪙',
                  label: 'Kazanılan',
                  value: '+${result.coinsEarned}',
                  color: AppTheme.gold,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _tile(
                  emoji: '📊',
                  label: 'Günün sırası',
                  value: result.rank > 0 ? '${result.rank}.' : '—',
                  color: AppTheme.cTertiary,
                  sub: _rankSubtitle(result),
                ),
              ),
            ],
          ),
          const SizedBox(height: 20),

          // VİRAL KANAL: Wordle tarzı metin paylaşımı (bedava büyüme).
          ChunkyButton(
            height: 60,
            color: AppTheme.cTertiaryContainer,
            foreground: Colors.white,
            shadowColor: AppTheme.cTertiaryShadow,
            onPressed: () => shareDailyResult(context, result),
            child: const Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(Icons.ios_share_rounded),
                SizedBox(width: 8),
                Text('SONUCU PAYLAŞ'),
              ],
            ),
          ),
          const SizedBox(height: 10),
          ChunkyButton(
            height: 56,
            onPressed: () => context.go('/lobby'),
            child: const Text('HIZLI MAÇ'),
          ),
          const SizedBox(height: 10),
          TextButton(
            onPressed: () => context.go('/home'),
            child: Text(
              'Yarın yeni 5 soru — görüşürüz! 👋',
              style: BiladaText.body(color: AppTheme.cOnSurfaceVariant, size: 14),
            ),
          ),
        ],
      ),
    );
  }

  /// Sıralama alt yazısı. SOĞUK BAŞLANGIÇ dostu: bugün çok az kişi oynadıysa
  /// yüzdelik dilim anlamsızdır ("1 oyuncu içinde en iyi %100" komik olur) —
  /// o durumda oyuncuyu öncü gibi hissettiren bir metin gösterilir.
  static String? _rankSubtitle(DailyChallengeResult r) {
    if (r.totalPlayers <= 1) return 'Bugünün ilk oyuncususun! 🎉';
    if (r.totalPlayers < 5) return '${r.totalPlayers} oyuncu içinde';
    return '${r.totalPlayers} oyuncu içinde • en iyi %${r.percentile}';
  }

  Widget _tile({
    required String emoji,
    required String label,
    required String value,
    required Color color,
    String? sub,
  }) {
    return GlassCard(
      padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 12),
      child: Column(
        children: [
          Text(emoji, style: const TextStyle(fontSize: 20)),
          const SizedBox(height: 4),
          Text(label, style: BiladaText.label(size: 11), textAlign: TextAlign.center),
          const SizedBox(height: 2),
          Text(value, style: BiladaText.title(color: color, size: 22)),
          if (sub != null) ...[
            const SizedBox(height: 4),
            Text(
              sub,
              textAlign: TextAlign.center,
              style: BiladaText.label(size: 10),
            ),
          ],
        ],
      ),
    );
  }
}
