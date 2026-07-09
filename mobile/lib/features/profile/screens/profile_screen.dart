import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:quizroyale/core/theme/app_theme.dart';
import 'package:quizroyale/features/auth/providers/auth_provider.dart';
import 'package:quizroyale/features/cosmetics/providers/cosmetics_provider.dart';
import 'package:quizroyale/features/profile/providers/profile_provider.dart';
import 'package:quizroyale/shared/widgets/bilada_ui.dart';
import 'package:quizroyale/shared/widgets/player_avatar.dart';

class ProfileScreen extends ConsumerWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(profileProvider);

    return Stack(
      children: [
        const Positioned.fill(child: BiladaBackground(showFloaters: false)),
        SafeArea(
          bottom: false,
          child: state.isLoading
              ? const Center(child: CircularProgressIndicator(color: AppTheme.cPrimaryContainer))
              : state.profile == null
                  ? Center(child: Text('Profil yüklenemedi', style: BiladaText.body(color: AppTheme.cOutline)))
                  : _ProfileBody(profile: state.profile!, stats: state.stats ?? const {}),
        ),
      ],
    );
  }
}

class _ProfileBody extends ConsumerWidget {
  const _ProfileBody({required this.profile, required this.stats});
  final Map<String, dynamic> profile;
  // /api/users/me/stats yanıtı (games_played, games_won, win_rate, best_rank...)
  final Map<String, dynamic> stats;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final username = profile['username'] as String? ?? '';
    final avatarId = profile['avatar_id'] as String? ?? 'default_01';
    final bio = profile['bio'] as String? ?? '';
    final level = profile['level'] as int? ?? 1;
    final xp = profile['xp'] as int? ?? 0;
    final coins = profile['coins'] as int? ?? 0;
    final isGuest = profile['is_guest'] as bool? ?? false;
    // Backend alan adı interest_tags ('interests' anahtarı backend'de yok).
    final interests = (profile['interest_tags'] as List? ?? []).cast<String>();
    // XP çubuğu backend seviye eğrisiyle aynı: T(L) = L*(L-1)*50.
    // Mevcut seviye tabanından bir sonraki seviyeye ilerleme oranı.
    final levelFloor = level * (level - 1) * 50;
    final nextLevelXp = (level + 1) * level * 50;
    final levelSpan = nextLevelXp - levelFloor;
    final xpProgress =
        levelSpan > 0 ? ((xp - levelFloor) / levelSpan).clamp(0.0, 1.0) : 0.0;

