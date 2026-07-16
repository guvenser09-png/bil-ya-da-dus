// ZOR MOD (v1.2): Rafta duran turnuva "ZOR MOD" olarak geri açıldı ve
// yeniden markalandı. Ana ekrandaki "🔥 ZOR MOD" kartından girilir.
// Giriş 100 altın; ödül havuzu (prize_pool + prize_top3) BÜYÜK gösterilir.

import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:quizroyale/core/theme/app_theme.dart';
import 'package:quizroyale/features/auth/providers/auth_provider.dart';
import 'package:quizroyale/features/tournament/providers/tournament_provider.dart';
import 'package:quizroyale/shared/widgets/bilada_ui.dart';

/// ZOR MOD — "Kendine güveniyor musun?"
///
/// Gaza getiren, sinematik bir cesaret ekranı. Sahne karanlık bir arena;
/// yükselen kıvılcımlar, nefes alan altın ışıltı, dönen enerji halkası ve
/// dev bir 3× madalyonu odakta. Ödül havuzu büyük gösterilir; alev göstergeli
/// zorluk (difficulty 4-5) + nabız atan CTA.
///
/// KORUNAN DAVRANIŞLAR (provider sözleşmesi hiç değişmedi):
///   1) entered → bakiye tazele + /lobby (mode:tournament)
///   2) error → SnackBar + clearError
///   3) secondsLeft canlı geri sayım
///   4) CTA yalnızca affordable && !entering iken aktif; bedel option'dan okunur
///   5) loading/error iskeletleri
///   6) yetersiz altın → mağazaya (reklam izleyip altın kazan) yönlendirme
class TournamentScreen extends ConsumerStatefulWidget {
  const TournamentScreen({super.key});

  @override
  ConsumerState<TournamentScreen> createState() => _TournamentScreenState();
}

