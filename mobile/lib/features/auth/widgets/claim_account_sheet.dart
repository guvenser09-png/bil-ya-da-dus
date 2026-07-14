import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:quizroyale/core/theme/app_theme.dart';
import 'package:quizroyale/features/auth/providers/auth_provider.dart';
import 'package:quizroyale/shared/widgets/bilada_ui.dart';

/// PAYLAŞILAN misafir→kayıtlı dönüşüm formu (POST /api/auth/claim).
///
/// Tek kaynak: profil bandı, sıralama ekranındaki davet ve maç sonu daveti
/// AYNI formu açar — akış, metinler ve hata davranışı her yerde birebir aynı.
///
/// SÜRTÜNME EN AZ:
///  • Sadece 2 zorunlu alan: e-posta + şifre. Kullanıcı adı OPSİYONEL ve
///    kapalı (mevcut ad korunur; isteyen "Kullanıcı adını değiştir" ile açar).
///  • autofillHints → iOS/Android şifre yöneticisi alanları kendi doldurur.
///  • Hata SHEET İÇİNDE, alanların üstünde görünür (snackbar klavyenin/sheet'in
///    altında kaybolmaz); form kapanmaz, yazılanlar durur.
///
/// Başarıda: kutlama diyaloğu + tek dokunuşla sıralamaya gidiş.
/// Döner: hesap kalıcılaştıysa true.
Future<bool> showClaimAccountSheet(
  BuildContext context, {
  String? currentUsername,
  String? title,
  String? subtitle,
}) async {
  final claimed = await showModalBottomSheet<bool>(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    builder: (_) => ClaimAccountSheet(
      currentUsername: currentUsername ?? '',
      title: title,
      subtitle: subtitle,
    ),
  );
  if (claimed != true) return false;
  if (context.mounted) await _showClaimSuccessDialog(context);
  return true;
}

/// 🏅 Kutlama — kaydın KARŞILIĞINI anında göster: "artık sıralamadasın".
/// Birincil buton doğrudan sıralamaya götürür (vaadin teslim edildiği yer).
Future<void> _showClaimSuccessDialog(BuildContext context) {
  return showDialog<void>(
    context: context,
    builder: (dialogContext) => AlertDialog(
      backgroundColor: AppTheme.cSurfaceContainerLow,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
      // Butonlar bilinçli olarak `actions` yerine içerikte: ChunkyButton
      // tam genişlik ister (expand → double.infinity), AlertDialog'un
      // OverflowBar'ında bu taşma riski taşır. İçerikte genişlik nettir.
      content: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Text('🏅', style: TextStyle(fontSize: 52)),
          const SizedBox(height: 12),
          Text('Artık sıralamadasın!',
              textAlign: TextAlign.center, style: BiladaText.headline(size: 20)),
          const SizedBox(height: 8),
          Text(
            'Hesabın kaydedildi. Puanların, seviyen ve altınların güvende — '
            'bundan sonra her maç seni tabloda yukarı taşıyacak.',
            textAlign: TextAlign.center,
            style: BiladaText.body(color: AppTheme.cOnSurfaceVariant, size: 13),
          ),
          const SizedBox(height: 20),
          // Vaadin teslim edildiği yer: tek dokunuşla sıralamaya.
          ChunkyButton(
            height: 52,
            color: AppTheme.gold,
            foreground: AppTheme.cOnPrimaryContainer,
            shadowColor: const Color(0xFF8A6A00),
            onPressed: () {
              Navigator.of(dialogContext).pop();
              dialogContext.go('/leaderboard');
            },
            child: const Text('SIRALAMAMI GÖR'),
          ),
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(),
            child: Text('Daha sonra',
                style: BiladaText.label(color: AppTheme.cOnSurfaceVariant, size: 12)),
          ),
        ],
      ),
    ),
  );
}

/// Misafir hesabı kalıcılaştırma formu. Doğrudan kullanmak yerine
/// [showClaimAccountSheet] çağır (kutlama + yönlendirme onda).
class ClaimAccountSheet extends ConsumerStatefulWidget {
  const ClaimAccountSheet({
    super.key,
    required this.currentUsername,
    this.title,
    this.subtitle,
  });

  final String currentUsername;

  /// Davetin geldiği bağlama göre başlık/alt başlık (maç sonu, sıralama, profil).
  final String? title;
  final String? subtitle;

  @override
  ConsumerState<ClaimAccountSheet> createState() => _ClaimAccountSheetState();
}

class _ClaimAccountSheetState extends ConsumerState<ClaimAccountSheet> {
  final _formKey = GlobalKey<FormState>();
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  final _usernameController = TextEditingController();

  bool _obscurePassword = true;
  bool _saving = false;

