import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:quizroyale/core/network/api_client.dart';
import 'package:quizroyale/features/auth/providers/auth_provider.dart';
import 'package:quizroyale/features/cosmetics/providers/cosmetics_provider.dart';
import 'package:quizroyale/shared/characters.dart';

/// Envanter durumu: kullanıcının SAHİP OLDUĞU her şey tek yerde.
///
/// Üç uçtan beslenir ve birleştirilir:
/// - `GET /api/store/characters` → coins, equipped (kuşanılı karakter id),
///   characters[] (her birinde owned bayrağı). Tek tek (bireysel) karakter
///   sahipliği — PAKET kavramı KALDIRILDI.
/// - `GET /api/store/inventory`  → coins, is_premium, premium_until.
/// - `GET /api/cosmetics`        → kozmetik kataloğu (owned) + kuşanılmış.
class InventoryState {
  const InventoryState({
    this.coins = 0,
    this.isPremium = false,
    this.premiumUntil,
    this.ownedCharacterIds = const {},
    this.equippedCharacterId,
    this.ownedCosmetics = const [],
    this.equippedFrame,
    this.equippedNameColor,
    this.equippedEffect,
    this.loading = false,
    this.loaded = false,
    this.busyCharacterId,
    this.error,
  });

  final int coins;
  final bool isPremium;

  /// Premium bitiş tarihi (ISO 8601 string), premium değilse null.
  final String? premiumUntil;

  /// Sahip olunan bireysel karakter id'leri (free + satın alınmış).
  final Set<String> ownedCharacterIds;

  /// Şu an kuşanılı karakter id'si (avatar_id).
  final String? equippedCharacterId;

  /// Sahip olunan kozmetikler (tüm slotlar karışık).
  final List<Cosmetic> ownedCosmetics;

  /// Kuşanılmış kozmetik id'leri (slot bazında). null → o slot boş.
  final String? equippedFrame;
  final String? equippedNameColor;
  final String? equippedEffect;

  final bool loading;
  final bool loaded;

  /// Şu an kuşanılıyor olan karakter id'si (kart spinner'ı için).
  final String? busyCharacterId;

  final String? error;

  /// Sahip olunan karakterlerin katalog nesneleri (görsel + ad).
  List<BiladaCharacter> get ownedCharacters =>
      kCharacters.where((c) => ownedCharacterIds.contains(c.id)).toList();

  /// Belirli slottaki sahip olunan kozmetikler.
  List<Cosmetic> ownedOfSlot(String slot) =>
      ownedCosmetics.where((c) => c.slot == slot).toList();

  /// Verilen slotta kuşanılmış id (yoksa null).
  String? equippedIdForSlot(String slot) {
    switch (slot) {
      case 'frame':
        return equippedFrame;
      case 'name_color':
        return equippedNameColor;
      case 'effect':
        return equippedEffect;
      default:
        return null;
    }
  }

  /// Hiç kozmetiğe sahip değil mi?
  bool get hasNoCosmetics => ownedCosmetics.isEmpty;

  InventoryState copyWith({
    int? coins,
    bool? isPremium,
    Object? premiumUntil = _s,
    Set<String>? ownedCharacterIds,
    Object? equippedCharacterId = _s,
    List<Cosmetic>? ownedCosmetics,
    Object? equippedFrame = _s,
    Object? equippedNameColor = _s,
    Object? equippedEffect = _s,
    bool? loading,
    bool? loaded,
    Object? busyCharacterId = _s,
    Object? error = _s,
  }) =>
      InventoryState(
        coins: coins ?? this.coins,
        isPremium: isPremium ?? this.isPremium,
        premiumUntil: identical(premiumUntil, _s) ? this.premiumUntil : premiumUntil as String?,
        ownedCharacterIds: ownedCharacterIds ?? this.ownedCharacterIds,
        equippedCharacterId: identical(equippedCharacterId, _s)
            ? this.equippedCharacterId
            : equippedCharacterId as String?,
        ownedCosmetics: ownedCosmetics ?? this.ownedCosmetics,
        equippedFrame: identical(equippedFrame, _s) ? this.equippedFrame : equippedFrame as String?,
        equippedNameColor: identical(equippedNameColor, _s) ? this.equippedNameColor : equippedNameColor as String?,
        equippedEffect: identical(equippedEffect, _s) ? this.equippedEffect : equippedEffect as String?,
        loading: loading ?? this.loading,
        loaded: loaded ?? this.loaded,
        busyCharacterId: identical(busyCharacterId, _s) ? this.busyCharacterId : busyCharacterId as String?,
        error: identical(error, _s) ? this.error : error as String?,
      );

