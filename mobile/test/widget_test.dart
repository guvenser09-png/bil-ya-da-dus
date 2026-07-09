// Temel duman testi.
//
// Eski Flutter şablon testi var olmayan MyApp sınıfına ve sayaç arayüzüne
// referans veriyordu (analyze hatası). Uygulamanın kök widget'ı BiladaApp;
// tam uygulamayı pump'lamak ağ/secure-storage bağımlılıkları gerektirdiğinden
// burada yalnızca hafif bir kurulum duman testi tutuyoruz.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('MaterialApp kurulum duman testi', (WidgetTester tester) async {
    await tester.pumpWidget(
      const MaterialApp(home: Scaffold(body: Text('Bil ya da Düş'))),
    );
    expect(find.text('Bil ya da Düş'), findsOneWidget);
  });
}
