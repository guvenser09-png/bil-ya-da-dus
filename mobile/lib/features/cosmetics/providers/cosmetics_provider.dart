import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:quizroyale/core/network/api_client.dart';

/// Tek bir kozmetik öğesi (katalog girdisi).
class Cosmetic {
  const Cosmetic({
    required this.id,
    required this.slot,
    required this.name,
    required this.priceCoins,
    this.colorHex,
    this.owned = false,
  });

  final String id;

  /// 'frame' | 'name_color' | 'effect'
  final String slot;
  final String name;
  final int priceCoins;

  /// name_color slotu için renk (örn "#FF479C"); diğerleri için null olabilir.
  final String? colorHex;
  final bool owned;

  factory Cosmetic.fromJson(Map<String, dynamic> j) => Cosmetic(
        id: j['id'].toString(),
        slot: j['slot']?.toString() ?? 'frame',
        name: j['name']?.toString() ?? '',
        priceCoins: (j['price_coins'] as num?)?.toInt() ?? 0,
        colorHex: j['color_hex'] as String?,
        owned: j['owned'] as bool? ?? false,
      );

  Cosmetic copyWith({bool? owned}) => Cosmetic(
        id: id,
        slot: slot,
        name: name,
        priceCoins: priceCoins,
        colorHex: colorHex,
        owned: owned ?? this.owned,
      );

  /// colorHex'i Flutter [Color]'a çevirir (geçersizse null).
  Color? get color => parseHexColor(colorHex);
}

/// Bir çerçeve kozmetik id'sini [PlayerAvatar.frame] anahtarına çevirir.
/// Backend id'leri `frame_gold` / `frame-neon` gibi olabilir; önek atılır.
/// Bilinen anahtarlar: gold/neon/fire/ice/royal. Diğerleri olduğu gibi geçer
/// (PlayerAvatar bilinmeyen anahtarda çerçeve çizmez → güvenli).
String? frameKeyFromId(String? cosmeticId) {
  if (cosmeticId == null) return null;
  var k = cosmeticId.toLowerCase();
  k = k.replaceFirst(RegExp(r'^frame[_-]'), '');
  return k;
}

/// "#RRGGBB" / "RRGGBB" / "#AARRGGBB" → Color. Geçersizse null.
Color? parseHexColor(String? hex) {
  if (hex == null) return null;
  var h = hex.replaceFirst('#', '').trim();
  if (h.length == 6) h = 'FF$h';
  if (h.length != 8) return null;
  final v = int.tryParse(h, radix: 16);
  return v == null ? null : Color(v);
}

class CosmeticsState {
  const CosmeticsState({
    this.catalog = const [],
    this.equippedFrame,
    this.equippedNameColor,
    this.equippedEffect,
    this.coins = 0,
    this.loading = false,
    this.busyId,
    this.loaded = false,
    this.error,
  });

  final List<Cosmetic> catalog;

  /// Kuşanılmış öğe id'leri (slot bazında). null → o slot boş.
  final String? equippedFrame;
  final String? equippedNameColor;
  final String? equippedEffect;

  final int coins;
  final bool loading;

  /// Şu an satın alınıyor/kuşanılıyor olan öğe id'si (buton spinner'ı için).
  final String? busyId;
  final bool loaded;
  final String? error;

  CosmeticsState copyWith({
    List<Cosmetic>? catalog,
    Object? equippedFrame = _s,
    Object? equippedNameColor = _s,
    Object? equippedEffect = _s,
    int? coins,
    bool? loading,
    Object? busyId = _s,
    bool? loaded,
    Object? error = _s,
  }) =>
      CosmeticsState(
        catalog: catalog ?? this.catalog,
        equippedFrame: identical(equippedFrame, _s) ? this.equippedFrame : equippedFrame as String?,
        equippedNameColor: identical(equippedNameColor, _s) ? this.equippedNameColor : equippedNameColor as String?,
        equippedEffect: identical(equippedEffect, _s) ? this.equippedEffect : equippedEffect as String?,
        coins: coins ?? this.coins,
        loading: loading ?? this.loading,
        busyId: identical(busyId, _s) ? this.busyId : busyId as String?,
        loaded: loaded ?? this.loaded,
        error: identical(error, _s) ? this.error : error as String?,
      );

