import 'dart:ui';

import 'package:flutter/material.dart';

class MarketExperienceScreen extends StatefulWidget {
  const MarketExperienceScreen({super.key});

  @override
  State<MarketExperienceScreen> createState() => _MarketExperienceScreenState();
}

class _MarketExperienceScreenState extends State<MarketExperienceScreen> with SingleTickerProviderStateMixin {
  late final TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _SectionCard(
            title: 'Mercado unificado',
            subtitle: 'Ofertas e serviços deslizam com swipe lateral, mas só os nomes das abas ganham a transição de opacidade.',
            accent: colorScheme.primary,
          ),
          const SizedBox(height: 12),
          _MarketTabBar(tabController: _tabController),
          const SizedBox(height: 12),
          Expanded(
            child: TabBarView(
              controller: _tabController,
              physics: const ClampingScrollPhysics(),
              children: [
                _MarketCategoryPage(
                  storageKey: const PageStorageKey<String>('market-offers'),
                  title: 'Ofertas em destaque',
                  subtitle: 'Seleções com leitura rápida e conversão direta.',
                  accent: colorScheme.primary,
                  items: const [
                    _MarketItem(
                      title: 'Oferta premium',
                      subtitle: 'Visibilidade alta com CTA direto e prioridade comercial.',
                      icon: Icons.local_offer_rounded,
                    ),
                    _MarketItem(
                      title: 'Oferta relâmpago',
                      subtitle: 'Janela curta com urgência visual e preço claro.',
                      icon: Icons.bolt_rounded,
                    ),
                    _MarketItem(
                      title: 'Proposta inteligente',
                      subtitle: 'Comparação rápida para fechar, negociar e acompanhar.',
                      icon: Icons.auto_awesome_rounded,
                    ),
                  ],
                ),
                _MarketCategoryPage(
                  storageKey: const PageStorageKey<String>('market-services'),
                  title: 'Serviços confiáveis',
                  subtitle: 'Operação assistida com foco em confiança e execução.',
                  accent: colorScheme.secondary,
                  items: const [
                    _MarketItem(
                      title: 'Serviço verificado',
                      subtitle: 'Profissionais avaliados e confiança visível na interface.',
                      icon: Icons.verified_rounded,
                    ),
                    _MarketItem(
                      title: 'Consultoria de safra',
                      subtitle: 'Apoio técnico sob demanda para decidir mais rápido.',
                      icon: Icons.support_agent_rounded,
                    ),
                    _MarketItem(
                      title: 'Operação assistida',
                      subtitle: 'Fluxo contínuo com acompanhamento humano e previsível.',
                      icon: Icons.handyman_rounded,
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _SectionCard extends StatelessWidget {
  const _SectionCard({required this.title, required this.subtitle, required this.accent});

  final String title;
  final String subtitle;
  final Color accent;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(22),
        color: Theme.of(context).colorScheme.surface.withOpacity(0.72),
        border: Border.all(color: accent.withOpacity(0.16)),
        boxShadow: const [
          BoxShadow(color: Color.fromRGBO(0, 0, 0, 0.08), blurRadius: 18, offset: Offset(0, 10)),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w900)),
          const SizedBox(height: 8),
          Text(subtitle, style: Theme.of(context).textTheme.bodyMedium),
        ],
      ),
    );
  }
}

class _MarketTabBar extends StatelessWidget {
  const _MarketTabBar({required this.tabController});

  final TabController tabController;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return ClipRRect(
      borderRadius: BorderRadius.circular(999),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 18, sigmaY: 18),
        child: Container(
          padding: const EdgeInsets.all(4),
          decoration: BoxDecoration(
            color: colorScheme.surface.withOpacity(0.74),
            borderRadius: BorderRadius.circular(999),
            border: Border.all(color: colorScheme.primary.withOpacity(0.14)),
          ),
          child: TabBar(
            controller: tabController,
            physics: const ClampingScrollPhysics(),
            dividerColor: Colors.transparent,
            indicatorSize: TabBarIndicatorSize.tab,
            indicator: BoxDecoration(
              borderRadius: BorderRadius.circular(999),
              gradient: LinearGradient(
                colors: [
                  colorScheme.primary,
                  colorScheme.secondary,
                ],
              ),
              boxShadow: [
                BoxShadow(
                  color: colorScheme.primary.withOpacity(0.22),
                  blurRadius: 18,
                  offset: const Offset(0, 8),
                ),
              ],
            ),
            tabs: [
              Tab(
                child: _MarketTabLabel(
                  tabController: tabController,
                  index: 0,
                  label: 'Ofertas',
                ),
              ),
              Tab(
                child: _MarketTabLabel(
                  tabController: tabController,
                  index: 1,
                  label: 'Serviços',
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _MarketTabLabel extends StatelessWidget {
  const _MarketTabLabel({required this.tabController, required this.index, required this.label});

  final TabController tabController;
  final int index;
  final String label;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return AnimatedBuilder(
      animation: tabController.animation ?? tabController,
      builder: (context, _) {
        final value = tabController.animation?.value ?? tabController.index.toDouble();
        final distance = (value - index).abs().clamp(0.0, 1.0);
        final progress = 1.0 - distance;
        final opacity = lerpDouble(0.56, 1.0, progress)!;
        final scale = lerpDouble(0.96, 1.0, progress)!;
        final weight = progress > 0.65 ? FontWeight.w900 : FontWeight.w700;

        return Opacity(
          opacity: opacity,
          child: Transform.scale(
            scale: scale,
            child: Text(
              label,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: Theme.of(context).textTheme.labelLarge?.copyWith(
                    color: colorScheme.onSurface,
                    fontWeight: weight,
                    letterSpacing: 0.1,
                  ),
            ),
          ),
        );
      },
    );
  }
}

class _MarketCategoryPage extends StatelessWidget {
  const _MarketCategoryPage({
    required this.storageKey,
    required this.title,
    required this.subtitle,
    required this.accent,
    required this.items,
  });

  final PageStorageKey<String> storageKey;
  final String title;
  final String subtitle;
  final Color accent;
  final List<_MarketItem> items;

  @override
  Widget build(BuildContext context) {
    return ListView(
      key: storageKey,
      physics: const ClampingScrollPhysics(),
      padding: const EdgeInsets.only(bottom: 100),
      children: [
        _SectionCard(title: title, subtitle: subtitle, accent: accent),
        const SizedBox(height: 12),
        ...items.map(
          (item) => Padding(
            padding: const EdgeInsets.only(bottom: 10),
            child: _MarketCard(item: item, accent: accent),
          ),
        ),
      ],
    );
  }
}

class _MarketCard extends StatelessWidget {
  const _MarketCard({required this.item, required this.accent});

  final _MarketItem item;
  final Color accent;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(20),
        color: colorScheme.surface.withOpacity(0.72),
        border: Border.all(color: accent.withOpacity(0.14)),
        boxShadow: const [
          BoxShadow(color: Color.fromRGBO(0, 0, 0, 0.08), blurRadius: 18, offset: Offset(0, 10)),
        ],
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(14),
              gradient: LinearGradient(
                colors: [
                  accent.withOpacity(0.18),
                  accent.withOpacity(0.08),
                ],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
            ),
            child: Icon(item.icon, color: accent),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  item.title,
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w900),
                ),
                const SizedBox(height: 6),
                Text(
                  item.subtitle,
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        color: colorScheme.onSurfaceVariant,
                      ),
                ),
              ],
            ),
          ),
          const Icon(Icons.chevron_right_rounded),
        ],
      ),
    );
  }
}

class _MarketItem {
  const _MarketItem({required this.title, required this.subtitle, required this.icon});

  final String title;
  final String subtitle;
  final IconData icon;
}
