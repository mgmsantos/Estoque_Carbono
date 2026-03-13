## Visão Geral

Esta automação foi desenvolvida para processar dados de inventário de carbono no solo, aplicando o método de Massa de Solo Equivalente. O script padroniza a leitura de dados brutos, realiza cálculos volumétricos e gera um relatório comparativo detalhado entre áreas de manejo (tratamentos) e áreas de referência (MATA).

## Resumo da Metodologia

O cálculo central utiliza a correção de massa para comparar camadas de solo de densidades diferentes, garantindo que a comparação do estoque de carbono seja feita sobre a mesma massa de solo seco.

A fórmula aplicada para o Estoque de Carbono Corrigido (Fernandes; Fernandes, 2008) corresponde a:

$$cs = cti + (mtn - (mti - msi)) \times ctn$$

**Onde:**
* **$cs$**: Estoque de Carbono Corrigido ($t/ha$).
* **$cti$**: Carbono acumulado até a penúltima camada ($t/ha$).
* **$mtn$**: Massa de solo seco da última camada ($t/   ha$).
* **$mti$**: Massa de solo acumulada total do ponto ($t/ha$).
* **$msi$**: Massa de solo acumulada da referência (MATA) ($t/ha$).
* **$ctn$**: Concentração de carbono na última camada ($t/t$).

## Arquitetura da Automação

1. Ingestão e Tratamento (carregar_e_tratar)
Varredura: Localiza todos os arquivos .xlsx no diretório configurado, ignorando arquivos temporários.

Limpeza: Remove colunas vazias e converte vírgulas em pontos para garantir que dados numéricos sejam lidos corretamente pelo Python.

Extração de Espessura: A função extrair_espessura interpreta strings de profundidade (ex: "0-20") para calcular a espessura em metros.

2. Processamento e Cálculo (estoque_carbono)
Cálculos de Camada: Calcula a Massa Seca (Dry_Mass) e o Estoque de Carbono por camada individual.

Agregação por Ponto: Consolida as camadas de cada ponto, identificando a última camada para fins de correção de massa.

Análise Cruzada: Realiza um merge tipo cross entre cada ponto de tratamento e todos os pontos da MATA, permitindo calcular a média do estoque corrigido com base em múltiplas referências.

3. Consolidação e Estatística
O script gera quatro níveis de visualização:

Por Ponto (Tratamentos): Média e desvio padrão de cada ponto de coleta.

Por Ponto (Mata): Validação interna da variabilidade da área de referência.

Por Talhão: Média consolidada de todas as amostras pertencentes a uma unidade de manejo.

Resumo Geral: Comparativo simplificado entre a média total dos talhões e a média da mata.

## Estrutura de saída

O arquivo de saída é nomeado dinamicamente (ex: 2025200_Relatorio_Estoque_Carbono.xlsx) e contém as seguintes abas:

| Aba | Conteúdo |
| :--- | :--- |
| **Estoque_Ponto_Trat** | Média e Desvio Padrão por Ponto |
| **Estoque_Ponto_Mata** | Média e Desvio Padrão da Referência (Mata) |
| **Estoque_Por_Talhao** | Média e Desvio Padrão por Talhão |
| **Estoque_Talhoes_Mata** | Médias Globais (Talhões vs Mata) |

## Requesitos do sistema

* Linguagem: Python 3.x

* Bibliotecas: pandas, numpy, openpyxl, pathlib.

* Input: Planilhas Excel com colunas padronizadas: Talhão, Ponto, Profundidade, Densidade_(g/cm3), C_Quantitativo_(g/kg).

# Referências

Fernandes, F. A.; Fernandes, A. H. B. M. [Cálculo dos estoques de carbono do solo sob diferentes condições de manejo](https://www.infoteca.cnptia.embrapa.br/bitstream/doc/792567/1/COT69.pdf). Comunicado Técnico, Embrapa Pantanal, n. 69, 2008.