    // Kuşanılmış kozmetikler: önce profil (/users/me) equipped_* alanları,
    // yoksa cosmetics provider equipped state. İsim rengini katalog color_hex'i
    // ile çözeriz (profil doğrudan hex döndürüyorsa onu da deneriz).
    final cos = ref.watch(cosmeticsProvider);
    final equippedFrameId = profile['equipped_frame'] as String? ?? cos.equippedFrame;
    final equippedNameColorId = profile['equipped_name_color'] as String? ?? cos.equippedNameColor;
    final nameColor = parseHexColor(profile['equipped_name_color_hex'] as String?) ??
        parseHexColor(cos.byId(equippedNameColorId)?.colorHex);
    final frameKey = frameKeyFromId(equippedFrameId);
    final equippedEffect = cos.byId(cos.equippedEffect);

    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 8, 20, 120),
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            const BiladaLogo(fontSize: 22),
            Row(
              children: [
                IconButton(
                  icon: const Icon(Icons.edit_outlined, color: AppTheme.cOnSurfaceVariant),
                  onPressed: () => context.push('/edit-profile'),
                ),
                IconButton(
                  icon: const Icon(Icons.settings_outlined, color: AppTheme.cOnSurfaceVariant),
                  onPressed: () => context.push('/settings'),
                ),
              ],
            ),
          ],
        ),
        const SizedBox(height: 8),
        // Misafir kullanıcıya kalıcılaştırma bandı: tek dokunuşla claim formu.
        if (isGuest) ...[
          GlassCard(
            padding: const EdgeInsets.all(16),
            onTap: () => _showClaimSheet(context, ref, username),
            child: Row(
              children: [
                const Icon(Icons.shield_rounded, color: AppTheme.gold, size: 26),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Hesabını kaydet', style: BiladaText.title(size: 15)),
                      const SizedBox(height: 3),
                      Text('İlerlemen kaybolmasın — e-posta ve şifre ekle',
                          style: BiladaText.label(color: AppTheme.cOnSurfaceVariant, size: 11)),
                    ],
                  ),
                ),
                const Icon(Icons.chevron_right_rounded, color: AppTheme.cOnSurfaceVariant),
              ],
            ),
          ),
          const SizedBox(height: 12),
        ],
        GlassCard(
          padding: const EdgeInsets.all(20),
          child: Column(
            children: [
              Row(
                children: [
                  // Kozmetik çerçeve varsa onu kullan; yoksa varsayılan pembe halka.
                  frameKey != null
                      ? PlayerAvatar(
                          avatarId: avatarId,
                          username: username,
                          size: 78,
                          frame: frameKey,
                        )
                      : Container(
                          padding: const EdgeInsets.all(3),
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            border: Border.all(color: AppTheme.cPrimaryContainer, width: 3),
                          ),
                          child: PlayerAvatar(avatarId: avatarId, username: username, size: 72),
                        ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        InkWell(
                          onTap: () => context.push('/edit-profile'),
                          borderRadius: BorderRadius.circular(8),
                          child: Padding(
                            padding: const EdgeInsets.symmetric(vertical: 2),
                            child: Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Flexible(
                                  child: Text(
                                    username,
                                    style: BiladaText.headline(
                                        color: nameColor ?? AppTheme.cOnSurface, size: 22),
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                ),
                                const SizedBox(width: 6),
                                const Icon(Icons.edit_rounded,
                                    color: AppTheme.cOnSurfaceVariant, size: 16),
                              ],
                            ),
                          ),
                        ),
                        const SizedBox(height: 6),
                        Row(
                          children: [
                            PillBadge('SEVİYE $level', color: AppTheme.cPrimaryContainer, fg: AppTheme.cOnPrimaryContainer),
                            const SizedBox(width: 8),
                            Text('🪙 $coins', style: BiladaText.label(color: AppTheme.gold, size: 12)),
                          ],
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              ClipRRect(
                borderRadius: BorderRadius.circular(999),
                child: LinearProgressIndicator(
                  value: xpProgress,
                  minHeight: 8,
                  color: AppTheme.cTertiary,
                  backgroundColor: AppTheme.cSurfaceVariant,
                ),
              ),
              const SizedBox(height: 4),
              Align(
                alignment: Alignment.centerRight,
                child: Text('${xp - levelFloor}/$levelSpan XP',
                    style: BiladaText.label(color: AppTheme.cOutline, size: 10)),
              ),
            ],
          ),
        ),
        if (bio.isNotEmpty) ...[
          const SizedBox(height: 16),
          Text(bio, style: BiladaText.body(color: AppTheme.cOnSurfaceVariant)),
        ],
        if (interests.isNotEmpty) ...[
          const SizedBox(height: 16),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: interests
                .map((t) => Container(
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                      decoration: BoxDecoration(
                        color: AppTheme.cPrimaryContainer.withValues(alpha: 0.15),
                        borderRadius: BorderRadius.circular(999),
                      ),
                      child: Text(t, style: BiladaText.label(color: AppTheme.cPrimary, size: 12)),
                    ))
                .toList(),
          ),
        ],
        const SizedBox(height: 20),
        _statsGrid(stats),
        const SizedBox(height: 28),
        Text('GÖRÜNÜMÜM', style: BiladaText.label(color: AppTheme.cOnSurfaceVariant)),
        const SizedBox(height: 12),
        GlassCard(
          padding: const EdgeInsets.all(20),
          child: Column(
            children: [
              Row(
                children: [
                  // Kuşanılmış çerçeveyle büyük avatar.
                  frameKey != null
                      ? PlayerAvatar(
                          avatarId: avatarId,
                          username: username,
                          size: 72,
                          frame: frameKey,
                        )
                      : Container(
                          padding: const EdgeInsets.all(3),
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            border: Border.all(color: AppTheme.cPrimaryContainer, width: 3),
                          ),
                          child: PlayerAvatar(avatarId: avatarId, username: username, size: 66),
                        ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        // Kuşanılmış isim rengiyle ad.
                        Text(username,
                            style: BiladaText.title(
                                color: nameColor ?? AppTheme.cOnSurface, size: 18)),
                        const SizedBox(height: 8),
                        Wrap(
                          spacing: 8,
                          runSpacing: 6,
                          children: [
                            PillBadge(
                              frameKey != null ? 'ÇERÇEVE ✓' : 'ÇERÇEVE YOK',
                              color: frameKey != null
                                  ? AppTheme.cSecondaryContainer
                                  : AppTheme.cSurfaceContainerHighest,
                              fg: frameKey != null ? Colors.white : AppTheme.cOutline,
                            ),
                            PillBadge(
                              nameColor != null ? 'RENK ✓' : 'RENK YOK',
                              color: nameColor ?? AppTheme.cSurfaceContainerHighest,
                              fg: nameColor != null ? Colors.white : AppTheme.cOutline,
                            ),
                            if (equippedEffect != null)
                              PillBadge('✨ ${equippedEffect.name}',
                                  color: AppTheme.cTertiaryContainer, fg: Colors.white),
                          ],
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              ChunkyButton(
                height: 48,
                depth: 4,
                color: AppTheme.cTertiaryContainer,
                foreground: Colors.white,
                shadowColor: AppTheme.cTertiaryShadow,
                onPressed: () => context.push('/cosmetics'),
                child: const Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.auto_awesome_rounded, size: 18),
                    SizedBox(width: 8),
                    Text('GÖRÜNÜMÜ DEĞİŞTİR', style: TextStyle(fontSize: 15)),
                  ],
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 28),
        Text('ENVANTERİM', style: BiladaText.label(color: AppTheme.cOnSurfaceVariant)),
        const SizedBox(height: 12),
        GlassCard(
          padding: const EdgeInsets.all(16),
          onTap: () => context.push('/inventory'),
          child: Row(
            children: [
              const Icon(Icons.inventory_2_rounded, color: AppTheme.cTertiary, size: 24),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Envanterim', style: BiladaText.title(size: 16)),
                    const SizedBox(height: 4),
                    Text('Karakterler, kozmetikler, bakiye ve premium',
                        style: BiladaText.label(color: AppTheme.cOutline, size: 11)),
                  ],
                ),
              ),
              const Icon(Icons.chevron_right_rounded, color: AppTheme.cOnSurfaceVariant),
            ],
          ),
        ),
        const SizedBox(height: 16),
        GlassCard(
          padding: const EdgeInsets.all(16),
          onTap: () => context.push('/account-settings'),
          child: Row(
            children: [
              const Icon(Icons.manage_accounts_rounded, color: AppTheme.cPrimary, size: 24),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Hesap Ayarları', style: BiladaText.title(size: 16)),
                    const SizedBox(height: 4),
                    Text('E-posta, şifre ve hesap silme',
                        style: BiladaText.label(color: AppTheme.cOutline, size: 11)),
                  ],
                ),
              ),
              const Icon(Icons.chevron_right_rounded, color: AppTheme.cOnSurfaceVariant),
            ],
          ),
        ),
        const SizedBox(height: 16),
        GlassCard(
          padding: const EdgeInsets.all(16),
          onTap: () => context.push('/friends'),
          child: Row(
            children: [
              const Icon(Icons.people_alt_rounded, color: AppTheme.cTertiary, size: 24),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Arkadaşlar', style: BiladaText.title(size: 16)),
                    const SizedBox(height: 4),
                    Text('Arkadaş ekle, istekleri yönet',
                        style: BiladaText.label(color: AppTheme.cOutline, size: 11)),
                  ],
                ),
              ),
              const Icon(Icons.chevron_right_rounded, color: AppTheme.cOnSurfaceVariant),
            ],
          ),
        ),
        const SizedBox(height: 16),
        ChunkyButton(
          height: 52,
          depth: 4,
          color: AppTheme.cErrorContainer,
          foreground: AppTheme.cOnErrorContainer,
          shadowColor: AppTheme.cErrorShadow,
          onPressed: () async {
            await ref.read(authProvider.notifier).logout();
            if (context.mounted) context.go('/login');
          },
          child: const Row(
            mainAxisSize: MainAxisSize.min,
            children: [Icon(Icons.logout_rounded, size: 18), SizedBox(width: 8), Text('ÇIKIŞ YAP', style: TextStyle(fontSize: 16))],
          ),
        ),
      ],
    );
  }

  /// Misafir hesabı kalıcılaştırma formunu (claim) alttan açar.
  void _showClaimSheet(BuildContext context, WidgetRef ref, String username) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => _ClaimAccountSheet(currentUsername: username),
    );
  }

  Widget _statsGrid(Map<String, dynamic> stats) {
    final winRate = (stats['win_rate'] as num?)?.round() ?? 0;
    final bestRank = stats['best_rank'];
    final items = [
      ('Oynanan', '${stats['games_played'] ?? 0}', Icons.sports_esports_outlined),
      ('Kazanılan', '${stats['games_won'] ?? 0}', Icons.emoji_events_outlined),
      ('Kazanma %', '$winRate%', Icons.percent_rounded),
      ('En İyi Sıra', bestRank == null ? '#-' : '#$bestRank', Icons.leaderboard_outlined),
    ];
    return GridView.count(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      crossAxisCount: 2,
      mainAxisSpacing: 12,
      crossAxisSpacing: 12,
      childAspectRatio: 2.4,
      children: items
          .map((item) => GlassCard(
                padding: const EdgeInsets.all(14),
                child: Row(
                  children: [
                    Icon(item.$3, size: 20, color: AppTheme.cPrimary),
                    const SizedBox(width: 10),
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Text(item.$2, style: BiladaText.title(size: 16)),
                        Text(item.$1, style: BiladaText.label(color: AppTheme.cOutline, size: 10)),
                      ],
                    ),
                  ],
                ),
              ))
          .toList(),
    );
  }
}

