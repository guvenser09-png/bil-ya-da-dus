import 'package:confetti/confetti.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:quizroyale/core/services/sound_service.dart';
import 'package:quizroyale/core/theme/app_theme.dart';
import 'package:quizroyale/features/auth/providers/auth_provider.dart';
import 'package:quizroyale/features/result/providers/result_provider.dart';
import 'package:quizroyale/features/result/widgets/fireworks_overlay.dart';
import 'package:quizroyale/features/store/providers/store_provider.dart';
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

  // Kutlama (konfeti + havai fişek + alkış) yalnızca BİR kez tetiklenir.
  bool _celebrated = false;
  bool _showFireworks = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(resultProvider(widget.gameId).notifier).fetchResult(widget.gameId);
      // MAÇ SONU BAKİYE: coins_earned/kalkan bedeli sunucuda işlendi —
      // üst bardaki CoinPill'in gerçek kaynağı (authProvider.user.coins)
      // burada zorunlu tazelenir; mağaza bakiyesi de bir sonraki açılışta
      // taze yüklensin diye invalidate edilir.
      ref.read(authProvider.notifier).refreshUser();
      ref.invalidate(storeProvider);
      // WS hızlı yolu: sonuç ekran açılmadan ÖNCE setResult ile dolmuş
      // olabilir — bu durumda ref.listen hiç tetiklenmez, kutlamayı ve
      // podyum animasyonunu burada başlatırız.
      final state = ref.read(resultProvider(widget.gameId));
      if (state.result != null) {
        _podiumController.forward();
        if (state.isWinner) _celebrate();
      }
    });
  }

  /// 🎉 Kazanan kutlaması: konfeti + tam ekran havai fişek + (fanfarın
  /// üstüne binen) alkış. Fanfar (GameSound.win) maç bittiği anda
  /// GameScreen'de çalmaya başladı; alkış ayrı player'dan üstüne gelir.
  void _celebrate() {
    if (_celebrated || !mounted) return;
    _celebrated = true;
    setState(() => _showFireworks = true);
    _confetti.play();
    Future.delayed(const Duration(milliseconds: 350), () {
      if (mounted) SoundService().playApplause();
    });
    // Havai fişek ~4.5 sn'de biter; overlay'i ağaçtan tamamen kaldır.
    Future.delayed(const Duration(milliseconds: 5200), () {
      if (mounted) setState(() => _showFireworks = false);
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
        if (next.isWinner) _celebrate();
        _podiumController.forward();
      }
      // Arkadaşlık isteği geri bildirimi: hata oluştuysa kısa bilgi ver
      // (buton zaten iyimser durumdan geri döner).
      if (next.result != null && next.error != null && prev?.error != next.error) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(next.error!), backgroundColor: AppTheme.danger),
        );
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
              gameId: widget.gameId,
              state: state,
              podiumAnimation: _podiumAnimation,
              onPlayAgain: () => context.go('/lobby'),
              onHome: () => context.go('/home'),
            ),
          // 🎆 Havai fişek — SADECE kazananda, ~4.5 sn sürer ve biter.
          // IgnorePointer içerir → alttaki butonlar tıklanabilir kalır.
          if (_showFireworks) const Positioned.fill(child: FireworksOverlay()),
        ],
      ),
    );
  }
}

class _ResultBody extends ConsumerWidget {
  const _ResultBody({
    required this.gameId,
    required this.state,
    required this.podiumAnimation,
    required this.onPlayAgain,
    required this.onHome,
  });

  final String gameId;
  final ResultState state;
  final Animation<double> podiumAnimation;
  final VoidCallback onPlayAgain;
  final VoidCallback onHome;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
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
    // 👻 Hayalet modu: elendikten sonra bilinen doğrular + altın karşılığı.
    final ghostCorrect = my['ghost_correct'] as int? ?? 0;
    final ghostReward = my['ghost_reward'] as int? ?? 0;
    // 🎯 Şampiyon bahsi: bahis yapıldıysa hedef + tuttu mu + ödül.
    final betOn = my['bet_on'] as String?;
    final betWon = my['bet_won'] == true;
    final betReward = my['bet_reward'] as int? ?? 0;
    // 🛡️ Kalkan bedeli (game_finished kişisel payload): kalkan kırıldıysa ya
    // bedel tahsil edildi (shield_cost) ya da bakiye yetmedi → hediye
    // (shield_gift). İkisi birden gelmez; kırılmadıysa ikisi de yok.
    final shieldCost = (my['shield_cost'] as num?)?.toInt() ?? 0;
    final shieldGift = my['shield_gift'] == true;

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

    final myUsername = ref.watch(authProvider).user?['username'] as String? ?? '';