class _TournamentScreenState extends ConsumerState<TournamentScreen>
    with TickerProviderStateMixin {
  late final AnimationController _breathe; // nabız/ışıltı (ileri-geri)
  late final AnimationController _shimmer; // parıltı taraması (döngü)
  late final AnimationController _embers; // kıvılcım + halka dönüşü (yavaş döngü)
  late final List<_Ember> _emberSeeds;

  @override
  void initState() {
    super.initState();
    _breathe = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 2200),
    )..repeat(reverse: true);
    _shimmer = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 2600),
    )..repeat();
    _embers = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 9),
    )..repeat();

    final rnd = math.Random(7);
    _emberSeeds = List.generate(
      18,
      (_) => _Ember(
        x: rnd.nextDouble(),
        phase: rnd.nextDouble(),
        speed: 0.55 + rnd.nextDouble() * 0.9,
        size: 1.4 + rnd.nextDouble() * 2.8,
        drift: (rnd.nextDouble() - 0.5) * 0.10,
      ),
    );

    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(tournamentProvider.notifier).load();
    });
  }

  @override
  void dispose() {
    _breathe.dispose();
    _shimmer.dispose();
    _embers.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(tournamentProvider);

    // ── KORUNAN DAVRANIŞ 1 & 2 ─────────────────────────────────────────
    ref.listen(tournamentProvider, (prev, next) {
      if (next.entered && (prev == null || !prev.entered)) {
        ref.read(tournamentProvider.notifier).clearEntered();
        ref.read(authProvider.notifier).refreshUser();
        context.go('/lobby', extra: 'tournament');
      }
      if (next.error != null && (prev?.error != next.error)) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(next.error!), backgroundColor: AppTheme.danger),
        );
        ref.read(tournamentProvider.notifier).clearError();
      }
    });

    return Scaffold(
      backgroundColor: const Color(0xFF20060F),
      body: Stack(
        children: [
          // Sahne: derin arena gradyanı.
          const Positioned.fill(
            child: DecoratedBox(
              decoration: BoxDecoration(
                gradient: RadialGradient(
                  center: Alignment(0, -0.45),
                  radius: 1.25,
                  colors: [
                    Color(0xFF7A0A45), // sıcak çekirdek
                    Color(0xFF2A0717),
                    Color(0xFF120308), // kenar karanlık
                  ],
                  stops: [0.0, 0.55, 1.0],
                ),
              ),
            ),
          ),
          // Üstten inen spot ışığı.
          Positioned.fill(
            child: IgnorePointer(
              child: AnimatedBuilder(
                animation: _breathe,
                builder: (_, __) => CustomPaint(
                  painter: _SpotlightPainter(t: _breathe.value),
                ),
              ),
            ),
          ),
          // Yükselen kıvılcımlar.
          Positioned.fill(
            child: IgnorePointer(
              child: AnimatedBuilder(
                animation: _embers,
                builder: (_, __) => CustomPaint(
                  painter: _EmberPainter(
                    progress: _embers.value,
                    embers: _emberSeeds,
                  ),
                ),
              ),
            ),
          ),
          SafeArea(
            child: Column(
              children: [
                _TopStrip(secondsLeft: state.secondsLeft, loaded: state.loaded),
                Expanded(
                  child: state.loading && !state.loaded
                      ? const Center(
                          child: CircularProgressIndicator(color: AppTheme.gold),
                        )
                      : (state.error != null && state.rewards.isEmpty)
                          ? _ErrorView(
                              onRetry: () =>
                                  ref.read(tournamentProvider.notifier).load(),
                            )
                          : _Content(
                              state: state,
                              breathe: _breathe,
                              shimmer: _shimmer,
                              embers: _embers,
                            ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

// ════════════════════════════════════════════════════════════════════════
//  İÇERİK
// ════════════════════════════════════════════════════════════════════════

class _Content extends StatelessWidget {
  const _Content({
    required this.state,
    required this.breathe,
    required this.shimmer,
    required this.embers,
  });
  final TournamentState state;
  final Animation<double> breathe;
  final Animation<double> shimmer;
  final Animation<double> embers;

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.fromLTRB(22, 4, 22, 40),
      children: [
        _Hero(state: state, breathe: breathe, shimmer: shimmer, embers: embers),
        const SizedBox(height: 22),
        // ÖDÜL HAVUZU — sayfanın en cazip vurgusu (payload: prize_pool + top3).
        _PrizePool(
          prizePool: state.prizePool,
          prizeTop3: state.prizeTop3,
          breathe: breathe,
        ),
        const SizedBox(height: 26),
        _StatusStrip(
          rank: state.myRank,
          score: state.myScore,
          pointsToNext: state.pointsToNext,
        ),
        const SizedBox(height: 18),
        // Sezon puanı çarpanını hatırlatan ince not — Sıralama'ya yönlendirir.
        const _SeasonHint(),
        const SizedBox(height: 26),
        _EntryCard(state: state, breathe: breathe, shimmer: shimmer),
      ],
    );
  }
}

// ════════════════════════════════════════════════════════════════════════
//  1) ÜST ŞERİT — ARENA + canlı geri sayım
// ════════════════════════════════════════════════════════════════════════

class _TopStrip extends StatelessWidget {
  const _TopStrip({required this.secondsLeft, required this.loaded});
  final int secondsLeft;
  final bool loaded;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(6, 6, 16, 0),
      child: Row(
        children: [
          IconButton(
            onPressed: () =>
                context.canPop() ? context.pop() : context.go('/home'),
            icon: const Icon(Icons.arrow_back_rounded, color: Colors.white70),
          ),
          const Spacer(),
          const Icon(Icons.local_fire_department_rounded,
              color: AppTheme.gold, size: 18),
          const SizedBox(width: 7),
          Text('ZOR MOD',
              style: BiladaText.label(color: AppTheme.gold, size: 16)
                  .copyWith(letterSpacing: 3)),
          const Spacer(),
          if (loaded)
            _CountdownPill(secondsLeft: secondsLeft)
          else
            const SizedBox(width: 48),
        ],
      ),
    );
  }
}

/// Kompakt canlı geri sayım hapı — gün:saat:dk (KORUNAN 3).
class _CountdownPill extends StatelessWidget {
  const _CountdownPill({required this.secondsLeft});
  final int secondsLeft;

  @override
  Widget build(BuildContext context) {
    final s = secondsLeft < 0 ? 0 : secondsLeft;
    final d = s ~/ 86400;
    final h = (s % 86400) ~/ 3600;
    final m = (s % 3600) ~/ 60;
    final text = d > 0
        ? '${d}g ${h}s ${m}d'
        : '${h.toString().padLeft(2, '0')}:${m.toString().padLeft(2, '0')}:${(s % 60).toString().padLeft(2, '0')}';

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: AppTheme.gold.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: AppTheme.gold.withValues(alpha: 0.35)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.timer_outlined, color: AppTheme.gold, size: 14),
          const SizedBox(width: 5),
          Text(text, style: BiladaText.label(color: AppTheme.gold, size: 12)),
        ],
      ),
    );
  }
}

