import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:quizroyale/core/constants/app_constants.dart';
import 'package:quizroyale/core/network/api_client.dart';
import 'package:quizroyale/core/network/ws_client.dart';

/// %50 JOKER bedeli — backend ws/game.py ile BİREBİR aynı tutulmalı (50 altın).
/// Tüm maçta bir kez kullanılabilir; 4 şıklı çoktan-seçmeli soruda 2 yanlış
/// şıkkı eler. (app_constants çekirdek dosyası bu ajanın kapsamı dışında
/// olduğundan sabit burada, oyun katmanında tanımlıdır.)
const int kJokerCost = 50;

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

class GameState {
  const GameState({
    this.gameId = '',
    this.status = 'waiting',
    this.currentRound = 0,
    this.totalRounds = 5,
    this.currentQuestion,
    this.timeRemaining = 0,
    this.totalTime = 8,
    this.selectedAnswer,
    this.answerLocked = false,
    this.roundResult,
    this.eliminatedThisRound = const [],
    this.allPlayers = const [],
    this.isSpectator = false,
    this.gameResult,
    this.myScore = 0,
    this.myRound = 0,
    this.emojiOverlay,
    this.quickMsg,
    this.betOn,
    this.jokerUsed = false,
    this.jokerPending = false,
    this.hiddenOptions = const [],
    this.coins,
    this.jokerError,
    this.jokerErrorTick = 0,
    this.isTournament = false,
  });

  final String gameId;

  /// 'waiting' | 'round_active' | 'round_revealing' | 'between_rounds'
  /// | 'spectator' | 'finished'
  final String status;

  final int currentRound;
  final int totalRounds;

  /// Full question object from backend.
  final Map<String, dynamic>? currentQuestion;

  final double timeRemaining;
  final double totalTime;

  /// null = not answered, int index for MC/TF, encoded double-as-int for slider
  final int? selectedAnswer;

  /// Slider "kilitle" state
  final bool answerLocked;

  /// Payload from round_reveal message
  final Map<String, dynamic>? roundResult;

  final List<String> eliminatedThisRound;

  /// Each player: {username, avatar_id, is_alive, score}
  final List<Map<String, dynamic>> allPlayers;

  final bool isSpectator;

  /// Payload from game_finished message
  final Map<String, dynamic>? gameResult;

  final int myScore;

  /// Last round the local player survived
  final int myRound;

  /// Emoji string shown in overlay, null when hidden
  final String? emojiOverlay;

  /// 💬 Hazır mesaj baloncuğu: {username, text}. 2sn sonra otomatik silinir.
  /// Metin SUNUCUDAN gelir (sabit izin listesinden çözülmüş) — serbest metin yok.
  final Map<String, String>? quickMsg;

  /// Şampiyon bahsi (🎯): elenmişken bahis koyulan oyuncunun username'i.
  /// null = henüz bahis yok. Bir kez set edilince değiştirilemez (kilitli).
  final String? betOn;

  // ── %50 JOKER (½) ──────────────────────────────────────────────────────
  /// Bu MAÇTA joker kullanıldı mı? Tek seferlik — yeni maçta (yeni notifier)
  /// otomatik false'a döner.
  final bool jokerUsed;

  /// Joker gönderildi, sunucu yanıtı (joker_result/joker_error) bekleniyor.
  /// Butonu anında pasifleştirmek için kullanılır.
  final bool jokerPending;

  /// Joker'in ELEDİĞİ şık indeksleri (2 yanlış şık). Sadece kullanıldığı turda
  /// doludur; her yeni turda temizlenir. Şıklar görsel olarak soluk+tıklanamaz.
  final List<int> hiddenOptions;

  /// joker_result ile gelen GÜNCEL altın bakiyesi. null = henüz güncellenmedi
  /// (o zaman authProvider bakiyesi kullanılır).
  final int? coins;

  /// joker_error ile gelen kısa sebep (toast metni). Tetik: [jokerErrorTick].
  final String? jokerError;

  /// Her joker_error'da artan sayaç — ekran aynı hatayı tekrar gösterebilsin
  /// diye (aynı metin arka arkaya gelse bile listener yeni olayı yakalar).
  final int jokerErrorTick;

