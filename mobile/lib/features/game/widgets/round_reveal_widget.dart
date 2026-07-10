import 'dart:async';
import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:quizroyale/core/services/haptic_service.dart';
import 'package:quizroyale/core/services/sound_service.dart';
import 'package:quizroyale/core/theme/app_theme.dart';
import 'package:quizroyale/shared/widgets/player_avatar.dart';

class RoundRevealWidget extends StatefulWidget {
  const RoundRevealWidget({
    super.key,
    required this.roundResult,
    required this.question,
    required this.onDismiss,
    this.aliveCount,
    this.eliminatedPlayers = const [],
    this.players = const [],
    this.myUsername,
    this.myFrame,
  });

  final Map<String, dynamic> roundResult;
  final Map<String, dynamic> question;
  final VoidCallback onDismiss;

  /// Number of players still alive after this round (derived from allPlayers).
  final int? aliveCount;

  /// Players eliminated this round, derived from allPlayers ∩ eliminatedThisRound.
  /// Each item: {username, avatar_id}. Used for the trapdoor fall animation.
  final List<Map<String, dynamic>> eliminatedPlayers;

  /// Tüm oyuncular {username, avatar_id, ...} — sonuç satırlarında gerçek
  /// 3D avatarı göstermek için username→avatar_id eşlemesi sağlar.
  final List<Map<String, dynamic>> players;

  /// Current user's username — if they are in [eliminatedPlayers] we show a
  /// bigger "ELENDİN!" treatment during the fall.
  final String? myUsername;

  /// Yerel kullanıcının kuşandığı çerçeve anahtarı (gold/neon/...). Düşen kendi
  /// avatarımıza ve sonuç satırımıza giydirilir → kozmetik elenme anında görünür.
  final String? myFrame;

  @override
  State<RoundRevealWidget> createState() => _RoundRevealWidgetState();
}

/// Reveal flow phases:
///  - results: doğru cevap + sonuç kartları kısa süre gösterilir.
///  - falling: trapdoor açılır, elenen oyuncular ~2sn aşağıya düşer.
enum _RevealPhase { results, falling }