// ════════════════════════════════════════════════════════════════════════
//  2) KAHRAMAN — sinematik 3× madalyon
// ════════════════════════════════════════════════════════════════════════

class _Hero extends StatelessWidget {
  const _Hero({
    required this.state,
    required this.breathe,
    required this.shimmer,
    required this.embers,
  });
  final TournamentState state;
  final Animation<double> breathe;
  final Animation<double> shimmer;
  final Animation<double> embers;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        const SizedBox(height: 10),
        Text(
          'ZOR MOD',
          style: BiladaText.label(color: Colors.white60, size: 12)
              .copyWith(letterSpacing: 5),
        ),
        const SizedBox(height: 18),
        SizedBox(
          width: 230,
          height: 230,
          child: Stack(
            alignment: Alignment.center,
            children: [
              // (a) Nefes alan dış ışıltı.
              AnimatedBuilder(
                animation: breathe,
                builder: (_, __) {
                  final t = breathe.value;
                  return Container(
                    width: 188,
                    height: 188,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      boxShadow: [
                        BoxShadow(
                          color: AppTheme.gold.withValues(alpha: 0.30 + 0.30 * t),
                          blurRadius: 50 + 40 * t,
                          spreadRadius: 2 + 8 * t,
                        ),
                        BoxShadow(
                          color: AppTheme.accentOrange
                              .withValues(alpha: 0.18 + 0.18 * t),
                          blurRadius: 70 + 30 * t,
                          spreadRadius: 4,
                        ),
                      ],
                    ),
                  );
                },
              ),
              // (b) Dönen enerji halkası (sweep gradyan).
              AnimatedBuilder(
                animation: embers,
                builder: (_, __) => Transform.rotate(
                  angle: embers.value * 2 * math.pi,
                  child: Container(
                    width: 212,
                    height: 212,
                    decoration: const BoxDecoration(
                      shape: BoxShape.circle,
                      gradient: SweepGradient(
                        colors: [
                          Color(0x00FFD23F),
                          AppTheme.gold,
                          Color(0x00FFD23F),
                          Color(0xFFFF6B35),
                          Color(0x00FFD23F),
                        ],
                        stops: [0.0, 0.18, 0.4, 0.62, 1.0],
                      ),
                    ),
                  ),
                ),
              ),
              // (c) Madalyon altın çerçeve.
              Container(
                width: 190,
                height: 190,
                decoration: const BoxDecoration(
                  shape: BoxShape.circle,
                  gradient: AppTheme.goldGradient,
                ),
              ),
              // (d) Madalyon yüzü (koyu) + 3× + PUAN.
              Container(
                width: 176,
                height: 176,
                decoration: const BoxDecoration(
                  shape: BoxShape.circle,
                  gradient: RadialGradient(
                    colors: [Color(0xFF4A0026), Color(0xFF2A0014)],
                  ),
                ),
                alignment: Alignment.center,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const SizedBox(height: 6),
                    _ShimmerSweep(
                      animation: shimmer,
                      child: Text(
                        '${state.pointMultiplier}×',
                        style: BiladaText.displayXl(
                                color: AppTheme.gold, size: 88)
                            .copyWith(height: 1.0),
                      ),
                    ),
                    Text(
                      'PUAN',
                      style: BiladaText.label(color: AppTheme.gold, size: 14)
                          .copyWith(letterSpacing: 6),
                    ),
                    const SizedBox(height: 8),
                  ],
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 22),
        _ShimmerSweep(
          animation: shimmer,
          child: Text(
            'KENDİNE\nGÜVENİYOR MUSUN?',
            textAlign: TextAlign.center,
            style: BiladaText.displayXl(color: AppTheme.gold, size: 32)
                .copyWith(height: 1.05, letterSpacing: 0.5),
          ),
        ),
        const SizedBox(height: 12),
        Text(
          'Zayıflar elenir. Cesurlar zirveye yazılır.',
          textAlign: TextAlign.center,
          style: BiladaText.body(color: Colors.white, size: 15),
        ),
        const SizedBox(height: 20),
        // Alev göstergeli zorluk + 3× puan rozeti.
        const _FlameMeter(),
        const SizedBox(height: 12),
        _HeroBadge(
          icon: Icons.bolt_rounded,
          text: '${state.pointMultiplier}× SEZON PUANI',
          color: AppTheme.gold,
        ),
      ],
    );
  }
}

