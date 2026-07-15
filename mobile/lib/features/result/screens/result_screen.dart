import 'package:confetti/confetti.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:quizroyale/core/services/claim_prompt_service.dart';
import 'package:quizroyale/core/services/review_service.dart';
import 'package:quizroyale/core/services/sound_service.dart';
import 'package:quizroyale/core/theme/app_theme.dart';
import 'package:quizroyale/features/auth/providers/auth_provider.dart';
import 'package:quizroyale/features/auth/widgets/claim_account_sheet.dart';
import 'package:quizroyale/features/leaderboard/providers/rank_projection_provider.dart';
import 'package:quizroyale/features/result/providers/result_provider.dart';
import 'package:quizroyale/features/result/widgets/fireworks_overlay.dart';
import 'package:quizroyale/features/store/providers/store_provider.dart';
import 'package:quizroyale/shared/widgets/adaptive_stage.dart';
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
  // Giriş koreografisi: şampiyon satırı elastik "pat" diye düşer, 2. ve 3.
  // satırlar arkasından kayarak gelir (Interval'larla sıralı sahne girişi).
  late final AnimationController _introController =
      AnimationController(vsync: this, duration: const Duration(milliseconds: 1100));

  // Kutlama (konfeti + havai fişek + alkış) yalnızca BİR kez tetiklenir.
  bool _celebrated = false;
  bool _showFireworks = false;
  // Puan istemi maç sayacı bu ekran örneğinde yalnızca BİR kez artsın.
  bool _matchRecorded = false;
  // Misafir daveti kararı (sayaç + sıklık kuralı) bir kez değerlendirilir.
  bool _claimEvaluated = false;
  bool _showClaimInvite = false;

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
      // giriş animasyonunu burada başlatırız.
      final state = ref.read(resultProvider(widget.gameId));
      if (state.result != null) {
        _recordMatchPlayed();
        _maybeOfferClaim(state.isWinner);
        _introController.forward();
        if (state.isWinner) _celebrate();
      }
    });
  }

  /// Puan istemi için: bu maç bittiğinde toplam maç sayacını (bir kez) artır.
  /// Kazansın kaybetsin her maçta sayılır ki "en az 2 maç" koşulu doğru işlesin.
  void _recordMatchPlayed() {
    if (_matchRecorded) return;
    _matchRecorded = true;
    ReviewService().recordMatchPlayed();
  }

  /// 🏅 MİSAFİR DAVETİ — dönüşümün en yüksek olduğu an (maç sonu).
  ///
  /// Yalnızca MİSAFİR oyuncuya, ClaimPromptService kurallarıyla gösterilir:
  /// şampiyonlukta her zaman (kayıp aversiyonunun zirvesi), aksi hâlde her 3
  /// maçta bir; oyuncu bugün "şimdi değil" dediyse o gün hiç sorulmaz.
  /// Kayıt ZORUNLU DEĞİL — davet kapatılabilir, oyun akışı hiç kesilmez.
  Future<void> _maybeOfferClaim(bool isWinner) async {
    if (_claimEvaluated) return;
    _claimEvaluated = true;
    // Misafir mi? (backend UserMeResponse.is_guest)
    if (ref.read(authProvider).user?['is_guest'] != true) return;

    final prompts = ClaimPromptService();
    final matchCount = await prompts.recordGuestMatch();
    final show = await prompts.shouldPrompt(isWinner: isWinner, matchCount: matchCount);
    if (!mounted || !show) return;
    setState(() => _showClaimInvite = true);
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
    // 🌟 NATIVE "uygulamaya puan ver" istemi — SADECE KAZANANDA (en mutlu an =
    // en yüksek dönüşüm), kutlama oturduktan ~2.5 sn sonra. maybeAskForReview
    // kendi içinde koşulları (en az 2 maç, 60 gün throttle, oturumda tek sefer)
    // ve iOS kotasını yönetir; istem çıkmayabilir — bu normaldir.
    // KURAL: puan karşılığı ödül (altın vb.) VERİLMEZ — Apple bunu yasaklar.
    Future.delayed(const Duration(milliseconds: 2500), () {
      if (mounted) ReviewService().maybeAskForReview();
    });
  }

  @override
  void dispose() {
    _confetti.dispose();
    _introController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(resultProvider(widget.gameId));

    ref.listen(resultProvider(widget.gameId), (prev, next) {
      if (prev?.isLoading == true && next.isLoading == false && next.result != null) {
        _recordMatchPlayed();
        _maybeOfferClaim(next.isWinner);
        if (next.isWinner) _celebrate();
        _introController.forward();
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
              intro: _introController,
              onPlayAgain: () => context.go('/lobby'),
              onHome: () => context.go('/home'),
              // 🏅 Misafir daveti: gösterme kararı ClaimPromptService'te.
              showClaimInvite: _showClaimInvite,
              onClaimDismissed: () {
                // "Şimdi değil" → bugün bir daha sorma (tercih cihazda saklanır).
                ClaimPromptService().dismissForToday();
                setState(() => _showClaimInvite = false);
              },
              onClaimed: () => setState(() => _showClaimInvite = false),
            ),
          // 🎆 Havai fişek — SADECE kazananda, ~4.5 sn sürer ve biter.
          // IgnorePointer içerir → alttaki butonlar tıklanabilir kalır.
          // StageFx: iPad'de içerik kuşağına hapsolmaz, TÜM ekranı kaplar.
          if (_showFireworks)
            const StageFx(child: Positioned.fill(child: FireworksOverlay())),
        ],
      ),
    );
  }
}

