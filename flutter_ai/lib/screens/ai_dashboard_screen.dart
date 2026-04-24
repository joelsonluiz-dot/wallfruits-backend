import 'dart:ui';

import 'package:flutter/material.dart';

import '../widgets/ai_assistant_fab.dart';
import '../widgets/agro_chat_view.dart';
import '../widgets/predictive_insights_card.dart';
import '../widgets/smart_suggestions_panel.dart';

class AIDashboardScreen extends StatelessWidget {
  const AIDashboardScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: const AIDashboardContent(),
      floatingActionButton: const AIAssistantFab(),
    );
  }
}

class AIDashboardContent extends StatelessWidget {
  const AIDashboardContent({super.key, this.tabController});

  final TabController? tabController;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Container(
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            colorScheme.primary.withOpacity(0.22),
            colorScheme.secondary.withOpacity(0.15),
            colorScheme.surface,
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
      ),
      child: SafeArea(
        top: tabController == null,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 100),
          children: [
            if (tabController != null) ...[
              _FeedTopTabBar(tabController: tabController!),
              const SizedBox(height: 16),
            ],
            SmartSuggestionsPanel(),
            const SizedBox(height: 12),
            PredictiveInsightsCard(),
            const SizedBox(height: 12),
            AgroChatView(),
          ],
        ),
      ),
    );
  }
}

class _FeedTopTabBar extends StatelessWidget {
  const _FeedTopTabBar({required this.tabController});

  final TabController tabController;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return ClipRRect(
      borderRadius: BorderRadius.circular(20),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 14, sigmaY: 14),
        child: Container(
          padding: const EdgeInsets.all(8),
          decoration: BoxDecoration(
            color: colorScheme.surface.withOpacity(0.62),
            borderRadius: BorderRadius.circular(20),
            border: Border.all(color: colorScheme.primary.withOpacity(0.18)),
          ),
          child: TabBar(
            controller: tabController,
            isScrollable: true,
            dividerColor: Colors.transparent,
            indicatorSize: TabBarIndicatorSize.tab,
            indicator: BoxDecoration(
              color: colorScheme.primary.withOpacity(0.14),
              borderRadius: BorderRadius.circular(999),
            ),
            labelColor: colorScheme.primary,
            unselectedLabelColor: colorScheme.onSurfaceVariant,
            labelPadding: const EdgeInsets.symmetric(horizontal: 14),
            tabs: const [
              Tab(text: 'Inicio', icon: Icon(Icons.home_rounded)),
              Tab(text: 'Mercado', icon: Icon(Icons.storefront_rounded)),
              Tab(text: 'IA', icon: Icon(Icons.auto_awesome_rounded)),
            ],
          ),
        ),
      ),
    );
  }
}