    // TEK SAYFA DÜZENİ: içerik üstte (küçük ekranlarda scrollable),
    // TEKRAR OYNA + ANA MENÜ alt barda SABİT → butonlara kaydırmasız erişim.
    return SafeArea(
      child: Column(
        children: [
          Expanded(
            child: SingleChildScrollView(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              child: Column(
                children: [
                  const SizedBox(height: 8),
                  if (isWinner)
                    // Kazanan BENİM: büyük "🏆 ŞAMPİYON!" + adım (abartılı
                    // "şampiyonun görünümü" söylemleri kaldırıldı).
                    _ChampionBanner(
                      winnerName: winnerName ?? myUsername,
                      avatarId: winnerAvatarId,
                    )
                  else ...[
                    if (survived) ...[
                      Text('HAYATTA KALDIN!',
                          style: BiladaText.displayXl(color: AppTheme.cTertiary, size: 26)),
                      const SizedBox(height: 2),
                      Text('Sona kadar dayandın — şampiyonluk kıl payı! 🔥',
                          style: BiladaText.body(color: AppTheme.cOnSurfaceVariant, size: 13)),
                    ] else ...[
                      Text('ELENDİN', style: BiladaText.displayXl(color: AppTheme.cPrimary, size: 24)),
                      const SizedBox(height: 2),
                      Text('$finalRound. turda elendin 💪',
                          style: BiladaText.body(color: AppTheme.cOnSurfaceVariant, size: 13)),
                    ],
                    // Kazanan başkası: küçük, sade "Şampiyon: <isim>" satırı.
                    if (winnerName != null) ...[
                      const SizedBox(height: 10),
                      _ChampionLine(winnerName: winnerName),
                    ],
                  ],
                  if (top3.isNotEmpty) ...[
                    const SizedBox(height: 10),
                    ScaleTransition(
                      scale: podiumAnimation,
                      child: _Podium(top3: top3, gameId: gameId, myUsername: myUsername),
                    ),
                  ],
                  const SizedBox(height: 10),
                  // İstatistikler: 2x2 büyük kart yerine TEK SATIR mini rozet
                  // şeridi (kompakt — tek sayfa hedefi).
                  _StatsStrip(stats: [
                    (
                      'SIRA',
                      isWinner
                          ? '#1'
                          // Gerçek sıra (rank) varsa onu, yoksa elenenler için
                          // ulaşılan turu göster.
                          : rank > 0
                              ? '#$rank'
                              : (survived ? 'Hayatta' : 'Tur $finalRound'),
                      AppTheme.cPrimary
                    ),
                    ('PUAN', '+$score', AppTheme.cTertiary),
                    ('DOĞRU', '$correct/$total', AppTheme.gold),
                    ('XP', '+$xp', AppTheme.cSecondary),
                  ]),
                  // Ödül/bedel bilgileri: tek satırlık kompakt şeritler.
                  // Coin — yalnızca pozitifse (0 ise günlük limit dolmuş olabilir).
                  if (coinsEarned > 0) ...[
                    const SizedBox(height: 8),
                    _MiniStrip(emoji: '🪙', text: '+$coinsEarned Altın kazandın!', color: AppTheme.gold),
                  ],
                  // 👻 Hayalet modu — elenmişken bilinen doğrular altın oldu.
                  if (ghostCorrect > 0) ...[
                    const SizedBox(height: 8),
                    _MiniStrip(
                        emoji: '👻',
                        text: 'Hayalet modunda $ghostCorrect doğru — +$ghostReward altın!',
                        color: AppTheme.cSecondary),
                  ],
                  // 🎯 Şampiyon bahsi sonucu.
                  if (betOn != null) ...[
                    const SizedBox(height: 8),
                    _MiniStrip(
                        emoji: '🎯',
                        text: betWon
                            ? 'Bahsin tuttu: $betOn — +$betReward altın!'
                            : 'Bahsin tutmadı ($betOn) — bir dahaki sefere!',
                        color: betWon ? AppTheme.gold : AppTheme.cOnSurfaceVariant),
                  ],
                  // 🛡️ Kalkan bedeli — tahsil edildi ya da hediye sayıldı.
                  if (shieldCost > 0 || shieldGift) ...[
                    const SizedBox(height: 8),
                    _MiniStrip(
                        emoji: '🛡️',
                        text: shieldGift
                            ? 'Kalkan hediye — bu sefer bizden 🎁'
                            : 'Kalkan bedeli: −$shieldCost altın',
                        color: shieldGift ? AppTheme.cTertiary : AppTheme.accent),
                  ],
                  // ── Maç özeti — soruları & doğru cevapları gör ──────────
                  // Yalnızca gerçek soru verisi varsa göster (eski maçlarda boş).
                  if (state.questions.isNotEmpty) ...[
                    const SizedBox(height: 10),
                    _MatchSummaryButton(questions: state.questions),
                  ],
                  const SizedBox(height: 8),
                ],
              ),
            ),
          ),
          // ── Alt bar: HER ZAMAN görünür aksiyonlar (kaydırma gerektirmez) ──
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 8, 20, 8),
            child: Row(
              children: [
                Expanded(
                  child: ChunkyButton(
                    height: 54,
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
                    height: 54,
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
          ),
        ],
      ),
    );
  }
}

/// Tek satırlık istatistik şeridi: 4 mini rozet (etiket + değer) yan yana.
/// Eski 2x2 büyük kart ızgarasının kompakt hâli (tek sayfa hedefi).
class _StatsStrip extends StatelessWidget {
  const _StatsStrip({required this.stats});
  final List<(String, String, Color)> stats;

