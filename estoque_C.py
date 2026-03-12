# %%

# ========== IMPORTAÇÃO DE BIBLIOTECAS ==========
from pathlib import Path
import pandas as pd
import numpy as np
from IPython.display import display
import openpyxl

# %%

# ======== DEFINIÇÃO DO CAMINHO ==========
CAMINHO = Path(r"\\Agroserver\libs_analise\Backup 2025\01_Comerciais\2025\21. OS_200\06_Estoque de Carbono\teste")
ANO = 2025
OS = 200

# %%

# ========== FUNÇÕES DE EXECUÇÃO ==========

# Obter os arquivos específicos na pasta
def carregar_e_tratar(origem: Path):
    """
    Localiza arquivos Excel no diretório, realiza a limpeza de colunas vazias
    e converte dados numéricos.

    Args:
        origem (Path).

    Returns:
        lista[df]
    """

    if not origem.exists():
        print(f" ERRO: O caminho {origem} não existe.")
        return []
    
    lista_df_tratados = []
    colunas_alvo = ['Massa_(g)', 'Volume_coletado_(cm3)',
                    'Densidade_(g/cm3)', 'C_Quantitativo_(g/kg)']
    
    arquivos = [f for f in origem.glob("*.xlsx") if not f.name.startswith("~$")]

    if not arquivos:
        print(f"AVISO: Nenhum arquivo .xlsx encontrado em '{origem.name}'.")

    print(f"Localizado {len(arquivos)} arquivos. Iniciando processamento...")

    for arquivo in arquivos:
        try:
            df_temp = pd.read_excel(arquivo).dropna(axis=1, how='all')
            df_temp.insert(0, 'nome_arquivo', arquivo.name)

            colunas_existentes = [c for c in colunas_alvo if c in df_temp.columns]

            if colunas_existentes:
                df_temp[colunas_existentes] = (
                    df_temp[colunas_existentes]
                    .astype(str)
                    .replace(',', '.', regex=True)
                    .apply(pd.to_numeric, errors='coerce')
                )
            else:
                print(f"As colunas alvo não foram encontradas em '{arquivo.name}'.")
            
            lista_df_tratados.append(df_temp)
            print(f"{arquivo.name} processado com sucesso.")
        
        except Exception as e:
            print(f"ERRO: O processamento de {arquivo.name} não foi executado: {e}")
    
    return lista_df_tratados

# Extrair valores de espessura da camada de solo
def extrair_espessura(df: pd.DataFrame):
    """
    Extrai a espessura das amostras de solo e adiciona os valores em outra coluna.

    Args:
        df: dataframe.

    Returns:
        df.
    """

    limites = df['Profundidade'].str.extract(r'(\d+)\s*-\s*(\d+)')

    lim_sup = pd.to_numeric(limites[1], errors='coerce')
    lim_inf = pd.to_numeric(limites[0], errors='coerce')

    df['Espessura_(m)'] = ((lim_sup - lim_inf).abs())/100

    return df

# Associar dados de carbono orgânico com densidade do solo
def associar_carbono_densidade(lista_dfs: list):
    """
    Associa os dados de C orgânico com de densidade do solo para possibilitar os cálculos.
    Retorna um df contendo os dados de forma agrupada.

    Args:
        list: lista de dataframes.
    
    Returns:
        df.
    """

    if not lista_dfs:
        return pd.DataFrame()
    
    df_total = pd.concat(lista_dfs, ignore_index=True)

    print(f"Arquivos detectados antes do agrupamento: {df_total['nome_arquivo'].unique().tolist()}")

    df_total = extrair_espessura(df_total)

    chaves = ['Talhão', 'Ponto', 'Profundidade']

    df_associado = df_total.groupby(chaves, as_index=False).agg({
        'nome_arquivo': 'first',
        'Ordem_de_Serviço': 'first',
        'SID': 'first',
        'Zona_de_Manejo': 'first',
        'Espessura_(m)': 'max',
        'Densidade_(g/cm3)': 'max',
        'C_Quantitativo_(g/kg)': 'max',
        'Massa_(g)': 'max',
        'Volume_coletado_(cm3)': 'max'
    })

    print(f"Arquivos que foram processados: {df_associado['nome_arquivo'].unique().tolist()}")

    return df_associado

# Calcular o estoque de carbono no solo
def estoque_carbono(df: pd.DataFrame):

    df['Dry_Mass_(t/ha)'] = df['Espessura_(m)'] * df['Densidade_(g/cm3)'] * 10000
    df['C_Estoque_(t/ha)'] = df['Espessura_(m)'] * df['C_Quantitativo_(g/kg)'] * df['Densidade_(g/cm3)'] * 10

    def preparar_agregacao(df_subset: pd.DataFrame):
        """
        Função auxiliar para calcular cti, mti, mtn e ctn por ponto
        """
        grupo = ['Talhão', 'Ponto']
        gp = df_subset.groupby(grupo)
        last_row = gp.tail(1).set_index(grupo)

        res = gp.agg({
            'nome_arquivo': 'first',
            'C_Estoque_(t/ha)': 'sum',
            'Dry_Mass_(t/ha)': 'sum'
        }).rename(columns={'C_Estoque_(t/ha)': 'total_C', 'Dry_Mass_(t/ha)': 'mti'})

        res['cti'] = res['total_C'] - last_row['C_Estoque_(t/ha)']
        res['mtn'] = last_row['Dry_Mass_(t/ha)']
        res['ctn'] = last_row['C_Quantitativo_(g/kg)'] / 1000

        return res.reset_index()

    df_mata_base = df[df['Talhão'] == 'MATA'].copy()
    df_trat_base = df[df['Talhão'] != 'MATA'].copy()

    res_trat = preparar_agregacao(df_trat_base)
    res_mata = preparar_agregacao(df_mata_base)

    msi_ref = res_mata[['Ponto', 'mti']].rename(columns={
        'Ponto': 'ponto_mata',
        'mti': 'msi'
    })

    df_trat_cross = pd.merge(
        res_trat.rename(columns={'Talhão': 'talhao_trat', 'Ponto': 'ponto_trat'}),
        msi_ref.rename(columns={'ponto_mata': 'ponto_referencia'}),
        how='cross'
    )

    df_mata_cross = pd.merge(
        res_mata.rename(columns={'Talhão': 'talhao_trat', 'Ponto': 'ponto_trat'}),
        msi_ref.rename(columns={'ponto_mata': 'ponto_referencia'}),
        how='cross'
    )

    df_final = pd.concat([df_trat_cross, df_mata_cross], ignore_index=True)

    df_final['cs'] = df_final['cti'] + (df_final['mtn'] - (df_final['mti'] - df_final['msi'])) * df_final['ctn']

    return df_final

