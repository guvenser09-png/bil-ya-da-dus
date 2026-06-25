import 'package:confetti/confetti.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:quizroyale/core/theme/app_theme.dart';
import 'package:quizroyale/features/result/providers/result_provider.dart';
import 'package:quizroyale/shared/widgets/bilada_ui.dart';
import 'package:quizroyale/shared/widgets/player_avatar.dart';

class ResultScreen extends ConsumerStatefulWidget {
  const ResultScreen({super.key, required this.gameId});
  final String gameId;

  @override
  ConsumerState<ResultScreen> createState() => _ResultScreenState();
}

class _ResultScreenState extends ConsumerState<ResultScreen> with TickerProviderStateMixin {
  late final ConfettiController _confetti = ConfettiController(duration: const Duration(seconds: 4));
  late final AnimationController _podiumController =
      AnimationController(vsync: this, duration: const Duration(milliseconds: 900));
  late final Animation<double> _podiumAnimation =
      CurvedAnimation(parent: _podiumController, curve: Curves.elasticOut);

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(resultProvider(widget.gameId).notifier).fetchResult(widget.gameId);
    });
  }

  @override
  void dispose() {
    _confetti.dispose();
    _podiumController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(resultProvider(widget.gameId));

    ref.listen(resultProvider(widget.gameId), (prev, next) {
      if (prev?.isLoading == true && next.isLoading == false && next.result != null) {
        if (next.isWinner) _confetti.play();
        _podiumController.forward();
      }
    });

    return Scaffold(
      body: Stack(
        children: [
          const Positioned.fill(child: BiladaBackground(gradient: AppTheme.epicGradient, showFloaters: false)),
          Align(
            alignment: Alignment.topCenter,
            child: ConfettiWidget(
              confettiController: _confetti,
              blastDirectionality: BlastDirectionality.explosive,
              numberOfParticles: 30,
              colors: const [AppTheme.cPrimary, AppTheme.gold, AppTheme.cSecondary, AppTheme.cTertiary],
            ),
          ),
          if (state.isLoading)
            const Center(child: CircularProgressIndicator(color: AppTheme.cPrimaryContainer))
          else if (state.result == null)
            _ErrorView(onRetry: () => ref.read(resultProvider(widget.gameId).notifier).fetchResult(widget.gameId))
          else
            _ResultBody(
              state: state,
              podiumAnimation: _podiumAnimation,
              onPlayAgain: () => context.go('/lobby'),
              onHome: () => context.go('/home'),
            ),
        ],
      ),
    );
  }
}

class _ResultBody extends StatelessWidget {
  const _ResultBody({
    required this.state,
    required this.podiumAnimation,
    required this.onPlayAgain,
    required this.onHome,
  });

  final ResultState state;
  final Animation<double> podiumAnimation;
  final VoidCallback onPlayAgain;
  final VoidCallback onHome;

