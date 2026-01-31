import 'package:flutter/material.dart';

class ExplainerTooltip extends StatelessWidget {
  final String title;
  final String explanation;
  final Widget child;

  const ExplainerTooltip({
    super.key,
    required this.title,
    required this.explanation,
    required this.child,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        child,
        GestureDetector(
          onTap: () => showDialog(
            context: context,
            builder: (ctx) => AlertDialog(
              title: Text(title),
              content: SingleChildScrollView(child: Text(explanation)),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(ctx),
                  child: const Text('Got it'),
                ),
              ],
            ),
          ),
          child: Padding(
            padding: const EdgeInsets.only(left: 4),
            child: Icon(Icons.help_outline, size: 18, color: Colors.grey[500]),
          ),
        ),
      ],
    );
  }
}
