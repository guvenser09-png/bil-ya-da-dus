import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:quizroyale/features/auth/providers/auth_provider.dart';
import 'package:quizroyale/features/store/services/store_api.dart';
import 'package:quizroyale/shared/characters.dart';

// İLK LANSMAN — TAMAMEN ÜCRETSİZ: gerçek-para (IAP) akışı rafa kaldırıldı.
// purchase_service.dart dosyası yerinde duruyor ama buradan ÇAĞRILMIYOR
// (registerCatalog / fetchLocalizedPrices / buy / restore devre dışı).
// Aşama 3'te geri açmak için git geçmişindeki bu dosyaya bakınız.

/// Karakter nadirliği. Backend `rarity` alanı ile birebir aynı (free → legendary).
/// Sıralama, nadirlik arttıkça daha gösterişli stil için kullanılır.
enum CharacterRarity { free, common, rare, epic, legendary }

CharacterRarity _rarityFrom(String? raw) {
  switch (raw) {
    case 'common':
      return CharacterRarity.common;
    case 'rare':
      return CharacterRarity.rare;
    case 'epic':
      return CharacterRarity.epic;
    case 'legendary':
      return CharacterRarity.legendary;
    case 'free':
    default:
      return CharacterRarity.free;
  }
}

/// Mağazada gösterilen tek bir karakter (otorite: backend).
///
/// Fiyat/nadirlik/sahiplik/kuşanılı durumu BACKEND'den gelir; görsel ve ad
/// `characters.dart` (imageUrlFor/characterById) ile id üzerinden eşlenir.
class StoreCharacter {
  const StoreCharacter({
    required this.id,
    required this.name,
    required this.priceCoins,
    required this.rarity,
    required this.free,
    required this.owned,
    required this.equipped,
  });

  final String id;
  final String name;
  final int priceCoins;
  final CharacterRarity rarity;
  final bool free;
  final bool owned;
  final bool equipped;

  /// id üzerinden 3D görsel URL'i (CDN). Katalogda yoksa null.
  String? get imageUrl => imageUrlFor(id);

  StoreCharacter copyWith({bool? owned, bool? equipped}) => StoreCharacter(
        id: id,
        name: name,
        priceCoins: priceCoins,
        rarity: rarity,
        free: free,
        owned: owned ?? this.owned,
        equipped: equipped ?? this.equipped,
      );

  factory StoreCharacter.fromJson(Map<String, dynamic> j) {
    final id = j['id']?.toString() ?? '';
    return StoreCharacter(
      id: id,
      name: j['name']?.toString() ?? characterById(id)?.name ?? id,
      priceCoins: (j['price_coins'] as num?)?.toInt() ?? 0,
      rarity: _rarityFrom(j['rarity']?.toString()),
      free: j['free'] == true,
      owned: j['owned'] == true,
      equipped: j['equipped'] == true,
    );
  }
}

/// Mağaza durumu: altın bakiyesi, karakter kataloğu (sahiplik + kuşanılı).
///
/// İLK LANSMAN: gerçek-para ürün kataloğu ([products], [livePrices],
/// [productsOfType], [priceFor]) doldurulmuyor — alanlar Aşama 3'te geri
/// açılış için yerinde bekliyor. [coins], [isPremium], [isPackUnlocked],
/// [isCharacterUnlocked], [ownedCharacterIds] korunur (profil ekranları
/// bunları kullanır).
class StoreState {
  const StoreState({
    this.coins = 0,
    this.equippedCharacterId,
    this.characters = const [],
    this.isPremium = false,
    this.premiumUntil,
    this.products = const [],
    this.livePrices = const {},
    this.buyingCharacterId,
    this.equipBusyId,
    this.loading = false,
    this.error,
  });

  /// Güncel altın bakiyesi.
  final int coins;

  /// Şu an kuşanılı karakter id'si (avatar_id).
  final String? equippedCharacterId;

  /// Karakter kataloğu — ucuzdan pahalıya sıralı (backend sırasını korur).
  final List<StoreCharacter> characters;

  final bool isPremium;
  final String? premiumUntil;

  /// Gerçek-para ürün kataloğu (gold_* + premium_*; ham product map'leri).
  final List<Map<String, dynamic>> products;

