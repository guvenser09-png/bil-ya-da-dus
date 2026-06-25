import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

/// WebSocket istemcisi (sağlam yeniden yazım).
///
/// TASARIM:
/// - TEKİL DEĞİL: her ekran (lobi/oyun) KENDİ `WsClient()` örneğini açar.
///   Böylece lobi→oyun geçişinde kanallar birbirini bozmaz. `instance` yalnızca
///   geriye dönük (lobi) için durur.
/// - GÖNDERİM ASLA DÜŞMEZ: Önceki sürüm gönderimi `channel.ready` future'ına
///   bağlıyordu; web'de bu future bazen tamamlanmıyor → `_isOpen` hep false →
///   cevap sonsuza dek kuyrukta kalıp HİÇ gönderilmiyordu (kritik bug). Yeni
///   sürümde soketin açık olduğunu ÜÇ yoldan anlarız: (1) `channel.ready`,
///   (2) İLK gelen mesaj (mesaj geldiyse soket kesin açıktır), (3) doğrudan
///   `sink.add` denemesi. Açık değilken gelen gönderimler kuyruğa alınır ve
///   bunlardan herhangi biri açılışı tespit edince anında boşaltılır.
class WsClient {
  WsClient();

  /// Geriye dönük tekil (lobi kullanır). Oyun KENDİ örneğini açar.
  static final WsClient instance = WsClient();

  WebSocketChannel? _channel;
  final _controller = StreamController<Map<String, dynamic>>.broadcast();
  String? _lastUrl;
  bool _disposed = false;
  int _attempts = 0;
  static const int _maxAttempts = 3;

  final List<String> _pendingSends = [];
  bool _isOpen = false;

  Stream<Map<String, dynamic>> get messages => _controller.stream;
  bool get isConnected => _channel != null;

  /// Kopma SONRASI yeniden bağlanınca çağrılır (ilk connect'te değil).
  void Function()? onReconnect;

  static bool _isPermanentClose(int? code) =>
      code != null && code >= 4001 && code <= 4010;

  /// Uygulama tarafından başlatılan taze bağlantı.
  Future<void> connect(String url) async {
    _lastUrl = url;
    _disposed = false;
    _attempts = 0;
    onReconnect = null;
    await _open(url);
  }

  Future<void> _open(String url) async {
    _isOpen = false;
    try {
      await _channel?.sink.close();
    } catch (_) {}

    final channel = WebSocketChannel.connect(Uri.parse(url));
    _channel = channel;

    channel.stream.listen(
      (data) {
        _attempts = 0;
        // İLK mesaj = soket kesinlikle açık. ready beklemeden açılışı işaretle
        // ve bekleyen gönderimleri boşalt (web'de ready hiç gelmeyebilir).
        if (_channel == channel && !_isOpen) {
          _isOpen = true;
          _flushPending();
        }
        try {
          final msg = jsonDecode(data as String) as Map<String, dynamic>;
          if (!_controller.isClosed) _controller.add(msg);
        } catch (_) {}
      },
      onDone: () {
        if (_lastUrl != url || _disposed) return;
        _isOpen = false;
        final code = _channel?.closeCode;
        if (_isPermanentClose(code)) {
          _emitError(code, _channel?.closeReason ?? 'Bağlantı reddedildi.');
        } else {
          _retry(url);
        }
      },
      onError: (_) {
        if (_lastUrl != url || _disposed) return;
        _isOpen = false;
        _retry(url);
      },
      cancelOnError: false,
    );

    // İkinci yol: ready tamamlanırsa da açılışı işaretle (lobi'nin "join"i için
    // önemli — lobi mesaj almadan ÖNCE göndermek zorunda). ready bazı web
    // ortamlarında gelmeyebilir; o yüzden tek başına buna güvenmiyoruz.
    unawaited(_markOpenWhenReady(channel));
  }

  Future<void> _markOpenWhenReady(WebSocketChannel channel) async {
    try {
      await channel.ready;
      if (_disposed || _channel != channel) return;
      if (!_isOpen) {
        _isOpen = true;
        _flushPending();
      }
    } catch (e) {
      if (kDebugMode) debugPrint('WsClient.ready failed: $e');
    }
  }

  void _flushPending() {
    if (_channel == null || _pendingSends.isEmpty) return;
    final queued = List<String>.from(_pendingSends);
    _pendingSends.clear();
    for (final payload in queued) {
      try {
        _channel!.sink.add(payload);
      } catch (e) {
        if (kDebugMode) debugPrint('WsClient flush failed: $e');
        _pendingSends.add(payload); // tekrar kuyrukla
      }
    }
  }

  void _retry(String url) {
    _attempts++;
    if (_attempts > _maxAttempts) {
      _emitError(4000, 'Oyuna bağlanılamadı.');
      return;
    }
    final delay = Duration(seconds: _attempts);
    Future.delayed(delay, () {
      if (_disposed || _lastUrl != url) return;
      _open(url);
      final cb = onReconnect;
      if (cb != null) {
        Future.delayed(const Duration(milliseconds: 400), () {
          if (!_disposed && _lastUrl == url) cb();
        });
      }
    });
  }

  void _emitError(int? code, String reason) {
    if (!_controller.isClosed) {
      _controller.add({'type': 'ws_error', 'code': code ?? 4000, 'reason': reason});
    }
  }

  /// Mesaj gönder. Soket açıksa DOĞRUDAN gider; değilse kuyruğa alınır ve
  /// açılış tespit edilince (ilk mesaj / ready) boşaltılır. Hiçbir koşulda
  /// sessizce kaybolmaz.
  void send(Map<String, dynamic> message) {
    final payload = jsonEncode(message);
    final channel = _channel;
    if (channel == null) {
      _pendingSends.add(payload);
      return;
    }
    // Açık olduğunu bilsek de bilmesek de doğrudan denemekte sakınca yok:
    // başarılıysa gitti, değilse kuyruğa alıp açılışta tekrar göndereceğiz.
    try {
      channel.sink.add(payload);
    } catch (e) {
      if (kDebugMode) debugPrint('WsClient.send queued (not open yet): $e');
      _pendingSends.add(payload);
    }
  }

  Future<void> reconnect({int maxAttempts = 3}) async {
    if (_lastUrl == null) return;
    await connect(_lastUrl!);
  }

  void disconnect() {
    _disposed = true;
    _isOpen = false;
    _pendingSends.clear();
    try {
      _channel?.sink.close();
    } catch (_) {}
    _channel = null;
  }

  void dispose() {
    disconnect();
    _controller.close();
  }
}
