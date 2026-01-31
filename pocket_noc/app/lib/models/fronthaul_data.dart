class CongestionEvent {
  final double timeSec;
  final List<Contributor> contributors;

  CongestionEvent({required this.timeSec, required this.contributors});

  factory CongestionEvent.fromJson(Map<String, dynamic> json) {
    final contribs = (json['contributors'] as List?)
        ?.map((c) => Contributor.fromJson(c as Map<String, dynamic>))
        .toList() ?? [];
    return CongestionEvent(
      timeSec: (json['time_sec'] as num?)?.toDouble() ?? 0,
      contributors: contribs,
    );
  }
}

class Contributor {
  final int cellId;
  final double pct;

  Contributor({required this.cellId, required this.pct});

  factory Contributor.fromJson(Map<String, dynamic> json) {
    return Contributor(
      cellId: (json['cell_id'] as num?)?.toInt() ?? 0,
      pct: (json['pct'] as num?)?.toDouble() ?? 0,
    );
  }
}

class TopologyOutlier {
  final String linkId;
  final int cellId;
  final double maxCorrelation;

  TopologyOutlier({required this.linkId, required this.cellId, required this.maxCorrelation});

  factory TopologyOutlier.fromJson(Map<String, dynamic> json) {
    return TopologyOutlier(
      linkId: json['link_id']?.toString() ?? '',
      cellId: (json['cell_id'] as num?)?.toInt() ?? 0,
      maxCorrelation: (json['max_correlation'] as num?)?.toDouble() ?? 0,
    );
  }
}

class TrafficSummary {
  final List<double> timeSec;
  final List<double> demandGbps;

  TrafficSummary({required this.timeSec, required this.demandGbps});

  factory TrafficSummary.fromJson(Map<String, dynamic> json) {
    final ts = (json['time_sec'] as List?)?.map((e) => (e as num).toDouble()).toList() ?? [];
    final dg = (json['demand_gbps'] as List?)?.map((e) => (e as num).toDouble()).toList() ?? [];
    return TrafficSummary(timeSec: ts, demandGbps: dg);
  }
}

class FronthaulData {
  final Map<String, List<int>> topology;
  final Map<String, double> capacityNoBuf;
  final Map<String, double> capacityWithBuf;
  final Map<String, int> bandwidthSavingsPct;
  final Map<String, RiskScore> riskScores;
  final Map<String, List<String>> recommendations;
  final Map<String, int>? topologyConfidence;
  final Map<String, List<CongestionEvent>> rootCauseAttribution;
  final List<TopologyOutlier> outliers;
  final Map<String, TrafficSummary> trafficSummary;
  final Map<String, String> congestionFingerprint;
  final CorrelationMatrix? correlationMatrix;
  final Map<String, LossCorrelationOverTime> lossCorrelationOverTime;

  FronthaulData({
    required this.topology,
    required this.capacityNoBuf,
    required this.capacityWithBuf,
    required this.bandwidthSavingsPct,
    required this.riskScores,
    required this.recommendations,
    this.topologyConfidence,
    this.rootCauseAttribution = const {},
    this.outliers = const [],
    this.trafficSummary = const {},
    this.congestionFingerprint = const {},
    this.correlationMatrix,
    this.lossCorrelationOverTime = const {},
  });

