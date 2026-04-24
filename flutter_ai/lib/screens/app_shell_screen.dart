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
                _ShellHeader(tabController: _tabController),
                const SizedBox(height: 10),
                _StoriesRail(tabController: _tabController),
                const SizedBox(height: 10),
                const _StructureAndTechStrip(),
                const SizedBox(height: 10),
                Expanded(
                  child: TabBarView(
                    controller: _tabController,
                    physics: const ClampingScrollPhysics(),
                    children: const [
                      AIDashboardContent(),
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

class _ShellHeader extends StatelessWidget {
  const _ShellHeader({required this.tabController});

  final TabController tabController;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(24),
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: 18, sigmaY: 18),
          child: Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [
                  colorScheme.surface.withOpacity(0.88),
                  colorScheme.surface.withOpacity(0.62),
                ],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              borderRadius: BorderRadius.circular(24),
              border: Border.all(color: colorScheme.primary.withOpacity(0.16)),
            ),
            child: AnimatedBuilder(
              animation: tabController,
              builder: (context, _) {
                final value = tabController.animation?.value ?? tabController.index.toDouble();
                final currentTab = _tabs[(value.round()).clamp(0, _tabs.length - 1)];

                return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Container(
                          height: 38,
                          width: 38,
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            gradient: LinearGradient(
                              colors: [
                                colorScheme.primary,
                                colorScheme.secondary,
                              ],
                            ),
                          ),
                          child: const Icon(Icons.play_arrow_rounded, color: Colors.white),
                        ),
                        const SizedBox(width: 10),
                        Text(
                          'WallFruits Studio',
                          style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w900),
                        ),
                      ],
                    ),
                    const SizedBox(height: 6),
                    Text(
                      'Interface social-first com foco em descoberta, feed visual e automacao inteligente.',
                      style: Theme.of(context).textTheme.bodyMedium,
                    ),
                    const SizedBox(height: 10),
                    Row(
                      children: [
                        _MetricChip(
                          icon: Icons.swipe_rounded,
                          label: 'Swipe ${(value + 1).round().clamp(1, 3)}/3',
                        ),
                        const SizedBox(width: 8),
                        _MetricChip(
                          icon: currentTab.icon,
                          label: currentTab.shortLabel,
                        ),
                      ],
                    ),
                  ],
                );
              },
            ),
          ),
        ),
      ),
    );
  }
}

class _StoriesRail extends StatelessWidget {
  const _StoriesRail({required this.tabController});

  final TabController tabController;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return SizedBox(
      height: 88,
      child: ListView.separated(
        padding: const EdgeInsets.symmetric(horizontal: 16),
        scrollDirection: Axis.horizontal,
        itemCount: _tabs.length,
        separatorBuilder: (_, __) => const SizedBox(width: 10),
        itemBuilder: (context, index) {
          final tab = _tabs[index];
          final isSelected = tabController.index == index;

          return GestureDetector(
            onTap: () => tabController.animateTo(index),
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 220),
              width: 84,
              padding: const EdgeInsets.symmetric(vertical: 8),
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(18),
                color: colorScheme.surface.withOpacity(isSelected ? 0.92 : 0.75),
                border: Border.all(
                  color: (isSelected ? tab.primary : colorScheme.outlineVariant).withOpacity(0.52),
                ),
              ),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Container(
                    height: 42,
                    width: 42,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      gradient: LinearGradient(
                        colors: [tab.primary, tab.secondary],
                      ),
                    ),
                    child: Icon(tab.icon, size: 22, color: Colors.white),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    tab.shortLabel,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: Theme.of(context).textTheme.labelSmall?.copyWith(fontWeight: FontWeight.w700),
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }
}

class _StructureAndTechStrip extends StatelessWidget {
  const _StructureAndTechStrip();

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(20),
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: 12, sigmaY: 12),
          child: Container(
            width: double.infinity,
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: colorScheme.surface.withOpacity(0.8),
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: colorScheme.outlineVariant.withOpacity(0.55)),
            ),
            child: Wrap(
              spacing: 8,
              runSpacing: 8,
              children: const [
                _TagPill(label: 'Visual: Social Video UX'),
                _TagPill(label: 'Estrutura: Modulos por dominio'),
                _TagPill(label: 'Flutter 3'),
                _TagPill(label: 'FastAPI'),
                _TagPill(label: 'PostgreSQL + Redis'),
                _TagPill(label: 'IA e Automacao'),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

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