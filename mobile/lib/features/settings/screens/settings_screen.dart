import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:quizroyale/core/providers/settings_provider.dart';
import 'package:quizroyale/core/theme/app_theme.dart';
import 'package:quizroyale/shared/widgets/bilada_ui.dart';

class SettingsScreen extends ConsumerWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final settings = ref.watch(settingsProvider);
    final notifier = ref.read(settingsProvider.notifier);

    return Scaffold(
      body: Stack(
        children: [
          const Positioned.fill(child: BiladaBackground(showFloaters: false)),
          SafeArea(
            child: Column(
              children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(8, 8, 20, 8),
                  child: Row(
                    children: [
                      IconButton(
                        icon: const Icon(Icons.arrow_back_rounded, color: AppTheme.cOnSurface),
                        onPressed: () => context.pop(),
                      ),
                      const SizedBox(width: 4),
                      Text('Ayarlar', style: BiladaText.headline(size: 24)),
                    ],
                  ),
                ),
                Expanded(
                  child: ListView(
                    padding: const EdgeInsets.fromLTRB(20, 0, 20, 32),
                    children: [
                      _header('SES VE TİTREŞİM'),
                      _toggle(Icons.volume_up_outlined, 'Ses Efektleri', settings.soundEnabled, notifier.setSoundEnabled),
                      _toggle(Icons.music_note_outlined, 'Arka Plan Müziği', settings.musicEnabled, notifier.setMusicEnabled),
                      _toggle(Icons.vibration_rounded, 'Titreşim (Haptic)', settings.hapticEnabled, notifier.setHapticEnabled),
                      _header('BİLDİRİMLER'),
                      _toggle(Icons.notifications_outlined, 'Oyun Bildirimleri', settings.notificationsEnabled, notifier.setNotificationsEnabled),
                      _toggle(Icons.person_add_alt_1_outlined, 'Arkadaşlık İstekleri', settings.friendRequestNotifs, notifier.setFriendRequestNotifs),
                      _header('GİZLİLİK'),
                      _toggle(Icons.explore_outlined, 'Profil Keşfine İzin Ver', settings.discoverable, notifier.setDiscoverable),
                      _header('HAKKINDA'),
                      _info(Icons.info_outline_rounded, 'Versiyon', '1.0.0 (build 1)'),
                      _link(Icons.description_outlined, 'Kullanım Koşulları',
                          () => context.push('/legal/terms')),
                      _link(Icons.privacy_tip_outlined, 'Gizlilik Politikası',
                          () => context.push('/legal/privacy')),
                      _link(Icons.bug_report_outlined, 'Hata Bildir',
                          () => _showReportDialog(context)),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _header(String label) => Padding(
        padding: const EdgeInsets.fromLTRB(4, 24, 4, 10),
        child: Text(label, style: BiladaText.label(color: AppTheme.cPrimary)),
      );

  Widget _toggle(IconData icon, String label, bool value, ValueChanged<bool> onChanged) => Padding(
        padding: const EdgeInsets.only(bottom: 10),
        child: GlassCard(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
          child: Row(
            children: [
              Icon(icon, color: AppTheme.cOnSurfaceVariant, size: 22),
              const SizedBox(width: 14),
              Expanded(child: Text(label, style: BiladaText.body(size: 15))),
              Switch(
                value: value,
                onChanged: onChanged,
                activeThumbColor: AppTheme.cPrimary,
                activeTrackColor: AppTheme.cPrimaryContainer,
              ),
            ],
          ),
        ),
      );

  Widget _info(IconData icon, String label, String value) => Padding(
        padding: const EdgeInsets.only(bottom: 10),
        child: GlassCard(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
          child: Row(
            children: [
              Icon(icon, color: AppTheme.cOnSurfaceVariant, size: 22),
              const SizedBox(width: 14),
              Expanded(child: Text(label, style: BiladaText.body(size: 15))),
              Text(value, style: BiladaText.label(color: AppTheme.cOutline, size: 12)),
            ],
          ),
        ),
      );

  Widget _link(IconData icon, String label, VoidCallback onTap) => Padding(
        padding: const EdgeInsets.only(bottom: 10),
        child: GlassCard(
          onTap: onTap,
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
          child: Row(
            children: [
              Icon(icon, color: AppTheme.cOnSurfaceVariant, size: 22),
              const SizedBox(width: 14),
              Expanded(child: Text(label, style: BiladaText.body(size: 15))),
              const Icon(Icons.chevron_right_rounded, color: AppTheme.cOutline, size: 20),
            ],
          ),
        ),
      );

  void _showReportDialog(BuildContext context) {
    showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Hata Bildir'),
        content: const Text(
          'Karşılaştığınız hata veya önerilerinizi şu adrese iletebilirsiniz:\n\n'
          'destek@bilyadadus.com',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: const Text('Tamam'),
          ),
        ],
      ),
    );
  }
}
