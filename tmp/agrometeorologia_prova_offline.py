"""
Script rapido de Agrometeorologia para prova.
Funciona totalmente offline (sem internet e sem bibliotecas externas).
"""


def ler_float(rotulo: str) -> float:
    """Le um numero (aceita virgula ou ponto) com validacao simples."""
    while True:
        valor = input(rotulo).strip().replace(",", ".")
        try:
            return float(valor)
        except ValueError:
            print("Valor invalido. Tente novamente usando numero.")


def bloco_temperatura() -> None:
    print("\n=== TEMPERATURA ===")
    print(
        "Definicao: temperatura e a medida da energia termica do ar ou de um corpo."
    )
    print("Formulas:")
    print("C -> F = (C * 9/5) + 32")
    print("C -> K = C + 273.15")
    print("F -> C = (F - 32) * 5/9")
    print("K -> C = K - 273.15")

    temp = ler_float("Temperatura: ")
    tipo = input("Escala (C, F ou K): ").strip().upper()

    if tipo == "C":
        f = (temp * 9.0 / 5.0) + 32.0
        k = temp + 273.15
        print("\nCalculo 1 - C para F")
        print(f"F = ({temp:.2f} * 9/5) + 32")
        print(f"F = {f:.2f}")
        print("\nCalculo 2 - C para K")
        print(f"K = {temp:.2f} + 273.15")
        print(f"K = {k:.2f}")
        print(
            "Autoexplicacao: Celsius e a escala usual no campo; Fahrenheit e Kelvin ajudam "
            "em comparacoes tecnicas e cientificas."
        )
    elif tipo == "F":
        c = (temp - 32.0) * 5.0 / 9.0
        k = c + 273.15
        print("\nCalculo 1 - F para C")
        print(f"C = ({temp:.2f} - 32) * 5/9")
        print(f"C = {c:.2f}")
        print("\nCalculo 2 - C para K")
        print(f"K = {c:.2f} + 273.15")
        print(f"K = {k:.2f}")
        print(
            "Autoexplicacao: convertemos para Celsius primeiro porque muitas formulas "
            "agrometeorologicas usam C."
        )
    elif tipo == "K":
        c = temp - 273.15
        f = (c * 9.0 / 5.0) + 32.0
        print("\nCalculo 1 - K para C")
        print(f"C = {temp:.2f} - 273.15")
        print(f"C = {c:.2f}")
        print("\nCalculo 2 - C para F")
        print(f"F = ({c:.2f} * 9/5) + 32")
        print(f"F = {f:.2f}")
        print(
            "Autoexplicacao: Kelvin e comum em contexto cientifico, mas para manejo "
            "agricola geralmente usamos C."
        )
    else:
        print("Escala invalida. Use C, F ou K.")


def bloco_gd_simples() -> None:
    print("\n=== GRAUS-DIA SIMPLES ===")
    print(
        "Definicao: Graus-Dia (GD) estima a energia termica util para o desenvolvimento "
        "da cultura no dia."
    )
    print("Formula: GD = ((Tmax + Tmin) / 2) - Tb")

    tmin = ler_float("Tmin: ")
    tmax = ler_float("Tmax: ")
    tb = ler_float("Tb (base inferior): ")

    soma = tmax + tmin
    media = soma / 2.0
    gd_bruto = media - tb
    gd_final = max(gd_bruto, 0.0)

    print("\nCalculo passo a passo")
    print(f"GD = (({tmax:.2f} + {tmin:.2f}) / 2) - {tb:.2f}")
    print(f"GD = ({soma:.2f} / 2) - {tb:.2f}")
    print(f"GD = {media:.2f} - {tb:.2f}")
    print(f"GD bruto = {gd_bruto:.2f}")

    if gd_bruto < 0:
        print("Ajuste biologico: GD negativo nao existe para crescimento, entao GD final = 0.00")

    print(f"GD final = {gd_final:.2f}")
    print(
        "Autoexplicacao: quanto maior o GD final, maior a chance de avancar estagios "
        "fenologicos da planta."
    )


def bloco_gd_tb_superior() -> None:
    print("\n=== GRAUS-DIA COM TB SUPERIOR (CASOS 1, 2, 3) ===")
    print(
        "Definicao: considera limite superior de temperatura (TB), pois calor excessivo "
        "pode reduzir o aproveitamento termico."
    )
    print("Caso 1: Tmax <= TB  -> GD = ((Tmax + Tmin)/2) - Tb")
    print("Caso 2: Tmin >= TB  -> GD = TB - Tb")
    print("Caso 3: Tmin < TB < Tmax -> GD = (TB - Tb) * (Tmax - Tb) / (Tmax - Tmin)")

    tmin = ler_float("Tmin: ")
    tmax = ler_float("Tmax: ")
    tb = ler_float("Tb (base inferior): ")
    tb_superior = ler_float("TB (base superior): ")

    if tmax <= tb_superior:
        gd_bruto = ((tmax + tmin) / 2.0) - tb
        caso = 1
        print("\nCaso aplicado: 1")
        print(f"Verificacao: Tmax <= TB -> {tmax:.2f} <= {tb_superior:.2f} (verdadeiro)")
        print(f"GD = (({tmax:.2f} + {tmin:.2f}) / 2) - {tb:.2f}")
        print(f"GD = ({(tmax + tmin):.2f} / 2) - {tb:.2f}")
        print(f"GD = {(tmax + tmin) / 2.0:.2f} - {tb:.2f}")
        print(f"GD bruto = {gd_bruto:.2f}")
    elif tmin >= tb_superior:
        gd_bruto = tb_superior - tb
        caso = 2
        print("\nCaso aplicado: 2")
        print(f"Verificacao: Tmin >= TB -> {tmin:.2f} >= {tb_superior:.2f} (verdadeiro)")
        print(f"GD = {tb_superior:.2f} - {tb:.2f}")
        print(f"GD bruto = {gd_bruto:.2f}")
    else:
        denominador = tmax - tmin
        if denominador == 0:
            gd_bruto = 0.0
        else:
            gd_bruto = (tb_superior - tb) * (tmax - tb) / denominador
        caso = 3
        print("\nCaso aplicado: 3")
        print(f"Verificacao: Tmin < TB < Tmax -> {tmin:.2f} < {tb_superior:.2f} < {tmax:.2f}")
        print(
            f"GD = ({tb_superior:.2f} - {tb:.2f}) * ({tmax:.2f} - {tb:.2f}) / "
            f"({tmax:.2f} - {tmin:.2f})"
        )
        if denominador == 0:
            print("Como Tmax = Tmin, divisao por zero evitada. GD bruto = 0.00")
        else:
            print(
                f"GD = {(tb_superior - tb):.2f} * {(tmax - tb):.2f} / {denominador:.2f}"
            )
            print(f"GD bruto = {gd_bruto:.2f}")

    gd_final = max(gd_bruto, 0.0)
    if gd_bruto < 0:
        print("Ajuste biologico: GD negativo vira 0.00")

    print(f"GD final = {gd_final:.2f}")
    print(
        "Autoexplicacao: esse metodo evita superestimar crescimento em dias com calor "
        "acima do ideal da cultura."
    )


