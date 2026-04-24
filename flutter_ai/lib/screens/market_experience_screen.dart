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
    final isMobile = MediaQuery.of(context).size.width < 768;
    if (isMobile) {
      return const _MobileMarketExperienceScreen();
    }

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

class _MobileMarketExperienceScreen extends StatefulWidget {
  const _MobileMarketExperienceScreen({super.key});

  @override
  State<_MobileMarketExperienceScreen> createState() => _MobileMarketExperienceScreenState();
}

class _MobileMarketExperienceScreenState extends State<_MobileMarketExperienceScreen> {
  static const _categories = [
    _MobileMarketCategory(label: 'Todos', icon: Icons.apps_rounded),
    _MobileMarketCategory(label: 'Insumos', icon: Icons.eco_rounded, tag: 'insumos'),
    _MobileMarketCategory(label: 'Logística', icon: Icons.local_shipping_rounded, tag: 'logistica'),
    _MobileMarketCategory(label: 'Consultoria', icon: Icons.support_agent_rounded, tag: 'consultoria'),
    _MobileMarketCategory(label: 'Tecnologia', icon: Icons.sensors_rounded, tag: 'tecnologia'),
  ];

  static const _offers = [
    _MobileMarketItem(
      title: 'Kit Irrigação Smart',
      subtitle: 'Instalação rápida com controle preciso para ciclos curtos.',
      priceLabel: 'R$ 249,90',
      location: 'Londrina • PR',
      icon: Icons.water_drop_rounded,
      tags: ['insumos', 'tecnologia'],
      actionLabel: 'Ver oferta',
    ),
    _MobileMarketItem(
      title: 'Semente Selecionada',
      subtitle: 'Lote premium com envio veloz e estoque imediato.',
      priceLabel: 'R$ 89,90',
      location: 'Ribeirão Preto • SP',
      icon: Icons.grass_rounded,
      tags: ['insumos'],
      actionLabel: 'Ver oferta',
    ),
    _MobileMarketItem(
      title: 'Entrega Express',
      subtitle: 'Rota otimizada para receber insumos sem atraso.',
      priceLabel: 'R$ 39,90',
      location: 'Curitiba • PR',
      icon: Icons.local_shipping_rounded,
      tags: ['logistica'],
      actionLabel: 'Agendar',
    ),
    _MobileMarketItem(
      title: 'Drone de Análise',
      subtitle: 'Monitoramento visual com leitura rápida do terreno.',
      priceLabel: 'R$ 1.290,00',
      location: 'Uberaba • MG',
      icon: Icons.sensors_rounded,
      tags: ['tecnologia'],
      actionLabel: 'Explorar',
    ),
    _MobileMarketItem(
      title: 'Pack Bioinsumos',
      subtitle: 'Linha compacta para manejo leve e recorrente.',
      priceLabel: 'R$ 179,90',
      location: 'Goiânia • GO',
      icon: Icons.spa_rounded,
      tags: ['insumos'],
      actionLabel: 'Comprar',
    ),
    _MobileMarketItem(
      title: 'Mapa de Campo',
      subtitle: 'Levantamento técnico para orientar a próxima decisão.',
      priceLabel: 'R$ 149,00',
      location: 'Campo Grande • MS',
      icon: Icons.map_rounded,
      tags: ['consultoria', 'tecnologia'],
      actionLabel: 'Solicitar',
    ),
  ];

