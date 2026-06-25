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
}

class SoundService {
  static final SoundService _i = SoundService._();
  factory SoundService() => _i;
  SoundService._();

  bool _soundEnabled = true;
  bool _musicEnabled = true;
  final AudioPlayer _sfxPlayer = AudioPlayer();
  final AudioPlayer _musicPlayer = AudioPlayer();

  static const _assetMap = {
    GameSound.correct: 'audio/correct.mp3',
    GameSound.wrong: 'audio/wrong.mp3',
    GameSound.countdown: 'audio/countdown.mp3',
    GameSound.elimination: 'audio/elimination.mp3',
    GameSound.win: 'audio/win.mp3',
    GameSound.lobbyJoin: 'audio/lobby_join.mp3',
    GameSound.roundStart: 'audio/round_start.mp3',
  };

  static const String _prefKeySound = 'sound_enabled';
  static const String _prefKeyMusic = 'music_enabled';

  bool get soundEnabled => _soundEnabled;
  bool get musicEnabled => _musicEnabled;

  Future<void> init() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      _soundEnabled = prefs.getBool(_prefKeySound) ?? true;
      _musicEnabled = prefs.getBool(_prefKeyMusic) ?? true;
      await _sfxPlayer.setReleaseMode(ReleaseMode.stop);
      await _musicPlayer.setReleaseMode(ReleaseMode.loop);
    } catch (_) {}
  }

  Future<void> playSound(GameSound sound) async {
    if (!_soundEnabled) return;
    final assetPath = _assetMap[sound];
    if (assetPath == null) return;
    try {
      await _sfxPlayer.stop();
      await _sfxPlayer.play(AssetSource(assetPath));
    } catch (_) {}
  }

  Future<void> startLobbyMusic() async {
    if (!_musicEnabled) return;
    try {
      await _musicPlayer.stop();
      await _musicPlayer.setReleaseMode(ReleaseMode.loop);
      await _musicPlayer.play(AssetSource('audio/lobby_music.mp3'));
    } catch (_) {}
  }

  Future<void> startGameMusic() async {
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
    } catch (_) {}
  }
}