  @override
  Widget build(BuildContext context) {
    final result = state.result!;
    final top3 = result['top_players'] as List? ?? const [];
    final my = result['my_result'] as Map<String, dynamic>? ?? const {};
    final isWinner = state.isWinner;
    // Oyuncu hiç elenmeden maçı bitirdi mi? (kazanan değilse bile "hayatta kaldın")
    final survived = state.survived;
    final score = my['score'] as int? ?? 0;
    final correct = my['correct_answers'] as int? ?? 0;
    final total = my['total_rounds'] as int? ?? 5;
    final xp = my['xp_gained'] as int? ?? 0;
    final finalRound = my['final_round'] as int? ?? 0;
    final rank = my['rank'] as int? ?? 0;
    final coinsEarned = my['coins_earned'] as int? ?? 0;

    // Resolve the winner name: explicit `winner` field, else top1 username.
    final top1 = top3.isNotEmpty ? top3.first as Map? : null;
    final winnerName = (result['winner'] as String?)?.trim().isNotEmpty == true
        ? result['winner'] as String
        : (top1?['username'] as String?)?.trim().isNotEmpty == true
            ? top1!['username'] as String
            : null;
    // Kazananın gerçek avatar_id'si (3D karakter için).
    final winnerEntry = top3.cast<Map?>().firstWhere(
          (p) => p?['username'] == winnerName,
          orElse: () => top1,
        );
    final winnerAvatarId = (winnerEntry?['avatar_id'] as String?) ?? 'default_01';

    return SafeArea(
      child: SingleChildScrollView(
        padding: const EdgeInsets.symmetric(horizontal: 20),
        child: Column(
          children: [
            const SizedBox(height: 10),
            if (isWinner) ...[
              Text('KAZANAN!', style: BiladaText.displayXl(size: 36)),
              const SizedBox(height: 6),
              const PillBadge('ŞAMPİYON — SENSİN!', color: AppTheme.cTertiaryContainer, fg: AppTheme.cOnTertiary),
            ] else if (survived) ...[
              // Son tura dek dayandı ama şampiyon olamadı — ELENMEDİ. Bu oyuncuya
              // "elendin" demek yanlıştı (asıl bug). Pozitif "hayatta kaldın" mesajı.
              Text('HAYATTA KALDIN!', style: BiladaText.displayXl(color: AppTheme.cTertiary, size: 32)),
              const SizedBox(height: 4),
              Text('Sona kadar dayandın — şampiyonluk kıl payı! 🔥',
                  style: BiladaText.body(color: AppTheme.cOnSurfaceVariant)),
            ] else ...[
              Text('ELENDİN', style: BiladaText.displayXl(color: AppTheme.cPrimary, size: 30)),
              const SizedBox(height: 4),
              Text('$finalRound. turda elendin 💪', style: BiladaText.body(color: AppTheme.cOnSurfaceVariant)),
            ],
            const SizedBox(height: 12),

            // ── Champion banner — herkese kazananı net göster ────────────
            if (winnerName != null)
              _ChampionBanner(winnerName: winnerName, avatarId: winnerAvatarId, isMe: isWinner),
            if (top3.isNotEmpty) ...[
              const SizedBox(height: 14),
              ScaleTransition(scale: podiumAnimation, child: _Podium(top3: top3)),
            ],
            const SizedBox(height: 18),
            GridView.count(
              crossAxisCount: 2,
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              mainAxisSpacing: 12,
              crossAxisSpacing: 12,
              childAspectRatio: 2.0,
              children: [
                _rewardCard(
                    'Sıralaman',
                    isWinner
                        ? '#1'
                        // Hayatta kalan/elenen için: gerçek sıra (rank) varsa onu,
                        // yoksa elenenler için ulaşılan turu göster.
                        : rank > 0
                            ? '#$rank'
                            : (survived ? 'Hayatta' : 'Tur $finalRound'),
                    AppTheme.cPrimary),
                _rewardCard('Kazanılan Puan', '+$score', AppTheme.cTertiary),
                _rewardCard('Doğru', '$correct/$total', AppTheme.gold),
                _rewardCard('XP Artışı', '+$xp', AppTheme.cSecondary),
              ],
            ),
            // Coin ödülü — yalnızca pozitifse göster (0 ise günlük limit dolmuş
            // olabilir; gereksiz "0 coin" göstermeyiz).
            if (coinsEarned > 0) ...[
              const SizedBox(height: 14),
              _CoinsEarnedBanner(coins: coinsEarned),
            ],
            // ── Maç özeti — soruları & doğru cevapları gör ──────────────
            // Yalnızca gerçek soru verisi varsa göster (eski maçlarda boş).
            if (state.questions.isNotEmpty) ...[
              const SizedBox(height: 14),
              _MatchSummaryButton(questions: state.questions),
            ],
            const SizedBox(height: 18),
            // İki aksiyon butonu YAN YANA → tek ekrana sığar, kaydırma gerekmez.
            Row(
              children: [
                Expanded(
                  child: ChunkyButton(
                    height: 58,
                    onPressed: onPlayAgain,
                    child: const Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.refresh_rounded, size: 18),
                        SizedBox(width: 6),
                        Flexible(child: Text('TEKRAR OYNA', overflow: TextOverflow.ellipsis)),
                      ],
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: ChunkyButton(
                    height: 58,
                    color: AppTheme.cSecondaryContainer,
                    foreground: Colors.white,
                    shadowColor: AppTheme.cSecondaryShadow,
                    onPressed: onHome,
                    child: const Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.home_rounded, size: 18),
                        SizedBox(width: 6),
                        Flexible(child: Text('ANA MENÜ', overflow: TextOverflow.ellipsis)),
                      ],
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 20),
          ],
        ),
      ),
    );
  }