  /// Zor Mod (turnuva) maçı mı? game_started'daki is_tournament bayrağından
  /// (reconnect'te game_state snapshot'ının prize_pool>0 değerinden) beslenir.
  /// Zor Mod'da şampiyon bahsi ve hayalet altını VERİLMEZ → bahis kartı gibi
  /// ödül vaat eden UI bu bayrakla gizlenir.
  final bool isTournament;

  GameState copyWith({
    String? gameId,
    String? status,
    int? currentRound,
    int? totalRounds,
    Map<String, dynamic>? currentQuestion,
    bool clearQuestion = false,
    double? timeRemaining,
    double? totalTime,
    int? selectedAnswer,
    bool clearSelectedAnswer = false,
    bool? answerLocked,
    Map<String, dynamic>? roundResult,
    List<String>? eliminatedThisRound,
    List<Map<String, dynamic>>? allPlayers,
    bool? isSpectator,
    Map<String, dynamic>? gameResult,
    int? myScore,
    int? myRound,
    String? emojiOverlay,
    bool clearEmoji = false,
    Map<String, String>? quickMsg,
    bool clearQuickMsg = false,
    String? betOn,
    bool? jokerUsed,
    bool? jokerPending,
    List<int>? hiddenOptions,
    int? coins,
    String? jokerError,
    int? jokerErrorTick,
    bool? isTournament,
  }) {
    return GameState(
      gameId: gameId ?? this.gameId,
      status: status ?? this.status,
      currentRound: currentRound ?? this.currentRound,
      totalRounds: totalRounds ?? this.totalRounds,
      currentQuestion: clearQuestion ? null : (currentQuestion ?? this.currentQuestion),
      timeRemaining: timeRemaining ?? this.timeRemaining,
      totalTime: totalTime ?? this.totalTime,
      selectedAnswer: clearSelectedAnswer ? null : (selectedAnswer ?? this.selectedAnswer),
      answerLocked: answerLocked ?? this.answerLocked,
      roundResult: roundResult ?? this.roundResult,
      eliminatedThisRound: eliminatedThisRound ?? this.eliminatedThisRound,
      allPlayers: allPlayers ?? this.allPlayers,
      isSpectator: isSpectator ?? this.isSpectator,
      gameResult: gameResult ?? this.gameResult,
      myScore: myScore ?? this.myScore,
      myRound: myRound ?? this.myRound,
      emojiOverlay: clearEmoji ? null : (emojiOverlay ?? this.emojiOverlay),
      quickMsg: clearQuickMsg ? null : (quickMsg ?? this.quickMsg),
      betOn: betOn ?? this.betOn,
      jokerUsed: jokerUsed ?? this.jokerUsed,
      jokerPending: jokerPending ?? this.jokerPending,
      hiddenOptions: hiddenOptions ?? this.hiddenOptions,
      coins: coins ?? this.coins,
      jokerError: jokerError ?? this.jokerError,
      jokerErrorTick: jokerErrorTick ?? this.jokerErrorTick,
      isTournament: isTournament ?? this.isTournament,
    );
  }
}

// ---------------------------------------------------------------------------
// Notifier
// ---------------------------------------------------------------------------

class GameNotifier extends StateNotifier<GameState> {
  GameNotifier(String gameId)
      : super(GameState(gameId: gameId)) {
    // KRİTİK: Oyun, lobi ile AYNI tekil WsClient'ı PAYLAŞMAZ. Lobi
    // `WsClient.instance` kullanırken oyun KENDİ bağımsız örneğini açar.
    // Böylece lobi→oyun geçişinde lobi'nin canlı dinleyicisi/reconnect'i
    // oyun kanalını bozamaz; oyunun `send()`'i her zaman OYUN soketine gider.
    // (Önceki bug: cevap lobi'nin bozduğu/kapattığı kanala gidip kayboluyordu.)
    _wsClient = WsClient();
  }

  late final WsClient _wsClient;
  StreamSubscription<Map<String, dynamic>>? _sub;
  Timer? _countdownTimer;
  Timer? _emojiTimer;
  Timer? _quickMsgTimer;

  /// Oyun bir kez 'finished' olduğunda terminal durumdur; geç gelen
  /// round_reveal / round_transition / game_state / spectator_mode mesajları
  /// bu durumu EZEMEZ. Aksi halde status 'finished'ten düşer ve sonuç ekranı
  /// navigasyonu hiç tetiklenmez ("donma").
  bool _gameOver = false;