  /// Kullanıcı adı alanı VARSAYILAN OLARAK KAPALI — sürtünmeyi azaltır.
  /// Açılmazsa mevcut (otomatik verilmiş) ad korunur; backend username=null'ı
  /// "adı değiştirme" olarak yorumlar.
  bool _showUsernameField = false;

  /// Sunucudan dönen hata (ör. "Bu e-posta adresi zaten kayıtlı.") — form
  /// kapanmadan, alanların üstünde gösterilir.
  String? _serverError;

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    _usernameController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _saving = true;
      _serverError = null;
    });

    final ok = await ref.read(authProvider.notifier).claimAccount(
          email: _emailController.text,
          password: _passwordController.text,
          username: _showUsernameField && _usernameController.text.trim().isNotEmpty
              ? _usernameController.text
              : null,
        );
    if (!mounted) return;

    if (ok) {
      // Kapanış değeri true → çağıran kutlamayı gösterir.
      Navigator.of(context).pop(true);
      return;
    }
    setState(() {
      _saving = false;
      _serverError =
          ref.read(authProvider).error ?? 'Kaydedilemedi — lütfen tekrar dene.';
    });
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
        child: SingleChildScrollView(
          child: AutofillGroup(
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
                  Text(widget.title ?? 'Sıralamaya gir', style: BiladaText.headline(size: 20)),
                  const SizedBox(height: 6),
                  Text(
                    widget.subtitle ??
                        'E-posta ve şifre ekle — puanların sıralamada görünsün, '
                            'seviyen ve altınların bu hesapta kalıcı olsun.',
                    style: BiladaText.body(color: AppTheme.cOnSurfaceVariant, size: 13),
                  ),
                  // Sunucu hatası — net, alanların hemen üstünde.
                  if (_serverError != null) ...[
                    const SizedBox(height: 14),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                      decoration: BoxDecoration(
                        color: AppTheme.cError.withValues(alpha: 0.12),
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(color: AppTheme.cError.withValues(alpha: 0.5)),
                      ),
                      child: Row(
                        children: [
                          const Icon(Icons.error_outline_rounded,
                              color: AppTheme.cError, size: 18),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(_serverError!,
                                style: BiladaText.label(color: AppTheme.cError, size: 12)),
                          ),
                        ],
                      ),
                    ),
                  ],
                  const SizedBox(height: 20),
                  TextFormField(
                    controller: _emailController,
                    enabled: !_saving,
                    keyboardType: TextInputType.emailAddress,
                    textInputAction: TextInputAction.next,
                    autofillHints: const [AutofillHints.email],
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
                    autofillHints: const [AutofillHints.newPassword],
                    textInputAction: TextInputAction.done,
                    onFieldSubmitted: (_) => _saving ? null : _submit(),
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
                  // Kullanıcı adı: OPSİYONEL ve kapalı. Açılmazsa mevcut ad kalır.
                  if (!_showUsernameField) ...[
                    const SizedBox(height: 6),
                    Align(
                      alignment: Alignment.centerLeft,
                      child: TextButton(
                        onPressed: _saving
                            ? null
                            : () => setState(() => _showUsernameField = true),
                        style: TextButton.styleFrom(
                          padding: const EdgeInsets.symmetric(vertical: 4),
                          minimumSize: Size.zero,
                          tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                        ),
                        child: Text(
                          widget.currentUsername.isEmpty
                              ? 'Kullanıcı adını değiştir'
                              : 'Kullanıcı adın: ${widget.currentUsername} — değiştir',
                          style: BiladaText.label(color: AppTheme.cTertiary, size: 12),
                        ),
                      ),
                    ),
                  ] else ...[
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
                        if (val.isEmpty) return null; // opsiyonel — mevcut ad kalır
                        if (val.length < 3) return 'En az 3 karakter olmalı';
                        if (!RegExp(r'^[a-zA-Z0-9_.]+$').hasMatch(val)) {
                          return 'Sadece harf, rakam, _ ve . kullanılabilir';
                        }
                        return null;
                      },
                    ),
                  ],
                  const SizedBox(height: 20),
                  ChunkyButton(
                    height: 56,
                    color: AppTheme.gold,
                    foreground: AppTheme.cOnPrimaryContainer,
                    shadowColor: const Color(0xFF8A6A00),
                    onPressed: _saving ? null : _submit,
                    child: _saving
                        ? const SizedBox(
                            width: 20,
                            height: 20,
                            child: CircularProgressIndicator(
                                strokeWidth: 2, color: AppTheme.cOnPrimaryContainer),
                          )
                        : const Text('SIRALAMAYA GİR'),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'İlerlemenin hiçbiri kaybolmaz — aynı hesap, artık kalıcı.',
                    textAlign: TextAlign.center,
                    style: BiladaText.label(color: AppTheme.cOutline, size: 11),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