/// 5/5 alev göstergesi — sorular acımasız.
class _FlameMeter extends StatelessWidget {
  const _FlameMeter();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 9),
      decoration: BoxDecoration(
        color: AppTheme.cError.withValues(alpha: 0.10),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: AppTheme.cError.withValues(alpha: 0.4)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            'ZORLUK 4-5 · ACIMASIZ',
            style: BiladaText.label(color: AppTheme.cError, size: 11)
                .copyWith(letterSpacing: 1.5),
          ),
          const SizedBox(width: 10),
          for (int i = 0; i < 5; i++)
            Padding(
              padding: const EdgeInsets.only(left: 1),
              child: Icon(
                Icons.local_fire_department_rounded,
                size: 17,
                color: Color.lerp(
                    AppTheme.accentOrange, AppTheme.cError, i / 4)!,
              ),
            ),
        ],
      ),
    );
  }
}

/// Hero altındaki ince çerçeveli vurgu rozeti.
class _HeroBadge extends StatelessWidget {
  const _HeroBadge(
      {required this.icon, required this.text, required this.color});
  final IconData icon;
  final String text;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: color.withValues(alpha: 0.4)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, color: color, size: 15),
          const SizedBox(width: 6),
          Text(text, style: BiladaText.label(color: color, size: 11)),
        ],
      ),
    );
  }
}

// ════════════════════════════════════════════════════════════════════════
//  2.5) ÖDÜL HAVUZU — büyük, nabız atan altın vitrin
// ════════════════════════════════════════════════════════════════════════

/// ZOR MOD ödül havuzu kartı. prize_pool BÜYÜK; prize_top3 [şampiyon,2.,3.]
/// altın payları rozet olarak. Havuz henüz dolmadıysa (0) yumuşak yer tutucu.
class _PrizePool extends StatelessWidget {
  const _PrizePool({
    required this.prizePool,
    required this.prizeTop3,
    required this.breathe,
  });
  final int prizePool;
  final List<int> prizeTop3;
  final Animation<double> breathe;

  static const _podium = ['👑 Şampiyon', '🥈 2.', '🥉 3.'];

