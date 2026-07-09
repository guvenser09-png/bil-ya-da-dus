import 'dart:async';
import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:quizroyale/core/constants/app_constants.dart';
import 'package:quizroyale/core/services/haptic_service.dart';
import 'package:quizroyale/core/services/sound_service.dart';
import 'package:quizroyale/core/theme/app_theme.dart';
import 'package:quizroyale/features/auth/providers/auth_provider.dart';
import 'package:quizroyale/features/game/providers/game_provider.dart';
import 'package:quizroyale/features/game/widgets/true_false_widget.dart';
import 'package:quizroyale/features/game/widgets/multiple_choice_widget.dart';
import 'package:quizroyale/features/game/widgets/comparison_widget.dart';
import 'package:quizroyale/features/game/widgets/slider_widget.dart';
import 'package:quizroyale/features/game/widgets/round_reveal_widget.dart';
import 'package:quizroyale/features/game/widgets/tutorial_hint.dart';
import 'package:quizroyale/features/game/providers/tutorial_provider.dart';
import 'package:quizroyale/features/cosmetics/providers/cosmetics_provider.dart';
import 'package:quizroyale/features/result/providers/result_provider.dart';
import 'package:quizroyale/shared/widgets/bilada_ui.dart';
import 'package:quizroyale/shared/widgets/player_avatar.dart';

// ---------------------------------------------------------------------------
// GameScreen
// ---------------------------------------------------------------------------

class GameScreen extends ConsumerStatefulWidget {
  const GameScreen({super.key, required this.gameId});
  final String gameId;

  @override
  ConsumerState<GameScreen> createState() => _GameScreenState();
}

class _GameScreenState extends ConsumerState<GameScreen> {
  bool _navigated = false;
  Timer? _finishFallbackTimer;

  // İlk-maç tutorial: aktif ipucu balonu (tur tipi + metin). null → gösterme.
  String? _hintType;
  String? _hintMessage;

  // 🏆 FİNAL duyurusu: tahmin turu başlarken HERKESE bir kez gösterilen tam
  // ekran kısa overlay (tutorial'dan bağımsız — her maçta, her oyuncuya).
  bool _finalAnnounceShown = false; // bu maçta bir kez tetiklendi mi
  bool _showFinalAnnounce = false; // overlay şu an ekranda mı