class _RoundRevealWidgetState extends State<RoundRevealWidget>
    with TickerProviderStateMixin {
  Timer? _resultsTimer;

  late final AnimationController _fallCtrl;

  // Toplam reveal bütçesi ≈ 4.8s (tur arası 5sn penceresinin içinde):
  // 2.2s sonuç gösterimi + 2.6s düşüş sekansı. Düşüş sekansının ilk ~%20'si
  // titreme/sallanma (kapı henüz açılmadı), kalan ~2.1s gerçek düşüş —
  // kullanıcı geri bildirimi ("düşme efektleri çok belli olmuyor") üzerine
  // düşüş fazı uzatıldı ve dramatikleştirildi.
  static const _resultsDuration = Duration(milliseconds: 2200);
  static const _fallDuration = Duration(milliseconds: 2600);

  _RevealPhase _phase = _RevealPhase.results;

  /// İlk ~1.4sn: soru + renkli şıklar (doğru=yeşil, yanlış=kırmızı) görünür
  /// kalsın diye scrim'in üstü şeffaf, reveal içeriği alta yaslanır. Süre
  /// dolunca tam-örtü özet/sonuç listesine geçilir.
  bool _optionsRevealWindow = true;
  Timer? _optionsWindowTimer;

  bool get _hasEliminated => widget.eliminatedPlayers.isNotEmpty;

  bool get _amIEliminated =>
      widget.myUsername != null &&
      widget.eliminatedPlayers
          .any((p) => p['username'] == widget.myUsername);

  /// Bu tur kalkanıyla kurtulanlar (round_reveal.shield_saved listesi).
  List<String> get _shieldSaved =>
      (widget.roundResult['shield_saved'] as List?)
          ?.map((e) => e.toString())
          .toList() ??
      const [];

  /// Benim kalkanım bu tur mu kırıldı? (belirgin uyarı banner'ı için)
  bool get _myShieldBroke =>
      widget.myUsername != null && _shieldSaved.contains(widget.myUsername);

  /// 👻 Hayalet (elenmişken verilen gölge cevap) sonucum — {answer, correct}
  /// ya da null. Reveal'da yarı saydam, hafif bir rozetle gösterilir.
  Map<String, dynamic>? get _myGhostResult {
    final me = widget.myUsername;
    if (me == null) return null;
    final ghosts =
        (widget.roundResult['ghost_results'] as Map?)?.cast<String, dynamic>();
    final mine = ghosts?[me];
    return mine is Map ? Map<String, dynamic>.from(mine) : null;
  }

  @override
  void initState() {
    super.initState();
    _fallCtrl = AnimationController(vsync: this, duration: _fallDuration);

    // İlk pencere boyunca renkli şıklar görünür; sonra tam-örtü içerik gelir.
    _optionsWindowTimer = Timer(_resultsDuration, () {
      if (!mounted) return;
      setState(() => _optionsRevealWindow = false);
    });

    if (!_hasEliminated) {
      // Elenen yoksa düşüş fazını atla; tüm süreyi sonuçlara ver.
      _resultsTimer = Timer(
        _resultsDuration + _fallDuration,
        _finish,
      );
      return;
    }

    _resultsTimer = Timer(_resultsDuration, () {
      if (!mounted) return;
      setState(() => _phase = _RevealPhase.falling);
      // Trapdoor açılıyor — düşüş glissandosu; kendim düşüyorsam güçlü titreşim.
      SoundService().playSound(GameSound.elimination);
      if (_amIEliminated) {
        HapticService().elimination();
      }
      _fallCtrl.forward();
    });
    _fallCtrl.addStatusListener((s) {
      if (s == AnimationStatus.completed) _finish();
    });
  }

  void _finish() {
    if (!mounted) return;
    widget.onDismiss();
  }

  @override
  void dispose() {
    _resultsTimer?.cancel();
    _optionsWindowTimer?.cancel();
    _fallCtrl.dispose();
    super.dispose();
  }

  /// Doğru cevabı okunur metne çevirir (index → seçenek metni, sayı + birim).
  String _formatCorrectAnswer(dynamic ca) {
    final options = (widget.question['options'] as List?);
    if (ca is int && options != null && ca >= 0 && ca < options.length) {
      return options[ca].toString();
    }
    final unit = (widget.question['unit'] ?? '').toString();
    if (ca is num) {
      final n = ca == ca.roundToDouble() ? ca.toInt().toString() : ca.toString();
      return unit.isNotEmpty ? '$n $unit' : n;
    }
    return ca?.toString() ?? '';
  }

  @override
  Widget build(BuildContext context) {
    final eliminated = List<String>.from(widget.roundResult['eliminated'] ?? []);
    final results =
        (widget.roundResult['results'] as Map?)?.cast<String, dynamic>() ?? {};
    final correctAnswer = widget.roundResult['correct_answer'];
    // Index'i okunur metne çevir: çoktan seçmeli/doğru-yanlış için seçenek
    // metni, tahmin için sayı (+ birim). Eskiden ham "1" gösteriliyordu.
    final correctText = _formatCorrectAnswer(correctAnswer);

    // İlk pencere: üstteki soru + renkli şıklar görünsün diye scrim'in üstü
    // şeffaf bırakılır ve reveal içeriği alt yarıya yaslanır. Pencere dolunca
    // (veya düşüş başlayınca) tam opak özet + sonuç listesine geçilir.
    final bool resultsPhase =
        _optionsRevealWindow && _phase == _RevealPhase.results;

    return Stack(
      children: [
        // Faz'a göre arka plan: results'ta üstte şeffaf gradyan (şıklar
        // görünür), falling/özet fazında tam koyu örtü.
        Positioned.fill(
          child: resultsPhase
              ? DecoratedBox(
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      begin: Alignment.topCenter,
                      end: Alignment.bottomCenter,
                      colors: [
                        Colors.transparent,
                        Colors.black.withOpacity(0.35),
                        Colors.black.withOpacity(0.82),
                      ],
                      stops: const [0.0, 0.45, 0.72],
                    ),
                  ),
                )
              : ColoredBox(color: Colors.black.withOpacity(0.88)),
        ),

        SafeArea(
          child: Column(
            children: [
              // results fazında içeriği alta yasla; soru/şıklar üstte kalsın.
              if (resultsPhase) const Spacer(),
              const SizedBox(height: 24),
              const Text('DOĞRU CEVAP',
                  style: TextStyle(
                      color: AppTheme.textSecondary,
                      fontSize: 12,
                      letterSpacing: 2,
                      fontWeight: FontWeight.w700)),
              const SizedBox(height: 8),
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
                decoration: BoxDecoration(
                  color: AppTheme.success.withOpacity(0.2),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: AppTheme.success),
                ),
                child: Text(
                  correctText,
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                      color: AppTheme.success,
                      fontSize: 22,
                      fontWeight: FontWeight.w800),
                ),
              ),
              const SizedBox(height: 16),

              // ── 🛡️ Kalkanım bu tur kırıldı — belirgin uyarı ────────────
              if (_myShieldBroke) ...[
                const _ShieldBrokenBanner(),
                const SizedBox(height: 12),
              ],

              // ── 👻 Hayalet sonucum — yarı saydam, hafif geri bildirim ──
              if (_myGhostResult != null) ...[
                _GhostResultChip(correct: _myGhostResult!['correct'] == true),
                const SizedBox(height: 12),
              ],

              // ── Survivor summary: bilen + kalan + bu turda elenen ───────
              // "BİLDİ" çipi, "bilen" ile "hayatta kalan" ayrımını netleştirir
              // (kalkanla kurtulan hayatta kalır ama puansızdır — kullanıcı
              // "bilen çok, puan alan az" diye karıştırıyordu).
              _SurvivorSummary(
                correctCount: results.values
                    .where((v) => (v as Map)['correct'] == true)
                    .length,
                aliveCount: widget.aliveCount,
                eliminatedCount: eliminated.length,
              ),
              const SizedBox(height: 16),

              // Player results — sadece tam-örtü fazında (results fazında
              // alttaki şıkların görünmesi için gizli). PUANA GÖRE SIRALI ve
              // TÜM oyuncular listelenir (eski take(10), 12 kişilik maçta 2
              // satırı sessizce yutuyordu; liste zaten kaydırılabilir).
              if (!resultsPhase)
                Expanded(
                  child: ListView(
                    padding: const EdgeInsets.symmetric(horizontal: 16),
                    children: (results.entries.toList()
                          ..sort((a, b) =>
                              (((b.value as Map)['score'] as num?)?.toInt() ?? 0)
                                  .compareTo(
                                      ((a.value as Map)['score'] as num?)
                                              ?.toInt() ??
                                          0)))
                        .map((e) {
                      final data = e.value as Map<String, dynamic>;
                      final correct = data['correct'] == true;
                      final score = data['score'] as int? ?? 0;
                      final avatarId = widget.players.firstWhere(
                            (p) => p['username'] == e.key,
                            orElse: () => const {},
                          )['avatar_id'] as String? ??
                          'default_01';
                      return _PlayerResultRow(
                        username: e.key,
                        avatarId: avatarId,
                        correct: correct,
                        score: score,
                        // Kalkanıyla kurtuldu → satırda kırık-kalkan rozeti.
                        shieldBroke: data['shield_saved'] == true,
                      );
                    }).toList(),
                  ),
                ),

              // Eliminated section — chunky danger banner
              if (eliminated.isNotEmpty) ...[
                Container(
                  width: double.infinity,
                  margin: const EdgeInsets.symmetric(
                      horizontal: 16, vertical: 4),
                  padding: const EdgeInsets.symmetric(
                      vertical: 12, horizontal: 16),
                  decoration: BoxDecoration(
                    color: AppTheme.danger.withOpacity(0.14),
                    borderRadius: BorderRadius.circular(14),
                    border: Border.all(
                        color: AppTheme.danger.withOpacity(0.5), width: 1.5),
                  ),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(
                        '💀 BU TURDA ELENEN: ${eliminated.length}',
                        style: const TextStyle(
                          color: AppTheme.danger,
                          fontSize: 13,
                          fontWeight: FontWeight.w800,
                          letterSpacing: 0.5,
                        ),
                        textAlign: TextAlign.center,
                      ),
                      const SizedBox(height: 4),
                      Text(
                        eliminated.join(', '),
                        style: const TextStyle(
                            color: AppTheme.danger,
                            fontSize: 12,
                            fontWeight: FontWeight.w600),
                        textAlign: TextAlign.center,
                      ),
                    ],
                  ),
                ),
              ],
              if (resultsPhase) const SizedBox(height: 16),
            ],
          ),
        ),

        // ── Trapdoor fall overlay ──────────────────────────────────────
        if (_phase == _RevealPhase.falling && _hasEliminated)
          _FallOverlay(
            controller: _fallCtrl,
            eliminatedPlayers: widget.eliminatedPlayers,
            amIEliminated: _amIEliminated,
            myUsername: widget.myUsername,
            myFrame: widget.myFrame,
          ),
      ],
    );
  }
}

