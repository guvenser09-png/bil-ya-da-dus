import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:quizroyale/core/constants/app_constants.dart';
import 'package:quizroyale/core/theme/app_theme.dart';
import 'package:quizroyale/features/profile/providers/profile_provider.dart';
import 'package:quizroyale/features/store/providers/store_provider.dart';
import 'package:quizroyale/shared/characters.dart';
import 'package:quizroyale/shared/widgets/bilada_ui.dart';
import 'package:quizroyale/shared/widgets/player_avatar.dart';

class EditProfileScreen extends ConsumerStatefulWidget {
  const EditProfileScreen({super.key});

  @override
  ConsumerState<EditProfileScreen> createState() => _EditProfileScreenState();
}

class _EditProfileScreenState extends ConsumerState<EditProfileScreen> {
  final _bioController = TextEditingController();
  String _avatarId = 'robot';
  List<String> _selectedInterests = [];
  bool _dirty = false;

  @override
  void initState() {
    super.initState();
    final profile = ref.read(profileProvider).profile ?? {};
    _bioController.text = profile['bio'] as String? ?? '';
    // Katalogdaki bir karaktere işaret etmiyorsa starter'ın ilkine düş.
    final saved = profile['avatar_id'] as String?;
    _avatarId = (saved != null && isCatalogCharacter(saved)) ? saved : 'robot';
    // Backend alan adı interest_tags ('interests' anahtarı backend'de yok).
    _selectedInterests = (profile['interest_tags'] as List? ?? []).cast<String>();
    _bioController.addListener(() => setState(() => _dirty = true));
    // Karakter sahipliğini tazele (bireysel owned/price için backend otoritedir).
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(storeProvider.notifier).loadCharacters();
    });
  }

  @override
  void dispose() {
    _bioController.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    final ok = await ref.read(profileProvider.notifier).update(
          bio: _bioController.text.trim(),
          avatarId: _avatarId,
          interests: _selectedInterests,
        );
    if (mounted) {
      if (ok) {
        context.pop();
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Kaydedilemedi, tekrar dene'), backgroundColor: AppTheme.danger),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final isSaving = ref.watch(profileProvider).isSaving;
    final username = ref.read(profileProvider).profile?['username'] as String? ?? '';
    final store = ref.watch(storeProvider);

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
                      Expanded(child: Text('Profili Düzenle', style: BiladaText.headline(size: 22))),
                      if (_dirty)
                        SizedBox(
                          width: 110,
                          child: ChunkyButton(
                            height: 44,
                            depth: 4,
                            onPressed: isSaving ? null : _save,
                            child: isSaving
                                ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2, color: AppTheme.cOnPrimaryContainer))
                                : const Text('KAYDET', style: TextStyle(fontSize: 14)),
                          ),
                        ),
                    ],
                  ),
                ),
                Expanded(
                  child: SingleChildScrollView(
                    padding: const EdgeInsets.fromLTRB(20, 8, 20, 32),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Center(
                          child: Container(
                            padding: const EdgeInsets.all(3),
                            decoration: BoxDecoration(
                              shape: BoxShape.circle,
                              border: Border.all(color: AppTheme.cPrimaryContainer, width: 3),
                            ),
                            child: PlayerAvatar(avatarId: _avatarId, username: username, size: 88),
                          ),
                        ),
                        const SizedBox(height: 20),
                        _charactersSection(store, username),
                        const SizedBox(height: 20),
                        const SizedBox(height: 4),
                        Text('BİO', style: BiladaText.label(color: AppTheme.cPrimary)),
                        const SizedBox(height: 8),
                        TextField(
                          controller: _bioController,
                          maxLength: 140,
                          maxLines: 3,
                          style: BiladaText.body(size: 14),
                          decoration: const InputDecoration(hintText: 'Kendini tanıt...'),
                        ),
                        const SizedBox(height: 12),
                        Text('İLGİ ALANLARI', style: BiladaText.label(color: AppTheme.cPrimary)),
                        const SizedBox(height: 10),
                        Wrap(
                          spacing: 8,
                          runSpacing: 8,
                          children: AppConstants.interestTags.map((tag) {
                            final selected = _selectedInterests.contains(tag);
                            return GestureDetector(
                              onTap: () {
                                final newList = List<String>.from(_selectedInterests);
                                if (selected) {
                                  newList.remove(tag);
                                } else if (newList.length < 5) {
                                  newList.add(tag);
                                }
                                setState(() { _selectedInterests = newList; _dirty = true; });
                              },
                              child: AnimatedContainer(
                                duration: const Duration(milliseconds: 180),
                                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                                decoration: BoxDecoration(
                                  color: selected ? AppTheme.cPrimaryContainer : AppTheme.cSurfaceContainerHigh,
                                  borderRadius: BorderRadius.circular(999),
                                  border: Border.all(color: selected ? AppTheme.cPrimaryContainer : AppTheme.cOutlineVariant),
                                ),
                                child: Text(tag, style: BiladaText.label(
                                    color: selected ? AppTheme.cOnPrimaryContainer : AppTheme.cOnSurfaceVariant, size: 12)),
                              ),
                            );
                          }).toList(),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  /// Karakter seçici — BİREYSEL sahiplik (paket yok).
  ///
  /// Otorite backend (`GET /api/store/characters`): her karakterde
  /// owned/price_coins. Sahip olunan karakterler seçilebilir (KAYDET avatar_id'yi
  /// PATCH /me ile yazar); sahip olunmayanlar kilitli görünür, dokununca altın
  /// fiyatıyla mağazaya yönlendirir. Katalog henüz gelmediyse (giriş yokken vb.)
  /// characters.dart kataloğundan türetilen güvenli bir varsayıma düşer:
  /// yalnızca ücretsiz başlangıç karakterleri (robot/alien/ghost) sahiplenilmiş
  /// sayılır.
  Widget _charactersSection(StoreState store, String username) {
    // Backend kataloğu varsa onu kullan; yoksa katalogdan free=starter türet.
    final hasBackend = store.characters.isNotEmpty;
    final tiles = hasBackend
        ? [
            for (final sc in store.characters)
              _CharTileData(
                id: sc.id,
                name: sc.name,
                owned: sc.owned,
                priceCoins: sc.priceCoins,
              ),
          ]
        : [
            for (final c in kCharacters)
              _CharTileData(
                id: c.id,
                name: c.name,
                owned: c.packId == kStarterPackId,
                priceCoins: 0,
              ),
          ];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            const Icon(Icons.emoji_emotions_rounded, size: 18, color: AppTheme.cPrimary),
            const SizedBox(width: 8),
            Text('KARAKTERİN', style: BiladaText.label(color: AppTheme.cPrimary)),
            const Spacer(),
            Text('🪙 ${store.coins}', style: BiladaText.label(color: AppTheme.gold, size: 12)),
          ],
        ),
        const SizedBox(height: 6),
        Text('Sahip olduğun bir karakteri seç, KAYDET ile kuşan. Kilitlileri mağazadan altınla al.',
            style: BiladaText.label(color: AppTheme.cOnSurfaceVariant, size: 11)),
        const SizedBox(height: 12),
        GlassCard(
          padding: const EdgeInsets.all(14),
          child: Wrap(
            spacing: 14,
            runSpacing: 14,
            children: [
              for (final t in tiles) _characterTile(t, username),
            ],
          ),
        ),
      ],
    );
  }

  Widget _characterTile(_CharTileData c, String username) {
    final selected = c.id == _avatarId;
    return GestureDetector(
      onTap: () {
        if (c.owned) {
          setState(() {
            _avatarId = c.id;
            _dirty = true;
          });
        } else {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('${c.name} kilitli — mağazadan ${c.priceCoins} 🪙 ile alabilirsin.'),
              backgroundColor: AppTheme.cSurfaceContainerHigh,
              action: SnackBarAction(
                label: 'MAĞAZA',
                textColor: AppTheme.gold,
                onPressed: () => context.push('/store'),
              ),
            ),
          );
        }
      },
      child: SizedBox(
        width: 62,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Stack(
              alignment: Alignment.center,
              children: [
                Container(
                  padding: const EdgeInsets.all(2),
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    border: Border.all(
                      color: selected ? AppTheme.gold : Colors.transparent,
                      width: 2.5,
                    ),
                  ),
                  child: Opacity(
                    opacity: c.owned ? 1 : 0.35,
                    child: PlayerAvatar(avatarId: c.id, username: username, size: 54),
                  ),
                ),
                if (!c.owned)
                  const Icon(Icons.lock_rounded, size: 20, color: Colors.white),
              ],
            ),
            const SizedBox(height: 4),
            Text(
              c.name,
              textAlign: TextAlign.center,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: BiladaText.label(
                color: selected ? AppTheme.gold : AppTheme.cOnSurfaceVariant,
                size: 10,
              ),
            ),
            if (!c.owned)
              Text('${c.priceCoins} 🪙',
                  style: BiladaText.label(color: AppTheme.gold, size: 9)),
          ],
        ),
      ),
    );
  }
}

/// Karakter karosu için sadeleştirilmiş veri (backend veya katalog kaynaklı).
class _CharTileData {
  const _CharTileData({
    required this.id,
    required this.name,
    required this.owned,
    required this.priceCoins,
  });
  final String id;
  final String name;
  final bool owned;
  final int priceCoins;
}