/// Misafir hesabı kalıcılaştırma formu (basit claim akışı).
///
/// E-posta + şifre (ve isteğe bağlı yeni kullanıcı adı) alır,
/// POST /api/auth/claim çağırır. Başarıda profil tazelenir ve
/// "Hesabını kaydet" bandı kaybolur (is_guest=false).
class _ClaimAccountSheet extends ConsumerStatefulWidget {
  const _ClaimAccountSheet({required this.currentUsername});
  final String currentUsername;

  @override
  ConsumerState<_ClaimAccountSheet> createState() => _ClaimAccountSheetState();
}

class _ClaimAccountSheetState extends ConsumerState<_ClaimAccountSheet> {
  final _formKey = GlobalKey<FormState>();
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  final _usernameController = TextEditingController();
  bool _obscurePassword = true;
  bool _saving = false;

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    _usernameController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _saving = true);
    final ok = await ref.read(authProvider.notifier).claimAccount(
          email: _emailController.text,
          password: _passwordController.text,
          username: _usernameController.text.trim().isEmpty
              ? null
              : _usernameController.text,
        );
    if (!mounted) return;
    setState(() => _saving = false);
    if (ok) {
      // Profili tazele ki is_guest=false olsun ve bant kaybolsun.
      await ref.read(profileProvider.notifier).load();
      if (!mounted) return;
      Navigator.of(context).pop();
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Hesabın kaydedildi! Artık ilerlemen güvende.'),
          backgroundColor: AppTheme.success,
        ),
      );
    } else {
      final error = ref.read(authProvider).error ?? 'Kaydedilemedi, tekrar dene';
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(error), backgroundColor: AppTheme.danger),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final bottomInset = MediaQuery.of(context).viewInsets.bottom;
    return Padding(
      padding: EdgeInsets.only(bottom: bottomInset),
      child: Container(
        decoration: const BoxDecoration(
          color: AppTheme.cSurfaceContainerLow,
          borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
        ),
        padding: const EdgeInsets.fromLTRB(24, 16, 24, 32),
        child: Form(
          key: _formKey,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Center(
                child: Container(
                  width: 40,
                  height: 4,
                  decoration: BoxDecoration(
                    color: AppTheme.cOutlineVariant,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ),
              const SizedBox(height: 16),
              Text('Hesabını kaydet', style: BiladaText.headline(size: 20)),
              const SizedBox(height: 6),
              Text(
                'E-posta ve şifre ekle; seviyen, altınların ve istatistiklerin '
                'bu hesapta kalıcı olsun.',
                style: BiladaText.body(color: AppTheme.cOnSurfaceVariant, size: 13),
              ),
              const SizedBox(height: 20),
              TextFormField(
                controller: _emailController,
                enabled: !_saving,
                keyboardType: TextInputType.emailAddress,
                style: BiladaText.body(),
                decoration: const InputDecoration(
                  labelText: 'E-posta',
                  prefixIcon: Icon(Icons.mail_rounded),
                ),
                validator: (v) {
                  final val = v?.trim() ?? '';
                  if (val.isEmpty) return 'E-posta zorunludur';
                  if (!val.contains('@') || !val.contains('.')) {
                    return 'Geçerli bir e-posta gir';
                  }
                  return null;
                },
              ),
              const SizedBox(height: 14),
              TextFormField(
                controller: _passwordController,
                enabled: !_saving,
                obscureText: _obscurePassword,
                style: BiladaText.body(),
                decoration: InputDecoration(
                  labelText: 'Şifre (en az 6 karakter)',
                  prefixIcon: const Icon(Icons.lock_rounded),
                  suffixIcon: IconButton(
                    icon: Icon(_obscurePassword
                        ? Icons.visibility_off_rounded
                        : Icons.visibility_rounded),
                    onPressed: () =>
                        setState(() => _obscurePassword = !_obscurePassword),
                  ),
                ),
                validator: (v) {
                  if (v == null || v.length < 6) return 'En az 6 karakter olmalı';
                  if (RegExp(r'^\d+$').hasMatch(v)) {
                    return 'Şifre sadece rakamlardan oluşamaz';
                  }
                  return null;
                },
              ),
              const SizedBox(height: 14),
              TextFormField(
                controller: _usernameController,
                enabled: !_saving,
                style: BiladaText.body(),
                decoration: InputDecoration(
                  labelText: 'Kullanıcı adı (opsiyonel)',
                  hintText: widget.currentUsername,
                  prefixIcon: const Icon(Icons.person_rounded),
                ),
                validator: (v) {
                  final val = v?.trim() ?? '';
                  if (val.isEmpty) return null; // opsiyonel
                  if (val.length < 3) return 'En az 3 karakter olmalı';
                  if (!RegExp(r'^[a-zA-Z0-9_.]+$').hasMatch(val)) {
                    return 'Sadece harf, rakam, _ ve . kullanılabilir';
                  }
                  return null;
                },
              ),
              const SizedBox(height: 24),
              ChunkyButton(
                height: 56,
                onPressed: _saving ? null : _submit,
                child: _saving
                    ? const SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(
                            strokeWidth: 2, color: AppTheme.cOnPrimaryContainer),
                      )
                    : const Text('HESABIMI KAYDET'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
