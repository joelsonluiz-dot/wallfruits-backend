import 'dart:ui';

import 'package:flutter/material.dart';

import '../widgets/ai_assistant_fab.dart';
import 'ai_dashboard_screen.dart';
import 'automation_lab_screen.dart';
import 'market_experience_screen.dart';

class AppShellScreen extends StatefulWidget {
  const AppShellScreen({super.key});

  @override
  State<AppShellScreen> createState() => _AppShellScreenState();
}

class _AppShellScreenState extends State<AppShellScreen> with SingleTickerProviderStateMixin {
  static const _tabs = [
    AppShellTab.feed,
    AppShellTab.market,
    AppShellTab.ai,
  ];

  late final TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: _tabs.length, vsync: this);
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Scaffold(
      body: Stack(
        children: [
          Container(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [
                  colorScheme.surface,
                  colorScheme.surfaceContainerLowest,
                  colorScheme.surface,
                ],
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
              ),
            ),
          ),
          Positioned(
            top: -80,
            right: -40,
            child: _GradientOrb(
              size: 220,
              colors: [
                colorScheme.primary.withOpacity(0.24),
                colorScheme.tertiary.withOpacity(0.18),
              ],
            ),
          ),
          Positioned(
            bottom: 120,
            left: -36,
            child: _GradientOrb(
              size: 180,
              colors: [
                colorScheme.secondary.withOpacity(0.2),
                colorScheme.primary.withOpacity(0.1),
              ],
            ),
          ),
          SafeArea(
            child: Column(
              children: [
                Expanded(
                  child: TabBarView(
                    controller: _tabController,
                    physics: const ClampingScrollPhysics(),
                    children: [
                      AIDashboardContent(tabController: _tabController),
                      MarketExperienceScreen(),
                      AutomationLabScreen(),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
      bottomNavigationBar: _BottomDockTabBar(tabController: _tabController),
      floatingActionButton: const AIAssistantFab(),
    );
  }
}

enum AppShellTab { feed, market, ai }
class _BottomDockTabBar extends StatelessWidget {
  const _BottomDockTabBar({required this.tabController});

  final TabController tabController;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return SafeArea(
      top: false,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(12, 4, 12, 12),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(24),
          child: BackdropFilter(
            filter: ImageFilter.blur(sigmaX: 14, sigmaY: 14),
            child: Container(
              decoration: BoxDecoration(
                color: colorScheme.surface.withOpacity(0.9),
                borderRadius: BorderRadius.circular(24),
                border: Border.all(color: colorScheme.outlineVariant.withOpacity(0.52)),
              ),
              child: TabBar(
                controller: tabController,
                dividerColor: Colors.transparent,
                indicatorColor: Colors.transparent,
                tabs: _tabs
                    .map(
                      (tab) => Tab(
                        icon: Icon(tab.icon),
                        text: tab.label,
                      ),
                    )
                    .toList(),
                labelColor: colorScheme.primary,
                unselectedLabelColor: colorScheme.onSurfaceVariant,
                labelStyle: const TextStyle(fontWeight: FontWeight.w800, fontSize: 12),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _GradientOrb extends StatelessWidget {
  const _GradientOrb({required this.size, required this.colors});

  final double size;
  final List<Color> colors;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: size,
      width: size,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        gradient: RadialGradient(colors: colors),
      ),
    );
  }
}

class _MetricChip extends StatelessWidget {
  const _MetricChip({required this.icon, required this.label});

  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
      decoration: BoxDecoration(
        color: colorScheme.primaryContainer.withOpacity(0.42),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 16, color: colorScheme.primary),
          const SizedBox(width: 6),
          Text(
            label,
            style: Theme.of(context).textTheme.labelSmall?.copyWith(
                  color: colorScheme.primary,
                  fontWeight: FontWeight.w800,
                ),
          ),
        ],
      ),
    );
  }
}

class _TagPill extends StatelessWidget {
  const _TagPill({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
      decoration: BoxDecoration(
        color: colorScheme.secondaryContainer.withOpacity(0.5),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        label,
        style: Theme.of(context).textTheme.labelSmall?.copyWith(fontWeight: FontWeight.w700),
      ),
    );
  }
}

extension on AppShellTab {
  String get label {
    switch (this) {
      case AppShellTab.feed:
        return 'Inicio';
      case AppShellTab.market:
        return 'Mercado';
      case AppShellTab.ai:
        return 'IA';
    }
  }

  String get shortLabel {
    switch (this) {
      case AppShellTab.feed:
        return 'Feed';
      case AppShellTab.market:
        return 'Shop';
      case AppShellTab.ai:
        return 'Lab';
    }
  }

  IconData get icon {
    switch (this) {
      case AppShellTab.feed:
        return Icons.video_collection_rounded;
      case AppShellTab.market:
        return Icons.storefront_rounded;
      case AppShellTab.ai:
        return Icons.auto_awesome_rounded;
    }
  }

  Color get primary {
    switch (this) {
      case AppShellTab.feed:
        return const Color(0xFFFC4A7D);
      case AppShellTab.market:
        return const Color(0xFF0DAD8B);
      case AppShellTab.ai:
        return const Color(0xFF2F7DFF);
    }
  }

  Color get secondary {
    switch (this) {
      case AppShellTab.feed:
        return const Color(0xFFFF9A44);
      case AppShellTab.market:
        return const Color(0xFF8AE05F);
      case AppShellTab.ai:
        return const Color(0xFF43C6FF);
    }
  }
}