import 'package:audioplayers/audioplayers.dart';
import 'package:shared_preferences/shared_preferences.dart';

enum GameSound {
  correct,
  wrong,
  countdown,
  elimination,
  win,
  lobbyJoin,
  roundStart,

  /// Şık seçme / buton kilitleme tıkı.
  click,

  /// Kalkan kırılma efekti — UI tetiği sonraki dalgada bağlanacak, ses hazır.
  shieldBreak,

  /// 👏 Alkış — kazananın sonuç ekranında fanfarın ÜSTÜNE bindirilir.
  applause,
}

class SoundService {
  static final SoundService _i = SoundService._();
  factory SoundService() => _i;
  SoundService._();

  bool _soundEnabled = true;
  bool _musicEnabled = true;
  final AudioPlayer _sfxPlayer = AudioPlayer();
  final AudioPlayer _musicPlayer = AudioPlayer();

  // Alkış için AYRI player: playSound() her çağrıda _sfxPlayer'ı durdurur;
  // alkışın fanfarı (GameSound.win) kesmeden üstüne binebilmesi için kendi
  // kanalından çalması gerekir.
  final AudioPlayer _applausePlayer = AudioPlayer();

  // Sentezlenmiş WAV varlıkları (assets/audio/ altında, pubspec'e kayıtlı).
  static const _assetMap = {
    GameSound.correct: 'audio/correct.wav',
    GameSound.wrong: 'audio/wrong.wav',
    GameSound.countdown: 'audio/tick.wav',
    GameSound.elimination: 'audio/fall.wav',
    GameSound.win: 'audio/champion.wav',
    GameSound.lobbyJoin: 'audio/click.wav',
    GameSound.roundStart: 'audio/round_start.wav',
    GameSound.click: 'audio/click.wav',
    GameSound.shieldBreak: 'audio/shield_break.wav',
    GameSound.applause: 'audio/applause.wav',
  };

  static const String _prefKeySound = 'sound_enabled';
  static const String _prefKeyMusic = 'music_enabled';

  bool get soundEnabled => _soundEnabled;
  bool get musicEnabled => _musicEnabled;

  /// init() bir kez çalıştı mı? İlk playSound çağrısında tembel başlatılır;
  /// böylece uygulama açılışına ek yük binmez ve init unutulsa bile ayarlar
  /// (ses aç/kapa) her zaman prefs'ten okunur.
  bool _initialized = false;
  Future<void>? _initFuture;

  Future<void> init() async {
    if (_initialized) return;
    // Eşzamanlı çağrılar aynı init'i beklesin (çifte başlatma olmasın).
    _initFuture ??= _doInit();
    await _initFuture;
  }

  Future<void> _doInit() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      _soundEnabled = prefs.getBool(_prefKeySound) ?? true;
      _musicEnabled = prefs.getBool(_prefKeyMusic) ?? true;
      await _sfxPlayer.setReleaseMode(ReleaseMode.stop);
      await _musicPlayer.setReleaseMode(ReleaseMode.loop);
    } catch (_) {}
    // iOS: telefonun SESSİZ ANAHTARINA SAYGI göster (kullanıcı isteği):
    // telefon sessizdeyken oyun da otomatik sessiz olur, ses açıksa çalar.
    // 'ambient' kategorisi tam bunu yapar; mixWithOthers ile kullanıcının
    // kendi müziğini (Spotify vb.) kesmeyiz.
    try {
      await AudioPlayer.global.setAudioContext(AudioContext(
        iOS: AudioContextIOS(
          category: AVAudioSessionCategory.ambient,
          options: const {AVAudioSessionOptions.mixWithOthers},
        ),
        android: const AudioContextAndroid(
          contentType: AndroidContentType.sonification,
          usageType: AndroidUsageType.game,
          // Kısa SFX'ler için odak çalma — diğer uygulamaların sesini kısmayız.
          audioFocus: AndroidAudioFocus.none,
        ),
      ));
    } catch (_) {}
    // Kısa efektlerde düşük gecikme (Android'de SoundPool) — reveal anındaki
    // ses, görselle aynı karede hissedilsin.
    try {
      await _sfxPlayer.setPlayerMode(PlayerMode.lowLatency);
    } catch (_) {}
    _initialized = true;
  }

  Future<void> playSound(GameSound sound) async {
    await init(); // tembel başlatma — ilk çağrıda ayarları/oturumu kurar
    if (!_soundEnabled) return;
    final assetPath = _assetMap[sound];
    if (assetPath == null) return;
    try {
      await _sfxPlayer.stop();
      await _sfxPlayer.play(AssetSource(assetPath));
    } catch (_) {}
  }

  /// 👏 Alkışı fanfarın ÜSTÜNE bindirerek çal (kazananın sonuç ekranı).
  /// _sfxPlayer'a dokunmaz → çalan şampiyon fanfarı kesilmez.
  Future<void> playApplause() async {
    await init();
    if (!_soundEnabled) return;
    try {
      await _applausePlayer.stop();
      await _applausePlayer.play(AssetSource(_assetMap[GameSound.applause]!));
    } catch (_) {}
  }

  Future<void> startLobbyMusic() async {
    await init();
    if (!_musicEnabled) return;
    try {
      await _musicPlayer.stop();
      await _musicPlayer.setReleaseMode(ReleaseMode.loop);
      await _musicPlayer.play(AssetSource('audio/lobby_music.mp3'));
    } catch (_) {}
  }

  Future<void> startGameMusic() async {
    await init();
    if (!_musicEnabled) return;
    try {
      await _musicPlayer.stop();
      await _musicPlayer.setReleaseMode(ReleaseMode.loop);
      await _musicPlayer.play(AssetSource('audio/game_music.mp3'));
    } catch (_) {}
  }

  Future<void> stopMusic() async {
    try {
      await _musicPlayer.stop();
    } catch (_) {}
  }

  Future<void> setSoundEnabled(bool value) async {
    _soundEnabled = value;
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setBool(_prefKeySound, value);
      if (!value) {
        await _sfxPlayer.stop();
        await _applausePlayer.stop();
      }
    } catch (_) {}
  }

  Future<void> setMusicEnabled(bool value) async {
    _musicEnabled = value;
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setBool(_prefKeyMusic, value);
      if (!value) {
        await _musicPlayer.stop();
      }
    } catch (_) {}
  }

  Future<void> dispose() async {
    try {
      await _sfxPlayer.dispose();
      await _musicPlayer.dispose();
      await _applausePlayer.dispose();
    } catch (_) {}
  }
}
