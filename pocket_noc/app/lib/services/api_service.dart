import 'dart:convert';
import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;

class ApiService {
  // Local: 127.0.0.1 avoids IPv6. Android emulator: http://10.0.2.2:8000
  // Production: set to your Render URL, e.g. https://pocket-noc-api.onrender.com
  static const String baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'https://o-ran-fronthaul.onrender.com',
  );

  static String getBaseUrl() => baseUrl;

  /// Try API first, then fallback to bundled static JSON when unreachable.
  Future<Map<String, dynamic>?> getResults() async {
    try {
      final response = await http.get(Uri.parse('$baseUrl/results')).timeout(
        const Duration(seconds: 5),
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
          .timeout(const Duration(seconds: 10), onTimeout: () => throw Exception('timeout'));
      if (response.statusCode == 200) {
        return jsonDecode(response.body) as Map<String, dynamic>;
      }
    } catch (_) {}
    return null;
  }
}