  @override
  Widget build(BuildContext context) {
    return GlassCard(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 10),
      child: Row(
        children: [
          for (final (label, value, color) in stats)
            Expanded(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(label, style: BiladaText.label(color: color, size: 9), textAlign: TextAlign.center),
                  const SizedBox(height: 3),
                  FittedBox(
                    fit: BoxFit.scaleDown,
                    child: Text(value, style: BiladaText.displayXl(color: color, size: 18)),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

/// Tek satırlık kompakt bilgi şeridi (coin/hayalet/bahis/kalkan).
/// Eski büyük banner'ların yerini alır — tek sayfa hedefi.
class _MiniStrip extends StatelessWidget {
  const _MiniStrip({required this.emoji, required this.text, required this.color});
  final String emoji;
  final String text;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return GlassCard(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Text(emoji, style: const TextStyle(fontSize: 15)),
          const SizedBox(width: 8),
          Flexible(
            child: Text(
              text,
              textAlign: TextAlign.center,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: BiladaText.title(color: color, size: 13),
            ),
          ),
        ],
      ),
    );
  }
}

/// Kazanan BENSEM gösterilen sade şampiyon kartı: büyük "🏆 ŞAMPİYON!" +
/// altın çerçeveli avatar + adım. (Eski "ŞAMPİYON SENSİN / BU GÖRÜNÜM
/// ŞAMPİYONUN" söylemleri kullanıcıya saçma geldiği için kaldırıldı.)
class _ChampionBanner extends StatelessWidget {
  const _ChampionBanner({required this.winnerName, required this.avatarId});
  final String winnerName;
  final String avatarId;

  @override
  Widget build(BuildContext context) {
    return GlassCard(
      padding: const EdgeInsets.fromLTRB(16, 14, 16, 14),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text('🏆 ŞAMPİYON!', style: BiladaText.displayXl(color: AppTheme.gold, size: 30)),
          const SizedBox(height: 10),
          // Şampiyon avatarı — altın halka + parıltı.
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
                  blurRadius: 24,
                  spreadRadius: 3,
                ),
              ],
            ),
            child: PlayerAvatar(
              avatarId: avatarId,
              username: winnerName,
              size: 84,
              isWinner: true,
            ),
          ),
          const SizedBox(height: 10),
          FittedBox(
            fit: BoxFit.scaleDown,
            child: Text(
              winnerName,
              style: BiladaText.displayXl(color: AppTheme.gold, size: 26),
            ),
          ),
        ],
      ),
    );
  }
}

/// Kazanan BAŞKASIYSA gösterilen küçük, sade satır: "Şampiyon: <isim>".
class _ChampionLine extends StatelessWidget {
  const _ChampionLine({required this.winnerName});
  final String winnerName;

  @override
  Widget build(BuildContext context) {
    return GlassCard(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.emoji_events_rounded, color: AppTheme.gold, size: 18),
          const SizedBox(width: 8),
          Flexible(
            child: Text(
              'Şampiyon: $winnerName',
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: BiladaText.title(color: AppTheme.cOnSurfaceVariant, size: 14),
            ),
          ),
        ],
      ),
    );
  }
}

class _Podium extends ConsumerWidget {
  const _Podium({required this.top3, required this.gameId, required this.myUsername});
  final List top3;
  final String gameId;
  final String myUsername;

