import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:pocket_noc/screens/dashboard_screen.dart';
import 'package:pocket_noc/theme/app_theme.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  SystemChrome.setSystemUIOverlayStyle(
    const SystemUiOverlayStyle(
      statusBarColor: Colors.transparent,
      systemNavigationBarColor: AppTheme.surfaceDark,
      systemNavigationBarDividerColor: AppTheme.surfaceDark,
    ),
  );
  runApp(const PocketNocApp());
}

class PocketNocApp extends StatelessWidget {
  const PocketNocApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Pocket NOC',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.darkTheme,
      home: const DashboardScreen(),
    );
  }
}