  Widget _rewardCard(String label, String value, Color color) {
    return GlassCard(
      padding: const EdgeInsets.all(12),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Text(label.toUpperCase(), style: BiladaText.label(color: color, size: 11), textAlign: TextAlign.center),
          const SizedBox(height: 6),
          FittedBox(child: Text(value, style: BiladaText.displayXl(color: color, size: 36))),
        ],
      ),
    );
  }
}

/// Maç sonu coin ödülü banner'ı — "+N coin kazandın".
class _CoinsEarnedBanner extends StatelessWidget {
  const _CoinsEarnedBanner({required this.coins});
  final int coins;

  @override
  Widget build(BuildContext context) {
    return GlassCard(
      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Text('🪙', style: TextStyle(fontSize: 26)),
          const SizedBox(width: 12),
          Text('+$coins Altın kazandın!',
              style: BiladaText.title(color: AppTheme.gold, size: 18)),
        ],
      ),
    );
  }
}

/// Kazananı sahneye çıkaran "şampiyon" kartı. Kozmetiği (3D karakter + altın
/// çerçeve + parıltı) DAHA BÜYÜK gösterir — görünürlük = kozmetik cazibesi.
class _ChampionBanner extends StatelessWidget {
  const _ChampionBanner({required this.winnerName, required this.avatarId, required this.isMe});
  final String winnerName;
  final String avatarId;
  final bool isMe;

  @override
  Widget build(BuildContext context) {
    return GlassCard(
      padding: const EdgeInsets.fromLTRB(20, 22, 20, 20),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.emoji_events_rounded, color: AppTheme.gold, size: 20),
              const SizedBox(width: 8),
              Text(
                isMe ? 'ŞAMPİYON SENSİN' : 'TURUN ŞAMPİYONU',
                style: BiladaText.label(color: AppTheme.gold, size: 13),
              ),
              const SizedBox(width: 8),
              const Icon(Icons.emoji_events_rounded, color: AppTheme.gold, size: 20),
            ],
          ),
          const SizedBox(height: 16),
          // Büyük şampiyon avatarı — kuşandığı kozmetik öne çıkar.
          Container(
            padding: const EdgeInsets.all(4),
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: const SweepGradient(
                colors: [AppTheme.gold, Color(0xFFFFA500), AppTheme.gold],
              ),
              boxShadow: [
                BoxShadow(
                  color: AppTheme.gold.withValues(alpha: 0.55),
                  blurRadius: 28,
                  spreadRadius: 4,
                ),
              ],
            ),
            child: PlayerAvatar(
              avatarId: avatarId,
              username: winnerName,
              size: 104,
              isWinner: true,
            ),
          ),
          const SizedBox(height: 14),
          // İsim — altın renkle vurgulu (isim rengi = kozmetik hissi).
          FittedBox(
            fit: BoxFit.scaleDown,
            child: Text(
              winnerName,
              style: BiladaText.displayXl(color: AppTheme.gold, size: 34),
            ),
          ),
          const SizedBox(height: 6),
          PillBadge(
            isMe ? '#1 — HARİKAYDIN!' : 'BU GÖRÜNÜM ŞAMPİYONUN',
            color: AppTheme.cTertiaryContainer,
            fg: AppTheme.cOnTertiary,
          ),
        ],
      ),
    );
  }
}