  static const _services = [
    _MobileMarketItem(
      title: 'Consultoria de Safra',
      subtitle: 'Plano de ação rápido com acompanhamento humano.',
      priceLabel: 'A partir de R$ 180',
      location: 'Online',
      icon: Icons.support_agent_rounded,
      tags: ['consultoria'],
      actionLabel: 'Solicitar',
    ),
    _MobileMarketItem(
      title: 'Operação Assistida',
      subtitle: 'Fluxo contínuo com previsibilidade na execução.',
      priceLabel: 'A partir de R$ 320',
      location: 'Campo Grande • MS',
      icon: Icons.handyman_rounded,
      tags: ['consultoria', 'logistica'],
      actionLabel: 'Agendar',
    ),
    _MobileMarketItem(
      title: 'Rota de Insumos',
      subtitle: 'Gestão de entrega e recebimento com rastreio.',
      priceLabel: 'Sob orçamento',
      location: 'Sul e Sudeste',
      icon: Icons.local_shipping_rounded,
      tags: ['logistica'],
      actionLabel: 'Abrir rota',
    ),
    _MobileMarketItem(
      title: 'Manejo de Pragas',
      subtitle: 'Diagnóstico enxuto para resposta rápida no campo.',
      priceLabel: 'R$ 240,00',
      location: 'Presencial',
      icon: Icons.bug_report_rounded,
      tags: ['consultoria'],
      actionLabel: 'Ver plano',
    ),
    _MobileMarketItem(
      title: 'Suporte Técnico',
      subtitle: 'Ajuda guiada para resolver gargalos operacionais.',
      priceLabel: 'R$ 99,00',
      location: 'Online e presencial',
      icon: Icons.headset_mic_rounded,
      tags: ['consultoria'],
      actionLabel: 'Falar agora',
    ),
    _MobileMarketItem(
      title: 'Diagnóstico por Drone',
      subtitle: 'Leitura de área com visão rápida e relatórios leves.',
      priceLabel: 'R$ 390,00',
      location: 'Regional',
      icon: Icons.sensors_rounded,
      tags: ['tecnologia'],
      actionLabel: 'Solicitar',
    ),
  ];

  final TextEditingController _searchController = TextEditingController();
  int _selectedCategoryIndex = 0;

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  List<_MobileMarketItem> _filterItems(List<_MobileMarketItem> items) {
    final query = _searchController.text.trim().toLowerCase();
    final selectedCategory = _categories[_selectedCategoryIndex];

    return items.where((item) {
      final matchesCategory = selectedCategory.tag == null || item.tags.contains(selectedCategory.tag);
      final matchesQuery = query.isEmpty ||
          item.title.toLowerCase().contains(query) ||
          item.subtitle.toLowerCase().contains(query) ||
          item.location.toLowerCase().contains(query) ||
          item.priceLabel.toLowerCase().contains(query);
      return matchesCategory && matchesQuery;
    }).toList(growable: false);
  }

  void _resetFilters() {
    setState(() {
      _selectedCategoryIndex = 0;
      _searchController.clear();
    });
  }

  void _goBack(BuildContext context) {
    Navigator.maybePop(context);
  }

