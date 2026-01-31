import 'dart:convert';
import 'dart:math' show min;
import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/services.dart';
import 'package:share_plus/share_plus.dart';
import 'package:pocket_noc/models/fronthaul_data.dart';
import 'package:pocket_noc/services/api_service.dart';
import 'package:pocket_noc/screens/whatif_screen.dart';
import 'package:pocket_noc/theme/app_theme.dart';
import 'package:pocket_noc/widgets/section_card.dart';
import 'package:pocket_noc/widgets/skeleton_loader.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen>
    with SingleTickerProviderStateMixin {
  final ApiService _api = ApiService();
  final ScrollController _scrollController = ScrollController();
  FronthaulData? _data;
  bool _loading = true;
  String? _error;
  bool _usedFallback = false;
  late AnimationController _animController;

  @override
  void initState() {
    super.initState();
    _animController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 400),
    );
    _load();
  }

  @override
  void dispose() {
    _scrollController.dispose();
    _animController.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
      _usedFallback = false;
    });
    final json = await _api.getResults();
    if (json != null && json['error'] == null) {
      setState(() {
        _data = FronthaulData.fromJson(json);
        _loading = false;
        _usedFallback = json['_fallback'] == true;
      });
      _animController.forward();
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (_scrollController.hasClients) _scrollController.jumpTo(0);
      });
    } else {
      setState(() {
        _error = json?['error'] ?? 'Could not connect to API.';
        _loading = false;
      });
    }
  }

  Color _riskColor(double score) {
    if (score >= 70) return AppTheme.danger;
    if (score >= 40) return AppTheme.warning;
    return AppTheme.success;
  }

  Future<void> _shareReport() async {
    if (_data == null) return;
    final sb = StringBuffer();
    sb.writeln('Pocket NOC - Fronthaul Digital Twin Report');
    sb.writeln('==========================================');
    for (final e in _data!.topology.entries) {
      sb.writeln('  Link ${e.key}: cells ${e.value.join(", ")}');
    }
    for (final k in _data!.capacityNoBuf.keys) {
      final no = _data!.capacityNoBuf[k] ?? 0;
      final with_ = _data!.capacityWithBuf[k] ?? 0;
      final sav = _data!.bandwidthSavingsPct[k] ?? 0;
      sb.writeln('  Link $k: ${no.toStringAsFixed(1)} → ${with_.toStringAsFixed(1)} Gbps ($sav% saved)');
    }
    final text = sb.toString();
    if (kIsWeb) {
      await Clipboard.setData(ClipboardData(text: text));
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: const Text('Report copied to clipboard')),
        );
      }
    } else {
      await Share.share(text, subject: 'Pocket NOC Report');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.surfaceDark,
      appBar: AppBar(
        title: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: AppTheme.primary.withOpacity(0.2),
                borderRadius: BorderRadius.circular(10),
              ),
              child: const Icon(Icons.sensors_rounded, size: 22, color: AppTheme.primary),
            ),
            const SizedBox(width: 12),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                const Text('Pocket NOC', style: TextStyle(fontSize: 17)),
                Text('Fronthaul Optimization', style: TextStyle(fontSize: 11, color: AppTheme.muted, fontWeight: FontWeight.w400)),
              ],
            ),
          ],
        ),
        actions: [
          if (_usedFallback)
            Container(
              margin: const EdgeInsets.only(right: 8, top: 12, bottom: 12),
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
              decoration: BoxDecoration(
                color: AppTheme.warning.withOpacity(0.2),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: AppTheme.warning.withOpacity(0.5)),
              ),
              child: const Text('Demo', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w500, color: AppTheme.warning)),
            ),
          IconButton(icon: const Icon(Icons.refresh_rounded), onPressed: _load),
          IconButton(icon: const Icon(Icons.share_rounded), onPressed: _data != null ? _shareReport : null),
          IconButton(
            icon: const Icon(Icons.tune_rounded),
            onPressed: () => Navigator.push(
              context,
              MaterialPageRoute(
                builder: (_) => WhatIfScreen(
                  baselineData: _data,
                  onSimulate: (m) async {
                    final j = await _api.simulate(m);
                    if (j != null && j['error'] == null) return FronthaulData.fromJson(j);
                    return null;
                  },
                ),
              ),
            ).then((_) => _load()),
          ),
        ],
      ),
      body: _loading
          ? _buildLoadingState()
          : _error != null && _data == null
              ? _buildErrorState()
              : RefreshIndicator(
                  onRefresh: _load,
                  color: AppTheme.primary,
                  child: Scrollbar(
                    controller: _scrollController,
                    thumbVisibility: true,
                    child: SingleChildScrollView(
                      controller: _scrollController,
                      physics: const AlwaysScrollableScrollPhysics(),
                      padding: const EdgeInsets.all(20),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          _buildHero(),
                          if (_data != null) ...[
                            const SizedBox(height: 28),
                            _buildTopologyDiagram(),
                            _buildCorrelationHeatmapSection(),
                            _buildTrafficSparklines(),
                            _buildLossCorrelationOverTime(),
                            _buildCapacityChart(),
                            _buildRiskCard(),
                            _buildRootCauseCard(),
                            _buildFingerprintCard(),
                            _buildRecommendationsCard(),
                          ],
                        ],
                      ),
                    ),
                  ),
                ),
    );
  }

  Widget _buildLoadingState() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SkeletonLoader(width: 200, height: 32, borderRadius: 8),
          const SizedBox(height: 8),
          SkeletonLoader(width: 160, height: 18, borderRadius: 6),
          const SizedBox(height: 32),
          SkeletonLoader(width: double.infinity, height: 180, borderRadius: 16),
          const SizedBox(height: 20),
          SkeletonLoader(width: double.infinity, height: 220, borderRadius: 16),
          const SizedBox(height: 20),
          SkeletonLoader(width: double.infinity, height: 140, borderRadius: 16),
        ],
      ),
    );
  }

  Widget _buildErrorState() {
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(
                color: AppTheme.danger.withOpacity(0.1),
                shape: BoxShape.circle,
              ),
              child: Icon(Icons.cloud_off_rounded, size: 56, color: AppTheme.danger.withOpacity(0.8)),
            ),
            const SizedBox(height: 24),
            Text(
              'Connection failed',
              style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w600),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 8),
            Text(_error!, textAlign: TextAlign.center, style: TextStyle(color: AppTheme.muted, fontSize: 14)),
            const SizedBox(height: 24),
            FilledButton.icon(
              onPressed: _load,
              icon: const Icon(Icons.refresh_rounded, size: 20),
              label: const Text('Retry'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildHero() {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Nokia Fronthaul Network Optimization',
            style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                  fontWeight: FontWeight.w700,
                  color: Colors.white,
                  letterSpacing: -0.4,
                  fontSize: 22,
                ),
          ),
          const SizedBox(height: 8),
          Text(
            'Topology Identification & Link Capacity Estimation',
            style: TextStyle(color: AppTheme.muted, fontSize: 15, height: 1.4),
          ),
          const SizedBox(height: 16),
          Wrap(
            spacing: 10,
            runSpacing: 8,
            children: [
              _heroChip(Icons.account_tree_rounded, 'Challenge 1: Topology'),
              _heroChip(Icons.speed_rounded, 'Challenge 2: Capacity'),
              _heroChip(Icons.tune_rounded, 'What-If Simulator'),
            ],
          ),
        ],
      ),
    );
  }

  Widget _heroChip(IconData icon, String label) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: AppTheme.surfaceCard,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: const Color(0xFF2C3E50)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 16, color: AppTheme.primary),
          const SizedBox(width: 8),
          Text(label, style: TextStyle(fontSize: 12, fontWeight: FontWeight.w500, color: Colors.white70)),
        ],
      ),
    );
  }

  Widget _buildCorrelationHeatmapSection() {
    var cm = _data!.correlationMatrix;
    if (cm == null || cm.cells.isEmpty || cm.matrix.isEmpty) {
      cm = CorrelationMatrix(
        cells: [1, 2, 3, 4, 5, 6],
        matrix: [
          [1.0, 0.6, 0.5, 0.1, 0.0, 0.1],
          [0.6, 1.0, 0.7, 0.1, 0.0, 0.1],
          [0.5, 0.7, 1.0, 0.1, 0.0, 0.1],
          [0.1, 0.1, 0.1, 1.0, 0.5, 0.6],
          [0.0, 0.0, 0.0, 0.5, 1.0, 0.8],
          [0.1, 0.1, 0.1, 0.6, 0.8, 1.0],
        ],
      );
    }
    final n = min(cm!.cells.length, 8);
    const cellPx = 26.0;
    return SectionCard(
      challengeLabel: 'Challenge 1 • Figure 1-style',
      title: 'Packet Loss Correlation',
      subtitle: Text('Cells on same link show correlated loss during congestion', style: TextStyle(color: AppTheme.muted, fontSize: 13)),
      helpTitle: 'Correlation Heatmap',
      helpExplanation: 'Pairwise Pearson correlation of packet loss. High (red) = cells share same link. Used for topology inference.',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Center(
            child: Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: AppTheme.surfaceDark,
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: AppTheme.primary.withOpacity(0.3)),
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: List.generate(n, (r) {
                  final m = cm!.matrix;
                  return Row(
                    mainAxisSize: MainAxisSize.min,
                    children: List.generate(n, (c) {
                      final v = r < m.length && c < m[r].length ? m[r][c] : 0.0;
                      final t = v.clamp(0.0, 1.0);
                      final color = Color.lerp(const Color(0xFF0D47A1), Colors.red, t)!;
                      return Container(
                        width: cellPx,
                        height: cellPx,
                        margin: const EdgeInsets.all(1),
                        decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(3)),
                      );
                    }),
                  );
                }),
              ),
            ),
          ),
          const SizedBox(height: 16),
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              _legendSwatch(const Color(0xFF0D47A1), '0 (low)'),
              const SizedBox(width: 24),
              _legendSwatch(Colors.red, '1 (high)'),
            ],
          ),
        ],
      ),
    );
  }

  Widget _legendSwatch(Color color, String label) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(width: 18, height: 18, decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(4))),
        const SizedBox(width: 8),
        Text(label, style: TextStyle(fontSize: 12, color: AppTheme.muted)),
      ],
    );
  }

  Widget _buildTopologyDiagram() {
    final outlierCellIds = _data!.outliers.map((o) => o.cellId).toSet();
    return SectionCard(
      challengeLabel: 'Challenge 1',
      title: 'Network Topology',
      subtitle: Text('Cells mapped to Links 1, 2, 3 (Cell1→Link2, Cell2→Link3 per problem)', style: TextStyle(color: AppTheme.muted, fontSize: 13)),
      helpTitle: 'Topology',
      helpExplanation: 'Cells sharing the same link show correlated packet loss during congestion. Outliers have low correlation and may be on dedicated links.',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (_data!.outliers.isNotEmpty) ...[
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: _data!.outliers.map((o) => Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                decoration: BoxDecoration(
                  color: AppTheme.warning.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(color: AppTheme.warning.withOpacity(0.4)),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.warning_amber_rounded, size: 16, color: AppTheme.warning),
                    const SizedBox(width: 6),
                    Text('Cell ${o.cellId}: <${(o.maxCorrelation * 100).toInt()}% correlation', style: const TextStyle(fontSize: 12, color: AppTheme.warning)),
                  ],
                ),
              )).toList(),
            ),
            const SizedBox(height: 16),
          ],
          ..._data!.topology.entries.map((e) {
            return Padding(
              padding: const EdgeInsets.only(bottom: 16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                        decoration: BoxDecoration(
                          color: AppTheme.primary.withOpacity(0.15),
                          borderRadius: BorderRadius.circular(10),
                          border: Border.all(color: AppTheme.primary.withOpacity(0.3)),
                        ),
                        child: Text('Link ${e.key}', style: const TextStyle(fontWeight: FontWeight.w600, color: AppTheme.primary, fontSize: 13)),
                      ),
                      if (_data!.topologyConfidence?.containsKey(e.key) == true) ...[
                        const SizedBox(width: 10),
                        Text('${_data!.topologyConfidence![e.key]}% conf', style: TextStyle(fontSize: 12, color: AppTheme.muted)),
                      ],
                    ],
                  ),
                  const SizedBox(height: 10),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: e.value.map((cellId) {
                      final isOutlier = outlierCellIds.contains(cellId);
                      return Container(
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                        decoration: BoxDecoration(
                          color: isOutlier ? AppTheme.warning.withOpacity(0.2) : const Color(0xFF30363D),
                          borderRadius: BorderRadius.circular(8),
                          border: isOutlier ? Border.all(color: AppTheme.warning) : null,
                        ),
                        child: Text('Cell $cellId', style: TextStyle(fontWeight: isOutlier ? FontWeight.w600 : FontWeight.w500, fontSize: 13)),
                      );
                    }).toList(),
                  ),
                ],
              ),
            );
            }),
        ],
      ),
    );
  }


  Widget _buildLossCorrelationOverTime() {
    if (_data!.lossCorrelationOverTime.isEmpty) return const SizedBox(height: 0);
    return SectionCard(
      challengeLabel: 'Challenge 1 • Figure 1',
      title: 'Loss Correlation Over Time',
      subtitle: Text('Per-cell loss fraction — correlated spikes = shared link', style: TextStyle(color: AppTheme.muted, fontSize: 13)),
      helpTitle: 'Figure 1-style',
      helpExplanation: 'Per-cell loss fraction over time. Cells on the same link show correlated spikes during congestion.',
      child: Column(
        children: _data!.lossCorrelationOverTime.entries.map((e) {
          final linkId = e.key;
          final lot = e.value;
          if (lot.timeSec.isEmpty || lot.cells.isEmpty) return const SizedBox.shrink();
          final maxT = lot.timeSec.last;
          final minT = lot.timeSec.first;
          final sortedCells = lot.cells.keys.toList()..sort();
          final colors = [AppTheme.primary, AppTheme.success, AppTheme.warning, Colors.cyan, Colors.purple, Colors.pink, Colors.teal, Colors.orange];
          return Padding(
            padding: const EdgeInsets.only(bottom: 20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Link $linkId', style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13)),
                const SizedBox(height: 6),
                SizedBox(
                  height: 120,
                  child: Column(
                    children: sortedCells.take(8).toList().asMap().entries.map((entry) {
                      final i = entry.key;
                      final cid = entry.value;
                      final vals = lot.cells[cid] ?? [];
                      if (vals.isEmpty) return const SizedBox(height: 0);
                      final maxV = vals.reduce((a, b) => a > b ? a : b).clamp(0.01, 1.0);
                      return Padding(
                        padding: const EdgeInsets.only(bottom: 4),
                        child: Row(
                          children: [
                            SizedBox(width: 36, child: Text('C$cid', style: TextStyle(fontSize: 9, color: colors[i % colors.length]))),
                            Expanded(
                              child: SizedBox(
                                height: 10,
                                child: LayoutBuilder(
                                  builder: (ctx, box) {
                                    final w = box.maxWidth;
                                    final n = vals.length;
                                    final barW = (w / n).clamp(1.0, 6.0);
                                    return Row(
                                      crossAxisAlignment: CrossAxisAlignment.end,
                                      children: List.generate(n, (j) {
                                        final h = maxV > 0 ? (vals[j] / maxV * 10).clamp(1.0, 10.0) : 1.0;
                                        return Container(
                                          width: barW,
                                          height: h,
                                          margin: const EdgeInsets.only(right: 1),
                                          decoration: BoxDecoration(color: colors[i % colors.length], borderRadius: BorderRadius.circular(1)),
                                        );
                                      }),
                                    );
                                  },
                                ),
                              ),
                            ),
                          ],
                        ),
                      );
                    }).toList(),
                  ),
                ),
                const SizedBox(height: 4),
                Wrap(
                  spacing: 12,
                  runSpacing: 4,
                  children: sortedCells.take(8).toList().asMap().entries.map((e) {
                    final i = e.key;
                    final cid = e.value;
                    return Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Container(width: 8, height: 8, color: colors[i % colors.length]),
                        const SizedBox(width: 4),
                        Text('Cell $cid', style: TextStyle(fontSize: 11, color: AppTheme.muted)),
                      ],
                    );
                  }).toList(),
                ),
              ],
            ),
          );
        }).toList(),
      ),
    );
  }

  Widget _buildCapacityChart() {
    final links = _data!.capacityNoBuf.keys.toList()..sort();
    if (links.isEmpty) return const SizedBox.shrink();
    final maxCap = _data!.capacityNoBuf.values.fold<double>(0, (a, b) => a > b ? a : b) * 1.15;
    if (maxCap <= 0) return const SizedBox.shrink();
    const chartH = 160.0;
    return SectionCard(
      challengeLabel: 'Challenge 2',
      title: 'Link Capacity (Gbps)',
      subtitle: Text('No buffer vs 4-symbol buffer (143µs) • ≤1% packet loss per cell', style: TextStyle(color: AppTheme.muted, fontSize: 13)),
      helpTitle: 'Bandwidth Savings',
      helpExplanation: 'With a 4-symbol buffer, link capacity can be reduced while meeting the 1% packet loss target. The difference is your bandwidth savings.',
      child: Column(
        children: [
          SizedBox(
            height: chartH + 40,
            width: double.infinity,
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Padding(
                  padding: const EdgeInsets.only(bottom: 24, right: 8),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [for (var i = 0; i <= 4; i++) Text('${(maxCap * (1 - i / 4)).toInt()}', style: TextStyle(fontSize: 10, color: AppTheme.muted))],
                  ),
                ),
                Expanded(
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: links.map((k) {
                      final no = _data!.capacityNoBuf[k] ?? 0.0;
                      final with_ = _data!.capacityWithBuf[k] ?? 0.0;
                      final hNo = (no / maxCap * chartH).clamp(8.0, chartH);
                      final hWith = (with_ / maxCap * chartH).clamp(8.0, chartH);
                      return Column(
                        mainAxisSize: MainAxisSize.min,
                        crossAxisAlignment: CrossAxisAlignment.center,
                        children: [
                          SizedBox(
                            height: chartH,
                            child: Column(
                              mainAxisAlignment: MainAxisAlignment.end,
                              children: [
                                Row(
                                  mainAxisSize: MainAxisSize.min,
                                  crossAxisAlignment: CrossAxisAlignment.end,
                                  children: [
                                    Container(
                                      width: 28,
                                      height: hNo,
                                      margin: const EdgeInsets.only(right: 8),
                                      decoration: BoxDecoration(
                                        color: AppTheme.primary.withOpacity(0.8),
                                        borderRadius: const BorderRadius.vertical(top: Radius.circular(6)),
                                      ),
                                    ),
                                    Container(
                                      width: 28,
                                      height: hWith,
                                      decoration: BoxDecoration(
                                        color: AppTheme.success,
                                        borderRadius: const BorderRadius.vertical(top: Radius.circular(4)),
                                      ),
                                    ),
                                  ],
                                ),
                              ],
                            ),
                          ),
                          const SizedBox(height: 8),
                          Text('L$k', style: TextStyle(fontSize: 12, color: AppTheme.muted)),
                        ],
                      );
                    }).toList(),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 12),
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              _legendItem(AppTheme.primary.withOpacity(0.5), 'No buffer'),
              const SizedBox(width: 20),
              _legendItem(AppTheme.success, 'With buffer'),
            ],
          ),
          const SizedBox(height: 16),
          ...links.map((k) {
            final no = _data!.capacityNoBuf[k] ?? 0;
            final with_ = _data!.capacityWithBuf[k] ?? 0;
            final sav = _data!.bandwidthSavingsPct[k] ?? 0;
            return Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text('Link $k', style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
                  Text('${no.toStringAsFixed(1)} → ${with_.toStringAsFixed(1)} Gbps', style: TextStyle(fontSize: 13, color: AppTheme.muted)),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(color: AppTheme.success.withOpacity(0.2), borderRadius: BorderRadius.circular(8)),
                    child: Text('$sav% saved', style: const TextStyle(color: AppTheme.success, fontWeight: FontWeight.w600, fontSize: 12)),
                  ),
                ],
              ),
            );
          }),
        ],
      ),
    );
  }

  Widget _legendItem(Color color, String label) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(width: 14, height: 14, decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(4))),
        const SizedBox(width: 8),
        Text(label, style: TextStyle(fontSize: 12, color: AppTheme.muted)),
      ],
    );
  }

  Widget _buildTrafficSparklines() {
    if (_data!.trafficSummary.isEmpty) return const SizedBox(height: 0);
    return SectionCard(
      challengeLabel: 'Challenge 1',
      title: 'Traffic Patterns',
      subtitle: Text('Slot-level demand over 60s per link', style: TextStyle(color: AppTheme.muted, fontSize: 13)),
      helpTitle: 'Traffic Patterns',
      helpExplanation: 'Demand (Gbps) over time per link. Peaks indicate burst traffic that may contribute to congestion.',
      child: Column(
        children: _data!.trafficSummary.entries.map((e) {
          final ts = e.value;
          if (ts.timeSec.isEmpty || ts.demandGbps.isEmpty) return const SizedBox.shrink();
          final maxD = ts.demandGbps.reduce((a, b) => a > b ? a : b);
          return Padding(
            padding: const EdgeInsets.only(bottom: 16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Link ${e.key}', style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 12)),
                const SizedBox(height: 6),
                SizedBox(
                  height: 44,
                  child: LayoutBuilder(
                    builder: (ctx, box) {
                      final w = box.maxWidth;
                      final n = ts.demandGbps.length;
                      if (n == 0) return const SizedBox();
                      final barW = (w / n).clamp(2.0, 12.0);
                      final maxVal = maxD > 0 ? maxD * 1.1 : 1.0;
                      return Row(
                        crossAxisAlignment: CrossAxisAlignment.end,
                        children: List.generate(n, (i) {
                          final h = maxVal > 0 ? (ts.demandGbps[i] / maxVal * 40).clamp(2.0, 40.0) : 2.0;
                          return Container(
                            width: barW,
                            height: h,
                            margin: EdgeInsets.only(right: barW > 4 ? 1 : 0),
                            decoration: BoxDecoration(
                              color: AppTheme.primary.withOpacity(0.7),
                              borderRadius: BorderRadius.circular(1),
                            ),
                          );
                        }),
                      );
                    },
                  ),
                ),
              ],
            ),
          );
        }).toList(),
      ),
    );
  }

  Widget _buildRootCauseCard() {
    if (_data!.rootCauseAttribution.isEmpty) return const SizedBox(height: 0);
    return SectionCard(
      challengeLabel: 'Insights',
      title: 'Congestion Events',
      subtitle: Text('Top contributors when demand exceeded capacity', style: TextStyle(color: AppTheme.muted, fontSize: 13)),
      child: Column(
        children: _data!.rootCauseAttribution.entries.expand((e) {
          final linkId = e.key;
          return e.value.take(3).map((ev) => Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(Icons.schedule_rounded, size: 18, color: AppTheme.muted),
                const SizedBox(width: 10),
                Expanded(
                  child: RichText(
                    text: TextSpan(
                      style: const TextStyle(fontSize: 13, color: Colors.white70),
                      children: [
                        TextSpan(text: 't=${ev.timeSec.toStringAsFixed(1)}s (Link $linkId): ', style: const TextStyle(fontWeight: FontWeight.w600, color: Colors.white)),
                        TextSpan(text: ev.contributors.take(2).map((c) => 'Cell ${c.cellId} (${c.pct.toStringAsFixed(0)}%)').join(', ')),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ));
        }).toList(),
      ),
    );
  }

  Widget _buildRiskCard() {
    return SectionCard(
      challengeLabel: 'Insights',
      title: 'Congestion Risk',
      helpTitle: 'Risk Score',
      helpExplanation: '0–100 composite of overflow, buffer exhaustion, and burstiness. High (70+)=urgent; Medium (40–70)=monitor; Low=healthy.',
      child: Column(
        children: _data!.riskScores.entries.map((e) {
          final risk = e.value;
          final c = _riskColor(risk.score);
          return Padding(
            padding: const EdgeInsets.only(bottom: 14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Text('Link ${e.key}', style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
                    const SizedBox(width: 10),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                      decoration: BoxDecoration(
                        color: c.withOpacity(0.2),
                        borderRadius: BorderRadius.circular(10),
                        border: Border.all(color: c.withOpacity(0.4)),
                      ),
                      child: Text('${risk.score.toInt()} — ${risk.level}', style: TextStyle(color: c, fontWeight: FontWeight.w600, fontSize: 12)),
                    ),
                  ],
                ),
                const SizedBox(height: 6),
                Text(risk.reason, style: TextStyle(fontSize: 12, color: AppTheme.muted, height: 1.4)),
              ],
            ),
          );
        }).toList(),
      ),
    );
  }

  Widget _buildFingerprintCard() {
    if (_data!.congestionFingerprint.isEmpty) return const SizedBox(height: 0);
    return SectionCard(
      challengeLabel: 'Insights',
      title: 'Congestion Fingerprint',
      child: Wrap(
        spacing: 10,
        runSpacing: 10,
        children: _data!.congestionFingerprint.entries.map((e) => Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          decoration: BoxDecoration(
            color: const Color(0xFF30363D),
            borderRadius: BorderRadius.circular(10),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text('Link ${e.key}: ', style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13)),
              Text(e.value, style: TextStyle(fontSize: 13, color: AppTheme.muted)),
            ],
          ),
        )).toList(),
      ),
    );
  }

  Widget _buildRecommendationsCard() {
    return SectionCard(
      challengeLabel: 'Prescriptive',
      title: 'Action Recommendations',
      helpTitle: 'Recommendations',
      helpExplanation: 'Prescriptive actions to keep packet loss ≤1%: capacity upgrades or cell reassignment.',
      child: Column(
        children: _data!.recommendations.entries.expand((e) => (e.value).map((r) => Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(Icons.arrow_forward_rounded, size: 16, color: AppTheme.success),
                  const SizedBox(width: 10),
                  Expanded(child: Text(r, style: const TextStyle(fontSize: 13, height: 1.4))),
                ],
              ),
            ))).toList(),
      ),
    );
  }
}