class _Podium extends StatelessWidget {
  const _Podium({required this.top3});
  final List top3;

  static const _gold = Color(0xFFFFD700);
  static const _silver = Color(0xFFC0C0C0);
  static const _bronze = Color(0xFFCD7F32);

  @override
  Widget build(BuildContext context) {
    Map? at(int i) => i < top3.length ? top3[i] as Map : null;
    return SizedBox(
      height: 168,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Expanded(child: _slot(at(1), 2, _silver, 70, 52)),
          const SizedBox(width: 10),
          Expanded(flex: 12, child: _slot(at(0), 1, _gold, 96, 72, crown: true)),
          const SizedBox(width: 10),
          Expanded(child: _slot(at(2), 3, _bronze, 48, 46)),
        ],
      ),
    );
  }

  Widget _slot(Map? p, int rank, Color color, double h, double avatar, {bool crown = false}) {
    if (p == null) return const SizedBox.shrink();
    final username = (p['username'] ?? '').toString();
    final score = p['score'] as int? ?? 0;
    final avatarId = (p['avatar_id'] as String?) ?? 'default_01';
    return Column(
      mainAxisAlignment: MainAxisAlignment.end,
      children: [
        if (crown) Icon(Icons.emoji_events_rounded, color: color, size: 40),
        Container(
          padding: const EdgeInsets.all(3),
          decoration: BoxDecoration(shape: BoxShape.circle, border: Border.all(color: color, width: 3)),
          child: PlayerAvatar(avatarId: avatarId, username: username, size: avatar, isWinner: rank == 1),
        ),
        const SizedBox(height: 6),
        Text(username.length > 8 ? '${username.substring(0, 8)}…' : username,
            style: BiladaText.label(color: AppTheme.cOnSurface, size: 11)),
        Text('$score', style: BiladaText.title(color: color, size: 14)),
        const SizedBox(height: 4),
        Container(
          height: h,
          width: double.infinity,
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.2),
            borderRadius: const BorderRadius.vertical(top: Radius.circular(12)),
            border: Border(top: BorderSide(color: color.withValues(alpha: 0.5), width: 2)),
          ),
          alignment: Alignment.topCenter,
          padding: const EdgeInsets.only(top: 8),
          child: Text('$rank', style: BiladaText.displayXl(color: color.withValues(alpha: 0.6), size: rank == 1 ? 40 : 28)),
        ),
      ],
    );
  }
}

/// "Maç Özeti" butonu — alt sayfada soru & doğru cevap listesini açar.
class _MatchSummaryButton extends StatelessWidget {
  const _MatchSummaryButton({required this.questions});
  final List<Map<String, dynamic>> questions;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: double.infinity,
      child: ChunkyButton(
        height: 54,
        color: AppTheme.cSurfaceContainerHigh,
        foreground: AppTheme.cOnSurface,
        shadowColor: AppTheme.cSurfaceContainerLowest,
        onPressed: () => _showMatchSummary(context, questions),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.fact_check_rounded, size: 20, color: AppTheme.cTertiary),
            const SizedBox(width: 8),
            Text('SORULARI GÖR (${questions.length})',
                style: BiladaText.label(color: AppTheme.cOnSurface, size: 13)),
          ],
        ),
      ),
    );
  }
}

void _showMatchSummary(BuildContext context, List<Map<String, dynamic>> questions) {
  showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    builder: (_) => _MatchSummarySheet(questions: questions),
  );
}

class _MatchSummarySheet extends StatelessWidget {
  const _MatchSummarySheet({required this.questions});
  final List<Map<String, dynamic>> questions;