  factory FronthaulData.fromJson(Map<String, dynamic> json) {
    final topo = <String, List<int>>{};
    if (json['topology'] != null) {
      (json['topology'] as Map).forEach((k, v) {
        topo[k.toString()] = (v as List).map((e) => (e as num).toInt()).toList();
      });
    }

    // Support both API format (capacity_no_buf) and results.json (capacity.no_buffer_gbps)
    final capNo = <String, double>{};
    if (json['capacity_no_buf'] != null) {
      (json['capacity_no_buf'] as Map).forEach((k, v) {
        capNo[k.toString()] = (v as num).toDouble();
      });
    } else if (json['capacity'] != null) {
      final cap = json['capacity'] as Map;
      final nb = cap['no_buffer_gbps'] as Map?;
      nb?.forEach((k, v) {
        capNo[k.toString()] = (v as num).toDouble();
      });
    }

    final capWith = <String, double>{};
    if (json['capacity_with_buf'] != null) {
      (json['capacity_with_buf'] as Map).forEach((k, v) {
        capWith[k.toString()] = (v as num).toDouble();
      });
    } else if (json['capacity'] != null) {
      final cap = json['capacity'] as Map;
      final wb = cap['with_buffer_gbps'] as Map?;
      wb?.forEach((k, v) {
        capWith[k.toString()] = (v as num).toDouble();
      });
    }

    final savings = <String, int>{};
    if (json['bandwidth_savings_pct'] != null) {
      (json['bandwidth_savings_pct'] as Map).forEach((k, v) {
        savings[k.toString()] = (v as num).toInt();
      });
    }

    final risks = <String, RiskScore>{};
    if (json['risk_scores'] != null) {
      (json['risk_scores'] as Map).forEach((k, v) {
        final m = v as Map<String, dynamic>;
        risks[k.toString()] = RiskScore(
          score: (m['score'] as num?)?.toDouble() ?? 0,
          reason: m['reason'] as String? ?? '',
        );
      });
    } else {
      for (final k in capWith.keys) {
        risks[k] = RiskScore(score: 0, reason: 'N/A (static data)');
      }
    }

    final recs = <String, List<String>>{};
    if (json['recommendations'] != null) {
      (json['recommendations'] as Map).forEach((k, v) {
        recs[k.toString()] = (v as List).map((e) => e.toString()).toList();
      });
    } else {
      for (final k in capWith.keys) {
        recs[k] = ['View static results'];
      }
    }

    final conf = <String, int>{};
    if (json['topology_confidence'] != null) {
      (json['topology_confidence'] as Map).forEach((k, v) {
        conf[k.toString()] = (v as num).toInt();
      });
    }

    final rca = <String, List<CongestionEvent>>{};
    if (json['root_cause_attribution'] != null) {
      (json['root_cause_attribution'] as Map).forEach((k, v) {
        rca[k.toString()] = (v as List)
            .map((e) => CongestionEvent.fromJson(e as Map<String, dynamic>))
            .toList();
      });
    }

    final outList = <TopologyOutlier>[];
    if (json['outliers'] != null) {
      for (final o in json['outliers'] as List) {
        outList.add(TopologyOutlier.fromJson(o as Map<String, dynamic>));
      }
    }

    final traffic = <String, TrafficSummary>{};
    if (json['traffic_summary'] != null) {
      (json['traffic_summary'] as Map).forEach((k, v) {
        traffic[k.toString()] = TrafficSummary.fromJson(v as Map<String, dynamic>);
      });
    }

    final fingerprint = <String, String>{};
    if (json['congestion_fingerprint'] != null) {
      (json['congestion_fingerprint'] as Map).forEach((k, v) {
        fingerprint[k.toString()] = v?.toString() ?? '';
      });
    }

    CorrelationMatrix? corrMat;
    if (json['correlation_matrix'] != null) {
      final cm = json['correlation_matrix'] as Map<String, dynamic>;
      final cells = (cm['cells'] as List?)?.map((e) => (e as num).toInt()).toList() ?? [];
      final matrix = (cm['matrix'] as List?)?.map((row) => (row as List).map((e) => (e as num).toDouble()).toList()).toList() ?? [];
      if (cells.isNotEmpty && matrix.isNotEmpty) {
        corrMat = CorrelationMatrix(cells: cells, matrix: matrix);
      }
    }

    final lossOverTime = <String, LossCorrelationOverTime>{};
    if (json['loss_correlation_over_time'] != null) {
      (json['loss_correlation_over_time'] as Map).forEach((k, v) {
        final m = v as Map<String, dynamic>;
        final timeSec = (m['time_sec'] as List?)?.map((e) => (e as num).toDouble()).toList() ?? [];
        final cellsMap = <int, List<double>>{};
        (m['cells'] as Map?)?.forEach((ck, cv) {
          final cid = int.tryParse(ck.toString()) ?? (ck is num ? (ck as num).toInt() : 0);
          if (cid > 0) cellsMap[cid] = (cv as List).map((e) => (e as num).toDouble()).toList();
        });
        lossOverTime[k.toString()] = LossCorrelationOverTime(timeSec: timeSec, cells: cellsMap);
      });
    }

    return FronthaulData(
      topology: topo,
      capacityNoBuf: capNo,
      capacityWithBuf: capWith,
      bandwidthSavingsPct: savings,
      riskScores: risks,
      recommendations: recs,
      topologyConfidence: conf.isNotEmpty ? conf : null,
      rootCauseAttribution: rca,
      outliers: outList,
      trafficSummary: traffic,
      congestionFingerprint: fingerprint,
      correlationMatrix: corrMat,
      lossCorrelationOverTime: lossOverTime,
    );
  }
}

class CorrelationMatrix {
  final List<int> cells;
  final List<List<double>> matrix;

  CorrelationMatrix({required this.cells, required this.matrix});
}

class LossCorrelationOverTime {
  final List<double> timeSec;
  final Map<int, List<double>> cells;

  LossCorrelationOverTime({required this.timeSec, required this.cells});
}

class RiskScore {
  final double score;
  final String reason;

  RiskScore({required this.score, required this.reason});

  String get level {
    if (score >= 70) return 'High';
    if (score >= 40) return 'Medium';
    return 'Low';
  }
}