  /// Mağazadan (StoreKit/Play) gelen yerelleştirilmiş fiyatlar:
  /// {katalog product_id → "₺29,99"}. Web/dev'de boş; UI price_display'e düşer.
  final Map<String, String> livePrices;

  /// Belirli ürün için gösterilecek fiyat: önce StoreKit yerel fiyatı, yoksa
  /// katalog `price_display`. UI bunu kullanır (App Store ile tutarlılık).
  String priceFor(Map<String, dynamic> product) {
    final id = product['product_id']?.toString();
    if (id != null && livePrices[id] != null) return livePrices[id]!;
    return product['price_display']?.toString() ?? '';
  }

  /// Şu an satın alınıyor olan karakter id'si (buton spinner'ı için).
  final String? buyingCharacterId;

  /// Şu an kuşanılıyor olan karakter id'si (buton spinner'ı için).
  final String? equipBusyId;

  final bool loading;
  final String? error;

  static const Object _sentinel = Object();

  StoreState copyWith({
    int? coins,
    Object? equippedCharacterId = _sentinel,
    List<StoreCharacter>? characters,
    bool? isPremium,
    String? premiumUntil,
    List<Map<String, dynamic>>? products,
    Map<String, String>? livePrices,
    Object? buyingCharacterId = _sentinel,
    Object? equipBusyId = _sentinel,
    bool? loading,
    Object? error = _sentinel,
  }) =>
      StoreState(
        coins: coins ?? this.coins,
        equippedCharacterId: identical(equippedCharacterId, _sentinel)
            ? this.equippedCharacterId
            : equippedCharacterId as String?,
        characters: characters ?? this.characters,
        isPremium: isPremium ?? this.isPremium,
        premiumUntil: premiumUntil ?? this.premiumUntil,
        products: products ?? this.products,
        livePrices: livePrices ?? this.livePrices,
        buyingCharacterId: identical(buyingCharacterId, _sentinel)
            ? this.buyingCharacterId
            : buyingCharacterId as String?,
        equipBusyId: identical(equipBusyId, _sentinel)
            ? this.equipBusyId
            : equipBusyId as String?,
        loading: loading ?? this.loading,
        error: identical(error, _sentinel) ? this.error : error as String?,
      );

  /// Sahip olunan tüm karakter id'leri (free dahil — backend `owned` der).
  Set<String> get ownedCharacterIds =>
      characters.where((c) => c.owned).map((c) => c.id).toSet();

  /// Bir karakter (id) oyuncu için açık mı? (free ya da satın alınmış)
  bool isCharacterUnlocked(String characterId) {
    for (final c in characters) {
      if (c.id == characterId) return c.owned;
    }
    return false;
  }

  /// Bir paket "açık" sayılır mı? (paketteki tüm karakterler sahip)
  /// Eski profil ekranı bunu kullanır; per-karakter sahipliğe göre türetilir.
  bool isPackUnlocked(String packId) {
    final ids = kCharacters
        .where((c) => c.packId == packId)
        .map((c) => c.id)
        .toList();
    if (ids.isEmpty) return false;
    return ids.every(isCharacterUnlocked);
  }

  /// Tip ('coins' | 'premium') bazında gerçek-para ürünleri.
  List<Map<String, dynamic>> productsOfType(String type) =>
      products.where((p) => p['type'] == type).toList();
}

class StoreNotifier extends StateNotifier<StoreState> {
  StoreNotifier(this._ref) : super(const StoreState()) {
    load();
  }

  final Ref _ref;
  final StoreApi _api = StoreApi.instance;

  /// Karakter kataloğunu yükler.
  ///
  /// İLK LANSMAN: gerçek-para katalog (getCatalog) + StoreKit/Play başlatma
  /// (registerCatalog / fetchLocalizedPrices) ÇAĞRILMIYOR — mağazada yalnızca
  /// altınla açılan karakterler var. Aşama 3'te git geçmişinden geri alınacak.
  Future<void> load() async {
    state = state.copyWith(loading: true, error: null);
    try {
      // Karakter kataloğu (altın fiyatları + sahiplik) — auth gerekir.
      var next = _applyCharacters(
          state.copyWith(loading: false), await _api.getCharacters());

      // Altın bakiyesi için envanter — başarısız olursa sessizce geç.
      try {
        next = _applyInventory(next, await _api.getInventory());
      } catch (_) {}

      state = next;
    } catch (e) {
      state = state.copyWith(
        loading: false,
        error: 'Mağaza yüklenemedi. Lütfen tekrar deneyin.',
      );
    }
  }