  @override
  Widget build(BuildContext context) {
    return DraggableScrollableSheet(
      initialChildSize: 0.85,
      minChildSize: 0.5,
      maxChildSize: 0.95,
      expand: false,
      builder: (context, scrollController) {
        return Container(
          decoration: const BoxDecoration(
            color: AppTheme.cSurfaceContainerLow,
            borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
          ),
          child: Column(
            children: [
              const SizedBox(height: 10),
              Container(
                width: 44,
                height: 5,
                decoration: BoxDecoration(
                  color: AppTheme.cOnSurfaceVariant.withValues(alpha: 0.4),
                  borderRadius: BorderRadius.circular(3),
                ),
              ),
              const SizedBox(height: 14),
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const Icon(Icons.fact_check_rounded, color: AppTheme.cTertiary, size: 22),
                  const SizedBox(width: 8),
                  Text('MAÇ ÖZETİ', style: BiladaText.headline(size: 22)),
                ],
              ),
              const SizedBox(height: 4),
              Text('Doğru cevaplar neymiş?',
                  style: BiladaText.body(color: AppTheme.cOnSurfaceVariant, size: 14)),
              const SizedBox(height: 12),
              Expanded(
                child: ListView.separated(
                  controller: scrollController,
                  padding: const EdgeInsets.fromLTRB(16, 4, 16, 28),
                  itemCount: questions.length,
                  separatorBuilder: (_, __) => const SizedBox(height: 12),
                  itemBuilder: (_, i) => _QuestionSummaryCard(data: questions[i], index: i),
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}

/// Tek bir sorunun özet kartı: metin + doğru cevap (yeşil) + kullanıcının
/// cevabı (doğru ✓ yeşil / yanlış ✗ kırmızı). Tüm alanlar savunmacı okunur.
class _QuestionSummaryCard extends StatelessWidget {
  const _QuestionSummaryCard({required this.data, required this.index});
  final Map<String, dynamic> data;
  final int index;

  @override
  Widget build(BuildContext context) {
    final round = data['round'] as int? ?? (index + 1);
    final type = (data['type'] as String?) ?? '';
    final text = (data['text'] as String?)?.trim() ?? '';
    final imageUrl = (data['image_url'] as String?)?.trim();
    final hasImage = imageUrl != null && imageUrl.isNotEmpty;

    final correctText = _correctAnswerText(data, type);

    // Kullanıcının cevabı (varsa). correct_bool yoksa null → nötr göster.
    final hasMyAnswer = data.containsKey('your_answer') && data['your_answer'] != null;
    final correctBool = data['correct_bool'];
    final isCorrect = correctBool == true;
    final myAnswerText = hasMyAnswer ? _userAnswerText(data, type) : null;

    return GlassCard(
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: AppTheme.cTertiary.withValues(alpha: 0.18),
                  borderRadius: BorderRadius.circular(20),
                ),
                child: Text('TUR $round',
                    style: BiladaText.label(color: AppTheme.cTertiary, size: 11)),
              ),
              const Spacer(),
              if (hasMyAnswer)
                Icon(
                  isCorrect ? Icons.check_circle_rounded : Icons.cancel_rounded,
                  color: isCorrect ? AppTheme.cTertiary : AppTheme.cError,
                  size: 22,
                ),
            ],
          ),
          const SizedBox(height: 10),
          if (hasImage) ...[
            ClipRRect(
              borderRadius: BorderRadius.circular(12),
              child: Image.network(
                imageUrl,
                height: 120,
                width: double.infinity,
                fit: BoxFit.cover,
                errorBuilder: (_, __, ___) => const SizedBox.shrink(),
              ),
            ),
            const SizedBox(height: 10),
          ],
          if (text.isNotEmpty) ...[
            Text(text, style: BiladaText.title(color: AppTheme.cOnSurface, size: 16)),
            const SizedBox(height: 12),
          ],
          // Doğru cevap — daima yeşil vurgulu.
          _AnswerRow(
            label: 'Doğru cevap',
            value: correctText,
            color: AppTheme.cTertiary,
            icon: Icons.verified_rounded,
          ),
          // Kullanıcının cevabı — yanlışsa kırmızıyla göster (doğruysa zaten
          // doğru cevapla aynı; tekrarı önlemek için yalnızca yanlışta).
          if (myAnswerText != null && !isCorrect) ...[
            const SizedBox(height: 8),
            _AnswerRow(
              label: 'Senin cevabın',
              value: myAnswerText,
              color: AppTheme.cError,
              icon: Icons.close_rounded,
            ),
          ],
        ],
      ),
    );
  }