  @override
  void initState() {
    super.initState();
    // connect after first frame so the provider is ready
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(gameProvider(widget.gameId).notifier).connectGame(widget.gameId);
    });
  }

  @override
  void dispose() {
    _finishFallbackTimer?.cancel();
    super.dispose();
  }

  /// Oyun durum geçişlerini sese/haptiğe çevirir. Reveal anı eleme oyununun
  /// tüm duygusudur — doğru/yanlış, düşüş ve şampiyon burada duyulur.
  /// Tetikler yalnızca DURUM GEÇİŞİNDE çalışır (her rebuild'de değil).
  void _handleAudioCues(GameState? prev, GameState next) {
    // Tur başlangıcı — kısa dikkat sinyali.
    if (next.status == 'round_active' && prev?.status != 'round_active') {
      SoundService().playSound(GameSound.roundStart);
      // Görsel soru: resmi hemen ısıt (precache) — süre işlerken oyuncu
      // spinner'a bakmasın, bayrak/resim ilk karede hazır olsun.
      final imageUrl = next.currentQuestion?['image_url'] as String?;
      if (imageUrl != null && imageUrl.isNotEmpty && mounted) {
        precacheImage(CachedNetworkImageProvider(imageUrl), context);
      }
    }

    // Sayaç son 3 saniye: her saniye geçişinde tık (3→2→1).
    if (next.status == 'round_active' && prev?.status == 'round_active') {
      final prevSec = prev!.timeRemaining.ceil();
      final nextSec = next.timeRemaining.ceil();
      if (nextSec != prevSec && nextSec >= 1 && nextSec <= 3) {
        SoundService().playSound(GameSound.countdown);
      }
    }

    // Reveal — kendi sonucuma göre doğru/yanlış sesi + titreşim.
    if (next.status == 'round_revealing' &&
        prev?.status != 'round_revealing') {
      final me = ref.read(authProvider).user?['username'] as String?;
      final results =
          (next.roundResult?['results'] as Map?)?.cast<String, dynamic>();
      final dynamic mine =
          (me == null || results == null) ? null : results[me];
      // KALKAN (🛡️): bu tur kalkanımla kurtulduysam yanlış sesi YERİNE
      // kalkan kırılma efekti + orta haptik (uyarı banner'ı reveal'da).
      final shieldSaved = (next.roundResult?['shield_saved'] as List?)
              ?.map((e) => e.toString())
              .toList() ??
          const <String>[];
      if (me != null && shieldSaved.contains(me)) {
        SoundService().playSound(GameSound.shieldBreak);
        HapticService().wrongAnswer();
      } else if (mine is Map) {
        if (mine['correct'] == true) {
          SoundService().playSound(GameSound.correct);
          HapticService().correctAnswer();
        } else {
          SoundService().playSound(GameSound.wrong);
          HapticService().wrongAnswer();
        }
      }
      // İzleyicideysem (results'ta yokum) sessiz geç — düşüş sesi zaten
      // RoundRevealWidget'ın falling fazında çalar; hayalet sonucum reveal'da
      // yarı saydam rozetle gösterilir.
    }

    // Maç bitti — şampiyon fanfarı (herkes duyar), zafer titreşimi kazananın.
    if (next.status == 'finished' && prev?.status != 'finished') {
      SoundService().playSound(GameSound.win);
      final rawWinner = next.gameResult?['winner'];
      final winnerName = rawWinner is Map
          ? rawWinner['username'] as String?
          : (rawWinner is String ? rawWinner : null);
      final me = ref.read(authProvider).user?['username'] as String?;
      if (winnerName != null && winnerName == me) {
        HapticService().win();
      }
    }
  }

  /// Sonuç ekranına geçişi GARANTİLE. Parse hatası, eksik veri, geç gelen
  /// mesaj veya overlay durumundan bağımsız olarak HER ZAMAN
  /// `/result/<gameId>`'e gider. Tek-sefer (idempotent).
  void _goToResult(GameState state) {
    if (_navigated || !mounted) return;
    _navigated = true;
    _finishFallbackTimer?.cancel();
    try {
      _populateResult(state.gameResult);
    } catch (_) {
      // Parse hatası navigasyonu ASLA bloklamasın.
    }
    if (mounted) context.go('/result/${widget.gameId}');
  }

  @override
  Widget build(BuildContext context) {
    // ── Navigasyon dinleyicisi ──────────────────────────────────────────
    // ref.listen, build atlansa bile durum geçişlerinde tetiklenir; bu
    // yüzden 'finished' geçişini build içindeki koşula bağımlı yapmak yerine
    // burada güvenle yakalarız.
    ref.listen<GameState>(gameProvider(widget.gameId), (prev, next) {
      // ── Ses + haptik tetikleri ────────────────────────────────────────
      _handleAudioCues(prev, next);

      // ── İlk-maç tutorial ipucu ────────────────────────────────────────
      // Yeni bir tur aktifleştiğinde (round_active) ve bu tur tipi için ilk
      // kez ipucu gösterilecekse non-blocking balonu tetikle.
      if (next.status == 'round_active' &&
          (prev?.status != 'round_active' ||
              prev?.currentQuestion?['tip'] != next.currentQuestion?['tip'])) {
        final type = next.currentQuestion?['tip'] as String? ?? '';
        final msg = tutorialMessageFor(type);
        if (msg != null &&
            ref.read(tutorialProvider.notifier).shouldShow(type)) {
          WidgetsBinding.instance.addPostFrameCallback((_) {
            if (mounted) {
              setState(() {
                _hintType = type;
                _hintMessage = msg;
              });
            }
          });
        }
      }

      // ── 🏆 FİNAL duyurusu ─────────────────────────────────────────────
      // Final (tahmin) turu aktifleşince 1.8sn'lik tam ekran duyuru göster.
      // Tur numarası son tura ulaştıysa VEYA tur tipi 'tahmin' ise final
      // sayılır (erken bitişte finalin daha önce gelmesine karşı savunmacı).
      if (!_finalAnnounceShown && next.status == 'round_active') {
        final qType =
            (next.currentQuestion?['tip'] ?? next.currentQuestion?['type'] ?? '')
                .toString();
        final isFinal =
            next.currentRound >= next.totalRounds || qType == 'tahmin';
        if (isFinal) {
          _finalAnnounceShown = true;
          WidgetsBinding.instance.addPostFrameCallback((_) {
            if (mounted) setState(() => _showFinalAnnounce = true);
          });
        }
      }

      if (next.status == 'finished') {
        // Maç bitti — tutorial'ı kalıcı olarak görüldü işaretle.
        ref.read(tutorialProvider.notifier).markSeen();
        // game_finished alındı — overlay'ları umursamadan sonuç ekranına git.
        WidgetsBinding.instance.addPostFrameCallback((_) => _goToResult(next));
        // SAĞLAMLAŞTIRMA: bir frame sonra hâlâ gidilmediyse 5sn içinde ZORLA git.
        _finishFallbackTimer ??= Timer(const Duration(seconds: 5), () {
          _goToResult(next);
        });
      } else if (next.status == 'error' && !_navigated) {
        _navigated = true;
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(
                content: Text('Oyun bulunamadı. Yeni maç başlatılıyor...'),
                backgroundColor: Color(0xFFEF4444),
              ),
            );
            context.go('/home');
          }
        });
      }
    });

    final state = ref.watch(gameProvider(widget.gameId));
    final notifier = ref.read(gameProvider(widget.gameId).notifier);

    // Güvenlik ağı: listener kaçırsa bile (örn. screen 'finished' durumla
    // doğrudan kurulduysa) build sırasında da geçişi tetikle.
    if (state.status == 'finished' && !_navigated) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _goToResult(state));
    }

    final aliveCount =
        state.allPlayers.where((p) => p['is_alive'] == true).length;

    // ── Kozmetik görünürlüğü ────────────────────────────────────────────
    // Backend oyuncu listesinde çerçeve göndermiyor; ancak yerel kullanıcının
    // kuşandığı çerçeve burada mevcut. Kendi avatarımıza çerçeveyi giydirerek
    // 12 kişilik maçta kozmetiğin görünür olmasını sağlarız (satış vitrini).
    final myUsername = ref.read(authProvider).user?['username'] as String?;
    final myFrame =
        frameKeyFromId(ref.watch(cosmeticsProvider).equippedFrame);

    // Son düzlük: az sayıda finalist kaldıysa platform şeridini büyüt.
    final isFinalStretch =
        aliveCount > 0 && aliveCount <= 4 && state.status != 'finished';

    // Bu tur kalkanıyla kurtulanlar (reveal sırasında kırık-kalkan rozeti).
    final shieldSavedThisRound = state.status == 'round_revealing'
        ? ((state.roundResult?['shield_saved'] as List?)
                ?.map((e) => e.toString())
                .toList() ??
            const <String>[])
        : const <String>[];

    return Scaffold(
      body: Stack(
        children: [
          // ── Background gradient ──────────────────────────────────────
          Container(
            decoration: const BoxDecoration(
              gradient: AppTheme.backgroundGradient,
            ),
          ),

          // ── Main game UI ─────────────────────────────────────────────
          SafeArea(
            child: Column(
              children: [
                // Top bar
                _TopBar(
                  currentRound: state.currentRound,
                  totalRounds: state.totalRounds,
                  questionType: state.currentQuestion?['tip'] as String? ?? '',
                  aliveCount: aliveCount,
                ),

                // Timer progress bar
                _TimerBar(
                  timeRemaining: state.timeRemaining,
                  totalTime: state.totalTime,
                ),

                // Question area (animated switch on question change).
                // HAYALET MODU (👻): elenmiş oyuncu da cevap VERMEYE devam
                // eder (eski IgnorePointer kaldırıldı) — cevabı backend'de
                // gölge sayaca gider, elemeye/skora etkisizdir; doğru başına
                // maç sonunda mini altın kazanır.
                Expanded(
                  child: AnimatedSwitcher(
                    duration: const Duration(milliseconds: 300),
                    switchInCurve: Curves.easeOut,
                    switchOutCurve: Curves.easeIn,
                    child: _buildQuestionWidget(state, notifier),
                  ),
                ),

                // Player platform bar at bottom
                _PlayerPlatformBar(
                  players: state.allPlayers,
                  myUsername: myUsername,
                  myFrame: myFrame,
                  finalStretch: isFinalStretch,
                  shieldSavedThisRound: shieldSavedThisRound,
                ),
              ],
            ),
          ),

          // ── Overlays ─────────────────────────────────────────────────

          if (state.status == 'round_revealing' && state.roundResult != null)
            RoundRevealWidget(
              roundResult: state.roundResult!,
              question: state.currentQuestion ?? {},
              aliveCount: aliveCount,
              eliminatedPlayers: _eliminatedPlayers(state),
              players: state.allPlayers,
              myUsername: myUsername,
              myFrame: myFrame,
              onDismiss: () {},
            ),

          if (state.status == 'between_rounds')
            _RoundTransitionOverlay(
              nextRound: state.currentRound + 1,
              aliveCount: aliveCount,
              eliminatedCount: state.eliminatedThisRound.length,
            ),

          if (state.isSpectator && state.status != 'finished')
            _GhostModeBanner(
              onLeave: () => context.go('/home'),
              betOn: state.betOn,
              // Bahis kartı: bahis yoksa, tur arasında/reveal'da (soru
              // cevaplamayı engellemesin) ve FİNAL başlamadıysa göster.
              // Final başladıysa kart kaybolur — bahis şansı kaçtı, sorun yok.
              showBetCard: state.betOn == null &&
                  state.status != 'round_active' &&
                  state.currentRound < state.totalRounds,
              alivePlayers: state.allPlayers
                  .where((p) => p['is_alive'] == true)
                  .toList(),
              onBet: (username) => notifier.placeBet(username),
            ),

          if (state.emojiOverlay != null)
            _EmojiFloatOverlay(emoji: state.emojiOverlay!),

          // ── 💬 Hazır mesaj baloncuğu (gönderen adı + sabit metin, 2sn) ──
          if (state.quickMsg != null)
            _QuickMsgBubble(
              username: state.quickMsg!['username'] ?? 'oyuncu',
              text: state.quickMsg!['text'] ?? '',
            ),

          // ── 💬 Hazır mesaj gönderme butonu (maç bitmediyse) ─────────────
          if (state.status != 'finished')
            Positioned(
              right: 12,
              bottom: 118,
              child: SafeArea(
                child: _QuickMsgButton(
                  onSelected: (id) => notifier.sendQuickMsg(id),
                ),
              ),
            ),

          // ── 🏆 FİNAL duyurusu — kısa tam ekran overlay (1.8sn) ──────────
          if (_showFinalAnnounce)
            _FinalAnnounceOverlay(
              onDone: () {
                if (mounted) setState(() => _showFinalAnnounce = false);
              },
            ),

          // ── İlk-maç tutorial ipucu (non-blocking, kendi kapanır) ───────
          // Sadece tur aktifken ve reveal/ara overlay'leri yokken göster ki
          // sonuç/düşüş animasyonunun önüne geçmesin.
          if (_hintMessage != null &&
              _hintType != null &&
              state.status == 'round_active')
            TutorialHint(
              type: _hintType!,
              message: _hintMessage!,
              onDismiss: () {
                if (mounted) {
                  setState(() {
                    _hintType = null;
                    _hintMessage = null;
                  });
                }
              },
            ),
        ],
      ),
    );
  }

  // Pre-populate the result screen from the game_finished payload.
  // Tamamen savunmacı: tüm sayısal alanlar num→int güvenli dönüştürülür,
  // `winner` backend'de bir OBJE ({username, display_name, score}) — String
  // değil; bu yüzden önce obje, sonra is_winner bayrağı, en sonda en yüksek
  // skor ile çözülür.
  void _populateResult(Map<String, dynamic>? gameResult) {
    if (gameResult == null) return;

    final standings = (gameResult['final_standings'] as List? ?? [])
        .map((e) => Map<String, dynamic>.from(e as Map))
        .toList();
    final myUsername =
        ref.read(authProvider).user?['username'] as String? ?? '';
    final myEntry = standings.firstWhere(
      (p) => p['username'] == myUsername,
      orElse: () => <String, dynamic>{},
    );

    int asInt(dynamic v) => v is num ? v.toInt() : 0;

    // Winner çözümü: backend `winner` alanı OBJE ({username,...}) gelir.
    // Geriye dönük uyumluluk için String ihtimali de korunur.
    String? winnerName;
    final rawWinner = gameResult['winner'];
    if (rawWinner is Map) {
      winnerName = rawWinner['username'] as String?;
    } else if (rawWinner is String) {
      winnerName = rawWinner;
    }
    if (winnerName == null || winnerName.trim().isEmpty) {
      final flagged = standings.firstWhere(
        (p) => p['is_winner'] == true,
        orElse: () => <String, dynamic>{},
      );
      if (flagged['username'] != null) {
        winnerName = flagged['username'] as String?;
      } else if (standings.isNotEmpty) {
        winnerName = standings.first['username'] as String?;
      }
    }

    final myScore = asInt(myEntry['score']);
    final bool myIsWinner = myEntry['is_winner'] == true ||
        (myEntry['is_winner'] == null &&
            myUsername.isNotEmpty &&
            myUsername == winnerName);
    // ELENME AYRIMI: backend final_standings her oyuncuda eliminated_at_round
    // verir (null = hiç elenmedi = hayatta). Bu olmadan, son tura dek dayanan
    // ama şampiyon olamayan oyuncuya yanlışlıkla "elendin" gösteriliyordu.
    final rawElim = myEntry['eliminated_at_round'];
    final int totalRounds = asInt(gameResult['total_rounds']) == 0
        ? 5
        : asInt(gameResult['total_rounds']);
    final int roundsSurvived = asInt(myEntry['rounds_survived']);
    // Hayatta = kazanan, ya da eliminated_at_round yok/0, ya da tüm turlara dayandı.
    final bool mySurvived = myIsWinner ||
        rawElim == null ||
        (rawElim is num && rawElim <= 0) ||
        (totalRounds > 0 && roundsSurvived >= totalRounds);
    ref.read(resultProvider(widget.gameId).notifier).setResult({
      'top_players': standings.take(3).toList(),
      'my_result': {
        'score': myScore,
        'final_round': roundsSurvived,
        'correct_answers': asInt(myEntry['correct_answers']),
        'total_rounds': totalRounds,
        'xp_gained': (myScore / 2).round(),
        // game_finished payload'unda gelen coin ödülü (varsa). Maç sonu ekranı
        // "+N coin kazandın" göstermek için kullanır.
        'coins_earned': asInt(gameResult['coins_earned']),
        // 👻 Hayalet modu özeti: elendikten sonra bilinen doğrular + altını.
        'ghost_correct': asInt(gameResult['ghost_correct']),
        'ghost_reward': asInt(gameResult['ghost_reward']),
        // 🎯 Şampiyon bahsi sonucu (bahis yaptıysa payload'da gelir).
        if (gameResult['bet_on'] is String) ...{
          'bet_on': gameResult['bet_on'],
          'bet_won': gameResult['bet_won'] == true,
          'bet_reward': asInt(gameResult['bet_reward']),
        },
        // 🛡️ Kalkan bedeli (kişisel payload): kalkan kırıldıysa YA
        // shield_cost (tahsil edildi) YA shield_gift (bakiye yetmedi,
        // bedava) gelir — sonuç ekranı ilgili satırı gösterir.
        if (gameResult['shield_cost'] is num)
          'shield_cost': asInt(gameResult['shield_cost']),
        if (gameResult['shield_gift'] == true) 'shield_gift': true,
        'is_winner': myIsWinner,
        // Hayatta kalma bayrağı + ham eleme turu → result ekranı "elendin" vs
        // "hayatta kaldın" ayrımını doğru yapar (yanlış "elendin" bug fix).
        'survived': mySurvived,
        if (rawElim != null) 'eliminated_at_round': rawElim,
      },
      'round_breakdown': const [],
      // Maç özeti — game_finished payload'unda gelirse sonuç ekranına aktar.
      // Yoksa result_screen API'den (/api/games/{id}/result) çeker.
      if (gameResult['questions'] is List) 'questions': gameResult['questions'],
      'winner': winnerName,
    });
  }

  // Derive the avatar info for players eliminated this round from allPlayers,
  // so RoundRevealWidget can render the trapdoor fall with real avatars.
  List<Map<String, dynamic>> _eliminatedPlayers(GameState state) {
    final names = state.eliminatedThisRound.toSet();
    if (names.isEmpty) return const [];
    final out = <Map<String, dynamic>>[];
    for (final name in state.eliminatedThisRound) {
      final p = state.allPlayers.firstWhere(
        (e) => e['username'] == name,
        orElse: () => <String, dynamic>{'username': name},
      );
      out.add({
        'username': name,
        'avatar_id': p['avatar_id'] as String? ?? 'default_01',
      });
    }
    return out;
  }

  // Build the correct question widget based on question type
  Widget _buildQuestionWidget(GameState state, GameNotifier notifier) {
    final question = state.currentQuestion;

    if (question == null || state.status == 'waiting') {
      return _WaitingWidget(key: const ValueKey('waiting'));
    }

    final type = question['tip'] as String? ?? '';
    final key = ValueKey('${type}_${question['id'] ?? state.currentRound}');

    // Reveal sırasında doğru cevabı şıklarda göstermek için index'i çıkar.
    // MC/TF/karşılaştırma için ham index; slider için doğru sayı.
    final bool revealing = state.status == 'round_revealing';
    dynamic rawCorrect;
    if (revealing) {
      rawCorrect = state.roundResult?['correct_answer'];
    }
    final int? correctIndex = rawCorrect is int ? rawCorrect : null;

    // selectedAnswer MC/TF için ham index olarak gelir; slider için *100
    // encode'lu int gelebilir. Buradaki widget'lar (MC/TF/comparison) ham
    // index bekler — slider zaten ayrı dalda.
    final int? selectedIndex = state.selectedAnswer;

    switch (type) {
      case 'dogru_yanlis':
        return TrueFalseWidget(
          key: key,
          question: question,
          selectedAnswer: selectedIndex,
          correctAnswer: correctIndex,
          onAnswer: (idx) => notifier.submitChoice(idx),
        );

      case 'gorsel':
        return MultipleChoiceWidget(
          key: key,
          question: question,
          selectedAnswer: selectedIndex,
          correctAnswer: correctIndex,
          onAnswer: (idx) => notifier.submitChoice(idx),
          hasImage: true,
        );

      case 'karsilastirma':
        return ComparisonWidget(
          key: key,
          question: question,
          selectedAnswer: selectedIndex,
          correctAnswer: correctIndex,
          onAnswer: (idx) => notifier.submitChoice(idx),
        );

      case 'coktan_secmeli':
        return MultipleChoiceWidget(
          key: key,
          question: question,
          selectedAnswer: selectedIndex,
          correctAnswer: correctIndex,
          onAnswer: (idx) => notifier.submitChoice(idx),
          hasImage: false,
        );

      case 'tahmin':
        // Slider için doğru cevap sayı olarak gelir (num).
        final double? correctValue =
            revealing && rawCorrect is num ? rawCorrect.toDouble() : null;
        return SliderWidget(
          key: key,
          question: question,
          currentValue: state.selectedAnswer is num
              ? (state.selectedAnswer as num).toDouble() / 100.0
              : null,
          correctValue: correctValue,
          onValueChanged: (val) => notifier.previewEstimate(val),
          isLocked: state.answerLocked,
          onLock: notifier.lockSlider,
        );

      default:
        return _WaitingWidget(key: ValueKey('unknown_$type'));
    }
  }
}