  // ------------------------------------------------------------------
  // Public API
  // ------------------------------------------------------------------

  /// Opens WebSocket connection to the game room.
  Future<void> connectGame(String gameId) async {
    // WS açmadan önce TAZE token sağla (süresi dolmuşsa refresh ile yenilenir).
    final token = await ApiClient.instance.ensureValidAccessToken();
    final url = '${AppConstants.wsBaseUrl}/ws/game/$gameId?token=$token';

    await _wsClient.connect(url);

    _sub?.cancel();
    _sub = _wsClient.messages.listen(
      _handleMessage,
      onError: (_) {},
      cancelOnError: false,
    );

    state = state.copyWith(gameId: gameId, status: 'waiting');
  }

  /// Çoktan seçmeli / doğru-yanlış / görsel / karşılaştırma cevabı.
  ///
  /// ŞIK İŞARETLE = ANINDA GÖNDER. Tek seferlik.
  ///
  /// ÖNEMLİ (web/dart2js): Eskiden tek bir `submitAnswer(dynamic)` vardı ve
  /// şık (int) ile tahmin önizlemesi (double) `answer is double` ile ayrılırdı.
  /// dart2js'te `0 is double` TRUE dönebildiğinden şık seçimi yanlışlıkla
  /// "slider önizlemesi" dalına düşüp HİÇ gönderilmiyordu → "doğru bildim ama
  /// elendin" hatası. Artık çağrı yolları AYRI; tür belirsizliği imkânsız.
  void submitChoice(int index) {
    if (state.answerLocked) return;
    // Tek seferlik: zaten bir şık seçildiyse tekrar gönderme.
    if (state.selectedAnswer != null) return;
    _wsClient.send({
      'type': 'submit_answer',
      'answer': index,
      'time_remaining': state.timeRemaining,
    });
    state = state.copyWith(selectedAnswer: index);
  }

  /// Tahmin (slider) sürüklenirken YEREL önizleme. Backend'e GÖNDERMEZ;
  /// gönderim `lockSlider()` (CEVABI GÖNDER) ile yapılır.
  /// selectedAnswer = değer*100 (int olarak saklanır).
  void previewEstimate(double value) {
    if (state.answerLocked) return;
    state = state.copyWith(selectedAnswer: (value * 100).round());
  }

  /// Slider/tahmin cevabını GÖNDER + kilitle (CEVABI GÖNDER butonu).
  void lockSlider() {
    if (state.answerLocked) return;
    final sel = state.selectedAnswer;
    final double value = sel is int ? sel / 100.0 : 0.0;
    _wsClient.send({
      'type': 'submit_answer',
      'answer': value,
      'time_remaining': state.timeRemaining,
    });
    _wsClient.send({'type': 'lock_answer'});
    state = state.copyWith(answerLocked: true);
  }

  /// Send an emoji reaction to all players.
  void sendEmoji(String emoji) {
    _wsClient.send({'type': 'emoji', 'emoji': emoji});
  }

  /// 💬 Hazır mesaj gönder — YALNIZCA sabit id gönderilir (serbest metin yok);
  /// metni sunucu kendi izin listesinden çözüp herkese yayınlar.
  void sendQuickMsg(String msgId) {
    if (!AppConstants.quickMessages.containsKey(msgId)) return;
    _wsClient.send({'type': 'quick_msg', 'msg_id': msgId});
  }

  /// Şampiyon bahsi (🎯): elenmişken hayatta kalan bir oyuncuya TEK SEFERLİK
  /// bahis koy. İyimser kilitlenir; backend 'bet_placed' ile doğrular
  /// (geçersizse 'error' döner ama bahis zaten sunucuda kaydedilmemiştir).
  void placeBet(String username) {
    if (state.betOn != null) return; // tek seferlik — değiştirilemez
    if (!state.isSpectator) return; // sadece elenmiş oyuncu
    _wsClient.send({'type': 'place_bet', 'username': username});
    state = state.copyWith(betOn: username);
  }

