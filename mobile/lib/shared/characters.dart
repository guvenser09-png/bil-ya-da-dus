import 'package:flutter/material.dart';
import 'package:quizroyale/core/theme/app_theme.dart';

/// Tek bir oynanabilir karakter.
///
/// [id] kısa, stabil ve katalog/profil/mağaza arasında ortak kimliktir
/// (örn 'robot', 'cat_face'). Backend'e avatar_id olarak bu kaydedilir.
/// [imageUrl] Microsoft Fluent 3D Emoji CDN bağlantısıdır.
/// [packId] bu karakterin hangi pakete ait olduğunu belirtir; sahiplik
/// paket bazında çözülür (bkz. store_provider).
class BiladaCharacter {
  const BiladaCharacter({
    required this.id,
    required this.name,
    required this.imageUrl,
    required this.packId,
  });

  final String id;
  final String name;
  final String imageUrl;
  final String packId;
}

/// Bir karakter paketi (mağaza ürünü + katalog grubu).
class BiladaCharacterPack {
  const BiladaCharacterPack({
    required this.id,
    required this.name,
    required this.subtitle,
    required this.price,
    required this.tag,
    required this.accent,
    required this.icon,
    this.featured = false,
  });

  final String id;
  final String name;
  final String subtitle;
  final int price; // coin; starter için 0
  final String tag;
  final Color accent;
  final IconData icon;
  final bool featured;

  /// Bu pakete ait karakterler.
  List<BiladaCharacter> get characters =>
      kCharacters.where((c) => c.packId == id).toList();
}

/// Fluent 3D emoji CDN kalıbı.
/// folder = "Sentence case" (boşluklar %20), file = snake_case.
String _fluentUrl(String folder, String file) =>
    'https://cdn.jsdelivr.net/gh/microsoft/fluentui-emoji@main/assets/'
    '${folder.replaceAll(' ', '%20')}/3D/${file}_3d.png';

/// Tüm karakter kataloğu.
/// (Tüm URL'ler microsoft/fluentui-emoji üzerinde 200 olarak doğrulanmıştır.)
final List<BiladaCharacter> kCharacters = [
  // --- STARTER (ücretsiz, herkeste açık, tam 3 karakter) ---
  BiladaCharacter(id: 'robot', name: 'Robot', packId: 'starter', imageUrl: _fluentUrl('Robot', 'robot')),
  BiladaCharacter(id: 'alien', name: 'Uzaylı', packId: 'starter', imageUrl: _fluentUrl('Alien', 'alien')),
  BiladaCharacter(id: 'ghost', name: 'Hayalet', packId: 'starter', imageUrl: _fluentUrl('Ghost', 'ghost')),

  // --- HAYVANLAR ---
  BiladaCharacter(id: 'cat_face', name: 'Kedi', packId: 'animals', imageUrl: _fluentUrl('Cat face', 'cat_face')),
  BiladaCharacter(id: 'dog_face', name: 'Köpek', packId: 'animals', imageUrl: _fluentUrl('Dog face', 'dog_face')),
  BiladaCharacter(id: 'fox', name: 'Tilki', packId: 'animals', imageUrl: _fluentUrl('Fox', 'fox')),
  BiladaCharacter(id: 'panda', name: 'Panda', packId: 'animals', imageUrl: _fluentUrl('Panda', 'panda')),
  BiladaCharacter(id: 'lion', name: 'Aslan', packId: 'animals', imageUrl: _fluentUrl('Lion', 'lion')),
  BiladaCharacter(id: 'tiger', name: 'Kaplan', packId: 'animals', imageUrl: _fluentUrl('Tiger', 'tiger')),
  BiladaCharacter(id: 'frog', name: 'Kurbağa', packId: 'animals', imageUrl: _fluentUrl('Frog', 'frog')),
  BiladaCharacter(id: 'penguin', name: 'Penguen', packId: 'animals', imageUrl: _fluentUrl('Penguin', 'penguin')),

  // --- UZAYLILAR ---
  BiladaCharacter(id: 'alien_monster', name: 'Uzay Canavarı', packId: 'aliens', imageUrl: _fluentUrl('Alien monster', 'alien_monster')),
  BiladaCharacter(id: 'flying_saucer', name: 'UFO', packId: 'aliens', imageUrl: _fluentUrl('Flying saucer', 'flying_saucer')),
  BiladaCharacter(id: 'rocket', name: 'Roket', packId: 'aliens', imageUrl: _fluentUrl('Rocket', 'rocket')),
  BiladaCharacter(id: 'octopus', name: 'Ahtapot', packId: 'aliens', imageUrl: _fluentUrl('Octopus', 'octopus')),
  BiladaCharacter(id: 'dragon_face', name: 'Ejder Yüzü', packId: 'aliens', imageUrl: _fluentUrl('Dragon face', 'dragon_face')),

  // --- EFSANEVİ ---
  BiladaCharacter(id: 'dragon', name: 'Ejderha', packId: 'mythic', imageUrl: _fluentUrl('Dragon', 'dragon')),
  BiladaCharacter(id: 'ogre', name: 'Dev', packId: 'mythic', imageUrl: _fluentUrl('Ogre', 'ogre')),
  BiladaCharacter(id: 'goblin', name: 'Goblin', packId: 'mythic', imageUrl: _fluentUrl('Goblin', 'goblin')),
  BiladaCharacter(id: 'unicorn', name: 'Tek Boynuz', packId: 'mythic', imageUrl: _fluentUrl('Unicorn', 'unicorn')),
  BiladaCharacter(id: 'owl', name: 'Baykuş', packId: 'mythic', imageUrl: _fluentUrl('Owl', 'owl')),

  // --- HAVALI ---
  BiladaCharacter(id: 'smiling_face_with_sunglasses', name: 'Gözlüklü', packId: 'cool', imageUrl: _fluentUrl('Smiling face with sunglasses', 'smiling_face_with_sunglasses')),
  BiladaCharacter(id: 'nerd_face', name: 'İnek', packId: 'cool', imageUrl: _fluentUrl('Nerd face', 'nerd_face')),
  BiladaCharacter(id: 'star-struck', name: 'Yıldız Gözlü', packId: 'cool', imageUrl: _fluentUrl('Star-struck', 'star-struck')),
  BiladaCharacter(id: 'cowboy_hat_face', name: 'Kovboy', packId: 'cool', imageUrl: _fluentUrl('Cowboy hat face', 'cowboy_hat_face')),
  BiladaCharacter(id: 'clown_face', name: 'Palyaço', packId: 'cool', imageUrl: _fluentUrl('Clown face', 'clown_face')),
];