  /// Tur tipine göre doğru cevabı okunur metne çevir.
  String _correctAnswerText(Map<String, dynamic> d, String type) {
    // Tahmin turu: sayısal değer + birim.
    if (type == 'tahmin' || d.containsKey('unit')) {
      final ca = d['correct_answer'];
      final unit = (d['unit'] as String?)?.trim() ?? '';
      if (ca != null) {
        final v = ca is num ? _fmtNum(ca) : ca.toString();
        return unit.isNotEmpty ? '$v $unit' : v;
      }
    }
    // Doğru/Yanlış turu.
    if (type == 'dogru_yanlis') {
      final ca = d['correct_answer'];
      if (ca is bool) return ca ? 'Doğru' : 'Yanlış';
      if (ca == 1 || ca == 0) return ca == 1 ? 'Doğru' : 'Yanlış';
    }
    // Çoktan seçmeli / görsel: hazır metin alanı.
    final optText = (d['correct_option_text'] as String?)?.trim();
    if (optText != null && optText.isNotEmpty) return optText;
    // Fallback: correct_index ile options'tan çek.
    final options = d['options'];
    final idx = d['correct_index'] ?? d['correct_answer'];
    if (options is List && idx is int && idx >= 0 && idx < options.length) {
      return options[idx].toString();
    }
    return d['correct_answer']?.toString() ?? '—';
  }

  /// Kullanıcının verdiği cevabı okunur metne çevir.
  String _userAnswerText(Map<String, dynamic> d, String type) {
    final ya = d['your_answer'];
    if (ya == null) return '—';
    if (type == 'dogru_yanlis') {
      if (ya is bool) return ya ? 'Doğru' : 'Yanlış';
      if (ya == 1 || ya == 0) return ya == 1 ? 'Doğru' : 'Yanlış';
    }
    if (type == 'tahmin' || d.containsKey('unit')) {
      final unit = (d['unit'] as String?)?.trim() ?? '';
      final v = ya is num ? _fmtNum(ya) : ya.toString();
      return unit.isNotEmpty ? '$v $unit' : v;
    }
    final options = d['options'];
    if (options is List && ya is int && ya >= 0 && ya < options.length) {
      return options[ya].toString();
    }
    return ya.toString();
  }

  String _fmtNum(num n) =>
      n == n.roundToDouble() ? n.toInt().toString() : n.toString();
}

class _AnswerRow extends StatelessWidget {
  const _AnswerRow({
    required this.label,
    required this.value,
    required this.color,
    required this.icon,
  });
  final String label;
  final String value;
  final Color color;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withValues(alpha: 0.4), width: 1.4),
      ),
      child: Row(
        children: [
          Icon(icon, color: color, size: 18),
          const SizedBox(width: 10),
          Text('$label: ',
              style: BiladaText.label(color: color, size: 12)),
          Expanded(
            child: Text(
              value,
              style: BiladaText.title(color: AppTheme.cOnSurface, size: 15),
            ),
          ),
        ],
      ),
    );
  }
}

class _ErrorView extends StatelessWidget {
  const _ErrorView({required this.onRetry});
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.error_outline_rounded, color: AppTheme.cError, size: 48),
          const SizedBox(height: 16),
          Text('Sonuç yüklenemedi', style: BiladaText.body(color: AppTheme.cOnSurfaceVariant)),
          const SizedBox(height: 16),
          ElevatedButton(onPressed: onRetry, child: const Text('Tekrar Dene')),
        ],
      ),
    );
  }
}