  /// %50 JOKER (½): tüm maçta bir kez, 4 şıklı çoktan-seçmeli soruda 2 yanlış
  /// şıkkı eler (50 altın). submit_answer ile AYNI oyun soketinden gönderilir.
  /// Sunucu `joker_result` (başarı) ya da `joker_error` (yetersiz altın / zaten
  /// kullanıldı / uygun olmayan soru) döner. Buton beklemeye alınır (jokerPending).
  void useJoker() {
    // Zaten kullanıldıysa veya yanıt bekleniyorsa çift gönderme.
    if (state.jokerUsed || state.jokerPending) return;
    _wsClient.send({
      'type': 'use_joker',
      'round_number': state.currentRound,
    });
    state = state.copyWith(jokerPending: true);
  }

  // ------------------------------------------------------------------
  // Internal – message dispatch
  // ------------------------------------------------------------------

  void _handleMessage(Map<String, dynamic> msg) {
    final type = msg['type'] as String? ?? '';

    // ── BAŞKA OYUNA AİT MESAJ FİLTRESİ ────────────────────────────────────
    // WsClient tekil + broadcast stream olduğu için, hızlı yeniden başlatmada
    // ESKİ oyunun (henüz dispose olmamış) notifier'ı YENİ oyunun mesajlarını
    // da duyabilir. Backend round_start/round_reveal/game_state/game_finished
    // mesajlarına 'game_id' ekliyor; gelen game_id bu notifier'ın
    // gameId'siyle eşleşmiyorsa mesajı YOK SAY. Aksi halde başka oyunun
    // 'game_finished'i erken/yanlış sonuç ekranı açar ("oyun patladı").
    // NOT: Artık tüm oyun yaşam-döngüsü mesajları (round_transition ve
    // spectator_mode dahil) game_id taşıyor. game_id alanı olmayan bir mesaj
    // gelirse (örn. emoji) filtre uygulanmaz — yalnızca bu oyunun
    // broadcast'inden geldiği için güvenlidir.
    final incomingGameId = msg['game_id'] as String?;
    if (incomingGameId != null &&
        state.gameId.isNotEmpty &&
        incomingGameId != state.gameId) {
      return;
    }

    // Oyun bittiyse: yalnızca tekrar gelen game_finished'i (idempotent) işle.
    // Geç gelen round_* / game_state / spectator_mode mesajları 'finished'
    // durumunu EZMESİN — aksi halde sonuç ekranına geçiş engellenir.
    if (_gameOver && type != 'game_finished') {
      return;
    }

    switch (type) {
      case 'game_started':
        // Zor Mod bayrağı maç başında gelir (is_tournament). Zor Mod'da bahis/
        // hayalet altını verilmediği için bahis kartı bu bayrakla gizlenir.
        state = state.copyWith(
          isTournament: msg['is_tournament'] == true ||
              ((msg['prize_pool'] as num?)?.toInt() ?? 0) > 0,
        );
      case 'game_state':
        _onGameState(msg);
      case 'round_start':
        _onRoundStart(msg);
      case 'round_reveal':
        _onRoundReveal(msg);
      case 'round_transition':
        _onRoundTransition(msg);
      case 'spectator_mode':
        _onSpectatorMode(msg);
      case 'bet_placed':
        _onBetPlaced(msg);
      case 'joker_result':
        _onJokerResult(msg);
      case 'joker_error':
        _onJokerError(msg);
      case 'game_finished':
        _onGameFinished(msg);
      case 'emoji':
        _onEmoji(msg);
      case 'quick_msg':
        _onQuickMsg(msg);
      case 'ws_error':
        // Permanent WS error (4001/4003/4004) — signal screen to go home
        state = state.copyWith(status: 'error');
      default:
        break;
    }
  }

  // game_state – full player list sync (can arrive any time)
  void _onGameState(Map<String, dynamic> msg) {
    final players = _parsePlayers(msg['players']);
    // Reconnect yolu: game_started kaçırıldıysa Zor Mod bayrağını snapshot'ın
    // prize_pool'undan türet (yalnızca turnuvada > 0). Bir kez true olunca kalır.
    final snapshotPool = (msg['prize_pool'] as num?)?.toInt() ?? 0;
    state = state.copyWith(
      allPlayers: players,
      isTournament: state.isTournament || snapshotPool > 0,
    );
  }

