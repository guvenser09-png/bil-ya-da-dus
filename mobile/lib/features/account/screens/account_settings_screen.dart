import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:quizroyale/core/theme/app_theme.dart';
import 'package:quizroyale/features/auth/providers/auth_provider.dart';
import 'package:quizroyale/shared/widgets/bilada_ui.dart';

/// Hesap ayarları — e-posta doğrulama, şifre değiştirme ve hesap silme.
/// Hesap silme (Apple onayı için ZORUNLU) net uyarı + onay diyaloglu yapılır.
class AccountSettingsScreen extends ConsumerWidget {
  const AccountSettingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final isLoading = ref.watch(authProvider).isLoading;
    return Scaffold(
      body: Stack(
        children: [
          const Positioned.fill(child: BiladaBackground(showFloaters: false)),
          SafeArea(
            child: ListView(
              padding: const EdgeInsets.fromLTRB(20, 8, 20, 40),
              children: [
                Row(
                  children: [
                    IconButton(
                      icon: const Icon(Icons.arrow_back_rounded, color: AppTheme.cOnSurface),
                      onPressed: () => context.pop(),
                    ),
                    const SizedBox(width: 4),
                    Text('Hesap Ayarları', style: BiladaText.headline(size: 22)),
                  ],
                ),
                const SizedBox(height: 16),

                // --- Güvenlik ---
                Text('GÜVENLİK', style: BiladaText.label(color: AppTheme.cOnSurfaceVariant)),
                const SizedBox(height: 12),
                _ActionTile(
                  icon: Icons.mark_email_read_rounded,
                  title: 'E-posta doğrula',
                  subtitle: 'Hesabını güvende tutmak için e-postanı doğrula',
                  enabled: !isLoading,
                  onTap: () => _sendVerification(context, ref),
                ),
                const SizedBox(height: 12),
                _ActionTile(
                  icon: Icons.lock_reset_rounded,
                  title: 'Şifre değiştir',
                  subtitle: 'E-postana sıfırlama bağlantısı gönderilir',
                  enabled: !isLoading,
                  onTap: () => context.push('/forgot-password'),
                ),

                const SizedBox(height: 28),

                // --- Tehlikeli bölge ---
                Text('TEHLİKELİ BÖLGE', style: BiladaText.label(color: AppTheme.cError)),
                const SizedBox(height: 12),
                GlassCard(
                  padding: const EdgeInsets.all(20),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Row(
                        children: [
                          const Icon(Icons.warning_amber_rounded, color: AppTheme.cError),
                          const SizedBox(width: 10),
                          Expanded(
                            child: Text('Hesabı Sil', style: BiladaText.title(size: 17)),
                          ),
                        ],
                      ),
                      const SizedBox(height: 10),
                      Text(
                        'Hesabını sildiğinde tüm ilerlemen, coinlerin, rozetlerin ve '
                        'istatistiklerin kalıcı olarak silinir. Bu işlem GERİ ALINAMAZ.',
                        style: BiladaText.body(color: AppTheme.cOnSurfaceVariant, size: 14),
                      ),
                      const SizedBox(height: 16),
                      ChunkyButton(
                        height: 52,
                        depth: 4,
                        color: AppTheme.cErrorContainer,
                        foreground: AppTheme.cOnErrorContainer,
                        shadowColor: AppTheme.cErrorShadow,
                        onPressed: isLoading ? null : () => _confirmDelete(context, ref),
                        child: const Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(Icons.delete_forever_rounded, size: 18),
                            SizedBox(width: 8),
                            Text('HESABI SİL', style: TextStyle(fontSize: 16)),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),

                if (isLoading) ...[
                  const SizedBox(height: 24),
                  const Center(child: CircularProgressIndicator(color: AppTheme.cPrimaryContainer)),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _sendVerification(BuildContext context, WidgetRef ref) async {
    final ok = await ref.read(authProvider.notifier).sendVerification();
    if (!context.mounted) return;
    if (ok) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Doğrulama e-postası gönderildi. Gelen kutunu kontrol et.'),
          backgroundColor: AppTheme.cTertiaryContainer,
        ),
      );
    } else {
      final error = ref.read(authProvider).error ?? 'İşlem başarısız';
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(error), backgroundColor: AppTheme.danger),
      );
    }
  }

  Future<void> _confirmDelete(BuildContext context, WidgetRef ref) async {
    final confirmed = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (dialogContext) => AlertDialog(
        backgroundColor: AppTheme.cSurfaceContainerHigh,
        icon: const Icon(Icons.warning_amber_rounded, color: AppTheme.cError, size: 40),
        title: Text('Hesabı silmek istediğine emin misin?',
            textAlign: TextAlign.center, style: BiladaText.title(size: 18)),
        content: Text(
          'Bu işlem GERİ ALINAMAZ. Tüm verilerin kalıcı olarak silinecek.',
          textAlign: TextAlign.center,
          style: BiladaText.body(color: AppTheme.cOnSurfaceVariant, size: 14),
        ),
        actionsAlignment: MainAxisAlignment.center,
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            child: Text('Vazgeç', style: BiladaText.title(color: AppTheme.cOnSurface, size: 15)),
          ),
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(true),
            child: Text('Evet, sil',
                style: BiladaText.title(color: AppTheme.cError, size: 15)),
          ),
        ],
      ),
    );

    if (confirmed != true || !context.mounted) return;

    final ok = await ref.read(authProvider.notifier).deleteAccount();
    if (!context.mounted) return;
    if (ok) {
      context.go('/login');
    } else {
      final error = ref.read(authProvider).error ?? 'Hesap silinemedi';
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(error), backgroundColor: AppTheme.danger),
      );
    }
  }
}

class _ActionTile extends StatelessWidget {
  const _ActionTile({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.onTap,
    this.enabled = true,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback onTap;
  final bool enabled;

  @override
  Widget build(BuildContext context) {
    return GlassCard(
      padding: const EdgeInsets.all(16),
      onTap: enabled ? onTap : null,
      child: Row(
        children: [
          Icon(icon, color: AppTheme.cPrimary, size: 24),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: BiladaText.title(size: 16)),
                const SizedBox(height: 4),
                Text(subtitle, style: BiladaText.label(color: AppTheme.cOutline, size: 11)),
              ],
            ),
          ),
          const Icon(Icons.chevron_right_rounded, color: AppTheme.cOnSurfaceVariant),
        ],
      ),
    );
  }
}