def bloco_umidade_relativa() -> None:
    print("\n=== UMIDADE RELATIVA ===")
    print(
        "Definicao: Umidade Relativa (UR) e a porcentagem de vapor de agua presente "
        "no ar em relacao ao maximo que o ar suportaria na mesma temperatura."
    )
    print("Formula: UR = (Ea / Es) * 100")

    ea = ler_float("Ea (pressao atual): ")
    es = ler_float("Es (pressao de saturacao): ")

    if es == 0:
        print("Nao e possivel dividir por zero (Es = 0).")
        return

    ur = (ea / es) * 100.0
    razao = ea / es
    print("\nCalculo passo a passo")
    print(f"UR = ({ea:.2f} / {es:.2f}) * 100")
    print(f"UR = {razao:.4f} * 100")
    print(f"UR = {ur:.2f}%")
    print(
        "Autoexplicacao: UR alta costuma reduzir a perda de agua da planta, mas pode "
        "aumentar risco de doencas fungicas."
    )


def bloco_lat_lon() -> None:
    print("\n=== LATITUDE E LONGITUDE ===")
    print(
        "Definicoes: latitude mede posicao em relacao ao Equador; longitude mede "
        "posicao em relacao ao meridiano de Greenwich."
    )
    lat = ler_float("Latitude: ")
    lon = ler_float("Longitude: ")

    if lat > 0:
        zona_lat = "Hemisferio Norte"
    elif lat < 0:
        zona_lat = "Hemisferio Sul"
    else:
        zona_lat = "Linha do Equador"

    if lon > 0:
        zona_lon = "Leste"
    elif lon < 0:
        zona_lon = "Oeste"
    else:
        zona_lon = "Meridiano de Greenwich"

    print(f"Latitude: {lat:.6f}")
    print(f"Longitude: {lon:.6f}")
    print(f"Interpretacao latitude: {zona_lat}")
    print(f"Interpretacao longitude: {zona_lon}")
    print(
        "Autoexplicacao: essas coordenadas ajudam a interpretar radiacao solar, "
        "fotoperiodo e condicoes climaticas locais."
    )


def bloco_vento() -> None:
    print("\n=== VELOCIDADE DO VENTO ===")
    print(
        "Definicao: velocidade do vento influencia evaporacao, transpirao e risco de "
        "dano mecanico nas plantas."
    )
    print("Formula util: V(km/h) = V(m/s) * 3.6")
    vento = ler_float("Velocidade do vento (m/s): ")
    vento_kmh = vento * 3.6

    if vento < 1:
        classe = "Calmo"
        msg = "Pouca evaporacao."
    elif vento < 5:
        classe = "Moderado"
        msg = "Evaporacao media."
    else:
        classe = "Forte"
        msg = "Alta evaporacao e maior estresse para a planta."

    print("\nCalculo passo a passo")
    print(f"V(km/h) = {vento:.2f} * 3.6")
    print(f"V(km/h) = {vento_kmh:.2f}")
    print(f"Classificacao: {classe}")
    print(f"Interpretacao: {msg}")
    print(
        "Autoexplicacao: com vento mais forte, o solo e a folha perdem agua mais rapido."
    )


def mostrar_menu() -> None:
    print("\n====================================")
    print("AGROMETEOROLOGIA - PROVA COMPLETA")
    print("Sistema com definicoes, calculo e autoexplicacao")
    print("(Execucao offline)")
    print("====================================")
    print("1 - Temperatura")
    print("2 - Graus-Dia Simples")
    print("3 - Graus-Dia com TB Superior (Casos 1, 2, 3)")
    print("4 - Umidade Relativa")
    print("5 - Latitude e Longitude")
    print("6 - Velocidade do Vento")
    print("7 - Sair")


def main() -> None:
    while True:
        mostrar_menu()
        op = input("Opcao: ").strip()

        if op == "1":
            bloco_temperatura()
        elif op == "2":
            bloco_gd_simples()
        elif op == "3":
            bloco_gd_tb_superior()
        elif op == "4":
            bloco_umidade_relativa()
        elif op == "5":
            bloco_lat_lon()
        elif op == "6":
            bloco_vento()
        elif op == "7":
            print("Encerrando. Boa prova!")
            break
        else:
            print("Opcao invalida. Escolha de 1 a 7.")


if __name__ == "__main__":
    main()