// ---------------------------------------------------------------------------
// _FallOverlay — Fall Guys tarzı trapdoor + avatar düşüşü
// ---------------------------------------------------------------------------

class _FallOverlay extends StatelessWidget {
  const _FallOverlay({
    required this.controller,
    required this.eliminatedPlayers,
    required this.amIEliminated,
    required this.myUsername,
    this.myFrame,
  });

  final AnimationController controller;
  final List<Map<String, dynamic>> eliminatedPlayers;
  final bool amIEliminated;
  final String? myUsername;
  final String? myFrame;

  @override
  Widget build(BuildContext context) {
    final screenH = MediaQuery.of(context).size.height;

    return Positioned.fill(
      child: AnimatedBuilder(
        animation: controller,
        builder: (context, _) {
          final t = controller.value;
          // DRAMATİK SEKANS: ilk ~%20 titreme/sallanma (kapı kapalı, gerilim),
          // kapılar %12-32 aralığında açılır, düşüş %20'den sonra başlar.
          final doorT = ((t - 0.12) / 0.20).clamp(0.0, 1.0);
          // "ELENDİN!" yazısı kapı açıldıktan sonra belirginleşir.
          final titleOpacity = ((t - 0.22) / 0.2).clamp(0.0, 1.0);

          // Ekran sarsıntısı — SADECE kendim eleniyorsam; titreme fazında
          // güçlü, düşüş başlayınca hızla söner.
          final shakeAmp = amIEliminated
              ? (t < 0.2 ? 6.0 : (t < 0.4 ? 6.0 * (1 - (t - 0.2) / 0.2) : 0.0))
              : 0.0;
          final shakeX = math.sin(t * 90) * shakeAmp;
          final shakeY = math.cos(t * 70) * shakeAmp * 0.6;

          return Transform.translate(
            offset: Offset(shakeX, shakeY),
            child: Container(
            color: Colors.black.withOpacity(0.55 * (1 - t * 0.4)),
            child: Stack(
              alignment: Alignment.center,
              children: [
                // Kırmızı vinyet — kendim eleniyorsam tam ekran; düşüş
                // ilerledikçe yumuşakça söner.
                if (amIEliminated)
                  Positioned.fill(
                    child: IgnorePointer(
                      child: DecoratedBox(
                        decoration: BoxDecoration(
                          gradient: RadialGradient(
                            radius: 1.1,
                            colors: [
                              Colors.transparent,
                              AppTheme.cError.withOpacity(
                                  (0.5 * (1 - t * 0.55)).clamp(0.0, 1.0)),
                            ],
                            stops: const [0.55, 1.0],
                          ),
                        ),
                      ),
                    ),
                  ),

                // Trapdoor — ortada açılan iki kanat
                _Trapdoor(open: doorT),

                // Düşen avatarlar
                ...List.generate(eliminatedPlayers.length, (i) {
                  final p = eliminatedPlayers[i];
                  final username = p['username'] as String? ?? '?';
                  final avatarId = p['avatar_id'] as String? ?? 'default_01';
                  final isMe = username == myUsername;
                  return _FallingAvatar(
                    progress: t,
                    index: i,
                    total: eliminatedPlayers.length,
                    screenHeight: screenH,
                    username: username,
                    avatarId: avatarId,
                    emphasized: isMe,
                    frame: isMe ? myFrame : null,
                  );
                }),

                // Kendim elendiysem büyük, NET okunan "ELENDİN!"
                // (beyaz kalın yazı + kırmızı parıltılı koyu panel → arka plandan
                //  net ayrışır; hafif "pop" ile büyüyerek gelir.)
                if (amIEliminated)
                  Positioned(
                    top: screenH * 0.15,
                    child: Opacity(
                      opacity: titleOpacity,
                      child: Transform.scale(
                        scale: 0.7 + 0.3 * titleOpacity,
                        child: Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 30, vertical: 16),
                          decoration: BoxDecoration(
                            color: Colors.black.withOpacity(0.55),
                            borderRadius: BorderRadius.circular(22),
                            border: Border.all(color: AppTheme.cError, width: 3.5),
                            boxShadow: [
                              BoxShadow(
                                color: AppTheme.cError.withOpacity(0.6),
                                blurRadius: 30,
                                spreadRadius: 2,
                              ),
                            ],
                          ),
                          child: const Text(
                            'ELENDİN!',
                            textAlign: TextAlign.center,
                            style: TextStyle(
                              color: Colors.white,
                              fontSize: 66,
                              fontWeight: FontWeight.w900,
                              letterSpacing: 2,
                              height: 1.0,
                              shadows: [
                                Shadow(color: AppTheme.cError, blurRadius: 18),
                                Shadow(
                                    color: Colors.black,
                                    offset: Offset(0, 3),
                                    blurRadius: 6),
                              ],
                            ),
                          ),
                        ),
                      ),
                    ),
                  ),
              ],
            ),
            ),
          );
        },
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// _Trapdoor — ortada açılan iki kapı kanadı
// ---------------------------------------------------------------------------

class _Trapdoor extends StatelessWidget {
  const _Trapdoor({required this.open});

  /// 0 = kapalı, 1 = tam açık.
  final double open;

  @override
  Widget build(BuildContext context) {
    // Kapılar dışa doğru devrilir (rotateZ ~75°).
    final angle = open * (75 * math.pi / 180);

    Widget door({required bool left}) => Transform(
          alignment: left ? Alignment.centerLeft : Alignment.centerRight,
          transform: Matrix4.identity()
            ..rotateZ(left ? angle : -angle),
          child: Container(
            width: 70,
            height: 16,
            decoration: BoxDecoration(
              color: AppTheme.cardLight,
              borderRadius: BorderRadius.only(
                topLeft: Radius.circular(left ? 6 : 0),
                bottomLeft: Radius.circular(left ? 6 : 0),
                topRight: Radius.circular(left ? 0 : 6),
                bottomRight: Radius.circular(left ? 0 : 6),
              ),
              border: const Border(
                bottom: BorderSide(color: Colors.black54, width: 3),
              ),
            ),
          ),
        );

    return SizedBox(
      width: 160,
      height: 40,
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        mainAxisSize: MainAxisSize.min,
        children: [
          door(left: true),
          door(left: false),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// _FallingAvatar — translateY + rotate + fade + hızlanma (easeIn)
// ---------------------------------------------------------------------------

class _FallingAvatar extends StatelessWidget {
  const _FallingAvatar({
    required this.progress,
    required this.index,
    required this.total,
    required this.screenHeight,
    required this.username,
    required this.avatarId,
    required this.emphasized,
    this.frame,
  });

  final double progress; // 0..1 (controller value)
  final int index;
  final int total;
  final double screenHeight;
  final String username;
  final String avatarId;
  final bool emphasized;
  final String? frame;

  @override
  Widget build(BuildContext context) {
    // Hafif sıralı kalkış (stagger) — çok oyuncuda küçük dalga hissi.
    final stagger = total > 1 ? (index / total) * 0.12 : 0.0;
    final raw = ((progress - stagger) / (1 - stagger)).clamp(0.0, 1.0);

    // FAZ 1 (0–0.2): platformda TİTREME + kırmızı parlama — düşüş öncesi
    // gerilim ("düşecek!" hissi). Kapılar bu fazın sonunda açılır.
    const shakeEnd = 0.2;
    final falling = raw > shakeEnd;
    final fallRaw =
        falling ? ((raw - shakeEnd) / (1 - shakeEnd)).clamp(0.0, 1.0) : 0.0;

    // easeIn → düşüş hızlanır (yer çekimi hissi).
    final eased = Curves.easeIn.transform(fallRaw);

    final dy = eased * (screenHeight * 0.95);
    // Titreme fazı: hızlı yatay jitter + minik sallanma (wobble).
    final jitterX = falling ? 0.0 : math.sin(raw * 85) * 3.5;
    final wobble = falling ? 0.0 : math.sin(raw * 60) * 0.06;
    // Düşerken hafif DÖNME (kendim düşüyorsam daha dramatik).
    final rotation = wobble + eased * (emphasized ? 1.5 : 1.0);
    // Karakter düşerken NET görünsün: çoğu yol boyunca tam opak kalsın,
    // yalnızca son %25'te solup kaybolsun (soluklaşma).
    final opacity =
        fallRaw < 0.75 ? 1.0 : (1.0 - (fallRaw - 0.75) / 0.25).clamp(0.0, 1.0);
    // Düşerken küçülme (uzaklaşma hissi) — yine de izlenebilir kalsın.
    final scale = 1.0 - eased * 0.35;

    // Kırmızı parlama: titreme fazında yanıp söner (uyarı), düşüşte yalnızca
    // vurgulanan (kendi) avatarda kalır.
    final glowOpacity = falling
        ? (emphasized ? 0.7 : 0.0)
        : (0.35 + 0.45 * math.sin(raw * 55).abs());

    // Yatay yelpaze: avatarlar trapdoor çevresinde dağılsın.
    final spread = total > 1 ? (index - (total - 1) / 2) * 56.0 : 0.0;

    final avatarSize = emphasized ? 124.0 : 60.0;

    return Transform.translate(
      offset: Offset(spread + jitterX, dy - screenHeight * 0.06),
      child: Opacity(
        opacity: opacity,
        child: Transform.rotate(
          angle: rotation,
          child: Transform.scale(
            scale: scale,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                // Titreme fazında herkes kırmızı parlar; düşüşte kendi
                // karakterim parıltılı halkayla öne çıkmayı sürdürür.
                Container(
                  decoration: glowOpacity > 0
                      ? BoxDecoration(
                          shape: BoxShape.circle,
                          boxShadow: [
                            BoxShadow(
                              color: AppTheme.cError
                                  .withOpacity(glowOpacity.clamp(0.0, 1.0)),
                              blurRadius: emphasized ? 26 : 16,
                              spreadRadius: emphasized ? 3 : 1,
                            ),
                          ],
                        )
                      : null,
                  child: PlayerAvatar(
                    avatarId: avatarId,
                    username: username,
                    size: avatarSize,
                    frame: frame,
                  ),
                ),
                const SizedBox(height: 4),
                Container(
                  padding: const EdgeInsets.symmetric(
                      horizontal: 8, vertical: 2),
                  decoration: BoxDecoration(
                    color: AppTheme.cErrorContainer.withOpacity(0.85),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Text(
                    username,
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: emphasized ? 14 : 11,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _SurvivorSummary extends StatelessWidget {
  const _SurvivorSummary(
      {this.correctCount,
      required this.aliveCount,
      required this.eliminatedCount});

  /// Bu turda DOĞRU cevaplayan sayısı (hayatta kalandan farklı olabilir:
  /// kalkanla kurtulan hayatta ama puansız). null → çip gösterilmez.
  final int? correctCount;
  final int? aliveCount;
  final int eliminatedCount;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        if (correctCount != null) ...[
          _StatChip(
            emoji: '🧠',
            value: '$correctCount',
            label: 'BİLDİ',
            color: AppTheme.cSecondary,
          ),
          if (aliveCount != null || eliminatedCount > 0)
            const SizedBox(width: 12),
        ],
        if (aliveCount != null)
          _StatChip(
            emoji: '👥',
            value: '$aliveCount',
            label: 'OYUNCU KALDI',
            color: AppTheme.cTertiary,
          ),
        if (aliveCount != null && eliminatedCount > 0)
          const SizedBox(width: 12),
        if (eliminatedCount > 0)
          _StatChip(
            emoji: '💀',
            value: '$eliminatedCount',
            label: 'ELENDİ',
            color: AppTheme.danger,
          ),
      ],
    );
  }
}

class _StatChip extends StatelessWidget {
  const _StatChip({
    required this.emoji,
    required this.value,
    required this.label,
    required this.color,
  });
  final String emoji;
  final String value;
  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      decoration: BoxDecoration(
        color: color.withOpacity(0.15),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: color.withOpacity(0.5), width: 1.5),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(emoji, style: const TextStyle(fontSize: 22)),
          const SizedBox(width: 10),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                value,
                style: TextStyle(
                  color: color,
                  fontSize: 24,
                  fontWeight: FontWeight.w900,
                  height: 1.0,
                ),
              ),
              Text(
                label,
                style: TextStyle(
                  color: color.withOpacity(0.85),
                  fontSize: 10,
                  fontWeight: FontWeight.w700,
                  letterSpacing: 0.5,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _PlayerResultRow extends StatelessWidget {
  const _PlayerResultRow({
    required this.username,
    required this.avatarId,
    required this.correct,
    required this.score,
    this.shieldBroke = false,
  });
  final String username;
  final String avatarId;
  final bool correct;
  final int score;

  /// Bu tur kalkanıyla kurtuldu → satırda küçük kırık-kalkan rozeti.
  final bool shieldBroke;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: correct
            ? AppTheme.success.withOpacity(0.08)
            : AppTheme.danger.withOpacity(0.06),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(
            color: correct
                ? AppTheme.success.withOpacity(0.2)
                : AppTheme.danger.withOpacity(0.15)),
      ),
      child: Row(
        children: [
          PlayerAvatar(avatarId: avatarId, username: username, size: 32),
          const SizedBox(width: 10),
          Expanded(
              child: Text(username,
                  style: const TextStyle(
                      fontWeight: FontWeight.w600, fontSize: 13))),
          // Kalkanıyla kurtuldu: yanlış ama elenmedi — kırık-kalkan rozeti.
          if (shieldBroke) ...[
            const Text('🛡️💥', style: TextStyle(fontSize: 13)),
            const SizedBox(width: 6),
          ],
          Icon(correct ? Icons.check_circle : Icons.cancel,
              color: correct ? AppTheme.success : AppTheme.danger, size: 18),
          const SizedBox(width: 8),
          if (correct) _ScoreBadge(score: score),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// _ShieldBrokenBanner — 🛡️ kalkan kırıldı uyarısı (sallanma + pop animasyonu)
// ---------------------------------------------------------------------------

class _ShieldBrokenBanner extends StatelessWidget {
  const _ShieldBrokenBanner();

  @override
  Widget build(BuildContext context) {
    // Tek seferlik pop + sallanma: ölçek 0.6→1.0 (elastik) + yatay titreşim.
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0.0, end: 1.0),
      duration: const Duration(milliseconds: 700),
      curve: Curves.easeOut,
      builder: (_, t, child) {
        final shake = math.sin(t * math.pi * 6) * 6 * (1 - t);
        return Transform.translate(
          offset: Offset(shake, 0),
          child: Transform.scale(
            scale: 0.6 + 0.4 * Curves.elasticOut.transform(t),
            child: child,
          ),
        );
      },
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 24),
        padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 10),
        decoration: BoxDecoration(
          color: AppTheme.accent.withOpacity(0.16),
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: AppTheme.accent, width: 2),
          boxShadow: [
            BoxShadow(
              color: AppTheme.accent.withOpacity(0.45),
              blurRadius: 18,
              spreadRadius: 1,
            ),
          ],
        ),
        // Bedel bilgisi reveal anında NETLEŞMEZ (tahsil mi hediye mi maç
        // sonunda belli olur) — burada nominal bedel (50 altın) duyurulur,
        // kesin sonuç sonuç ekranındaki kalkan bedeli satırında gösterilir.
        child: const Text(
          '🛡️ Kalkanın kırıldı — bir hakkın daha yok! (50 altın)',
          textAlign: TextAlign.center,
          style: TextStyle(
            color: AppTheme.accent,
            fontSize: 15,
            fontWeight: FontWeight.w900,
            letterSpacing: 0.3,
          ),
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// _GhostResultChip — 👻 hayalet cevabın hafif (yarı saydam) geri bildirimi
// ---------------------------------------------------------------------------

class _GhostResultChip extends StatelessWidget {
  const _GhostResultChip({required this.correct});
  final bool correct;

  @override
  Widget build(BuildContext context) {
    final color = correct ? AppTheme.success : AppTheme.danger;
    // Yarı saydam: normal oyuncu deneyimiyle karışmasın; skor değişmez,
    // sadece "bilseydin/bilemedin" hissi + altın hatırlatması.
    return Opacity(
      opacity: 0.75,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
        decoration: BoxDecoration(
          color: color.withOpacity(0.14),
          borderRadius: BorderRadius.circular(999),
          border: Border.all(color: color.withOpacity(0.5)),
        ),
        child: Text(
          correct ? '👻 Hayalet cevabın DOĞRU — +5 altın!' : '👻 Hayalet cevabın yanlış',
          style: TextStyle(
            color: color,
            fontSize: 12,
            fontWeight: FontWeight.w700,
          ),
        ),
      ),
    );
  }
}

class _ScoreBadge extends StatelessWidget {
  const _ScoreBadge({required this.score});
  final int score;

  @override
  Widget build(BuildContext context) {
    return TweenAnimationBuilder<int>(
      tween: IntTween(begin: 0, end: score),
      duration: const Duration(milliseconds: 600),
      builder: (_, v, __) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
        decoration: BoxDecoration(
          color: AppTheme.accent.withOpacity(0.2),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Text('+$v',
            style: const TextStyle(
                color: AppTheme.accent,
                fontWeight: FontWeight.w700,
                fontSize: 12)),
      ),
    );
  }
}
