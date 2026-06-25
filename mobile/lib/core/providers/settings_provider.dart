import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../services/sound_service.dart';
import '../services/haptic_service.dart';

class SettingsState {
  final bool soundEnabled;
  final bool musicEnabled;
  final bool hapticEnabled;
  final bool notificationsEnabled;
  final bool friendRequestNotifs;
  final bool discoverable;
  final bool profileDiscovery;

  const SettingsState({
    this.soundEnabled = true,
    this.musicEnabled = true,
    this.hapticEnabled = true,
    this.notificationsEnabled = true,
    this.friendRequestNotifs = true,
    this.discoverable = true,
    this.profileDiscovery = true,
  });

  SettingsState copyWith({
    bool? soundEnabled,
    bool? musicEnabled,
    bool? hapticEnabled,
    bool? notificationsEnabled,
    bool? friendRequestNotifs,
    bool? discoverable,
    bool? profileDiscovery,
  }) {
    return SettingsState(
      soundEnabled: soundEnabled ?? this.soundEnabled,
      musicEnabled: musicEnabled ?? this.musicEnabled,
      hapticEnabled: hapticEnabled ?? this.hapticEnabled,
      notificationsEnabled: notificationsEnabled ?? this.notificationsEnabled,
      friendRequestNotifs: friendRequestNotifs ?? this.friendRequestNotifs,
      discoverable: discoverable ?? this.discoverable,
      profileDiscovery: profileDiscovery ?? this.profileDiscovery,
    );
  }
}

class SettingsNotifier extends StateNotifier<SettingsState> {
  SettingsNotifier() : super(const SettingsState());

  static const _keySound = 'sound_enabled';
  static const _keyMusic = 'music_enabled';
  static const _keyHaptic = 'haptic_enabled';
  static const _keyNotifications = 'notifications_enabled';
  static const _keyFriendRequestNotifs = 'friend_request_notifs';
  static const _keyDiscoverable = 'discoverable';
  static const _keyProfileDiscovery = 'profile_discovery';

  Future<void> init() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      state = SettingsState(
        soundEnabled: prefs.getBool(_keySound) ?? true,
        musicEnabled: prefs.getBool(_keyMusic) ?? true,
        hapticEnabled: prefs.getBool(_keyHaptic) ?? true,
        notificationsEnabled: prefs.getBool(_keyNotifications) ?? true,
        profileDiscovery: prefs.getBool(_keyProfileDiscovery) ?? true,
      );
    } catch (_) {}
  }

  Future<void> toggleSound() async {
    await setSoundEnabled(!state.soundEnabled);
  }

  Future<void> setSoundEnabled(bool value) async {
    state = state.copyWith(soundEnabled: value);
    await SoundService().setSoundEnabled(value);
    await _savePrefs(_keySound, value);
  }

  Future<void> toggleMusic() async {
    await setMusicEnabled(!state.musicEnabled);
  }

  Future<void> setMusicEnabled(bool value) async {
    state = state.copyWith(musicEnabled: value);
    await SoundService().setMusicEnabled(value);
    await _savePrefs(_keyMusic, value);
  }

  Future<void> toggleHaptic() async {
    await setHapticEnabled(!state.hapticEnabled);
  }

  Future<void> setHapticEnabled(bool value) async {
    state = state.copyWith(hapticEnabled: value);
    await HapticService().setEnabled(value);
    await _savePrefs(_keyHaptic, value);
  }

  Future<void> toggleNotifications() async {
    await setNotificationsEnabled(!state.notificationsEnabled);
  }

  Future<void> setNotificationsEnabled(bool value) async {
    state = state.copyWith(notificationsEnabled: value);
    await _savePrefs(_keyNotifications, value);
  }

  Future<void> setFriendRequestNotifs(bool value) async {
    state = state.copyWith(friendRequestNotifs: value);
    await _savePrefs(_keyFriendRequestNotifs, value);
  }

  Future<void> setDiscoverable(bool value) async {
    state = state.copyWith(discoverable: value);
    await _savePrefs(_keyDiscoverable, value);
  }

  Future<void> toggleProfileDiscovery() async {
    final newValue = !state.profileDiscovery;
    state = state.copyWith(profileDiscovery: newValue);
    await _savePrefs(_keyProfileDiscovery, newValue);
  }

  Future<void> _savePrefs(String key, bool value) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setBool(key, value);
    } catch (_) {}
  }
}

final settingsProvider =
    StateNotifierProvider<SettingsNotifier, SettingsState>((ref) {
  final notifier = SettingsNotifier();
  notifier.init();
  return notifier;
});
