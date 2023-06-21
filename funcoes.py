import psycopg2 #pip install psycopg2 
import psycopg2.extras
import pandas as pd
import warnings
import unicodedata

warnings.filterwarnings("ignore")

# DB_HOST = "localhost"
DB_HOST = "database-2.cdcogkfzajf0.us-east-1.rds.amazonaws.com"
DB_NAME = "postgres"
DB_USER = "postgres"
DB_PASS = "15512332"

# conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST)   

# cur = conn.cursor
# df = pd.read_csv('Carretas Agrícolas (1).csv', encoding='latin-1', sep=";")

# columns = df.columns

# # Criar a tabela no banco de dados
# create_table_query = f"CREATE TABLE tb_produtos ({columns});"
# cursor = conn.cursor()
# cursor.execute(create_table_query)
# conn.commit()
# conn.close()

# # Substitua os valores NaN por None e normalize os nomes das colunas
# for row in df.itertuples(index=False):
#     query = f"INSERT INTO tb_produtos VALUES {row}"

#     row_values = (row.Chave, row.Codigo, row.Nome, row.Referencia_Principal, row.Descricao_Generica, row.Classe, row.CRM, row.Un, row.Localizacao_fisica, row.Classificacao_Fiscal, row.Procedencia, row.Modelo, row.Eixo, row.Mola_Freio, row.Cor, row.Tamanho, row.Rodado, row.Pneu, row.Outras_Caracteristicas, row.Volume, row.Bruto, row.Liquido)
#     row_values = [None if pd.isna(value) else value for value in row_values]
#     column_names = ['Chave', 'Codigo', 'Nome', 'Referencia_Principal', 'Descricao_Generica', 'Classe', 'CRM', 'Un', 'Localizacao_fisica', 'Classificacao_Fiscal', 'Procedencia', 'Modelo', 'Eixo', 'Mola_Freio', 'Cor', 'Tamanho', 'Rodado', 'Pneu', 'Outras_Caracteristicas', 'Volume', 'Bruto', 'Liquido']

#     # Montar a string de inserção com os nomes das colunas
#     columns = ', '.join(column_names)

#     # Montar a string de placeholders para os valores
#     placeholders = ', '.join(['%s'] * len(row_values))

#     # Montar a query de inserção
#     query = f"INSERT INTO tb_produtos ({columns}) VALUES ({placeholders});"

#     # Executar a query com os valores da linha
#     cursor.execute(query, row_values)