  @override
  Widget build(BuildContext context) {
    final hasPool = prizePool > 0;
    return AnimatedBuilder(
      animation: breathe,
      builder: (_, child) {
        final t = breathe.value;
        return Container(
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(24),
            boxShadow: [
              BoxShadow(
                color: AppTheme.gold.withValues(alpha: 0.18 + 0.22 * t),
                blurRadius: 22 + 20 * t,
                spreadRadius: 1,
              ),
            ],
          ),
          child: child,
        );
      },
      child: Container(
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(24),
          gradient: AppTheme.goldGradient,
        ),
        padding: const EdgeInsets.all(2.5),
        child: Container(
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(21.5),
            gradient: const RadialGradient(
              center: Alignment(-0.5, -0.9),
              radius: 1.5,
              colors: [Color(0xFF4A0026), Color(0xFF2A0014)],
            ),
          ),
          padding: const EdgeInsets.fromLTRB(20, 18, 20, 18),
          child: Column(
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const Text('💰', style: TextStyle(fontSize: 18)),
                  const SizedBox(width: 8),
                  Text(
                    'ÖDÜL HAVUZU',
                    style: BiladaText.label(color: AppTheme.gold, size: 13)
                        .copyWith(letterSpacing: 3),
                  ),
                ],
              ),
              const SizedBox(height: 10),
              if (hasPool) ...[
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  crossAxisAlignment: CrossAxisAlignment.baseline,
                  textBaseline: TextBaseline.alphabetic,
                  children: [
                    Text(
                      _fmt(prizePool),
                      style: BiladaText.displayXl(color: AppTheme.gold, size: 52)
                          .copyWith(height: 1.0),
                    ),
                    const SizedBox(width: 8),
                    Text('altın',
                        style: BiladaText.title(color: Colors.white70, size: 16)),
                  ],
                ),
                const SizedBox(height: 14),
                Row(
                  children: [
                    for (int i = 0; i < 3; i++)
                      Expanded(
                        child: Padding(
                          padding: EdgeInsets.only(
                              left: i == 0 ? 0 : 5, right: i == 2 ? 0 : 5),
                          child: _podiumChip(
                            _podium[i],
                            i < prizeTop3.length ? prizeTop3[i] : null,
                          ),
                        ),
                      ),
                  ],
                ),
              ] else
                Text(
                  'Havuz doluyor — sen girdikçe büyür.',
                  textAlign: TextAlign.center,
                  style: BiladaText.body(color: Colors.white70, size: 13),
                ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _podiumChip(String label, int? gold) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 8),
      decoration: BoxDecoration(
        color: AppTheme.gold.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppTheme.gold.withValues(alpha: 0.3)),
      ),
      child: Column(
        children: [
          Text(label,
              textAlign: TextAlign.center,
              maxLines: 1,
              style: BiladaText.label(color: Colors.white70, size: 10)),
          const SizedBox(height: 4),
          Text(
            gold != null ? _fmt(gold) : '—',
            style: BiladaText.title(color: AppTheme.gold, size: 16),
          ),
        ],
      ),
    );
  }

  /// Binlik ayraçlı altın gösterimi (1234 → 1.234).
  static String _fmt(int n) {
    final s = n.toString();
    final buf = StringBuffer();
    for (int i = 0; i < s.length; i++) {
      if (i > 0 && (s.length - i) % 3 == 0) buf.write('.');
      buf.write(s[i]);
    }
    return buf.toString();
  }
}

// ════════════════════════════════════════════════════════════════════════
//  3) SENİN DURUMUN
// ════════════════════════════════════════════════════════════════════════

class _StatusStrip extends StatelessWidget {
  const _StatusStrip({this.rank, this.score, this.pointsToNext});
  final int? rank;
  final int? score;
  final int? pointsToNext;