  void _showInfo(BuildContext context, String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message)),
    );
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final bottomInset = MediaQuery.of(context).padding.bottom;

    return ColoredBox(
      color: const Color(0xFFF5F5F2),
      child: DefaultTabController(
        length: 2,
        child: Builder(
          builder: (context) {
            final tabController = DefaultTabController.of(context)!;
            final offers = _filterItems(_offers);
            final services = _filterItems(_services);

            return Stack(
              children: [
                Positioned.fill(
                  child: SafeArea(
                    bottom: false,
                    child: Padding(
                      padding: const EdgeInsets.fromLTRB(16, 12, 16, 96),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          _MobileStoreHeader(
                            colorScheme: colorScheme,
                            onBackPressed: () => _goBack(context),
                            onResetPressed: _resetFilters,
                            onCartPressed: () => _showInfo(context, 'Carrinho em breve'),
                          ),
                          const SizedBox(height: 12),
                          _MobileSearchBar(
                            controller: _searchController,
                            onChanged: (_) => setState(() {}),
                            onClear: _resetFilters,
                          ),
                          const SizedBox(height: 12),
                          _MobileCategoryRail(
                            categories: _categories,
                            selectedIndex: _selectedCategoryIndex,
                            onSelected: (index) => setState(() {
                              _selectedCategoryIndex = index;
                            }),
                          ),
                          const SizedBox(height: 12),
                          _MobileHistoryEmptyState(
                            onExploreOffers: () {
                              tabController.animateTo(0);
                            },
                          ),
                          const SizedBox(height: 12),
                          _MobileTabBar(tabController: tabController),
                          const SizedBox(height: 12),
                          Expanded(
                            child: TabBarView(
                              controller: tabController,
                              physics: const ClampingScrollPhysics(),
                              children: [
                                _MobileMarketGridPage(
                                  storageKey: const PageStorageKey<String>('mobile-market-offers'),
                                  accent: colorScheme.primary,
                                  emptyTitle: 'Nenhuma oferta encontrada',
                                  emptySubtitle: 'Ajuste a busca ou volte para ver todas as ofertas disponíveis.',
                                  emptyButtonLabel: 'Explorar ofertas',
                                  onEmptyPressed: _resetFilters,
                                  items: offers,
                                ),
                                _MobileMarketGridPage(
                                  storageKey: const PageStorageKey<String>('mobile-market-services'),
                                  accent: colorScheme.secondary,
                                  emptyTitle: 'Nenhum serviço encontrado',
                                  emptySubtitle: 'Tente outro filtro para abrir novos serviços e operações.',
                                  emptyButtonLabel: 'Explorar serviços',
                                  onEmptyPressed: () {
                                    tabController.animateTo(1);
                                    _resetFilters();
                                  },
                                  items: services,
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
                Positioned(
                  right: 16,
                  bottom: bottomInset + 16,
                  child: _MobileFloatingActions(
                    onSearchPressed: () => _showInfo(context, 'Busque pelo topo'),
                    onCartPressed: () => _showInfo(context, 'Carrinho em breve'),
                  ),
                ),
              ],
            );
          },
        ),
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


class _MobileStoreHeader extends StatelessWidget {
  const _MobileStoreHeader({
    required this.colorScheme,
    required this.onBackPressed,
    required this.onResetPressed,
    required this.onCartPressed,
  });

  final ColorScheme colorScheme;
  final VoidCallback onBackPressed;
  final VoidCallback onResetPressed;
  final VoidCallback onCartPressed;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(16),
        color: colorScheme.surface.withOpacity(0.95),
        border: Border.all(color: colorScheme.primary.withOpacity(0.12)),
        boxShadow: const [
          BoxShadow(color: Color.fromRGBO(0, 0, 0, 0.08), blurRadius: 16, offset: Offset(0, 8)),
        ],
      ),
      child: Row(
        children: [
          _HeaderIconButton(
            icon: Icons.arrow_back_rounded,
            tooltip: 'Voltar',
            onPressed: onBackPressed,
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text(
                  'Loja Agro',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w900),
                ),
                const SizedBox(height: 2),
                Text(
                  'Marketplace mobile',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: colorScheme.onSurfaceVariant,
                        fontWeight: FontWeight.w600,
                      ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          _HeaderIconButton(
            icon: Icons.tune_rounded,
            tooltip: 'Limpar filtros',
            onPressed: onResetPressed,
          ),
          const SizedBox(width: 6),
          _HeaderIconButton(
            icon: Icons.shopping_cart_rounded,
            tooltip: 'Carrinho',
            onPressed: onCartPressed,
          ),
        ],
      ),
    );
  }
}

class _HeaderIconButton extends StatelessWidget {
  const _HeaderIconButton({required this.icon, required this.tooltip, required this.onPressed});

  final IconData icon;
  final String tooltip;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: tooltip,
      child: Material(
        color: Theme.of(context).colorScheme.surfaceVariant.withOpacity(0.45),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        child: InkWell(
          borderRadius: BorderRadius.circular(12),
          onTap: onPressed,
          child: SizedBox(
            width: 40,
            height: 40,
            child: Icon(icon),
          ),
        ),
      ),
    );
  }
}

class _MobileSearchBar extends StatelessWidget {
  const _MobileSearchBar({required this.controller, required this.onChanged, required this.onClear});

  final TextEditingController controller;
  final ValueChanged<String> onChanged;
  final VoidCallback onClear;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 48,
      child: TextField(
        controller: controller,
        onChanged: onChanged,
        textInputAction: TextInputAction.search,
        style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
        decoration: InputDecoration(
          hintText: 'Buscar ofertas, serviços e insumos',
          prefixIcon: const Icon(Icons.search_rounded),
          suffixIcon: controller.text.isEmpty
              ? null
              : IconButton(
                  icon: const Icon(Icons.close_rounded),
                  onPressed: onClear,
                ),
          filled: true,
          fillColor: Colors.white,
          contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 0),
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: BorderSide(color: Theme.of(context).colorScheme.outlineVariant),
          ),
          enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: BorderSide(color: Theme.of(context).colorScheme.outlineVariant),
          ),
          focusedBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: BorderSide(color: Theme.of(context).colorScheme.primary, width: 1.2),
          ),
        ),
      ),
    );
  }
}