/// SAYFA DÜZENİ (yukarıdan aşağıya, 390×844'te kaydırmasız):
///  1. Sonuç manşeti (ŞAMPİYONSUN / HAYATTA KALDIN / DÜŞTÜN)
///  2. Dikey sıralama listesi — şampiyon büyük altın satır, 2. ve 3. sade
///  3. Kişisel istatistik şeridi (sıra/puan/doğru/XP)
///  4. [esnek boşluk]
///  5. Ödül/bedel şeritleri + SORULARI GÖR  ← alt butonların hemen üstünde
///  6. Sabit alt bar: ANA MENÜ (ikincil) + TEKRAR OYNA (birincil, geniş)
class _ResultBody extends ConsumerWidget {
  const _ResultBody({
    required this.gameId,
    required this.state,
    required this.intro,
    required this.onPlayAgain,
    required this.onHome,
    required this.showClaimInvite,
    required this.onClaimDismissed,
    required this.onClaimed,
  });

  final String gameId;
  final ResultState state;
  final Animation<double> intro;
  final VoidCallback onPlayAgain;
  final VoidCallback onHome;

  /// Misafir kayıt daveti gösterilsin mi (sıklık kuralı ekran state'inde).
  final bool showClaimInvite;
  final VoidCallback onClaimDismissed;
  final VoidCallback onClaimed;

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
    // 🏆 Zor Mod (turnuva): tek ödül SABİT havuz payıdır (700/300/200). Zor
    // Mod'da normal maç ödülü/hayalet/bahis VERİLMEZ → aşağıda bu şeritler
    // gizlenir, yalnızca 🏆 ödül gösterilir.
    final isTournament = my['is_tournament'] == true;
    final zorModPrize = my['zor_mod_prize'] as int? ?? 0;
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

    final myUsername = ref.watch(authProvider).user?['username'] as String? ?? '';

