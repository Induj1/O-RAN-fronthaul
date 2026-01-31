import 'package:flutter/material.dart';
import 'package:pocket_noc/theme/app_theme.dart';

class SectionCard extends StatelessWidget {
  final String title;
  final Widget? subtitle;
  final Widget child;
  final Widget? trailing;
  final String? helpTitle;
  final String? helpExplanation;
  final String? challengeLabel;

  const SectionCard({
    super.key,
    required this.title,
    this.subtitle,
    required this.child,
    this.trailing,
    this.helpTitle,
    this.helpExplanation,
    this.challengeLabel,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 24),
      decoration: BoxDecoration(
        color: AppTheme.surfaceCard,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFF2C3E50), width: 1),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.2),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      if (challengeLabel != null) ...[
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                          decoration: BoxDecoration(
                            color: AppTheme.primary.withOpacity(0.15),
                            borderRadius: BorderRadius.circular(6),
                          ),
                          child: Text(
                            challengeLabel!,
                            style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: AppTheme.primary),
                          ),
                        ),
                        const SizedBox(height: 10),
                      ],
                      Text(
                        title,
                        style: Theme.of(context).textTheme.titleMedium?.copyWith(
                              fontWeight: FontWeight.w600,
                              color: Colors.white,
                              fontSize: 16,
                            ),
                      ),
                      if (subtitle != null) ...[
                        const SizedBox(height: 4),
                        subtitle!,
                      ],
                    ],
                  ),
                ),
                if (trailing != null) trailing!,
                if (helpTitle != null && helpExplanation != null) ...[
                  const SizedBox(width: 8),
                  IconButton(
                    icon: Icon(Icons.info_outline_rounded, size: 20, color: AppTheme.muted),
                    onPressed: () => _showHelp(context),
                    style: IconButton.styleFrom(
                      padding: const EdgeInsets.all(4),
                      minimumSize: const Size(36, 36),
                    ),
                  ),
                ],
              ],
            ),
            const SizedBox(height: 20),
            child,
          ],
        ),
      ),
    );
  }

  void _showHelp(BuildContext context) {
    if (helpTitle == null || helpExplanation == null) return;
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(helpTitle!),
        content: SingleChildScrollView(
          child: Text(
            helpExplanation!,
            style: const TextStyle(fontSize: 14, height: 1.5),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Got it'),
          ),
        ],
      ),
    );
  }
}