  // round_start – new question arrives, start countdown
  void _onRoundStart(Map<String, dynamic> msg) {
    _stopTimer();

    final question = msg['question'] as Map<String, dynamic>? ?? {};
    final round = (msg['round'] as num?)?.toInt() ?? state.currentRound + 1;
    final timeSec = (msg['time_seconds'] as num?)?.toDouble()
        ?? (question['sure_saniye'] as num?)?.toDouble()
        ?? 8.0;
    final players = _parsePlayers(msg['players']);

    state = state.copyWith(
      status: 'round_active',
      currentRound: round,
      currentQuestion: question,
      timeRemaining: timeSec,
      totalTime: timeSec,
      clearSelectedAnswer: true,
      answerLocked: false,
      eliminatedThisRound: [],
      allPlayers: players,
      // Joker'in eledi̇ği şıklar yalnızca kullanıldığı tura aittir; yeni turda
      // temizlenir (jokerUsed ise buton zaten görünmez — tek seferlik). Bekleme
      // bayrağı da güvenlik için sıfırlanır.
      hiddenOptions: const [],
      jokerPending: false,
    );

    _startTimer();
  }

  // round_reveal – stop timer, show results
  void _onRoundReveal(Map<String, dynamic> msg) {
    _stopTimer();

    final eliminated = (msg['eliminated'] as List<dynamic>? ?? [])
        .map((e) => e.toString())
        .toList();

    final players = _parsePlayers(msg['players']);
    final myScore = (msg['my_score'] as num?)?.toInt() ?? state.myScore;
    final myRound = (msg['my_round'] as num?)?.toInt() ?? state.myRound;

    state = state.copyWith(
      status: 'round_revealing',
      roundResult: msg,
      eliminatedThisRound: eliminated,
      allPlayers: players,
      myScore: myScore,
      myRound: myRound,
    );
  }

  // round_transition – brief "TUR X" overlay between rounds
  void _onRoundTransition(Map<String, dynamic> msg) {
    final players = _parsePlayers(msg['players']);
    state = state.copyWith(
      status: 'between_rounds',
      clearQuestion: true,
      allPlayers: players.isNotEmpty ? players : null,
    );
  }

  // spectator_mode – yerel oyuncu elendi. Eve GÖNDERME; izleyici olarak oyunda
  // kal ki oyun bitince herkes gibi şampiyon/sonuç ekranını görsün.
  void _onSpectatorMode(Map<String, dynamic> msg) {
    final players = _parsePlayers(msg['players']);
    state = state.copyWith(
      isSpectator: true,
      allPlayers: players.isNotEmpty ? players : null,
    );
  }

  // bet_placed – sunucu şampiyon bahsini onayladı; kilitli hedefi senkronla.
  void _onBetPlaced(Map<String, dynamic> msg) {
    final betOn = msg['bet_on'] as String?;
    if (betOn != null && betOn.isNotEmpty) {
      state = state.copyWith(betOn: betOn);
    }
  }

  // joker_result – 2 yanlış şık elendi: hidden_options'ı görsel devre dışı
  // bırak, jokerUsed=true yap, altın bakiyesini güncelle.
  void _onJokerResult(Map<String, dynamic> msg) {
    final hidden = (msg['hidden_options'] as List? ?? const [])
        .map((e) => (e as num).toInt())
        .toList();
    final newCoins = (msg['coins'] as num?)?.toInt();
    // Bayatlık koruması: sonuç HANGİ tura aitse yalnız o turda şık soldurulur.
    // Geç gelen (tur atlamış) bir joker_result YENİ sorunun şıklarını yanlışlıkla
    // gizlememeli. Tahsilat sunucuda yapıldı → jokerUsed/coins her durumda işlenir.
    final resultRound = (msg['round_number'] as num?)?.toInt();
    final isCurrentRound =
        resultRound == null || resultRound == state.currentRound;
    state = state.copyWith(
      jokerUsed: true,
      jokerPending: false,
      hiddenOptions: isCurrentRound ? hidden : state.hiddenOptions,
      coins: newCoins,
    );
  }

