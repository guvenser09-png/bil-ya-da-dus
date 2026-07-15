// HEDİYE KARAKTER (v1.2): Başlangıç altını 1000→300'e indi; telafi olarak
// yeni oyuncuya ilk ana ekranda BİR KEZ "Hoş geldin — bir karakter seç!"
// ekranı gösterilir. Seçilen karakter mevcut kuşanma akışıyla kuşanılır
// (PATCH /api/users/me {avatar_id}). Hediye SADECE başlangıç (ücretsiz/sahip
// olunan) karakterlerden seçildiği için BACKEND DEĞİŞMEDEN çalışır.

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:quizroyale/core/network/api_client.dart';
import 'package:quizroyale/core/theme/app_theme.dart';
import 'package:quizroyale/features/auth/providers/auth_provider.dart';
import 'package:quizroyale/shared/characters.dart';
import 'package:quizroyale/shared/widgets/bilada_ui.dart';
import 'package:quizroyale/shared/widgets/player_avatar.dart';

/// Hediye karakter seçim ekranını modal olarak açar.
/// Tek seferliktir; çağıran taraf (home) prefs bayrağıyla tekrarı engeller.
Future<void> showGiftCharacterSheet(BuildContext context, WidgetRef ref) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    isDismissible: false, // hediye — kullanıcı bir seçim yapsın
    enableDrag: false,
    backgroundColor: Colors.transparent,
    builder: (_) => _GiftCharacterSheet(ref: ref),
  );
}

class _GiftCharacterSheet extends StatefulWidget {
  const _GiftCharacterSheet({required this.ref});
  final WidgetRef ref;

  @override
  State<_GiftCharacterSheet> createState() => _GiftCharacterSheetState();
}

class _GiftCharacterSheetState extends State<_GiftCharacterSheet> {
  /// Hediye adayları: yalnız başlangıç paketi (herkese açık, ücretsiz sahip).
  /// Böylece kuşanma (avatar_id) backend'de sahiplik kapısına takılmaz.
  late final List<BiladaCharacter> _gifts =
      kCharacters.where((c) => c.packId == kStarterPackId).toList();

  late String _selectedId = _gifts.isNotEmpty ? _gifts.first.id : 'robot';
  bool _busy = false;

  Future<void> _claim() async {
    if (_busy) return;
    setState(() => _busy = true);
    try {
      // Mevcut kuşanma akışı: PATCH /api/users/me {avatar_id}.
      await ApiClient.instance
          .patch('/api/users/me', body: {'avatar_id': _selectedId});
      await widget.ref.read(authProvider.notifier).refreshUser();
    } catch (_) {
      // Ağ hatası olsa bile ekranı kapat — tekrar sunulmaz (bayrak set edildi).
      // Kullanıcı karakteri profil/mağazadan da kuşanabilir.
    }
    if (!mounted) return;
    Navigator.of(context).maybePop();
  }

  @override
  Widget build(BuildContext context) {
    final bottomInset = MediaQuery.of(context).padding.bottom;
    return Container(
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [Color(0xFF2A0A3D), Color(0xFF1A0526)],
        ),
        borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
      ),
      padding: EdgeInsets.fromLTRB(20, 14, 20, 20 + bottomInset),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Tutamak.
          Container(
            width: 44,
            height: 5,
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.25),
              borderRadius: BorderRadius.circular(999),
            ),
          ),
          const SizedBox(height: 18),
          const Text('🎁', style: TextStyle(fontSize: 44)),
          const SizedBox(height: 10),
          Text(
            'Hoş geldin!',
            style: BiladaText.displayXl(color: AppTheme.cOnSurface, size: 26),
          ),
          const SizedBox(height: 8),
          Text(
            'Sana bir başlangıç karakteri hediye ediyoruz.\nBirini seç, oyuna onunla başla.',
            textAlign: TextAlign.center,
            style: BiladaText.body(color: AppTheme.cOnSurfaceVariant, size: 14),
          ),
          const SizedBox(height: 22),
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              for (final c in _gifts)
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 6),
                  child: _GiftTile(
                    character: c,
                    selected: c.id == _selectedId,
                    onTap: _busy ? null : () => setState(() => _selectedId = c.id),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 26),
          ChunkyButton(
            height: 60,
            color: AppTheme.gold,
            foreground: const Color(0xFF3A0020),
            shadowColor: const Color(0xFFB8860B),
            onPressed: _busy ? null : _claim,
            child: _busy
                ? const SizedBox(
                    width: 22,
                    height: 22,
                    child: CircularProgressIndicator(
                        strokeWidth: 2.5, color: Color(0xFF3A0020)),
                  )
                : const Text('HEDİYEMİ AL'),
          ),
        ],
      ),
    );
  }
}

/// Tek bir hediye karakter kutucuğu — seçiliyken altın çerçeve + tik.
class _GiftTile extends StatelessWidget {
  const _GiftTile({
    required this.character,
    required this.selected,
    required this.onTap,
  });
  final BiladaCharacter character;
  final bool selected;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 160),
        width: 96,
        padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 6),
        decoration: BoxDecoration(
          color: selected
              ? AppTheme.gold.withValues(alpha: 0.14)
              : Colors.white.withValues(alpha: 0.05),
          borderRadius: BorderRadius.circular(18),
          border: Border.all(
            color: selected
                ? AppTheme.gold
                : Colors.white.withValues(alpha: 0.12),
            width: selected ? 2 : 1,
          ),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            PlayerAvatar(
              avatarId: character.id,
              username: character.name,
              size: 56,
            ),
            const SizedBox(height: 8),
            Text(
              character.name,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: BiladaText.label(
                color: selected ? AppTheme.gold : AppTheme.cOnSurfaceVariant,
                size: 12,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