    return SafeArea(
      child: Column(
        children: [
          // Üst bölge: hedef cihazda (390×844) kaydırmadan sığar; çok küçük
          // ekranlarda taşma yerine zarifçe kaydırılabilir (minHeight kalıbı).
          Expanded(
            child: LayoutBuilder(
              builder: (context, constraints) {
                return SingleChildScrollView(
                  padding: const EdgeInsets.symmetric(horizontal: 20),
                  child: ConstrainedBox(
                    constraints: BoxConstraints(minHeight: constraints.maxHeight),
                    child: IntrinsicHeight(
                      child: Column(
                        children: [
                          const SizedBox(height: 10),
                          _ResultHeader(
                            isWinner: isWinner,
                            survived: survived,
                            finalRound: finalRound,
                          ),
                          const SizedBox(height: 14),
                          if (top3.isNotEmpty)
                            _StandingsList(
                              top3: top3,
                              gameId: gameId,
                              myUsername: myUsername,
                              intro: intro,
                            ),
                          const SizedBox(height: 12),
                          _StatsStrip(stats: [
                            (
                              'SIRA',
                              isWinner
                                  ? '#1'
                                  // Gerçek sıra (rank) varsa onu, yoksa elenenler
                                  // için ulaşılan turu göster.
                                  : rank > 0
                                      ? '#$rank'
                                      : (survived ? 'Hayatta' : 'Tur $finalRound'),
                              AppTheme.cPrimary
                            ),
                            ('PUAN', '+$score', AppTheme.cTertiary),
                            ('DOĞRU', '$correct/$total', AppTheme.gold),
                            ('XP', '+$xp', AppTheme.cSecondary),
                          ]),
                          // 🏅 MİSAFİR DAVETİ — bilinçli olarak PUAN şeridinin
                          // hemen ALTINDA: oyuncu skorunu yeni okudu, kaybı tam
                          // o anda somutlaştırıyoruz ("bu puanla 7. olurdun").
                          if (showClaimInvite) ...[
                            const SizedBox(height: 12),
                            _GuestClaimInvite(
                              isWinner: isWinner,
                              onDismiss: onClaimDismissed,
                              onClaimed: onClaimed,
                            ),
                          ],
                          // Esnek boşluk: ödüller + SORULARI GÖR sayfanın ALTINA,
                          // sabit butonların hemen üstüne yaslanır.
                          const Spacer(),
                          const SizedBox(height: 12),
                          // ── Ödül/bedel şeritleri ─────────────────────────
                          if (isTournament) ...[
                            // 🏆 ZOR MOD — tek ödül SABİT havuz payı (700/300/200).
                            // İlk 3 dışına ödül yok → prize 0 ise şerit gösterilmez.
                            if (zorModPrize > 0) ...[
                              _MiniStrip(emoji: '🏆', text: '+$zorModPrize Altın — Zor Mod ödülü!', color: AppTheme.gold),
                              const SizedBox(height: 8),
                            ],
                          ] else ...[
                            // Normal maç ödülleri (Zor Mod'da bunlar VERİLMEZ).
                            // Coin — yalnızca pozitifse (0 ise günlük limit dolmuş olabilir).
                            if (coinsEarned > 0) ...[
                              _MiniStrip(emoji: '🪙', text: '+$coinsEarned Altın kazandın!', color: AppTheme.gold),
                              const SizedBox(height: 8),
                            ],
                            // 👻 Hayalet modu — elenmişken bilinen doğrular altın oldu.
                            if (ghostCorrect > 0) ...[
                              _MiniStrip(
                                  emoji: '👻',
                                  text: 'Hayalet modunda $ghostCorrect doğru — +$ghostReward altın!',
                                  color: AppTheme.cSecondary),
                              const SizedBox(height: 8),
                            ],
                            // 🎯 Şampiyon bahsi sonucu.
                            if (betOn != null) ...[
                              _MiniStrip(
                                  emoji: '🎯',
                                  text: betWon
                                      ? 'Bahsin tuttu: $betOn — +$betReward altın!'
                                      : 'Bahsin tutmadı ($betOn) — bir dahaki sefere!',
                                  color: betWon ? AppTheme.gold : AppTheme.cOnSurfaceVariant),
                              const SizedBox(height: 8),
                            ],
                          ],
                          // 🛡️ Kalkan bedeli — tahsil edildi ya da hediye sayıldı.
                          if (shieldCost > 0 || shieldGift) ...[
                            _MiniStrip(
                                emoji: '🛡️',
                                text: shieldGift
                                    ? 'Kalkan hediye — bu sefer bizden 🎁'
                                    : 'Kalkan bedeli: −$shieldCost altın',
                                color: shieldGift ? AppTheme.cTertiary : AppTheme.accent),
                            const SizedBox(height: 8),
                          ],
                          // ── Maç özeti — soruları & doğru cevapları gör ──
                          // Yalnızca gerçek soru verisi varsa (eski maçlarda boş).
                          if (state.questions.isNotEmpty)
                            _MatchSummaryButton(questions: state.questions),
                          const SizedBox(height: 4),
                        ],
                      ),
                    ),
                  ),
                );
              },
            ),
          ),
          // ── Alt bar: HER ZAMAN görünür aksiyonlar (kaydırma gerektirmez) ──
          // TEKRAR OYNA birincil ve GENİŞ (başparmak tarafı, yazı asla
          // kesilmez); ANA MENÜ ikincil ve daha dar.
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 10, 20, 8),
            child: Row(
              children: [
                Expanded(
                  flex: 2,
                  child: ChunkyButton(
                    height: 56,
                    color: AppTheme.cSecondaryContainer,
                    foreground: Colors.white,
                    shadowColor: AppTheme.cSecondaryShadow,
                    padding: const EdgeInsets.symmetric(horizontal: 10),
                    onPressed: onHome,
                    child: const FittedBox(
                      fit: BoxFit.scaleDown,
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(Icons.home_rounded, size: 20),
                          SizedBox(width: 6),
                          Text('ANA MENÜ'),
                        ],
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  flex: 3,
                  child: ChunkyButton(
                    height: 56,
                    padding: const EdgeInsets.symmetric(horizontal: 10),
                    onPressed: onPlayAgain,
                    child: const FittedBox(
                      fit: BoxFit.scaleDown,
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(Icons.replay_rounded, size: 20),
                          SizedBox(width: 6),
                          Text('TEKRAR OYNA'),
                        ],
                      ),
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

/// Sonuç manşeti — oyuncunun kendi hikâyesi tek bakışta:
/// şampiyonsa coşku, hayatta kaldıysa gurur, elendiyse motive edici ton.
class _ResultHeader extends StatelessWidget {
  const _ResultHeader({
    required this.isWinner,
    required this.survived,
    required this.finalRound,
  });

  final bool isWinner;
  final bool survived;
  final int finalRound;

  @override
  Widget build(BuildContext context) {
    final (String title, Color titleColor, String subtitle) = isWinner
        ? ('🏆 ŞAMPİYONSUN!', AppTheme.gold, 'Herkes düştü, sen kaldın — taç senin! 👑')
        : survived
            ? ('HAYATTA KALDIN!', AppTheme.cTertiary, 'Sona kadar dayandın — şampiyonluk kıl payı! 🔥')
            : ('BU SEFER DÜŞTÜN', AppTheme.cPrimary, '$finalRound. turda elendin — rövanş bir maç uzakta 💪');

    return Column(
      children: [
        FittedBox(
          fit: BoxFit.scaleDown,
          child: Text(title, style: BiladaText.displayXl(color: titleColor, size: isWinner ? 30 : 26)),
        ),
        const SizedBox(height: 4),
        Text(
          subtitle,
          textAlign: TextAlign.center,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: BiladaText.body(color: AppTheme.cOnSurfaceVariant, size: 13),
        ),
      ],
    );
  }
}

/// Dikey sıralama listesi — YAN YANA PODYUM DEĞİL:
/// şampiyon en üstte büyük altın satır (taç + parıltılı avatar),
/// 2. ve 3. altında sade madalyalı satırlar. Sahne girişi sıralı:
/// şampiyon elastik "pat" diye iner, diğerleri arkasından kayar.
class _StandingsList extends StatelessWidget {
  const _StandingsList({
    required this.top3,
    required this.gameId,
    required this.myUsername,
    required this.intro,
  });

  final List top3;
  final String gameId;
  final String myUsername;
  final Animation<double> intro;

  @override
  Widget build(BuildContext context) {
    Map? at(int i) => i < top3.length ? top3[i] as Map : null;
    final champion = at(0);
    final second = at(1);
    final third = at(2);

    // Şampiyon: elastik ölçek (0 → 1, hafif taşmalı iniş).
    final championScale = CurvedAnimation(parent: intro, curve: const Interval(0.0, 0.55, curve: Curves.elasticOut));

    Widget staggered(int order, Widget child) {
      final a = CurvedAnimation(
        parent: intro,
        curve: Interval(0.35 + order * 0.18, 1.0, curve: Curves.easeOutCubic),
      );
      return FadeTransition(
        opacity: a,
        child: SlideTransition(
          position: Tween<Offset>(begin: const Offset(0, 0.5), end: Offset.zero).animate(a),
          child: child,
        ),
      );
    }

    return Column(
      children: [
        if (champion != null)
          ScaleTransition(
            scale: championScale,
            child: _ChampionRow(player: champion, gameId: gameId, myUsername: myUsername),
          ),
        if (second != null) ...[
          const SizedBox(height: 8),
          staggered(0, _RunnerUpRow(player: second, rank: 2, gameId: gameId, myUsername: myUsername)),
        ],
        if (third != null) ...[
          const SizedBox(height: 8),
          staggered(1, _RunnerUpRow(player: third, rank: 3, gameId: gameId, myUsername: myUsername)),
        ],
      ],
    );
  }
}

/// 1.lik satırı — listenin yıldızı: altın gradyan zemin, parıltılı sweep
/// halkalı büyük avatar, yana yatık taç ve büyük puan. "SEN" rozetiyle
/// kendi zaferin ayrıca işaretlenir.
class _ChampionRow extends StatelessWidget {
  const _ChampionRow({required this.player, required this.gameId, required this.myUsername});

  final Map player;
  final String gameId;
  final String myUsername;

  @override
  Widget build(BuildContext context) {
    final username = (player['username'] ?? '').toString();
    final score = player['score'] as int? ?? 0;
    final avatarId = (player['avatar_id'] as String?) ?? 'default_01';
    final isMe = username.isNotEmpty && username == myUsername;

    return Container(
      padding: const EdgeInsets.fromLTRB(14, 12, 16, 12),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(22),
        gradient: LinearGradient(
          colors: [
            AppTheme.gold.withValues(alpha: 0.22),
            AppTheme.gold.withValues(alpha: 0.06),
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        border: Border.all(color: AppTheme.gold.withValues(alpha: 0.65), width: 2),
        boxShadow: [
          BoxShadow(color: AppTheme.gold.withValues(alpha: 0.22), blurRadius: 18, spreadRadius: 1),
        ],
      ),
      child: Row(
        children: [
          Stack(
            clipBehavior: Clip.none,
            children: [
              // Altın sweep halka + parıltı — şampiyonun avatarı sahnenin yıldızı.
              Container(
                padding: const EdgeInsets.all(3),
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  gradient: const SweepGradient(
                    colors: [AppTheme.gold, Color(0xFFFFA500), AppTheme.gold],
                  ),
                  boxShadow: [
                    BoxShadow(color: AppTheme.gold.withValues(alpha: 0.5), blurRadius: 16, spreadRadius: 2),
                  ],
                ),
                child: PlayerAvatar(avatarId: avatarId, username: username, size: 58, isWinner: true),
              ),
              // Yana yatık taç — Fall Guys tınısında şımarık bir dokunuş.
              Positioned(
                top: -14,
                left: -8,
                child: Transform.rotate(
                  angle: -0.4,
                  child: const Text('👑', style: TextStyle(fontSize: 26)),
                ),
              ),
              // ➕ Arkadaş ekle — yalnızca GERÇEK oyuncularda (bot/ben değil).
              _AddFriendBadge(gameId: gameId, player: player, myUsername: myUsername),
            ],
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Text('ŞAMPİYON', style: BiladaText.label(color: AppTheme.gold, size: 10)),
                    if (isMe) ...[
                      const SizedBox(width: 6),
                      const PillBadge('Sen', color: AppTheme.cPrimaryContainer, fg: Colors.white),
                    ],
                  ],
                ),
                const SizedBox(height: 2),
                FittedBox(
                  fit: BoxFit.scaleDown,
                  alignment: Alignment.centerLeft,
                  child: Text(
                    username,
                    style: BiladaText.displayXl(color: AppTheme.cOnSurface, size: 22),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 10),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text('$score', style: BiladaText.displayXl(color: AppTheme.gold, size: 24)),
              Text('PUAN', style: BiladaText.label(color: AppTheme.gold.withValues(alpha: 0.8), size: 9)),
            ],
          ),
        ],
      ),
    );
  }
}

/// 2. ve 3.lük satırları — sade cam satır: madalya emojisi + küçük avatar +
/// isim + puan. Şampiyon satırından bilinçli olarak daha sessiz.
class _RunnerUpRow extends StatelessWidget {
  const _RunnerUpRow({
    required this.player,
    required this.rank,
    required this.gameId,
    required this.myUsername,
  });

  final Map player;
  final int rank;
  final String gameId;
  final String myUsername;

  static const _silver = Color(0xFFC0C0C0);
  static const _bronze = Color(0xFFCD7F32);

  @override
  Widget build(BuildContext context) {
    final username = (player['username'] ?? '').toString();
    final score = player['score'] as int? ?? 0;
    final avatarId = (player['avatar_id'] as String?) ?? 'default_01';
    final isMe = username.isNotEmpty && username == myUsername;
    final medalColor = rank == 2 ? _silver : _bronze;
    final medal = rank == 2 ? '🥈' : '🥉';

    return GlassCard(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      borderRadius: 18,
      // Kendi satırım hafif pembe tonla ayrışır — "ben buradayım".
      color: isMe ? AppTheme.cPrimaryContainer.withValues(alpha: 0.18) : null,
      child: Row(
        children: [
          Text(medal, style: const TextStyle(fontSize: 22)),
          const SizedBox(width: 10),
          Stack(
            clipBehavior: Clip.none,
            children: [
              Container(
                padding: const EdgeInsets.all(2),
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  border: Border.all(color: medalColor.withValues(alpha: 0.8), width: 2),
                ),
                child: PlayerAvatar(avatarId: avatarId, username: username, size: 36),
              ),
              // ➕ Arkadaş ekle — yalnızca GERÇEK oyuncularda (bot/ben değil).
              _AddFriendBadge(gameId: gameId, player: player, myUsername: myUsername),
            ],
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Row(
              children: [
                Flexible(
                  child: Text(
                    username,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: BiladaText.title(color: AppTheme.cOnSurface, size: 15),
                  ),
                ),
                if (isMe) ...[
                  const SizedBox(width: 6),
                  const PillBadge('Sen', color: AppTheme.cPrimaryContainer, fg: Colors.white),
                ],
              ],
            ),
          ),
          const SizedBox(width: 8),
          Text('$score', style: BiladaText.title(color: medalColor, size: 16)),
        ],
      ),
    );
  }
}

/// Tek satırlık istatistik şeridi: 4 mini rozet (etiket + değer) yan yana.
/// Büyük kart ızgarası yerine kompakt şerit (tek sayfa hedefi).
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

/// 🏅 Misafir → kayıtlı dönüşüm daveti (maç sonu).
///
/// DEĞER ODAKLI: "kayıt ol" demez; oyuncunun bu maçta ne KAYBETTİĞİNİ söyler.
/// Sıra tahmini (GET /api/leaderboard/projection) gelirse kayıp somut bir
/// sayıya döner ("Bugün 7. sıradaydın"); gelmezse sade metne düşer — davet her
/// hâlükârda anlamlı kalır.
///
/// ŞAMPİYONLUK ANI ayrı ve daha güçlü konuşur: kazanmışken tabloda görünmemek
/// en yüksek kayıp aversiyonu anıdır.
///
/// RAHATSIZ ETMEZ: "Şimdi değil" ile kapatılır (o gün tekrar sorulmaz) ve
/// TEKRAR OYNA akışını hiçbir şekilde engellemez.
class _GuestClaimInvite extends ConsumerWidget {
  const _GuestClaimInvite({
    required this.isWinner,
    required this.onDismiss,
    required this.onClaimed,
  });

  final bool isWinner;
  final VoidCallback onDismiss;
  final VoidCallback onClaimed;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // Günlük tahmin: oyuncunun BUGÜN biriken puanı (bu maç dâhil) sıralamada
    // nereye denk gelirdi. Yüklenirken/hata olduğunda null → sade metin.
    final projection = ref.watch(rankProjectionProvider('daily')).valueOrNull;
    final rank = projection?.hasRank == true ? projection!.wouldBeRank : null;

    final String title;
    final String body;
    if (isWinner) {
      title = '🏆 Şampiyon oldun ama sıralamada yoksun!';
      body = rank != null
          ? 'Bugünkü puanınla $rank. sıradaydın — hesabını kaydet, adını tabloya yaz.'
          : 'Misafir oynuyorsun: puanların birikiyor ama tabloda görünmüyorsun.';
    } else if (rank != null) {
      title = '🏅 Bugün $rank. sıradaydın';
      body = 'Ama misafirsin — puanların tabloda görünmüyor. '
          'Hesabını kaydet, sıralamaya gir.';
    } else {
      title = '🏅 Sıralamada görünmüyorsun';
      body = 'Puanların kaydediliyor ama misafir olduğun için tabloda yoksun. '
          'Hesabını kaydet, sıralamaya gir.';
    }

    return Container(
      padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(20),
        gradient: LinearGradient(
          colors: [
            AppTheme.gold.withValues(alpha: 0.18),
            AppTheme.gold.withValues(alpha: 0.05),
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        border: Border.all(color: AppTheme.gold.withValues(alpha: 0.55), width: 1.5),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: BiladaText.title(color: AppTheme.gold, size: 14)),
          const SizedBox(height: 3),
          Text(body,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: BiladaText.label(color: AppTheme.cOnSurfaceVariant, size: 11)),
          const SizedBox(height: 10),
          Row(
            children: [
              // "Şimdi değil" — davet ASLA zorlayıcı değil (Apple 5.1.1 + tasarım
              // kararımız: misafir oyun sonsuza kadar oynanabilir).
              TextButton(
                onPressed: onDismiss,
                style: TextButton.styleFrom(
                  padding: const EdgeInsets.symmetric(horizontal: 8),
                  minimumSize: Size.zero,
                  tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                ),
                child: Text('Şimdi değil',
                    style: BiladaText.label(color: AppTheme.cOnSurfaceVariant, size: 12)),
              ),
              const Spacer(),
              ChunkyButton(
                height: 40,
                depth: 4,
                expand: false,
                color: AppTheme.gold,
                foreground: AppTheme.cOnPrimaryContainer,
                shadowColor: const Color(0xFF8A6A00),
                padding: const EdgeInsets.symmetric(horizontal: 16),
                onPressed: () async {
                  final claimed = await showClaimAccountSheet(
                    context,
                    currentUsername:
                        (ref.read(authProvider).user?['username'] ?? '').toString(),
                    title: rank != null ? '$rank. sıraya adını yaz' : 'Sıralamaya gir',
                    subtitle: rank != null
                        ? 'E-posta ve şifre yeter — biriken puanların anında '
                            'sıralamada görünsün.'
                        : null,
                  );
                  if (claimed) onClaimed();
                },
                child: const Text('SIRALAMAYA GİR', style: TextStyle(fontSize: 13)),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

/// Tek satırlık kompakt bilgi şeridi (coin/hayalet/bahis/kalkan).
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

/// Sıralamadaki GERÇEK oyuncuların avatarına iliştirilen "➕ arkadaş ekle"
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
