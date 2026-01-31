import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/services.dart';
import 'package:share_plus/share_plus.dart';
import 'package:pocket_noc/models/fronthaul_data.dart';
import 'package:pocket_noc/theme/app_theme.dart';

class WhatIfScreen extends StatefulWidget {
  final FronthaulData? baselineData;
  final Future<FronthaulData?> Function(Map<String, double> multipliers) onSimulate;

  const WhatIfScreen({super.key, this.baselineData, required this.onSimulate});

  @override
  State<WhatIfScreen> createState() => _WhatIfScreenState();
}

class _WhatIfScreenState extends State<WhatIfScreen> {
  final Map<String, double> _multipliers = {};
  FronthaulData? _result;
  bool _loading = false;

  void _setMultiplier(String cellId, double value) {
    setState(() {
      if ((value - 1.0).abs() < 0.01) {
        _multipliers.remove(cellId);
      } else {
        _multipliers[cellId] = value;
      }
    });
  }

  void _applyPreset(String presetId) {
    setState(() {
      _multipliers.clear();
      switch (presetId) {
        case 'cell7_40':
          _multipliers['7'] = 1.4;
          break;
        case 'all_20':
          for (int i = 1; i <= 24; i++) _multipliers[i.toString()] = 1.2;
          break;
        case 'peak_hour':
          for (int i = 1; i <= 24; i++) {
            _multipliers[i.toString()] = i % 3 == 0 ? 1.5 : (i % 2 == 0 ? 1.3 : 1.1);
          }
          break;
        case 'reset':
          _multipliers.clear();
          break;
      }
    });
  }

