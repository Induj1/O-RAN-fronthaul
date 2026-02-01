import 'dart:convert';
import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;

class ApiService {
  // Local: 127.0.0.1. Android emulator: http://10.0.2.2:8000
  // Render: o-ran-fronthaul (override with --dart-define=API_BASE_URL=...)
  static const String baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'https://o-ran-fronthaul.onrender.com',
  );

  static String getBaseUrl() => baseUrl;

  /// Try API first, then fallback to bundled static JSON when unreachable.
  /// Timeout 90s: Render free tier cold start can take 30-60s after inactivity.
  Future<Map<String, dynamic>?> getResults() async {
    try {
      final url = '$baseUrl/results';
      final response = await http.get(Uri.parse(url)).timeout(
        const Duration(seconds: 90),
        onTimeout: () => throw Exception('timeout'),
      );
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        if (data['error'] == null) return data;
      }
    } catch (_) {}
    // Fallback to bundled static JSON when API unreachable
    return _loadStaticFallback();
  }

  Future<Map<String, dynamic>?> _loadStaticFallback() async {
    try {
      final str = await rootBundle.loadString('assets/results_fallback.json');
      final json = jsonDecode(str) as Map<String, dynamic>;
      json['_fallback'] = true;
      return json;
    } catch (_) {}
    return null;
  }

  /// Returns result on success, or null on failure.
  /// On 400: backend is in static mode (no raw data for simulations).
  Future<Map<String, dynamic>?> simulate(Map<String, double> trafficMultipliers) async {
    try {
      final body = jsonEncode({
        'traffic_multipliers': trafficMultipliers.map((k, v) => MapEntry(k.toString(), v)),
      });
      final response = await http
          .post(
            Uri.parse('$baseUrl/simulate'),
            headers: {'Content-Type': 'application/json'},
            body: body,
          )
          .timeout(const Duration(seconds: 60), onTimeout: () => throw Exception('timeout'));
      if (response.statusCode == 200) {
        return jsonDecode(response.body) as Map<String, dynamic>;
      }
      // 400 = static mode (Render deploy without raw data)
      if (response.statusCode == 400) {
        return null; // Caller will show "simulations not available" message
      }
    } catch (_) {}
    return null;
  }

  /// AI chat. Pass optional context (topology, capacity, etc.) from FronthaulData.
  Future<String?> chat(String message, [Map<String, dynamic>? context]) async {
    try {
      final body = jsonEncode({'message': message, 'context': context});
      final response = await http
          .post(
            Uri.parse('$baseUrl/chat'),
            headers: {'Content-Type': 'application/json'},
            body: body,
          )
          .timeout(const Duration(seconds: 30), onTimeout: () => throw Exception('timeout'));
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        return data['reply'] as String?;
      }
    } catch (_) {}
    return null;
  }
}