// ---------------------------------------------------------------------------
// _TopBar
// ---------------------------------------------------------------------------

class _TopBar extends StatelessWidget {
  const _TopBar({
    required this.currentRound,
    required this.totalRounds,
    required this.questionType,
    required this.aliveCount,
  });

  final int currentRound;
  final int totalRounds;
  final String questionType;
  final int aliveCount;

  @override
  Widget build(BuildContext context) {
    final typeLabel =
        AppConstants.roundTypeLabels[questionType] ?? questionType;

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      child: Row(
        children: [
          // Round indicator
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            decoration: BoxDecoration(
              gradient: AppTheme.primaryGradient,
              borderRadius: BorderRadius.circular(20),
            ),
            child: Text(
              currentRound > 0
                  ? 'TUR $currentRound/$totalRounds'
                  : 'HAZIR OL',
              style: const TextStyle(
                color: Colors.white,
                fontWeight: FontWeight.w700,
                fontSize: 13,
              ),
            ),
          ),

          const SizedBox(width: 10),

          // Question type chip
          if (typeLabel.isNotEmpty)
            Expanded(
              child: Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                decoration: BoxDecoration(
                  color: AppTheme.card,
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(color: AppTheme.surface, width: 1),
                ),
                child: Text(
                  typeLabel,
                  style: const TextStyle(
                    color: AppTheme.textSecondary,
                    fontSize: 12,
                    fontWeight: FontWeight.w500,
                  ),
                  overflow: TextOverflow.ellipsis,
                  textAlign: TextAlign.center,
                ),
              ),
            ),

          const SizedBox(width: 10),

          // Alive count
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            decoration: BoxDecoration(
              color: AppTheme.card,
              borderRadius: BorderRadius.circular(20),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Text('👥', style: TextStyle(fontSize: 14)),
                const SizedBox(width: 4),
                Text(
                  '$aliveCount',
                  style: const TextStyle(
                    color: AppTheme.textPrimary,
                    fontWeight: FontWeight.w700,
                    fontSize: 14,
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

// ---------------------------------------------------------------------------
// _TimerBar
// ---------------------------------------------------------------------------

class _TimerBar extends StatelessWidget {
  const _TimerBar({
    required this.timeRemaining,
    required this.totalTime,
  });

  final double timeRemaining;
  final double totalTime;

  @override
  Widget build(BuildContext context) {
    final ratio = totalTime > 0 ? (timeRemaining / totalTime).clamp(0.0, 1.0) : 0.0;

    Color barColor;
    if (ratio > 0.5) {
      barColor = AppTheme.success;
    } else if (ratio > 0.25) {
      barColor = AppTheme.accent;
    } else {
      barColor = AppTheme.danger;
    }

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Stack(
        children: [
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: ratio,
              minHeight: 8,
              backgroundColor: AppTheme.surface,
              valueColor: AlwaysStoppedAnimation<Color>(barColor),
            ),
          ),
          if (timeRemaining > 0)
            Positioned.fill(
              child: Align(
                alignment: Alignment.center,
                child: Text(
                  timeRemaining.ceil().toString(),
                  style: TextStyle(
                    color: Colors.white.withOpacity(0.85),
                    fontSize: 9,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// _PlayerPlatformBar
// ---------------------------------------------------------------------------

class _PlayerPlatformBar extends StatelessWidget {
  const _PlayerPlatformBar({
    required this.players,
    this.myUsername,
    this.myFrame,
    this.finalStretch = false,
    this.shieldSavedThisRound = const [],
  });
  final List<Map<String, dynamic>> players;

  /// Yerel kullanıcının adı — kendi avatarına kuşanılmış çerçeve giydirmek için.
  final String? myUsername;

  /// Yerel kullanıcının kuşandığı çerçeve anahtarı (gold/neon/...).
  final String? myFrame;

  /// Son düzlük: az finalist kaldı → avatarlar büyütülür, kozmetik öne çıkar.
  final bool finalStretch;

  /// Bu tur KALKANIYLA kurtulan oyuncular — reveal sırasında avatarlarının
  /// üstünde küçük kırık-kalkan rozeti gösterilir.
  final List<String> shieldSavedThisRound;

  @override
  Widget build(BuildContext context) {
    if (players.isEmpty) return const SizedBox(height: 64);

    // Son düzlükte sadece hayatta kalanları, daha büyük göster.
    final visible = finalStretch
        ? players.where((p) => p['is_alive'] == true).toList()
        : players;
    final avatarSize = finalStretch ? 56.0 : 40.0;

    return AnimatedContainer(
      duration: const Duration(milliseconds: 300),
      height: finalStretch ? 96 : 72,
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
      decoration: BoxDecoration(
        color: AppTheme.surface.withOpacity(0.85),
        border: Border(
          top: BorderSide(
            color: finalStretch ? AppTheme.gold.withOpacity(0.6) : AppTheme.card,
            width: finalStretch ? 1.5 : 1,
          ),
        ),
      ),
      child: Center(
        child: SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: visible
                .map((p) => Padding(
                      padding: EdgeInsets.symmetric(
                          horizontal: finalStretch ? 6 : 3),
                      child: _PlayerAvatar(
                        player: p,
                        size: avatarSize,
                        frame: (p['username'] == myUsername)
                            ? myFrame
                            : frameKeyFromId(p['frame'] as String?),
                        shieldBroke: shieldSavedThisRound
                            .contains(p['username'] as String? ?? ''),
                      ),
                    ))
                .toList(),
          ),
        ),
      ),
    );
  }
}

class _PlayerAvatar extends StatelessWidget {
  const _PlayerAvatar({
    required this.player,
    this.size = 36,
    this.frame,
    this.shieldBroke = false,
  });
  final Map<String, dynamic> player;
  final double size;

  /// Kuşanılmış çerçeve anahtarı (varsa). PlayerAvatar bilinmeyen anahtarda
  /// çerçeve çizmez → güvenli.
  final String? frame;

  /// Bu tur kalkanıyla kurtuldu — reveal sırasında kırık-kalkan rozeti.
  final bool shieldBroke;

  @override
  Widget build(BuildContext context) {
    final isAlive = player['is_alive'] as bool? ?? true;
    final username = player['username'] as String? ?? '?';
    final avatarId = player['avatar_id'] as String? ?? 'default_01';
    // Kalan kalkan sayısı — 🛡️ rozeti kalkanı olan HERKESE çizilir, 0 olunca
    // kaybolur (round_start/game_state oyuncu girdisindeki "shields" alanı).
    final shields = (player['shields'] as num?)?.toInt() ?? 0;

    return Opacity(
      opacity: isAlive ? 1.0 : 0.4,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Stack(
            clipBehavior: Clip.none,
            children: [
              PlayerAvatar(
                avatarId: avatarId,
                username: username,
                size: size,
                isEliminated: !isAlive,
                frame: isAlive ? frame : null,
              ),
              // 🛡️ Kalkan rozeti (canlı + kalkanlı) / 💥 kırık-kalkan (bu tur
              // kalkanıyla kurtuldu). Kırık rozet önceliklidir (o an daha önemli).
              if (shieldBroke || (isAlive && shields > 0))
                Positioned(
                  right: -3,
                  top: -3,
                  child: Text(
                    shieldBroke ? '💥' : '🛡️',
                    style: TextStyle(fontSize: size * 0.34),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 2),
          SizedBox(
            width: size,
            child: Text(
              username,
              style: TextStyle(
                color: AppTheme.textSecondary,
                fontSize: size >= 56 ? 10 : 8,
                fontWeight: size >= 56 ? FontWeight.w700 : FontWeight.w400,
              ),
              overflow: TextOverflow.ellipsis,
              textAlign: TextAlign.center,
            ),
          ),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// _WaitingWidget
// ---------------------------------------------------------------------------

class _WaitingWidget extends StatelessWidget {
  const _WaitingWidget({super.key});

  @override
  Widget build(BuildContext context) {
    return const Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          CircularProgressIndicator(color: AppTheme.primary),
          SizedBox(height: 16),
          Text(
            'Oyun başlıyor...',
            style: TextStyle(
              color: AppTheme.textSecondary,
              fontSize: 16,
            ),
          ),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// _GhostModeBanner — 👻 hayalet modu bandı + 🎯 şampiyon bahsi kartı
// ---------------------------------------------------------------------------

class _GhostModeBanner extends StatelessWidget {
  const _GhostModeBanner({
    this.onLeave,
    this.betOn,
    this.showBetCard = false,
    this.alivePlayers = const [],
    this.onBet,
  });

  final VoidCallback? onLeave;

  /// Kilitli bahis hedefi (username). null = henüz bahis yok.
  final String? betOn;

  /// Bahis kartı gösterilsin mi? (bahis yok + final başlamadı + tur arası)
  final bool showBetCard;

  /// Hayatta kalan oyuncular — bahis hedefi listesi.
  final List<Map<String, dynamic>> alivePlayers;

  /// Bir hedefe dokununca çağrılır (tek seferlik kilitlenir).
  final ValueChanged<String>? onBet;

  @override
  Widget build(BuildContext context) {
    return Positioned(
      top: 0,
      left: 0,
      right: 0,
      child: SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            // ── Hayalet modu bandı ────────────────────────────────────────
            Container(
              margin: const EdgeInsets.fromLTRB(16, 0, 16, 0),
              padding: const EdgeInsets.fromLTRB(16, 10, 8, 10),
              decoration: BoxDecoration(
                color: AppTheme.primary.withOpacity(0.92),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Row(
                children: [
                  const Text('👻', style: TextStyle(fontSize: 16)),
                  const SizedBox(width: 8),
                  const Expanded(
                    child: Text(
                      'Hayalet Modu — cevaplamaya devam et, altın kazan!',
                      style: TextStyle(
                          color: Colors.white,
                          fontWeight: FontWeight.w700,
                          fontSize: 13),
                    ),
                  ),
                  if (onLeave != null)
                    GestureDetector(
                      onTap: onLeave,
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 12, vertical: 6),
                        decoration: BoxDecoration(
                          color: Colors.white.withOpacity(0.25),
                          borderRadius: BorderRadius.circular(999),
                        ),
                        child: const Text('Çık',
                            style: TextStyle(
                                color: Colors.white,
                                fontWeight: FontWeight.w700,
                                fontSize: 13)),
                      ),
                    ),
                ],
              ),
            ),

            // ── Kilitli bahis rozeti ──────────────────────────────────────
            if (betOn != null) ...[
              const SizedBox(height: 6),
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
                decoration: BoxDecoration(
                  color: AppTheme.gold.withOpacity(0.18),
                  borderRadius: BorderRadius.circular(999),
                  border:
                      Border.all(color: AppTheme.gold.withOpacity(0.6)),
                ),
                child: Text(
                  '🎯 Bahsin: $betOn 🔒',
                  style: const TextStyle(
                      color: AppTheme.gold,
                      fontWeight: FontWeight.w800,
                      fontSize: 12),
                ),
              ),
            ]
            // ── Şampiyon bahsi kartı (tek seferlik seçim) ─────────────────
            else if (showBetCard && alivePlayers.isNotEmpty) ...[
              const SizedBox(height: 6),
              _ChampionBetCard(alivePlayers: alivePlayers, onBet: onBet),
            ],
          ],
        ),
      ),
    );
  }
}

/// 🎯 "Şampiyonu bil, +25 altın kazan" kartı — hayatta kalanların avatar+isim
/// listesi; birine dokununca bahis KİLİTLENİR (değiştirilemez).
class _ChampionBetCard extends StatelessWidget {
  const _ChampionBetCard({required this.alivePlayers, this.onBet});
  final List<Map<String, dynamic>> alivePlayers;
  final ValueChanged<String>? onBet;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16),
      padding: const EdgeInsets.fromLTRB(12, 10, 12, 8),
      decoration: BoxDecoration(
        color: AppTheme.card.withOpacity(0.95),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppTheme.gold.withOpacity(0.5), width: 1.5),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Text(
            '🎯 Şampiyonu bil, +25 altın kazan!',
            style: TextStyle(
                color: AppTheme.gold,
                fontWeight: FontWeight.w800,
                fontSize: 13),
          ),
          const SizedBox(height: 8),
          SizedBox(
            height: 66,
            child: ListView.separated(
              scrollDirection: Axis.horizontal,
              itemCount: alivePlayers.length,
              separatorBuilder: (_, __) => const SizedBox(width: 10),
              itemBuilder: (_, i) {
                final p = alivePlayers[i];
                final username = p['username'] as String? ?? '?';
                final avatarId = p['avatar_id'] as String? ?? 'default_01';
                return GestureDetector(
                  onTap: () => onBet?.call(username),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      PlayerAvatar(
                          avatarId: avatarId, username: username, size: 42),
                      const SizedBox(height: 2),
                      SizedBox(
                        width: 52,
                        child: Text(
                          username,
                          style: const TextStyle(
                              color: AppTheme.textSecondary, fontSize: 9),
                          overflow: TextOverflow.ellipsis,
                          textAlign: TextAlign.center,
                        ),
                      ),
                    ],
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// _RoundTransitionOverlay
// ---------------------------------------------------------------------------

class _RoundTransitionOverlay extends StatefulWidget {
  const _RoundTransitionOverlay({
    required this.nextRound,
    required this.aliveCount,
    this.eliminatedCount = 0,
  });
  final int nextRound;
  final int aliveCount;
  final int eliminatedCount;

  @override
  State<_RoundTransitionOverlay> createState() =>
      _RoundTransitionOverlayState();
}

class _RoundTransitionOverlayState extends State<_RoundTransitionOverlay>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;
  late final Animation<double> _scale;
  late final Animation<double> _fade;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1500),
    );
    _scale = Tween<double>(begin: 0.6, end: 1.15).animate(
      CurvedAnimation(parent: _ctrl, curve: Curves.elasticOut),
    );
    _fade = TweenSequence<double>([
      TweenSequenceItem(tween: Tween(begin: 0.0, end: 1.0), weight: 25),
      TweenSequenceItem(tween: Tween(begin: 1.0, end: 1.0), weight: 50),
      TweenSequenceItem(tween: Tween(begin: 1.0, end: 0.0), weight: 25),
    ]).animate(_ctrl);
    _ctrl.forward();
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _ctrl,
      builder: (_, __) => Opacity(
        opacity: _fade.value,
        child: Container(
          color: Colors.black.withOpacity(0.75),
          child: Center(
            child: Transform.scale(
              scale: _scale.value,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  ShaderMask(
                    blendMode: BlendMode.srcIn,
                    shaderCallback: (bounds) =>
                        AppTheme.primaryGradient.createShader(
                      Rect.fromLTWH(0, 0, bounds.width, bounds.height),
                    ),
                    child: Text(
                      'TUR ${widget.nextRound}',
                      style: const TextStyle(
                        fontSize: 64,
                        fontWeight: FontWeight.w900,
                        letterSpacing: 4,
                      ),
                    ),
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'BAŞLIYOR',
                    style: TextStyle(
                      color: AppTheme.textSecondary,
                      fontSize: 18,
                      letterSpacing: 6,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: 16),
                  if (widget.eliminatedCount > 0) ...[
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                      decoration: BoxDecoration(
                        color: AppTheme.danger.withOpacity(0.18),
                        borderRadius: BorderRadius.circular(20),
                        border: Border.all(color: AppTheme.danger.withOpacity(0.5), width: 1.5),
                      ),
                      child: Text(
                        '💀 Bu turda elenen: ${widget.eliminatedCount}',
                        style: const TextStyle(
                          color: AppTheme.danger,
                          fontSize: 15,
                          letterSpacing: 0.5,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                    ),
                    const SizedBox(height: 10),
                  ],
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 9),
                    decoration: BoxDecoration(
                      color: AppTheme.cTertiary.withOpacity(0.18),
                      borderRadius: BorderRadius.circular(20),
                      border: Border.all(color: AppTheme.cTertiary.withOpacity(0.5), width: 1.5),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Text('👥', style: TextStyle(fontSize: 18)),
                        const SizedBox(width: 8),
                        Text(
                          '${widget.aliveCount} oyuncu kaldı',
                          style: const TextStyle(
                            color: AppTheme.cTertiary,
                            fontSize: 16,
                            letterSpacing: 0.5,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// _FinalAnnounceOverlay — 🏆 FİNAL turu duyurusu (1.8sn, kendiliğinden kapanır)
// ---------------------------------------------------------------------------

class _FinalAnnounceOverlay extends StatefulWidget {
  const _FinalAnnounceOverlay({required this.onDone});
  final VoidCallback onDone;

  @override
  State<_FinalAnnounceOverlay> createState() => _FinalAnnounceOverlayState();
}

class _FinalAnnounceOverlayState extends State<_FinalAnnounceOverlay>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;
  late final Animation<double> _scale;
  late final Animation<double> _fade;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1800),
    );
    _scale = Tween<double>(begin: 0.7, end: 1.05).animate(
      CurvedAnimation(parent: _ctrl, curve: Curves.elasticOut),
    );
    // Hızlı belir → sabit kal → yumuşak kaybol (RoundTransition ile aynı dil).
    _fade = TweenSequence<double>([
      TweenSequenceItem(tween: Tween(begin: 0.0, end: 1.0), weight: 15),
      TweenSequenceItem(tween: Tween(begin: 1.0, end: 1.0), weight: 65),
      TweenSequenceItem(tween: Tween(begin: 1.0, end: 0.0), weight: 20),
    ]).animate(_ctrl);
    _ctrl.forward();
    _ctrl.addStatusListener((s) {
      if (s == AnimationStatus.completed) widget.onDone();
    });
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _ctrl,
      builder: (_, __) => IgnorePointer(
        child: Opacity(
          opacity: _fade.value,
          child: Container(
            color: Colors.black.withValues(alpha: 0.78),
            alignment: Alignment.center,
            child: Transform.scale(
              scale: _scale.value,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Text('🏆', style: TextStyle(fontSize: 64)),
                  const SizedBox(height: 12),
                  ShaderMask(
                    blendMode: BlendMode.srcIn,
                    shaderCallback: (bounds) =>
                        AppTheme.primaryGradient.createShader(
                      Rect.fromLTWH(0, 0, bounds.width, bounds.height),
                    ),
                    child: const Text(
                      'FİNAL',
                      style: TextStyle(
                        fontSize: 60,
                        fontWeight: FontWeight.w900,
                        letterSpacing: 6,
                      ),
                    ),
                  ),
                  const SizedBox(height: 12),
                  Container(
                    margin: const EdgeInsets.symmetric(horizontal: 32),
                    padding: const EdgeInsets.symmetric(
                        horizontal: 18, vertical: 10),
                    decoration: BoxDecoration(
                      color: AppTheme.gold.withValues(alpha: 0.16),
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(
                          color: AppTheme.gold.withValues(alpha: 0.6), width: 1.5),
                    ),
                    child: const Text(
                      'EN YAKIN TAHMİN ŞAMPİYON OLUR!',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        color: AppTheme.gold,
                        fontSize: 17,
                        fontWeight: FontWeight.w800,
                        letterSpacing: 0.5,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// _QuickMsgButton — 💬 hazır mesaj sheet'ini açan küçük buton
// ---------------------------------------------------------------------------

class _QuickMsgButton extends StatelessWidget {
  const _QuickMsgButton({required this.onSelected});

  /// Seçilen hazır mesajın id'si (qm_*) ile çağrılır.
  final ValueChanged<String> onSelected;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () => _openSheet(context),
      child: Container(
        width: 46,
        height: 46,
        decoration: BoxDecoration(
          color: AppTheme.card.withValues(alpha: 0.92),
          shape: BoxShape.circle,
          border: Border.all(color: AppTheme.surface, width: 1.5),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.35),
              blurRadius: 10,
              offset: const Offset(0, 3),
            ),
          ],
        ),
        alignment: Alignment.center,
        child: const Text('💬', style: TextStyle(fontSize: 20)),
      ),
    );
  }

  void _openSheet(BuildContext context) {
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: Colors.transparent,
      builder: (sheetCtx) => SafeArea(
        child: Container(
          margin: const EdgeInsets.fromLTRB(12, 0, 12, 12),
          padding: const EdgeInsets.fromLTRB(16, 14, 16, 16),
          decoration: BoxDecoration(
            color: AppTheme.cSurfaceContainerHigh,
            borderRadius: BorderRadius.circular(22),
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text('HAZIR MESAJ GÖNDER',
                  style: BiladaText.label(
                      color: AppTheme.cOnSurfaceVariant, size: 12)),
              const SizedBox(height: 12),
              // Sabit liste — serbest metin girişi bilerek YOK (moderasyon
              // riski sıfır; sunucu da yalnızca bu id'leri kabul eder).
              for (final entry in AppConstants.quickMessages.entries)
                Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: SizedBox(
                    width: double.infinity,
                    child: ChunkyButton(
                      height: 48,
                      depth: 4,
                      color: AppTheme.cSurfaceContainer,
                      foreground: AppTheme.cOnSurface,
                      shadowColor: AppTheme.cSurfaceContainerLowest,
                      onPressed: () {
                        onSelected(entry.key);
                        Navigator.of(sheetCtx).pop();
                      },
                      child: Text(entry.value,
                          style: const TextStyle(fontSize: 16)),
                    ),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// _QuickMsgBubble — gelen hazır mesajın 2sn'lik baloncuğu (gönderen adıyla)
// ---------------------------------------------------------------------------

class _QuickMsgBubble extends StatelessWidget {
  const _QuickMsgBubble({required this.username, required this.text});
  final String username;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Positioned(
      top: 0,
      left: 0,
      right: 0,
      child: SafeArea(
        child: Padding(
          padding: const EdgeInsets.only(top: 56),
          child: Center(
            child: TweenAnimationBuilder<double>(
              tween: Tween(begin: 0.0, end: 1.0),
              duration: const Duration(milliseconds: 220),
              curve: Curves.easeOutBack,
              builder: (_, t, child) => Opacity(
                opacity: t.clamp(0.0, 1.0),
                child: Transform.scale(scale: 0.8 + 0.2 * t, child: child),
              ),
              child: Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 16, vertical: 9),
                decoration: BoxDecoration(
                  color: AppTheme.card.withValues(alpha: 0.95),
                  borderRadius: BorderRadius.circular(999),
                  border: Border.all(
                      color: AppTheme.cPrimaryContainer.withValues(alpha: 0.6)),
                  boxShadow: [
                    BoxShadow(
                      color: Colors.black.withValues(alpha: 0.35),
                      blurRadius: 12,
                      offset: const Offset(0, 4),
                    ),
                  ],
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(username,
                        style: const TextStyle(
                          color: AppTheme.cPrimary,
                          fontWeight: FontWeight.w800,
                          fontSize: 13,
                        )),
                    const SizedBox(width: 8),
                    Text(text,
                        style: const TextStyle(
                          color: AppTheme.textPrimary,
                          fontWeight: FontWeight.w600,
                          fontSize: 14,
                        )),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// _EmojiFloatOverlay
// ---------------------------------------------------------------------------

class _EmojiFloatOverlay extends StatefulWidget {
  const _EmojiFloatOverlay({required this.emoji});
  final String emoji;

  @override
  State<_EmojiFloatOverlay> createState() => _EmojiFloatOverlayState();
}

class _EmojiFloatOverlayState extends State<_EmojiFloatOverlay>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;
  late final Animation<double> _posY;
  late final Animation<double> _opacity;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1500),
    );
    _posY = Tween<double>(begin: 0, end: -140).animate(
      CurvedAnimation(parent: _ctrl, curve: Curves.easeOut),
    );
    _opacity = TweenSequence<double>([
      TweenSequenceItem(tween: Tween(begin: 0.0, end: 1.0), weight: 20),
      TweenSequenceItem(tween: Tween(begin: 1.0, end: 1.0), weight: 50),
      TweenSequenceItem(tween: Tween(begin: 1.0, end: 0.0), weight: 30),
    ]).animate(_ctrl);
    _ctrl.forward();
  }

  @override
  void didUpdateWidget(_EmojiFloatOverlay old) {
    super.didUpdateWidget(old);
    if (old.emoji != widget.emoji) {
      _ctrl.reset();
      _ctrl.forward();
    }
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final size = MediaQuery.of(context).size;

    return AnimatedBuilder(
      animation: _ctrl,
      builder: (_, __) => Positioned(
        bottom: 100 + _posY.value.abs(),
        left: size.width / 2 - 28,
        child: Opacity(
          opacity: _opacity.value,
          child: Text(
            widget.emoji,
            style: const TextStyle(fontSize: 56),
          ),
        ),
      ),
    );
  }
}