  Future<void> _runSimulation() async {
    if (_multipliers.isEmpty) return;
    setState(() => _loading = true);
    final data = await widget.onSimulate(_multipliers);
    setState(() {
      _result = data;
      _loading = false;
    });
    if (data == null && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: const Text('Simulations require raw data. This deployment uses precomputed results—What-If is read-only.'),
          backgroundColor: AppTheme.warning,
          duration: const Duration(seconds: 4),
        ),
      );
    }
  }

  Future<void> _shareResult() async {
    if (_result == null) return;
    final baseline = widget.baselineData;
    final sb = StringBuffer();
    sb.writeln('Pocket NOC - What-If Simulation Result');
    sb.writeln('======================================');
    sb.writeln('Traffic multipliers: $_multipliers');
    if (baseline != null) {
      sb.writeln();
      sb.writeln('Baseline vs Simulated:');
      for (final k in _result!.capacityWithBuf.keys) {
        final baseCap = baseline.capacityWithBuf[k] ?? 0;
        final simCap = _result!.capacityWithBuf[k] ?? 0;
        final diff = simCap - baseCap;
        sb.writeln('  Link $k: ${baseCap.toStringAsFixed(1)} -> ${simCap.toStringAsFixed(1)} Gbps (${diff >= 0 ? "+" : ""}${diff.toStringAsFixed(1)})');
      }
    }
    sb.writeln();
    sb.writeln('Risk Scores:');
    for (final e in _result!.riskScores.entries) {
      sb.writeln('  Link ${e.key}: ${e.value.score.toInt()} - ${e.value.level}');
    }
    final text = sb.toString();
    if (kIsWeb) {
      await Clipboard.setData(ClipboardData(text: text));
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Result copied to clipboard')));
    } else {
      await Share.share(text, subject: 'Pocket NOC Simulation');
    }
  }

  Color _riskColor(double score) {
    if (score >= 70) return AppTheme.danger;
    if (score >= 40) return AppTheme.warning;
    return AppTheme.success;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.surfaceDark,
      appBar: AppBar(
        title: Row(
          children: [
            Icon(Icons.tune_rounded, size: 22, color: AppTheme.primary),
            const SizedBox(width: 10),
            const Text('What-If Simulator'),
          ],
        ),
        actions: [
          if (_result != null)
            IconButton(icon: const Icon(Icons.share_rounded), onPressed: _shareResult),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Simulate traffic changes',
              style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w600, color: Colors.white, fontSize: 18),
            ),
            const SizedBox(height: 6),
            Text(
              'e.g. "What if traffic on Cell 7 increases by 40%?" → Set multiplier to 1.4',
              style: TextStyle(color: AppTheme.muted, fontSize: 14),
            ),
            const SizedBox(height: 24),
            Text('Quick presets', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 15, color: Colors.white)),
            const SizedBox(height: 12),
            _buildPresetCards(),
            const SizedBox(height: 24),
            Text('Cell traffic multipliers', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 15, color: Colors.white)),
            const SizedBox(height: 12),
            _buildSliders(),
            const SizedBox(height: 24),
            SizedBox(
              width: double.infinity,
              height: 52,
              child: FilledButton.icon(
                onPressed: _loading || _multipliers.isEmpty ? null : _runSimulation,
                icon: _loading ? SizedBox(width: 22, height: 22, child: CircularProgressIndicator(strokeWidth: 2, color: AppTheme.surfaceDark)) : const Icon(Icons.play_arrow_rounded, size: 24),
                label: Text(_loading ? 'Simulating...' : 'Run Simulation', style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
              ),
            ),
            if (_result != null) ...[
              const SizedBox(height: 32),
              if (widget.baselineData != null) _buildBaselineComparison(),
              const SizedBox(height: 20),
              _buildResultsCard(),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildPresetCards() {
    final presets = [
      ('cell7_40', Icons.cell_tower_rounded, 'Cell 7 +40%', 'Single-cell spike'),
      ('all_20', Icons.grid_view_rounded, 'All cells +20%', 'Uniform increase'),
      ('peak_hour', Icons.trending_up_rounded, 'Peak hour', 'Stress scenario'),
      ('reset', Icons.refresh_rounded, 'Reset', 'Clear all'),
    ];
    return Wrap(
      spacing: 12,
      runSpacing: 12,
      children: presets.map((p) => _PresetCard(
        icon: p.$2,
        title: p.$3,
        subtitle: p.$4,
        onTap: () => _applyPreset(p.$1),
      )).toList(),
    );
  }

  Widget _buildSliders() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.surfaceCard,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFF30363D)),
      ),
      child: Column(
        children: List.generate(24, (i) {
          final cellId = (i + 1).toString();
          final val = _multipliers[cellId] ?? 1.0;
          final isActive = val != 1.0;
          return Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: Row(
              children: [
                SizedBox(
                  width: 56,
                  child: Text(
                    'Cell $cellId',
                    style: TextStyle(
                      fontWeight: isActive ? FontWeight.w600 : FontWeight.w500,
                      color: isActive ? AppTheme.primary : AppTheme.muted,
                      fontSize: 13,
                    ),
                  ),
                ),
                Expanded(
                  child: SliderTheme(
                    data: SliderTheme.of(context).copyWith(
                      trackHeight: 6,
                      thumbShape: const RoundSliderThumbShape(enabledThumbRadius: 8),
                      overlayShape: const RoundSliderOverlayShape(overlayRadius: 16),
                    ),
                    child: Slider(
                      value: val,
                      min: 0.5,
                      max: 2.0,
                      divisions: 15,
                      label: '${val.toStringAsFixed(1)}x',
                      onChanged: (v) => _setMultiplier(cellId, v),
                    ),
                  ),
                ),
                SizedBox(
                  width: 44,
                  child: Text(
                    '${val.toStringAsFixed(1)}x',
                    style: TextStyle(
                      fontWeight: FontWeight.w600,
                      fontSize: 13,
                      color: isActive ? AppTheme.primary : AppTheme.muted,
                    ),
                  ),
                ),
              ],
            ),
          );
        }),
      ),
    );
  }

  Widget _buildBaselineComparison() {
    final baseline = widget.baselineData!;
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppTheme.surfaceCard,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppTheme.primary.withOpacity(0.3)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.compare_arrows_rounded, size: 22, color: AppTheme.primary),
              const SizedBox(width: 10),
              Text('Baseline vs Simulated', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600, color: Colors.white)),
            ],
          ),
          const SizedBox(height: 16),
          ..._result!.capacityWithBuf.keys.map((k) {
            final baseCap = baseline.capacityWithBuf[k] ?? 0;
            final simCap = _result!.capacityWithBuf[k] ?? 0;
            final diff = simCap - baseCap;
            final baseRisk = baseline.riskScores[k]?.score ?? 0;
            final simRisk = _result!.riskScores[k]?.score ?? 0;
            final riskUp = simRisk > baseRisk + 5;
            final riskDown = simRisk < baseRisk - 5;
            return Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: Row(
                children: [
                  Text('Link $k', style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      '${baseCap.toStringAsFixed(1)} → ${simCap.toStringAsFixed(1)} Gbps',
                      style: TextStyle(
                        fontWeight: diff.abs() > 0.5 ? FontWeight.w600 : FontWeight.normal,
                        color: diff > 0 ? AppTheme.warning : (diff < 0 ? AppTheme.success : AppTheme.muted),
                        fontSize: 14,
                      ),
                    ),
                  ),
                  if (riskUp) Icon(Icons.trending_up_rounded, size: 20, color: AppTheme.danger),
                  if (riskDown) Icon(Icons.trending_down_rounded, size: 20, color: AppTheme.success),
                ],
              ),
            );
          }),
        ],
      ),
    );
  }

  Widget _buildResultsCard() {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppTheme.surfaceCard,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFF30363D)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Simulation Results', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600, color: Colors.white)),
          const SizedBox(height: 16),
          Text('Updated Capacity (Gbps)', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 13, color: AppTheme.muted)),
          const SizedBox(height: 8),
          ..._result!.capacityWithBuf.entries.map((e) => Padding(
                padding: const EdgeInsets.only(bottom: 6),
                child: Text('Link ${e.key}: ${e.value.toStringAsFixed(1)} Gbps', style: const TextStyle(fontSize: 14)),
              )),
          const SizedBox(height: 20),
          Text('Risk Scores', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 13, color: AppTheme.muted)),
          const SizedBox(height: 8),
          ..._result!.riskScores.entries.map((e) {
            final r = e.value;
            final c = _riskColor(r.score);
            return Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Text('Link ${e.key}', style: const TextStyle(fontSize: 14)),
                      const SizedBox(width: 10),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                        decoration: BoxDecoration(color: c.withOpacity(0.2), borderRadius: BorderRadius.circular(8)),
                        child: Text('${r.score.toInt()} — ${r.level}', style: TextStyle(color: c, fontSize: 12, fontWeight: FontWeight.w600)),
                      ),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Text(r.reason, style: TextStyle(fontSize: 12, color: AppTheme.muted, height: 1.3)),
                ],
              ),
            );
          }),
          const SizedBox(height: 20),
          Text('Recommendations', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 13, color: AppTheme.muted)),
          const SizedBox(height: 8),
          ..._result!.recommendations.values.expand((l) => l).map((r) => Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(Icons.arrow_forward_rounded, size: 16, color: AppTheme.success),
                    const SizedBox(width: 10),
                    Expanded(child: Text(r, style: const TextStyle(fontSize: 13, height: 1.4))),
                  ],
                ),
              )),
        ],
      ),
    );
  }
}

class _PresetCard extends StatelessWidget {
  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback onTap;

  const _PresetCard({required this.icon, required this.title, required this.subtitle, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(14),
        child: Container(
          width: 155,
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: AppTheme.surfaceCard,
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: const Color(0xFF30363D)),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(color: AppTheme.primary.withOpacity(0.15), borderRadius: BorderRadius.circular(10)),
                child: Icon(icon, size: 20, color: AppTheme.primary),
              ),
              const SizedBox(height: 12),
              Text(title, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
              const SizedBox(height: 2),
              Text(subtitle, style: TextStyle(fontSize: 12, color: AppTheme.muted)),
            ],
          ),
        ),
      ),
    );
  }
}