  static const _gold = Color(0xFFFFD700);
  static const _silver = Color(0xFFC0C0C0);
  static const _bronze = Color(0xFFCD7F32);

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    Map? at(int i) => i < top3.length ? top3[i] as Map : null;
    // Kompakt podyum (168→150): avatar/kule boyutları tek sayfa hedefine göre
    // küçültüldü — sıralama hâlâ net okunur.
    return SizedBox(
      height: 150,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Expanded(child: _slot(context, ref, at(1), 2, _silver, 44, 44)),
          const SizedBox(width: 10),
          Expanded(flex: 12, child: _slot(context, ref, at(0), 1, _gold, 58, 56, crown: true)),
          const SizedBox(width: 10),
          Expanded(child: _slot(context, ref, at(2), 3, _bronze, 30, 40)),
        ],
      ),
    );
  }

  Widget _slot(BuildContext context, WidgetRef ref, Map? p, int rank, Color color,
      double h, double avatar,
      {bool crown = false}) {
    if (p == null) return const SizedBox.shrink();
    final username = (p['username'] ?? '').toString();
    final score = p['score'] as int? ?? 0;
    final avatarId = (p['avatar_id'] as String?) ?? 'default_01';
    return Column(
      mainAxisAlignment: MainAxisAlignment.end,
      children: [
        if (crown) Icon(Icons.emoji_events_rounded, color: color, size: 24),
        Stack(
          clipBehavior: Clip.none,
          children: [
            Container(
              padding: const EdgeInsets.all(3),
              decoration: BoxDecoration(shape: BoxShape.circle, border: Border.all(color: color, width: 3)),
              child: PlayerAvatar(avatarId: avatarId, username: username, size: avatar, isWinner: rank == 1),
            ),
            // ➕ Arkadaş ekle — yalnızca GERÇEK oyuncularda (bot değil, ben değil).
            _AddFriendBadge(gameId: gameId, player: p, myUsername: myUsername),
          ],
        ),
        const SizedBox(height: 4),
        Text(username.length > 8 ? '${username.substring(0, 8)}…' : username,
            style: BiladaText.label(color: AppTheme.cOnSurface, size: 10)),
        Text('$score', style: BiladaText.title(color: color, size: 12)),
        const SizedBox(height: 3),
        Container(
          height: h,
          width: double.infinity,
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.2),
            borderRadius: const BorderRadius.vertical(top: Radius.circular(12)),
            border: Border(top: BorderSide(color: color.withValues(alpha: 0.5), width: 2)),
          ),
          alignment: Alignment.topCenter,
          padding: const EdgeInsets.only(top: 4),
          child: Text('$rank',
              style: BiladaText.displayXl(
                  color: color.withValues(alpha: 0.6), size: rank == 1 ? 26 : 18)),
        ),
      ],
    );
  }
}

/// Podyumdaki GERÇEK oyuncuların avatarına iliştirilen "➕ arkadaş ekle"
/// rozeti; istek gönderilince "✓"ya döner.
///
/// BOT AYRIMI: yalnızca payload'da AÇIKÇA `is_bot == false` gelen oyuncularda
/// gösterilir (WS final_standings bu alanı taşır). Alan hiç yoksa (eski REST
/// fallback) güvenli tarafta kalıp GÖSTERMEYİZ — bota istek atma riski sıfır.
/// Kendi satırımızda da buton yok.
class _AddFriendBadge extends ConsumerWidget {
  const _AddFriendBadge({required this.gameId, required this.player, required this.myUsername});
  final String gameId;
  final Map player;
  final String myUsername;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final username = (player['username'] ?? '').toString();
    final isRealPlayer = player.containsKey('is_bot') && player['is_bot'] == false;
    if (!isRealPlayer || username.isEmpty || username == myUsername) {
      return const SizedBox.shrink();
    }

    final sent = ref.watch(resultProvider(gameId)
        .select((s) => s.friendRequestsSent.contains(username)));

    return Positioned(
      bottom: -4,
      right: -6,
      child: GestureDetector(
        onTap: sent
            ? null
            : () {
                ref
                    .read(resultProvider(gameId).notifier)
                    .addFriendByUsername(username);
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: Text('✓ İstek gönderildi: $username'),
                    duration: const Duration(seconds: 2),
                    backgroundColor: AppTheme.cTertiaryContainer,
                  ),
                );
              },
        child: Container(
          width: 24,
          height: 24,
          decoration: BoxDecoration(
            color: sent ? AppTheme.cTertiaryContainer : AppTheme.cPrimaryContainer,
            shape: BoxShape.circle,
            border: Border.all(color: AppTheme.cSurfaceContainerHigh, width: 2),
          ),
          child: Icon(
            sent ? Icons.check_rounded : Icons.person_add_alt_1_rounded,
            size: 13,
            color: Colors.white,
          ),
        ),
      ),
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
        height: 46,
        depth: 4,
        color: AppTheme.cSurfaceContainerHigh,
        foreground: AppTheme.cOnSurface,
        shadowColor: AppTheme.cSurfaceContainerLowest,
        onPressed: () => _showMatchSummary(context, questions),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.fact_check_rounded, size: 18, color: AppTheme.cTertiary),
            const SizedBox(width: 8),
            Text('SORULARI GÖR (${questions.length})',
                style: BiladaText.label(color: AppTheme.cOnSurface, size: 12)),
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