class _MobileCategoryRail extends StatelessWidget {
  const _MobileCategoryRail({required this.categories, required this.selectedIndex, required this.onSelected});

  final List<_MobileMarketCategory> categories;
  final int selectedIndex;
  final ValueChanged<int> onSelected;

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      physics: const ClampingScrollPhysics(),
      child: Row(
        children: List.generate(categories.length, (index) {
          final category = categories[index];
          final isSelected = index == selectedIndex;
          return Padding(
            padding: EdgeInsets.only(right: index == categories.length - 1 ? 0 : 10),
            child: _MobileCategoryTile(
              category: category,
              isSelected: isSelected,
              onTap: () => onSelected(index),
            ),
          );
        }),
      ),
    );
  }
}

class _MobileCategoryTile extends StatelessWidget {
  const _MobileCategoryTile({required this.category, required this.isSelected, required this.onTap});

  final _MobileMarketCategory category;
  final bool isSelected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Material(
      color: isSelected ? const Color(0xFF5D7F2F).withOpacity(0.12) : colorScheme.surface,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: BorderSide(
          color: isSelected ? const Color(0xFF5D7F2F) : colorScheme.outlineVariant,
        ),
      ),
      elevation: isSelected ? 3 : 0,
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: onTap,
        child: SizedBox(
          width: 102,
          height: 90,
          child: Padding(
            padding: const EdgeInsets.all(10),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Container(
                  width: 34,
                  height: 34,
                  decoration: BoxDecoration(
                    color: isSelected ? const Color(0xFF5D7F2F) : colorScheme.surfaceVariant,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Icon(
                    category.icon,
                    color: isSelected ? Colors.white : colorScheme.onSurfaceVariant,
                    size: 20,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  category.label,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.labelMedium?.copyWith(
                        fontWeight: FontWeight.w800,
                        color: isSelected ? const Color(0xFF5D7F2F) : colorScheme.onSurfaceVariant,
                      ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _MobileHistoryEmptyState extends StatelessWidget {
  const _MobileHistoryEmptyState({required this.onExploreOffers});

  final VoidCallback onExploreOffers;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(16),
        color: colorScheme.surface.withOpacity(0.95),
        border: Border.all(color: colorScheme.outlineVariant),
      ),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.history_rounded, size: 44, color: colorScheme.primary),
          const SizedBox(height: 8),
          Text(
            'Histórico vazio',
            style: Theme.of(context).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w800),
          ),
          const SizedBox(height: 4),
          Text(
            'Suas buscas recentes vão aparecer aqui.',
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(color: colorScheme.onSurfaceVariant),
          ),
          const SizedBox(height: 10),
          FilledButton.tonal(
            onPressed: onExploreOffers,
            child: const Text('Explorar ofertas'),
          ),
        ],
      ),
    );
  }
}

class _MobileTabBar extends StatelessWidget {
  const _MobileTabBar({required this.tabController});