  @override
  Widget build(BuildContext context) {
    final hasEntry = rank != null;
    return GlassCard(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      child: Row(
        children: [
          Container(
            width: 48,
            height: 48,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: AppTheme.gold.withValues(alpha: 0.14),
              border: Border.all(color: AppTheme.gold.withValues(alpha: 0.4)),
            ),
            alignment: Alignment.center,
            child: hasEntry
                ? Text('#$rank',
                    style: BiladaText.title(color: AppTheme.gold, size: 15))
                : const Icon(Icons.emoji_events_rounded,
                    color: AppTheme.gold, size: 24),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  hasEntry ? '${score ?? 0} sezon puanı' : 'Henüz katılmadın',
                  style: BiladaText.title(size: 16),
                ),
                const SizedBox(height: 3),
                Text(
                  hasEntry
                      ? (pointsToNext != null && pointsToNext! > 0
                          ? 'Bir üst sıraya $pointsToNext puan'
                          : 'Zirvedesin — şimdi savun.')
                      : 'Yerini al, tablodaki adını gör.',
                  style: BiladaText.label(color: AppTheme.gold, size: 11),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

// ════════════════════════════════════════════════════════════════════════
//  4) SEZON İPUCU — kullanıcıyı Sıralama'ya yönlendiren ince not
// ════════════════════════════════════════════════════════════════════════

/// Aylık lig ödülleri artık yalnızca "Sıralama → SEZON" sekmesinde yaşıyor.
/// Burada sadece çarpanı hatırlatan tek satırlık ince bir yönlendirme var.
class _SeasonHint extends StatelessWidget {
  const _SeasonHint();

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        const Icon(Icons.trending_up_rounded, color: AppTheme.gold, size: 15),
        const SizedBox(width: 7),
        Flexible(
          child: Text(
            "Zor Mod'da sezon puanın 3× işler — Sıralama'da yüksel.",
            textAlign: TextAlign.center,
            style: BiladaText.label(color: Colors.white54, size: 11),
          ),
        ),
      ],
    );
  }
}

// ════════════════════════════════════════════════════════════════════════
//  5) GİRİŞ KARTI — nabız atan baskın CTA
// ════════════════════════════════════════════════════════════════════════

class _EntryCard extends ConsumerWidget {
  const _EntryCard({
    required this.state,
    required this.breathe,
    required this.shimmer,
  });
  final TournamentState state;
  final Animation<double> breathe;
  final Animation<double> shimmer;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final option = state.entryOptions.isNotEmpty ? state.entryOptions.first : null;
    final canEnter = option != null && option.affordable && !state.entering;
    final cost = option?.cost ?? 0;
    final label = option?.currencyLabel ?? 'Altın';
    final insufficient = option != null && !option.affordable;

    return GlassCard(
      padding: const EdgeInsets.all(18),
      child: Column(
        children: [
          Row(
            children: [
              Text('BAKİYEN',
                  style: BiladaText.label(color: Colors.white60, size: 11)),
              const SizedBox(width: 6),
              const Text('🪙', style: TextStyle(fontSize: 14)),
              const SizedBox(width: 4),
              Text('${state.gold}',
                  style: BiladaText.title(color: AppTheme.gold, size: 15)),
              const Spacer(),
              Text('GİRİŞ',
                  style: BiladaText.label(color: Colors.white60, size: 11)),
              const SizedBox(width: 6),
              Text('$cost $label',
                  style: BiladaText.title(
                      color: insufficient ? AppTheme.cError : Colors.white,
                      size: 15)),
            ],
          ),
          const SizedBox(height: 16),
          // Nabız atan altın CTA — sayfanın en güçlü görsel ağırlığı.
          AnimatedBuilder(
            animation: breathe,
            builder: (_, child) {
              final t = canEnter ? breathe.value : 0.0;
              return Container(
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(20),
                  boxShadow: [
                    BoxShadow(
                      color: AppTheme.gold.withValues(alpha: 0.25 + 0.35 * t),
                      blurRadius: 16 + 22 * t,
                      spreadRadius: 1 + 2 * t,
                    ),
                  ],
                ),
                child: child,
              );
            },
            child: ChunkyButton(
              height: 64,
              color: AppTheme.gold,
              foreground: const Color(0xFF3A0020),
              shadowColor: const Color(0xFFB8860B),
              onPressed: canEnter
                  ? () => ref.read(tournamentProvider.notifier).enter()
                  : null,
              child: state.entering
                  ? const SizedBox(
                      width: 22,
                      height: 22,
                      child: CircularProgressIndicator(
                          strokeWidth: 2.5, color: Color(0xFF3A0020)),
                    )
                  : Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Text('CESARETİM VAR — GİR!',
                            style: BiladaText.title(
                                color: const Color(0xFF3A0020), size: 17)),
                        const SizedBox(width: 8),
                        const Text('🔥', style: TextStyle(fontSize: 18)),
                      ],
                    ),
            ),
          ),
          if (insufficient) ...[
            const SizedBox(height: 10),
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(Icons.lock_rounded, color: AppTheme.cError, size: 14),
                const SizedBox(width: 6),
                Text('Yetersiz altın · $cost $label gerekiyor',
                    style: BiladaText.label(color: AppTheme.cError, size: 11)),
              ],
            ),
            const SizedBox(height: 12),
            // Altın yoksa mağazaya yönlendir — orada reklam izleyip altın
            // kazanılabilir (reklam UI'ı başka ekranda; burası yalnız yönlendirir).
            ChunkyButton(
              height: 52,
              color: AppTheme.cSecondaryContainer,
              foreground: Colors.white,
              shadowColor: AppTheme.cSecondaryShadow,
              onPressed: () => context.go('/store'),
              child: const Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.storefront_rounded, size: 18),
                  SizedBox(width: 8),
                  Text('MAĞAZADAN ALTIN KAZAN', style: TextStyle(fontSize: 15)),
                ],
              ),
            ),
          ] else if (canEnter) ...[
            const SizedBox(height: 10),
            Text('Geri dönüş yok. Hazırsan bas.',
                style: BiladaText.label(color: Colors.white54, size: 11)),
          ],
        ],
      ),
    );
  }
}

