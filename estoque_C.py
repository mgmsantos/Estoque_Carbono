# %%

# ========== IMPORTAÇÃO DE BIBLIOTECAS ==========
from pathlib import Path
import pandas as pd
import numpy as np
from IPython.display import display

# %%

# ======== DEFINIÇÃO DO CAMINHO ==========
CAMINHO = Path(r"\\Agroserver\libs_analise\Backup 2025\01_Comerciais\2025\21. OS_200\06_Estoque de Carbono\teste")

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
        df.
    """

    if not origem.exists():
        print(f" ERRO: O caminho {origem} não existe.")
        return []
    
    df_tratados = []
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
            
            df_tratados.append(df_temp)
            print(f"{arquivo.name} processado com sucesso.")
        
        except Exception as e:
            print(f"ERRO: O processamento de {arquivo.name} não foi executado.")
    
    return df_tratados

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

    lim_sup = pd.to_numeric(limites[0], errors='coerce')
    lim_inf = pd.to_numeric(limites[1], errors='coerce')

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

    print(f"Arquivos detectados antes do agrupamento: {df_total['nome_arquivo'].unique()}")

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

    print(f"Arquivos que foram processados: {df_associado['nome_arquivo'].unique()}")

    return df_associado

# Calcular o estoque de carbono no solo
def estoque_carbono(df: pd.DataFrame):

    df['Dry_Mass_(t/ha)'] = df['Espessura_(m)'] * df['Densidade_(g/cm3)'] * 10000
    df['C_Estoque_(t/ha)'] = df['Espessura_(m)'] * df['C_Quantitativo_(g/kg)'] * df['Densidade_(g/cm3)'] * 10

    MATA = df[(df['Talhão'] == 'MATA')].reset_index(drop=True)
    TRATAMENTOS = df[~(df['Talhão'] == 'MATA')].reset_index(drop=True)

    grupo = ['Talhão', 'Ponto']
    gp_trat = TRATAMENTOS.groupby(grupo)
    last_row = gp_trat.tail(1).set_index(grupo)
    
    df_res = gp_trat.agg({
        'nome_arquivo': 'first',
        'C_Estoque_(t/ha)': 'sum',
        'Dry_Mass_(t/ha)': 'sum'
    }).rename(columns={'C_Estoque_(t/ha)': 'total_C',
                       'Dry_Mass_(t/ha)': 'mti'})
    
    df_res['cti'] = df_res['total_C'] - last_row['C_Estoque_(t/ha)']
    df_res['mtn'] = last_row['Dry_Mass_(t/ha)']
    df_res['ctn'] = last_row['C_Quantitativo_(g/kg)'] / 1000
    df_res = df_res.reset_index()

    msi = (
    MATA.groupby(grupo)['Dry_Mass_(t/ha)']
    .sum()
    .reset_index(name='msi')
    )

    df_res = df_res.rename(columns={
    'Talhão': 'talhao_trat',
    'Ponto': 'ponto_trat'
    }).copy()

    msi = msi.rename(columns={
        'Talhão': 'talhao_mata',
        'Ponto': 'ponto_mata'
    }).copy()

    df_cross = pd.merge(df_res, msi, how='cross')
    df_cross['cs'] = df_cross['cti'] +(df_cross['mtn'] - (df_cross['mti'] - df_cross['msi'])) * df_cross['ctn']
    return df_cross, MATA

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
    
    df_final, df_mata = estoque_carbono(df_associado)
    
    print(f"--- Processamento Concluído ---")
    print(f"Total de arquivos .xlsx processados: {len(lista_dfs)}")
    print(f"Total de pontos únicos processados: {np.max(df_final['ponto_trat'])}")
    
    return df_final[['talhao_trat', 'ponto_trat', 'nome_arquivo', 'cs']], df_mata

# %%

# ========== EXECUÇÃO ==========
dados_finais, dados_mata = main(CAMINHO)

# %%

estoque_C_ponto = (
dados_finais.groupby(['talhao_trat', 'ponto_trat'])['cs'].agg(
    media='mean',
    desvio='std'
).round(0).reset_index())

estoque_C_ponto.to_excel("estoque_C_ponto_teste.xlsx", index=False)

# %%

display(
dados_finais.groupby(['talhao_trat'])['cs'].agg(
    media='mean',
    desvio='std'
).round(0).reset_index()
)


# %%

print(f"média: {np.mean(dados_finais['cs']).round(0)}")
print(f"dv: {np.std(dados_finais['cs'])}")