  static const Object _s = Object();
}

class InventoryNotifier extends StateNotifier<InventoryState> {
  InventoryNotifier(this._ref) : super(const InventoryState()) {
    load();
  }

  final Ref _ref;

  /// Üç ucu paralel çeker, birleştirip state'e yazar. Biri başarısız olsa bile
  /// diğeri uygulanır (ör. kozmetik ucu çökse de bakiye/karakterler görünür).
  Future<void> load() async {
    state = state.copyWith(loading: true, error: null);

    final results = await Future.wait([
      _fetch('/api/store/characters'),
      _fetch('/api/store/inventory'),
      _fetch('/api/cosmetics'),
    ]);

    final chars = results[0];
    final inv = results[1];
    final cos = results[2];

    if (chars == null && inv == null && cos == null) {
      state = state.copyWith(loading: false, loaded: true, error: 'Envanter yüklenemedi');
      return;
    }

    var next = state;

    if (chars != null) {
      final raw = chars['characters'];
      final ownedIds = (raw is List ? raw : const [])
          .whereType<Map>()
          .where((c) => c['owned'] == true)
          .map((c) => c['id'].toString())
          .toSet();
      next = next.copyWith(
        coins: (chars['coins'] as num?)?.toInt() ?? next.coins,
        ownedCharacterIds: ownedIds,
        equippedCharacterId: chars['equipped']?.toString(),
      );
    }

    if (inv != null) {
      next = next.copyWith(
        coins: (inv['coins'] as num?)?.toInt() ?? next.coins,
        isPremium: inv['is_premium'] as bool? ?? next.isPremium,
        premiumUntil: inv['premium_until'] as String?,
      );
    }

    if (cos != null) {
      final catalogRaw = cos['catalog'];
      final owned = (catalogRaw is List ? catalogRaw : const [])
          .whereType<Map>()
          .map((e) => Cosmetic.fromJson(e.map((k, v) => MapEntry(k.toString(), v))))
          .where((c) => c.owned)
          .toList();
      final eq = cos['equipped'];
      final eqMap = eq is Map ? eq : const {};
      next = next.copyWith(
        ownedCosmetics: owned,
        equippedFrame: eqMap['frame'] as String?,
        equippedNameColor: eqMap['name_color'] as String?,
        equippedEffect: eqMap['effect'] as String?,
      );
    }

    state = next.copyWith(loading: false, loaded: true, error: null);
  }

  /// Bir karakteri kuşanır (`PATCH /api/users/me {avatar_id}`). Sunucu sahiplik
  /// kapısı uygular (sahip değilse 400). Başarıda kuşanılı durumu güncellenir ve
  /// auth provider'daki kullanıcı avatar_id'si tazelenir (ana ekran/profil).
  Future<bool> equipCharacter(String characterId) async {
    if (state.busyCharacterId != null) return false;
    // Zaten kuşanılıysa işlem yapma.
    if (state.equippedCharacterId == characterId) return true;
    state = state.copyWith(busyCharacterId: characterId, error: null);
    try {
      await ApiClient.instance.patch('/api/users/me', body: {'avatar_id': characterId});
      state = state.copyWith(
        busyCharacterId: null,
        equippedCharacterId: characterId,
      );
      try {
        await _ref.read(authProvider.notifier).refreshUser();
      } catch (_) {}
      return true;
    } catch (e) {
      final msg = e.toString().contains('400')
          ? 'Bu karaktere sahip değilsin.'
          : 'Kuşanma başarısız, tekrar dene.';
      state = state.copyWith(busyCharacterId: null, error: msg);
      return false;
    }
  }

  Future<Map<String, dynamic>?> _fetch(String path) async {
    try {
      return await ApiClient.instance.get(path);
    } catch (_) {
      return null;
    }
  }
}

final inventoryProvider =
    StateNotifierProvider<InventoryNotifier, InventoryState>((ref) => InventoryNotifier(ref));