  /// Yalnızca karakter kataloğunu tazeler (satın alma/kuşanma sonrası).
  Future<void> loadCharacters() async {
    try {
      state = _applyCharacters(state, await _api.getCharacters());
    } catch (_) {}
  }

  /// Bir karakteri ALTIN ile satın alır. Başarıda bakiye + sahiplik güncellenir.
  /// Yetersiz altın / geçersizde `false` döner ve [StoreState.error] set edilir.
  Future<bool> buyCharacter(String characterId) async {
    if (state.buyingCharacterId != null) return false;
    state = state.copyWith(buyingCharacterId: characterId, error: null);
    try {
      final r = await _api.buyCharacter(characterId);
      final coins = (r['coins'] as num?)?.toInt();
      final owned = r['bought'] == true || r['already_owned'] == true;
      state = state.copyWith(
        buyingCharacterId: null,
        coins: coins ?? state.coins,
        characters: owned
            ? state.characters
                .map((c) => c.id == characterId ? c.copyWith(owned: true) : c)
                .toList()
            : state.characters,
      );
      // Bakiye TEK gerçek kaynaktan (authProvider.user.coins) da tazelensin —
      // home/leaderboard üst barındaki CoinPill satın alma sonrası güncellensin.
      try {
        await _ref.read(authProvider.notifier).refreshUser();
      } catch (_) {}
      return owned;
    } catch (e) {
      final msg = e.toString().contains('400')
          ? 'Yetersiz altın'
          : 'Satın alma başarısız, tekrar dene.';
      state = state.copyWith(buyingCharacterId: null, error: msg);
      return false;
    }
  }

  /// Bir karakteri kuşanır (PATCH /me). Başarıda kuşanılı durumu güncellenir ve
  /// auth provider'daki kullanıcı avatar_id'si tazelenir (profil/ana ekran
  /// yansısın). Sahip değilse backend 400 döner → `false`.
  Future<bool> equipCharacter(String characterId) async {
    if (state.equipBusyId != null) return false;
    state = state.copyWith(equipBusyId: characterId, error: null);
    try {
      await _api.equipCharacter(characterId);
      state = state.copyWith(
        equipBusyId: null,
        equippedCharacterId: characterId,
        characters: state.characters
            .map((c) => c.copyWith(equipped: c.id == characterId))
            .toList(),
      );
      // Kullanıcı avatarını uygulama genelinde tazele.
      try {
        await _ref.read(authProvider.notifier).refreshUser();
      } catch (_) {}
      return true;
    } catch (e) {
      final msg = e.toString().contains('400')
          ? 'Bu karaktere sahip değilsin.'
          : 'Kuşanma başarısız, tekrar dene.';
      state = state.copyWith(equipBusyId: null, error: msg);
      return false;
    }
  }

  // NOT (İLK LANSMAN): gerçek-para satın alma (buyProduct) ve geri yükleme
  // (restore) metotları rafa kaldırıldı — Aşama 3'te git geçmişinden geri
  // alınacak. Altınla karakter satın alma (buyCharacter) aynen çalışır.

  /// `GET /api/store/characters` cevabını state'e uygular.
  StoreState _applyCharacters(StoreState base, Map<String, dynamic> res) {
    final raw = res['characters'];
    final list = raw is List
        ? raw
            .whereType<Map>()
            .map((e) => StoreCharacter.fromJson(
                e.map((k, v) => MapEntry(k.toString(), v))))
            .toList()
        : <StoreCharacter>[];
    return base.copyWith(
      coins: (res['coins'] as num?)?.toInt() ?? base.coins,
      equippedCharacterId:
          res['equipped']?.toString() ?? base.equippedCharacterId,
      characters: list,
    );
  }

  /// Envanter map'ini state'e uygular (coins/premium).
  StoreState _applyInventory(StoreState base, Map<String, dynamic> inv) {
    return base.copyWith(
      coins: (inv['coins'] as num?)?.toInt() ?? base.coins,
      isPremium: inv['is_premium'] as bool? ?? base.isPremium,
      premiumUntil: inv['premium_until'] as String?,
    );
  }
}

final storeProvider =
    StateNotifierProvider<StoreNotifier, StoreState>((ref) => StoreNotifier(ref));