  final TabController tabController;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
  final PageStorageKey<String> storageKey;
    return ClipRRect(
      borderRadius: BorderRadius.circular(25),
      child: Container(
        padding: const EdgeInsets.all(6),
        decoration: BoxDecoration(
          color: const Color(0xFFF5F5F2),
          borderRadius: BorderRadius.circular(25),
          boxShadow: const [
            BoxShadow(color: Color.fromRGBO(0, 0, 0, 0.08), blurRadius: 18, offset: Offset(0, 8)),
          ],
          border: Border.all(color: colorScheme.outlineVariant.withOpacity(0.7)),
        ),
        child: TabBar(
          controller: tabController,
          isScrollable: true,
          dividerColor: Colors.transparent,
          indicatorSize: TabBarIndicatorSize.tab,
          labelPadding: const EdgeInsets.symmetric(horizontal: 18),
          indicator: BoxDecoration(
            borderRadius: BorderRadius.circular(20),
            color: const Color(0xFF5D7F2F),
          ),
          labelColor: Colors.white,
          unselectedLabelColor: colorScheme.onSurfaceVariant,
          tabs: [
            Tab(
              child: _MobileTabLabel(
                tabController: tabController,
                index: 0,
                label: 'Ofertas',
              ),
            ),
            Tab(
              child: _MobileTabLabel(
                tabController: tabController,
                index: 1,
                label: 'Serviços',
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _MobileTabLabel extends StatelessWidget {
  const _MobileTabLabel({required this.tabController, required this.index, required this.label});

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
        final opacity = lerpDouble(0.62, 1.0, progress)!;
        final scale = lerpDouble(0.97, 1.0, progress)!;

        return Opacity(
          opacity: opacity,
          child: Transform.scale(
            scale: scale,
            child: Text(
              label,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: Theme.of(context).textTheme.labelLarge?.copyWith(
                    color: Color.lerp(colorScheme.onSurfaceVariant, Colors.white, progress),
                    fontWeight: progress > 0.5 ? FontWeight.w900 : FontWeight.w700,
                    letterSpacing: 0.08,
                  ),
            ),
          ),
        );
      },
    );
  }
}

class _MobileMarketGridPage extends StatelessWidget {
  const _MobileMarketGridPage({
    required this.storageKey,
    required this.accent,
    required this.items,
    required this.emptyTitle,
    required this.emptySubtitle,
    required this.emptyButtonLabel,
    required this.onEmptyPressed,
  });

  final PageStorageKey<String> storageKey;
  final Color accent;
  final List<_MobileMarketItem> items;
  final String emptyTitle;
  final String emptySubtitle;
  final String emptyButtonLabel;
  final VoidCallback onEmptyPressed;

  @override
  Widget build(BuildContext context) {
    if (items.isEmpty) {
      return _MobileEmptyCatalogState(
        icon: Icons.search_off_rounded,
        title: emptyTitle,
        subtitle: emptySubtitle,
        buttonLabel: emptyButtonLabel,
        onPressed: onEmptyPressed,
        accent: accent,
      );
    }

    return GridView.builder(
      key: storageKey,
      physics: const ClampingScrollPhysics(),
      padding: const EdgeInsets.only(bottom: 104),
      itemCount: items.length,
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 2,
        childAspectRatio: 0.75,
        crossAxisSpacing: 12,
        mainAxisSpacing: 12,
      ),
      itemBuilder: (context, index) {
        return _MobileProductCard(
          item: items[index],
          accent: accent,
        );
      },
    );
  }
}

class _MobileEmptyCatalogState extends StatelessWidget {
  const _MobileEmptyCatalogState({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.buttonLabel,
    required this.onPressed,
    required this.accent,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final String buttonLabel;
  final VoidCallback onPressed;
  final Color accent;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Center(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 20),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              width: 72,
              height: 72,
              decoration: BoxDecoration(
                color: accent.withOpacity(0.12),
                borderRadius: BorderRadius.circular(20),
              ),
              child: Icon(icon, size: 34, color: accent),
            ),
            const SizedBox(height: 14),
            Text(
              title,
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w900),
            ),
            const SizedBox(height: 8),
            Text(
              subtitle,
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(color: colorScheme.onSurfaceVariant),
            ),
            const SizedBox(height: 14),
            FilledButton(
              onPressed: onPressed,
              child: Text(buttonLabel),
            ),
          ],
        ),
      ),
    );
  }
}

