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
            colorScheme.primary.withOpacity(0.16),
            colorScheme.secondary.withOpacity(0.1),
            colorScheme.surface,
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
      ),
      child: CustomScrollView(
        physics: const BouncingScrollPhysics(parent: AlwaysScrollableScrollPhysics()),
        slivers: [
          SliverSafeArea(
            bottom: false,
            sliver: SliverAppBar(
              pinned: true,
              floating: false,
              automaticallyImplyLeading: false,
              elevation: 0,
              scrolledUnderElevation: 0,
              surfaceTintColor: Colors.transparent,
              backgroundColor: colorScheme.surface.withOpacity(0.94),
              toolbarHeight: 58,
              titleSpacing: 16,
              title: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(
                    'Início',
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w900),
                  ),
                  Text(
                    'Feed fluido, premium e mais leve',
                    style: Theme.of(context).textTheme.labelMedium?.copyWith(color: colorScheme.onSurfaceVariant),
                  ),
                ],
              ),
              bottom: tabController == null
                  ? null
                  : PreferredSize(
                      preferredSize: const Size.fromHeight(50),
                      child: Padding(
                        padding: const EdgeInsets.fromLTRB(12, 0, 12, 8),
                        child: _FeedTopTabBar(tabController: tabController!),
                      ),
                    ),
            ),
          ),
          SliverPadding(
            padding: const EdgeInsets.fromLTRB(12, 8, 12, 96),
            sliver: SliverList(
              delegate: SliverChildListDelegate(
                [
                  SmartSuggestionsPanel(),
                  const SizedBox(height: 12),
                  PredictiveInsightsCard(),
                  const SizedBox(height: 12),
                  AgroChatView(),
                ],
              ),
            ),
          ),
        ],
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
      borderRadius: BorderRadius.circular(18),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 12, sigmaY: 12),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
          decoration: BoxDecoration(
            color: colorScheme.surface.withOpacity(0.82),
            borderRadius: BorderRadius.circular(18),
            border: Border.all(color: colorScheme.outlineVariant.withOpacity(0.45)),
          ),
          child: TabBar(
            controller: tabController,
            isScrollable: true,
            dividerColor: Colors.transparent,
            indicatorSize: TabBarIndicatorSize.label,
            indicatorPadding: const EdgeInsets.symmetric(horizontal: 10),
            indicator: UnderlineTabIndicator(
              borderSide: BorderSide(color: colorScheme.primary, width: 2.4),
              insets: const EdgeInsets.symmetric(horizontal: 18),
            ),
            labelColor: colorScheme.primary,
            unselectedLabelColor: colorScheme.onSurfaceVariant.withOpacity(0.78),
            labelStyle: const TextStyle(fontWeight: FontWeight.w800, fontSize: 12),
            unselectedLabelStyle: const TextStyle(fontWeight: FontWeight.w600, fontSize: 12),
            labelPadding: const EdgeInsets.symmetric(horizontal: 10),
            tabs: const [
              Tab(text: 'Inicio', icon: Icon(Icons.home_rounded, size: 18)),
              Tab(text: 'Mercado', icon: Icon(Icons.storefront_rounded, size: 18)),
              Tab(text: 'IA', icon: Icon(Icons.auto_awesome_rounded, size: 18)),
            ],
          ),
        ),
      ),
    );
  }
}