  static const Object _s = Object();

  List<Cosmetic> ofSlot(String slot) => catalog.where((c) => c.slot == slot).toList();

  /// Belirli slotta SAHİP OLUNAN öğeler (dolap).
  List<Cosmetic> ownedOfSlot(String slot) =>
      catalog.where((c) => c.slot == slot && c.owned).toList();

  /// Belirli slotta sahip OLUNMAYAN öğeler (mağaza).
  List<Cosmetic> shopOfSlot(String slot) =>
      catalog.where((c) => c.slot == slot && !c.owned).toList();

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

  Cosmetic? byId(String? id) {
    if (id == null) return null;
    for (final c in catalog) {
      if (c.id == id) return c;
    }
    return null;
  }
}

class CosmeticsNotifier extends StateNotifier<CosmeticsState> {
  CosmeticsNotifier() : super(const CosmeticsState()) {
    load();
  }

  Future<void> load() async {
    state = state.copyWith(loading: true, error: null);
    try {
      final r = await ApiClient.instance.get('/api/cosmetics');
      state = _applyResponse(r).copyWith(loading: false, loaded: true);
    } catch (_) {
      state = state.copyWith(loading: false, loaded: true, error: 'Kozmetikler yüklenemedi');
    }
  }

  /// Coin ile satın alır. Başarıda true; yetersiz coin/zaten sahip → false.
  Future<bool> buy(String cosmeticId) async {
    state = state.copyWith(busyId: cosmeticId, error: null);
    try {
      final r = await ApiClient.instance.post('/api/cosmetics/buy', body: {'cosmetic_id': cosmeticId});
      final owned = r['owned'] as bool? ?? true;
      final coins = (r['coins'] as num?)?.toInt() ?? state.coins;
      final catalog = state.catalog
          .map((c) => c.id == cosmeticId ? c.copyWith(owned: owned) : c)
          .toList();
      state = state.copyWith(catalog: catalog, coins: coins, busyId: null);
      return owned;
    } catch (e) {
      // 400 → yetersiz coin ya da zaten sahip.
      state = state.copyWith(busyId: null, error: _errorText(e));
      return false;
    }
  }

  /// Bir slotu kuşandırır (cosmeticId null → çıkarır).
  Future<bool> equip(String slot, String? cosmeticId) async {
    state = state.copyWith(busyId: cosmeticId ?? '__unequip_$slot', error: null);
    try {
      final r = await ApiClient.instance
          .post('/api/cosmetics/equip', body: {'slot': slot, 'cosmetic_id': cosmeticId});
      final eq = r['equipped'] as Map<String, dynamic>? ?? {};
      state = state.copyWith(
        equippedFrame: eq['frame'] as String?,
        equippedNameColor: eq['name_color'] as String?,
        equippedEffect: eq['effect'] as String?,
        busyId: null,
      );
      return true;
    } catch (e) {
      state = state.copyWith(busyId: null, error: _errorText(e));
      return false;
    }
  }

  CosmeticsState _applyResponse(Map<String, dynamic> r) {
    final catalogRaw = r['catalog'] as List? ?? [];
    final catalog = catalogRaw
        .whereType<Map<String, dynamic>>()
        .map(Cosmetic.fromJson)
        .toList();
    final eq = r['equipped'] as Map<String, dynamic>? ?? {};
    return state.copyWith(
      catalog: catalog,
      equippedFrame: eq['frame'] as String?,
      equippedNameColor: eq['name_color'] as String?,
      equippedEffect: eq['effect'] as String?,
      coins: (r['coins'] as num?)?.toInt() ?? state.coins,
    );
  }

  String _errorText(Object e) {
    final s = e.toString();
    if (s.contains('400')) return 'İşlem yapılamadı (yetersiz altın ya da zaten sahipsin).';
    return 'Bir hata oluştu, tekrar deneyin.';
  }
}

final cosmeticsProvider =
    StateNotifierProvider<CosmeticsNotifier, CosmeticsState>((_) => CosmeticsNotifier());