class _MobileFloatingActions extends StatelessWidget {
  const _MobileFloatingActions({required this.onSearchPressed, required this.onCartPressed});

  final VoidCallback onSearchPressed;
  final VoidCallback onCartPressed;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        _FloatingCircleButton(
          icon: Icons.search_rounded,
          color: colorScheme.primary,
          onPressed: onSearchPressed,
        ),
        const SizedBox(height: 10),
        _FloatingCircleButton(
          icon: Icons.shopping_cart_rounded,
          color: colorScheme.secondary,
          onPressed: onCartPressed,
        ),
      ],
    );
  }
}

class _FloatingCircleButton extends StatelessWidget {
  const _FloatingCircleButton({required this.icon, required this.color, required this.onPressed});

  final IconData icon;
  final Color color;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: color,
      shape: const CircleBorder(),
      elevation: 8,
      child: InkWell(
        customBorder: const CircleBorder(),
        onTap: onPressed,
        child: SizedBox(
          width: 56,
          height: 56,
          child: Icon(icon, color: Colors.white, size: 24),
        ),
      ),
    );
  }
}

class _MobileMarketCategory {
  const _MobileMarketCategory({required this.label, required this.icon, this.tag});

  final String label;
  final IconData icon;
  final String? tag;
}

class _MobileMarketItem {
  const _MobileMarketItem({
    required this.title,
    required this.subtitle,
    required this.priceLabel,
    required this.location,
    required this.icon,
    required this.tags,
    required this.actionLabel,
  });

  final String title;
  final String subtitle;
  final String priceLabel;
  final String location;
  final IconData icon;
  final List<String> tags;
  final String actionLabel;
}

class _MobileProductCard extends StatelessWidget {
  const _MobileProductCard({required this.item, required this.accent});

  final _MobileMarketItem item;
  final Color accent;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Material(
      color: colorScheme.surface,
      elevation: 0,
      borderRadius: BorderRadius.circular(16),
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: () {},
        child: Container(
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: colorScheme.outlineVariant),
            color: colorScheme.surface,
          ),
          clipBehavior: Clip.antiAlias,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              SizedBox(
                height: 132,
                child: Container(
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      colors: [
                        accent.withOpacity(0.22),
                        accent.withOpacity(0.08),
                      ],
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                    ),
                  ),
                  child: Center(
                    child: Icon(item.icon, size: 48, color: accent),
                  ),
                ),
              ),
              Expanded(
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Flexible(
                        child: Text(
                          item.title,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: Theme.of(context).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w900),
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        item.priceLabel,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: Theme.of(context).textTheme.titleSmall?.copyWith(
                              color: accent,
                              fontWeight: FontWeight.w900,
                            ),
                      ),
                      const SizedBox(height: 2),
                      Row(
                        children: [
                          Icon(Icons.place_outlined, size: 14, color: colorScheme.onSurfaceVariant),
                          const SizedBox(width: 3),
                          Expanded(
                            child: Text(
                              item.location,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                                    color: colorScheme.onSurfaceVariant,
                                  ),
                            ),
                          ),
                        ],
                      ),
                      const Spacer(),
                      SizedBox(
                        width: double.infinity,
                        height: 34,
                        child: FilledButton.tonal(
                          onPressed: () {},
                          style: FilledButton.styleFrom(
                            padding: const EdgeInsets.symmetric(horizontal: 10),
                          ),
                          child: Text(
                            item.actionLabel,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
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