  // joker_error – joker kullanılamadı: butonu tekrar aktif et (jokerPending
  // false) ve ekranın toast göstermesi için sebep + tetik sayacını ilerlet.
  void _onJokerError(Map<String, dynamic> msg) {
    final reason = msg['reason']?.toString();
    state = state.copyWith(
      jokerPending: false,
      jokerError:
          (reason != null && reason.isNotEmpty) ? reason : 'Joker kullanılamadı',
      jokerErrorTick: state.jokerErrorTick + 1,
    );
  }

  // game_finished – terminal durum. status='finished' + gameResult set edilir;
  // _gameOver bayrağı sayesinde bir daha hiçbir mesaj bu durumu ezemez.
  void _onGameFinished(Map<String, dynamic> msg) {
    _stopTimer();
    _gameOver = true;
    state = state.copyWith(
      status: 'finished',
      gameResult: msg,
    );
  }

  // quick_msg – gönderenin adıyla 2 saniyelik baloncuk göster.
  // Güvenlik: metin İSTEMCİDE de izin listesinden doğrulanır — sunucu dışı
  // bir kaynaktan gelebilecek serbest metin asla ekrana basılmaz.
  void _onQuickMsg(Map<String, dynamic> msg) {
    final msgId = msg['msg_id'] as String?;
    final text = AppConstants.quickMessages[msgId];
    if (text == null) return; // izin listesinde olmayan id → yok say
    final username = (msg['username'] as String?) ?? 'oyuncu';
    _quickMsgTimer?.cancel();
    state = state.copyWith(quickMsg: {'username': username, 'text': text});
    _quickMsgTimer = Timer(const Duration(seconds: 2), () {
      if (mounted) state = state.copyWith(clearQuickMsg: true);
    });
  }

  // emoji – show floating overlay for 2 seconds
  void _onEmoji(Map<String, dynamic> msg) {
    final emoji = msg['emoji'] as String? ?? '👏';
    _emojiTimer?.cancel();
    state = state.copyWith(emojiOverlay: emoji);
    _emojiTimer = Timer(const Duration(seconds: 2), () {
      if (mounted) state = state.copyWith(clearEmoji: true);
    });
  }

  // ------------------------------------------------------------------
  // Countdown timer
  // ------------------------------------------------------------------

  void _startTimer() {
    _countdownTimer = Timer.periodic(const Duration(milliseconds: 100), (t) {
      if (!mounted) {
        t.cancel();
        return;
      }
      final next = state.timeRemaining - 0.1;
      if (next <= 0) {
        state = state.copyWith(timeRemaining: 0);
        t.cancel();
      } else {
        state = state.copyWith(timeRemaining: next);
      }
    });
  }

  void _stopTimer() {
    _countdownTimer?.cancel();
    _countdownTimer = null;
  }

  // ------------------------------------------------------------------
  // Helpers
  // ------------------------------------------------------------------

  List<Map<String, dynamic>> _parsePlayers(dynamic raw) {
    if (raw == null) return state.allPlayers;
    return (raw as List<dynamic>)
        .map((e) => Map<String, dynamic>.from(e as Map))
        .toList();
  }

  // ------------------------------------------------------------------
  // Dispose
  // ------------------------------------------------------------------

  @override
  void dispose() {
    _sub?.cancel();
    _stopTimer();
    _emojiTimer?.cancel();
    _quickMsgTimer?.cancel();
    // Oyun kendi WsClient örneğine sahip → ekran kapanınca soketi de kapat.
    // (Lobi'nin paylaşılan tekili DEĞİL; güvenle dispose edilir.)
    _wsClient.dispose();
    super.dispose();
  }
}

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

// autoDispose: oyun ekranı kapanınca (home/lobiye dönüş, sonuç ekranına
// geçiş) bu notifier dispose edilir → _sub iptal olur, timer'lar durur.
// Böylece eski oyunun notifier'ı broadcast stream'e abone KALMAZ; yeni
// oyun başlatıldığında eski notifier yeni mesajları duyup state'i bozmaz.
// family hâlâ korunur (her gameId için ayrı notifier). Oyun ekranı
// ref.watch(gameProvider(gameId)) ile dinlediği sürece notifier canlı
// kalır; ekran ağaçtan çıkınca dispose tetiklenir.
final gameProvider =
    StateNotifierProvider.autoDispose.family<GameNotifier, GameState, String>(
  (_, gameId) => GameNotifier(gameId),
);