# Função Mestre
def main(caminho_origem: Path):
    """
    listagem, tratamento, associação e cálculo do estoque de C.

    Args:
        caminho_origem (Path): caminho para a pasta onde estão os arquivos .xlsx.
    
    Returns:
        df.
    """
    print("--- Iniciando Processamento ---")
    
    lista_dfs = carregar_e_tratar(caminho_origem)
    
    if not lista_dfs:
        print("Nenhum dado processado.")
        return None

    df_associado = associar_carbono_densidade(lista_dfs)
    
    df_calculado = estoque_carbono(df_associado)
    
    print(f"--- Processamento Concluído ---")

    n_trat = df_calculado.query("talhao_trat != 'MATA'")['ponto_trat'].nunique()
    n_mata = df_calculado.query("talhao_trat == 'MATA'")['ponto_trat'].nunique()
    
    print(f"Pontos de Tratamento: {n_trat}")
    print(f"Pontos de Referência (MATA): {n_mata}")

    df_calculado = df_calculado[['talhao_trat', 'ponto_trat', 'ponto_referencia', 'cs']].copy()

    df_calculado = (
        df_calculado.assign(
            prioridade = np.where(df_calculado['talhao_trat'] == 'MATA', 0, 1)
        )
        .sort_values(by=['prioridade', 'ponto_trat'])
        .drop(columns='prioridade')
        .reset_index(drop=True)
    )

    return df_calculado

# %%

# ========== EXECUÇÃO ==========
dados_finais = main(CAMINHO)
dados_finais

# %%

# ==== ESTOQUE DE CARBONO DOS TRATAMENTOS POR PONTO ====
estoque_ponto = (
    dados_finais.groupby(['talhao_trat', 'ponto_trat'])['cs']
    .agg(media = 'mean',desvio = 'std')
    .round(0)
    .astype(int)
    .reset_index()
    .sort_values(by=['talhao_trat', 'ponto_trat'],
                 key=lambda x: x != 'MATA' if x.name == 'talhao_trat' else x)
    .reset_index(drop=True)
)

estoque_ponto_trat = estoque_ponto[estoque_ponto['talhao_trat'] != 'MATA'].reset_index(drop=True)
print(f"Estoque de carbono médio e desvio padrão por ponto em cada tratamento:")
display(estoque_ponto_trat)

# ==== ESTOQUE DE CARBONO DA MATA POR PONTO
estoque_ponto_mata = estoque_ponto[estoque_ponto['talhao_trat'] == 'MATA'].reset_index(drop=True)
print(f"Estoque de carbono médio de desvio padrão por ponto na MATA:")
display(estoque_ponto_mata)

# ==== ESTOQUE DE CARBONO POR TALHAO ====
estoque_talhao = (
    dados_finais.groupby(['talhao_trat'])['cs']
    .agg(media = 'mean',
         desvio = 'std')
    .astype(int)
    .reset_index()
    .sort_values(by='talhao_trat')
)

estoque_talhao = estoque_talhao[estoque_talhao['talhao_trat'] != 'MATA'].copy()

print(f"Estoque de carbono médio e desvio padrão por talhão e mata:")
display(estoque_talhao)

# ==== ESTOQUE DE CARBONO MÉDIO FAZENDA E MATA ====

resumo = (
    dados_finais.assign(condicao = np.where(dados_finais['talhao_trat'] == 'MATA', 'MATA', 'TALHOES'))
    .groupby('condicao')['cs']
    .agg(media='mean', desvio='std')
    .round(0).astype(int)
    .reindex(['TALHOES', 'MATA'])
)

print(f"Estoque de carbono médio e desvio padrão dos talhões e mata:")
display(resumo)

# %%

# %%
# ========== EXPORTAÇÃO PARA EXCEL EM MÚLTIPLAS ABAS ==========

# Nome do arquivo de saída
arquivo_saida = f"{ANO}{OS}_Relatorio_Estoque_Carbono.xlsx"

with pd.ExcelWriter(arquivo_saida) as writer:
    # 1ª Aba: Estoque por ponto de coleta (apenas tratamentos)
    estoque_ponto_trat.to_excel(writer, sheet_name='Estoque_Ponto_Trat', index=False)

    # 2ª Aba: Estoque da mata detalhado por ponto
    estoque_ponto_mata.to_excel(writer, sheet_name='Estoque_Ponto_Mata', index=False)
    
    # 3ª Aba: Estoque por talhão (inclui o resumo por talhão e a média da mata)
    estoque_talhao.to_excel(writer, sheet_name='Estoque_Por_Talhao', index=False)
    
    # 4ª Aba: Resumo geral
    resumo.to_excel(writer, sheet_name='Estoque_Talhoes_Mata', index=True)

print(f"Arquivo '{arquivo_saida}' gerado com sucesso!")