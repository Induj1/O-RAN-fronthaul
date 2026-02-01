import 'package:flutter/material.dart';
import 'package:pocket_noc/models/fronthaul_data.dart';
import 'package:pocket_noc/services/api_service.dart';
import 'package:pocket_noc/theme/app_theme.dart';

class ChatScreen extends StatefulWidget {
  final FronthaulData? data;

  const ChatScreen({super.key, this.data});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final ApiService _api = ApiService();
  final TextEditingController _controller = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final List<_ChatMessage> _messages = [];
  bool _loading = false;

  Map<String, dynamic>? _buildContext() {
    final d = widget.data;
    if (d == null) return null;
    final rca = <String, List<Map<String, dynamic>>>{};
    for (final e in d.rootCauseAttribution.entries) {
      rca[e.key] = e.value.map((ev) => {
        'time_sec': ev.timeSec,
        'contributors': ev.contributors.map((c) => {'cell_id': c.cellId, 'pct': c.pct}).toList(),
      }).toList();
    }
    return {
      'topology': d.topology.map((k, v) => MapEntry(k, v)),
      'capacity_no_buf': d.capacityNoBuf.map((k, v) => MapEntry(k, v)),
      'capacity_with_buf': d.capacityWithBuf.map((k, v) => MapEntry(k, v)),
      'topology_confidence': d.topologyConfidence ?? {},
      'bandwidth_savings_pct': d.bandwidthSavingsPct.map((k, v) => MapEntry(k, v)),
      'root_cause_attribution': rca,
    };
  }

  Future<void> _send() async {
    final text = _controller.text.trim();
    if (text.isEmpty || _loading) return;

    _controller.clear();
    setState(() {
      _messages.add(_ChatMessage(role: 'user', content: text));
      _loading = true;
    });
    _scrollToBottom();

    final reply = await _api.chat(text, _buildContext());

    if (!mounted) return;
    setState(() {
      _messages.add(_ChatMessage(
        role: 'assistant',
        content: reply ?? 'Could not reach AI. Check backend has OPENAI_API_KEY set.',
      ));
      _loading = false;
    });
    _scrollToBottom();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 200),
          curve: Curves.easeOut,
        );
      }
    });
  }

  @override
  void dispose() {
    _controller.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.surfaceDark,
      appBar: AppBar(
        title: Row(
          children: [
            Icon(Icons.smart_toy_rounded, size: 22, color: AppTheme.primary),
            const SizedBox(width: 10),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                const Text('AI Assistant'),
                if (widget.data != null)
                  Text('Context loaded', style: TextStyle(fontSize: 11, color: AppTheme.muted, fontWeight: FontWeight.w400)),
              ],
            ),
          ],
        ),
      ),
      body: Column(
        children: [
          Expanded(
            child: _messages.isEmpty
                ? Center(
                    child: Padding(
                      padding: const EdgeInsets.all(24),
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(Icons.chat_bubble_outline_rounded, size: 48, color: AppTheme.primary.withOpacity(0.5)),
                          const SizedBox(height: 16),
                          Text(
                            'Ask about topology, capacity, congestion, or recommendations.',
                            textAlign: TextAlign.center,
                            style: TextStyle(color: AppTheme.muted, fontSize: 14),
                          ),
                          const SizedBox(height: 8),
                          Wrap(
                            alignment: WrapAlignment.center,
                            spacing: 8,
                            runSpacing: 8,
                            children: [
                              _SuggestionChip(label: 'Which cells share Link 2?', onTap: () => _controller.text = 'Which cells share Link 2?'),
                              _SuggestionChip(label: 'What causes congestion on Link 3?', onTap: () => _controller.text = 'What causes congestion on Link 3?'),
                              _SuggestionChip(label: 'Explain bandwidth savings', onTap: () => _controller.text = 'Explain bandwidth savings'),
                            ],
                          ),
                        ],
                      ),
                    ),
                  )
                : ListView.builder(
                    controller: _scrollController,
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                    itemCount: _messages.length + (_loading ? 1 : 0),
                    itemBuilder: (_, i) {
                      if (i == _messages.length) {
                        return _buildBubble('assistant', 'Thinking...', isTyping: true);
                      }
                      final m = _messages[i];
                      return _buildBubble(m.role, m.content);
                    },
                  ),
          ),
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(color: AppTheme.surfaceElevated),
            child: SafeArea(
              child: Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _controller,
                      decoration: InputDecoration(
                        hintText: 'Ask about fronthaul...',
                        hintStyle: TextStyle(color: AppTheme.muted),
                        filled: true,
                        fillColor: AppTheme.surfaceCard,
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(24),
                          borderSide: BorderSide.none,
                        ),
                        contentPadding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
                      ),
                      style: const TextStyle(color: Colors.white),
                      maxLines: 2,
                      minLines: 1,
                      onSubmitted: (_) => _send(),
                      textInputAction: TextInputAction.send,
                    ),
                  ),
                  const SizedBox(width: 8),
                  IconButton.filled(
                    onPressed: _loading ? null : _send,
                    icon: _loading
                        ? SizedBox(width: 22, height: 22, child: CircularProgressIndicator(strokeWidth: 2, color: AppTheme.primary))
                        : const Icon(Icons.send_rounded),
                    style: IconButton.styleFrom(backgroundColor: AppTheme.primary, foregroundColor: Colors.white),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildBubble(String role, String content, {bool isTyping = false}) {
    final isUser = role == 'user';
    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.only(bottom: 12),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.85),
        decoration: BoxDecoration(
          color: isUser ? AppTheme.primary.withOpacity(0.2) : AppTheme.surfaceCard,
          borderRadius: BorderRadius.circular(16),
          border: isUser ? null : Border.all(color: AppTheme.primary.withOpacity(0.3), width: 1),
        ),
        child: isTyping
            ? Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2, color: AppTheme.primary),
                  ),
                  const SizedBox(width: 12),
                  Text('Thinking...', style: TextStyle(color: AppTheme.muted, fontSize: 14)),
                ],
              )
            : SelectableText(
                content,
                style: TextStyle(color: Colors.white, fontSize: 14, height: 1.4),
              ),
      ),
    );
  }
}

class _ChatMessage {
  final String role;
  final String content;

  _ChatMessage({required this.role, required this.content});
}

class _SuggestionChip extends StatelessWidget {
  final String label;
  final VoidCallback onTap;

  const _SuggestionChip({required this.label, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        decoration: BoxDecoration(
          color: AppTheme.primary.withOpacity(0.15),
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: AppTheme.primary.withOpacity(0.4)),
        ),
        child: Text(label, style: TextStyle(fontSize: 12, color: AppTheme.primary)),
      ),
    );
  }
}
