import 'package:flutter_test/flutter_test.dart';

import 'package:safecircle/main.dart';

void main() {
  testWidgets('SafeCircle app renders and displays title', (WidgetTester tester) async {
    // Build our app and trigger a frame.
    await tester.pumpWidget(const SafeCircleApp());

    // Verify that SafeCircle title and subtitle are displayed.
    expect(find.text('SafeCircle'), findsWidgets);
    expect(find.text('Your personal safety companion'), findsOneWidget);
  });
}