/// Tüm paketler (mağaza ürün kataloğu ile birebir aynı kaynak).
/// Sıra: starter (ücretsiz), sonra satın alınabilir paketler.
const List<BiladaCharacterPack> kCharacterPacks = [
  BiladaCharacterPack(
    id: 'starter',
    name: 'Başlangıç',
    subtitle: 'Herkese açık 3 ücretsiz karakter',
    price: 0,
    tag: 'ÜCRETSİZ',
    accent: AppTheme.cPrimary,
    icon: Icons.emoji_emotions_rounded,
  ),
  BiladaCharacterPack(
    id: 'animals',
    name: 'Hayvanlar',
    subtitle: '8 Sevimli Karakter',
    price: 500,
    tag: 'Popüler',
    accent: AppTheme.cSecondaryContainer,
    icon: Icons.pets_rounded,
  ),
  BiladaCharacterPack(
    id: 'aliens',
    name: 'Uzaylılar',
    subtitle: '5 Galaktik Dost',
    price: 800,
    tag: 'Yeni',
    accent: AppTheme.cTertiary,
    icon: Icons.rocket_launch_rounded,
  ),
  BiladaCharacterPack(
    id: 'mythic',
    name: 'Efsanevi',
    subtitle: '5 Efsanevi Yaratık',
    price: 1200,
    tag: 'Efsanevi',
    accent: AppTheme.cPrimaryContainer,
    icon: Icons.auto_awesome_rounded,
  ),
  BiladaCharacterPack(
    id: 'cool',
    name: 'Havalı',
    subtitle: '5 Karizmatik Surat',
    price: 2500,
    tag: 'PREMIUM',
    accent: AppTheme.cPrimaryContainer,
    icon: Icons.local_fire_department_rounded,
    featured: true,
  ),
];

/// Verilen [id]'ye sahip karakteri döndürür; yoksa null.
BiladaCharacter? characterById(String id) {
  for (final c in kCharacters) {
    if (c.id == id) return c;
  }
  return null;
}

/// Verilen [id] için 3D görsel URL'i; katalogda yoksa null.
String? imageUrlFor(String id) => characterById(id)?.imageUrl;

/// Verilen [id] bir katalog karakteri mi?
bool isCatalogCharacter(String id) => characterById(id) != null;

/// Verilen [packId]'ye sahip paketi döndürür; yoksa null.
BiladaCharacterPack? packById(String packId) {
  for (final p in kCharacterPacks) {
    if (p.id == packId) return p;
  }
  return null;
}

/// Herkeste her zaman açık olan paket.
const String kStarterPackId = 'starter';