// ════════════════════════════════════════════════════════════════════════
//  PARILTI TARAMASI (shimmer) — altın metnin üstünden geçen ışık bandı
// ════════════════════════════════════════════════════════════════════════

class _ShimmerSweep extends StatelessWidget {
  const _ShimmerSweep({required this.animation, required this.child});
  final Animation<double> animation;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: animation,
      builder: (_, __) {
        final p = animation.value; // 0..1
        // Işık bandı sola/sağa kayar.
        final dx = (p * 2.0) - 1.0; // -1..1
        return ShaderMask(
          blendMode: BlendMode.srcATop,
          shaderCallback: (rect) {
            return LinearGradient(
              begin: Alignment(dx - 0.4, 0),
              end: Alignment(dx + 0.4, 0),
              colors: const [
                Color(0x00FFFFFF),
                Color(0xCCFFFFFF),
                Color(0x00FFFFFF),
              ],
              stops: const [0.0, 0.5, 1.0],
            ).createShader(rect);
          },
          child: child,
        );
      },
    );
  }
}

// ════════════════════════════════════════════════════════════════════════
//  SAHNE EFEKTLERİ — spot ışığı + yükselen kıvılcımlar
// ════════════════════════════════════════════════════════════════════════

class _SpotlightPainter extends CustomPainter {
  _SpotlightPainter({required this.t});
  final double t; // 0..1 nefes

  @override
  void paint(Canvas canvas, Size size) {
    final rect = Offset.zero & size;
    final paint = Paint()
      ..shader = RadialGradient(
        center: const Alignment(0, -0.7),
        radius: 0.9,
        colors: [
          AppTheme.gold.withValues(alpha: 0.10 + 0.05 * t),
          const Color(0x00000000),
        ],
      ).createShader(rect);
    canvas.drawRect(rect, paint);
  }

  @override
  bool shouldRepaint(covariant _SpotlightPainter old) => old.t != t;
}

class _Ember {
  const _Ember({
    required this.x,
    required this.phase,
    required this.speed,
    required this.size,
    required this.drift,
  });
  final double x; // 0..1 yatay temel konum
  final double phase; // 0..1 başlangıç ofseti
  final double speed; // dikey hız çarpanı
  final double size; // yarıçap (px)
  final double drift; // yatay sapma
}

class _EmberPainter extends CustomPainter {
  _EmberPainter({required this.progress, required this.embers});
  final double progress; // 0..1 döngü
  final List<_Ember> embers;

  @override
  void paint(Canvas canvas, Size size) {
    for (final e in embers) {
      // y: alttan üste; her kıvılcım kendi fazı/hızıyla döner.
      final cycle = (progress * e.speed + e.phase) % 1.0;
      final y = size.height * (1.0 - cycle) + 8;
      final wobble = math.sin((cycle + e.phase) * 2 * math.pi) * 14 * e.drift.sign;
      final x = size.width * e.x + wobble + size.width * e.drift * cycle;
      // Üstte ve altta sönümle.
      final fade = (cycle < 0.12)
          ? cycle / 0.12
          : (cycle > 0.82 ? (1.0 - cycle) / 0.18 : 1.0);
      final alpha = (0.55 * fade).clamp(0.0, 1.0);
      if (alpha <= 0.01) continue;

      final color = Color.lerp(AppTheme.gold, AppTheme.accentOrange, e.phase)!
          .withValues(alpha: alpha);
      final paint = Paint()
        ..color = color
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 2.2);
      canvas.drawCircle(Offset(x, y), e.size, paint);
    }
  }

  @override
  bool shouldRepaint(covariant _EmberPainter old) =>
      old.progress != progress;
}

// ════════════════════════════════════════════════════════════════════════
//  HATA GÖRÜNÜMÜ
// ════════════════════════════════════════════════════════════════════════

class _ErrorView extends StatelessWidget {
  const _ErrorView({required this.onRetry});
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.wifi_off_rounded, color: AppTheme.cOutline, size: 40),
          const SizedBox(height: 12),
          Text('Turnuva yüklenemedi',
              style: BiladaText.body(color: Colors.white70)),
          const SizedBox(height: 12),
          TextButton(onPressed: onRetry, child: const Text('Tekrar Dene')),
        ],
      ),
    );
  }
}
