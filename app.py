from flask import Flask, render_template, redirect, url_for, request, session, flash, make_response, Response
from flask import render_template_string, jsonify
import psycopg2  # pip install psycopg2
import psycopg2.extras
import pandas as pd
import numpy as np
import functools
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from io import BytesIO
from datetime import date
import json
from datetime import datetime
import uuid
from sqlalchemy import create_engine
import warnings
from babel.numbers import format_currency
import requests
import cachetools
from datetime import timedelta

warnings.filterwarnings("ignore")

app = Flask(__name__)
app.secret_key = "listaPreco"

# DB_HOST = "localhost"
DB_HOST = "database-2.cdcogkfzajf0.us-east-1.rds.amazonaws.com"
DB_NAME = "postgres"
DB_USER = "postgres"
DB_PASS = "15512332"

conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER,
                        password=DB_PASS, host=DB_HOST)

engine = create_engine(
    f'postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{5432}/{DB_NAME}')

# Você pode ajustar o tamanho máximo do cache conforme necessário
cache_precos = cachetools.LRUCache(maxsize=128)
# Você pode ajustar o tamanho máximo do cache conforme necessário
cache_produtos = cachetools.LRUCache(maxsize=128)


def resetar_cache():
    cache_precos.clear()
    cache_produtos.clear()


@cachetools.cached(cache_precos)
def api_precos():

    response = requests.get(
        'http://cemag.innovaro.com.br/api/publica/v1/tabelas/listarPrecos')

    # Verificar o código de status HTTP
    if response.status_code == 200:

        # A consulta foi bem-sucedida
        dados = response.json()
        df = pd.json_normalize(dados, 'tabelaPreco')
        df = df.explode('precos')

        # Criar colunas separadas para "valor" e "produto"
        df['valor'] = df['precos'].apply(lambda x: x['valor'])
        df['produto'] = df['precos'].apply(lambda x: x['produto'])
        df['valor'] = pd.to_numeric(
            df['valor'].str.replace('.', '').str.replace(',', '.'))

        df['nome'] = df['nome'].replace(
            'Lista Preço Sudeste/Centro Oeste', 'Lista de Preço SDE/COE')
        df['nome'] = df['nome'].replace(
            'Lista Preço MT/RO', 'Lista de Preço MT/RO')
        df['nome'] = df['nome'].replace(
            'Lista Preço N e NE', 'Lista Norte/Nordeste')

        df = df.drop(columns=['precos', 'codigo'])

        df = df.rename(
            columns={'nome': 'lista', 'valor': 'preco', 'produto': 'codigo'})

        print(df)

        df_final = df[['lista', 'codigo', 'preco']].reset_index(drop=True)
        df_final['lista_nova'] = df_final['lista'].str.replace(' de ', ' ')\
            .str.replace('/', ' e ')\
            .str.replace('Lista Norte e Nordeste', 'Lista Preço N e NE')

        df_final_precos = df_final

    else:
        conn = psycopg2.connect(
            dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        df_final = pd.read_sql("select * from tb_lista_precos", conn)

        df_final['lista_nova'] = df_final['lista'].str.replace(' de ', ' ')\
            .str.replace('/', ' e ')\
            .str.replace('Lista Norte e Nordeste', 'Lista Preço N e NE')

        df_final_precos = df_final

    return df_final_precos


@cachetools.cached(cache_produtos)
def api_lista_produtos():

    response = requests.get(
        'https://cemag.innovaro.com.br/api/publica/v1/tabelas/listarProdutos')

    # A consulta foi bem-sucedida
    dados = response.json()
    df = pd.json_normalize(dados, 'produtos')

    df_final = df[df['CRM'] == True].reset_index(drop=True)
    df_final['pneu_tratado'] = df_final['pneu'].replace('', 'Sem pneu')
    df_final['outras_caracteristicas_tratadas'] = df_final['funcionalidade'].replace(
        '', 'N/A')
    df_final['tamanho_tratados'] = df_final['tamanho'].replace('', 'N/A')

    return df_final


@app.route('/login', methods=['GET', 'POST'])
def login():
    conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER,
                            password=DB_PASS, host=DB_HOST)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        cur.execute(
            "SELECT * FROM users WHERE username = %s AND password = %s", (username, password))
        user = cur.fetchone()

        if user is not None:
            session['user_id'] = user['username']
            return redirect(url_for('opcoes'))
        else:
            flash('Usuário ou Senha inválida', category='error')

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        # Verifique se o nome de usuário já está em uso
        cur.execute(
            'SELECT id FROM users WHERE username = {}'.format("'"+username+"'"))
        verific = cur.fetchall()
        if len(verific) > 0:
            flash('Username {} is already taken.'.format(username))
        else:
            # Insira o novo usuário no banco de dados
            cur.execute("INSERT INTO users (username, email, password) VALUES (%s, %s, %s)",
                        (username, email, password))
            conn.commit()
            flash('User {} registered successfully.'.format(username))
            return redirect(url_for('login'))

    return render_template('register.html')


def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))

        return view(**kwargs)

    return wrapped_view


@app.route('/atualizar-cache',  methods=['GET', 'POST'])
@login_required
def atualizar_caches():

    if request.method == 'POST':

        cache_precos.clear()
        cache_produtos.clear()
        print("atualizado")
        return jsonify({'message': 'Cache atualizado com sucesso!'})

    return render_template('lista.html')


@app.route('/',  methods=['GET', 'POST'])
@login_required
def lista():

    nome_cliente = request.args.get('nome_cliente')

    if nome_cliente == None:
        nome_cliente = 'Agro Imperial-Leopoldina'

    conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER,
                            password=DB_PASS, host=DB_HOST)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    representante = session['user_id']

    df_precos = api_precos()

    df_produtos = api_lista_produtos()

    tb_favoritos = tabela_favoritos(representante)

    df = df_produtos.merge(df_precos, how='left', on='codigo')
    
    df = df.merge(tb_favoritos, how='left', on='codigo')
    
    regiao = buscarRegiaoCliente(nome_cliente)

    df = df[df['lista_nova'] == regiao]

    df['preco'] = df['preco'].apply(lambda x: "R$ {:,.2f}".format(
        x).replace(",", "X").replace(".", ",").replace("X", "."))

    df['pneu_tratado'] = df['pneu_tratado'].fillna('Sem pneu')

    df = df.sort_values(by='favorito')

    data = df.values.tolist()

    print(df)

    descricao_unique = df[['descGenerica']
                          ].drop_duplicates().values.tolist()
    modelo_unique = df[['modelo']].drop_duplicates().values.tolist()
    eixo_unique = df[['eixo']].drop_duplicates().values.tolist()
    mola_freio_unique = df[['molaFreio']].drop_duplicates().values.tolist()
    tamanho_unique = df[['tamanho_tratados']].drop_duplicates().values.tolist()
    rodado_unique = df[['rodado']].drop_duplicates().values.tolist()
    pneu_unique = df[['pneu_tratado']].drop_duplicates().values.tolist()
    descricao_generica_unique = df[[
        'outras_caracteristicas_tratadas']].drop_duplicates().values.tolist()

    return render_template('lista.html', representante=representante, data=data,
                           descricao_unique=descricao_unique, modelo_unique=modelo_unique,
                           eixo_unique=eixo_unique, mola_freio_unique=mola_freio_unique,
                           tamanho_unique=tamanho_unique, rodado_unique=rodado_unique,
                           pneu_unique=pneu_unique, descricao_generica_unique=descricao_generica_unique,
                           nome_cliente=nome_cliente)


@app.route('/move/<string:id>', methods=['POST', 'GET'])
@login_required
def move(id):

    conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER,
                            password=DB_PASS, host=DB_HOST)

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    representante = ""+session['user_id']+""

    df = pd.read_sql_query(
        'SELECT * FROM tb_lista_precos WHERE id = {}'.format(id), conn)

    for coluna in df.columns:
        if df[coluna].dtype == 'object':
            df[coluna] = df[coluna].str.strip()

    cur.execute("INSERT INTO tb_favoritos (id, familia, codigo, descricao, representante, preco) VALUES (%s,%s,%s,%s,%s,%s)", (int(
        np.int64(df['id'][0])), df['familia'][0], df['codigo'][0], df['descricao'][0], representante, df['preco'][0]))
    cur.execute('DELETE FROM tb_lista_precos WHERE id = {0}'.format(id))
    conn.commit()
    conn.close()

    return redirect(url_for('lista'))


@app.route('/favoritos', methods=['POST'])
@login_required
def lista_favoritos():

    conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER,
                            password=DB_PASS, host=DB_HOST)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Obter o estado do favorito da solicitação
    favorite_state = request.json.get('favorite')
    codigo_carreta = request.json.get('rowId')
    representante = ""+session['user_id']+""

    print(favorite_state)
    print(codigo_carreta)
    print(representante)
    # Faça o processamento necessário com os dados recebidos

    if favorite_state == 'on':
        """QUERY PARA ADICIONAR ITEM NA TABELA DE FAVORITOS"""
        query = """ insert into tb_favoritos (codigo,representante,favorito) 
                    values ('{}','{}','{}')""".format(codigo_carreta, representante, favorite_state)

        cur.execute(query)

        conn.commit()
        conn.close()

    else:
        """QUERY PARA EXCLUIR O ITEM DA TABELA DE FAVORITOS"""
        query = """DELETE FROM tb_favoritos WHERE codigo = '{}' and representante = '{}'""".format(
            codigo_carreta, representante)
        cur.execute(query)

        conn.commit()
        conn.close()

    return 'Sucesso'


def tabela_favoritos(representante):

    conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER,
                            password=DB_PASS, host=DB_HOST)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
                SELECT *
                FROM tb_favoritos
                WHERE representante = '{}'
                """.format(representante))

    tb_favoritos = cur.fetchall()
    tb_favoritos = pd.DataFrame(tb_favoritos) 

    return tb_favoritos


@app.route('/remove/<string:id>', methods=['POST', 'GET'])
@login_required
def remove(id):

    conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER,
                            password=DB_PASS, host=DB_HOST)

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    representante = ""+session['user_id']+""

    representante = """Galo"""

    df = pd.read_sql_query(
        'SELECT * FROM tb_favoritos WHERE id = {}'.format(id), conn)

    for coluna in df.columns:
        if df[coluna].dtype == 'object':
            df[coluna] = df[coluna].str.strip()

    cur.execute("INSERT INTO tb_lista_precos (id, familia, codigo, descricao, representante, preco) VALUES (%s,%s,%s,%s,%s,%s)", (int(
        np.int64(df['id'][0])), df['familia'][0], df['codigo'][0], df['descricao'][0], representante, df['preco'][0]))

    cur.execute('DELETE FROM tb_favoritos WHERE id = {0}'.format(id))

    conn.commit()
    conn.close()

    return redirect(url_for('lista_favoritos'))


@app.route('/logout')
@login_required
def logout():
    session.clear()  # limpa as informações da sessão
    return redirect(url_for('login'))  # redireciona para a página de login


@app.route('/teste')
@login_required
def teste():
    return render_template("teste.html")


@app.route('/export/pdf')
def export_pdf():
    # Dados da tabela

    representante = "'"+session['user_id']+"'"

    # representante = "'Galo'"
    conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER,
                            password=DB_PASS, host=DB_HOST)

    s = "SELECT familia,codigo,descricao,preco FROM tb_favoritos where representante = {}".format(
        representante)
    data = pd.read_sql_query(s, conn)

    data['codigo'] = data['codigo'].str.strip()
    data['descricao'] = data['descricao'].str.strip()
    data['familia'] = data['familia'].str.strip()

    header = ['Família', 'Código', 'Descrição', 'Preço']

    data = data.values.tolist()
    data.insert(0, header)

    # Estilos para a tabela
    styles = getSampleStyleSheet()
    style_heading = styles['Heading2']
    style_table = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.gray),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('ALIGN', (0, 1), (-1, -1), 'CENTER'),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ('RIGHTPADDING', (0, 1), (-1, -1), 6),
        ('LEFTPADDING', (0, 1), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ])

    # Criar a tabela
    table = Table(data)
    table.setStyle(style_table)

    # Criar o documento
    response = make_response('')
    response.headers.set('Content-Disposition', 'attachment',
                         filename='tabela-produtos.pdf')
    buff = BytesIO()
    # doc = SimpleDocTemplate(buff, pagesize=landscape(letter))

    # Mudar a orientação para paisagem
    doc_width, doc_height = landscape(letter)
    # Passar o tamanho do documento
    doc = SimpleDocTemplate(buff, pagesize=(doc_width, doc_height))

    # Adicionar a tabela ao documento
    elements = []
    elements.append(table)

    doc.build(elements)

    # Retornar o PDF como resposta HTTP
    response.data = buff.getvalue()
    buff.close()
    response.headers.set('Content-Type', 'application/pdf')
    return response


@app.route('/export/pdf-all')
def export_pdf_all():
    # Dados da tabela

    representante = "'"+session['user_id']+"'"

    # representante = "'Galo'"
    conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER,
                            password=DB_PASS, host=DB_HOST)

    s = "SELECT familia,codigo,descricao,preco FROM tb_lista_precos where representante = {}".format(
        representante)
    data = pd.read_sql_query(s, conn)

    data['codigo'] = data['codigo'].str.strip()
    data['descricao'] = data['descricao'].str.strip()
    data['familia'] = data['familia'].str.strip()

    header = ['Família', 'Código', 'Descrição', 'Preço']

    data = data.values.tolist()
    data.insert(0, header)

    # Estilos para a tabela
    styles = getSampleStyleSheet()
    style_heading = styles['Heading2']
    style_table = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.gray),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        # ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 7),
        ('ALIGN', (0, 1), (-1, -1), 'CENTER'),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ('RIGHTPADDING', (0, 1), (-1, -1), 6),
        ('LEFTPADDING', (0, 1), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ])

    # Criar a tabela
    table = Table(data)
    table.setStyle(style_table)

    # Criar o documento
    response = make_response('')
    response.headers.set('Content-Disposition', 'attachment',
                         filename='tabela-produtos-all.pdf')
    buff = BytesIO()
    # doc = SimpleDocTemplate(buff, pagesize=landscape(letter))

    # Mudar a orientação para paisagem
    doc_width, doc_height = landscape(letter)
    # Passar o tamanho do documento
    doc = SimpleDocTemplate(buff, pagesize=(doc_width, doc_height))

    # Adicionar a tabela ao documento
    elements = []
    elements.append(table)

    doc.build(elements)

    # Retornar o PDF como resposta HTTP
    response.data = buff.getvalue()
    buff.close()
    response.headers.set('Content-Type', 'application/pdf')
    return response


@app.route('/car')
def adicionar_ao_carrinho():

    conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER,
                            password=DB_PASS, host=DB_HOST)

    representante = "'"+session['user_id']+"'"
    # representante = """'Galo'"""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "SELECT * FROM tb_carrinho_representante where representante = {}".format(representante))
    data = cur.fetchall()

    for row in data:
        preco = float(row['preco'])
        row['preco'] = "R$ {:,.2f}".format(preco).replace(
            ",", "X").replace(".", ",").replace("X", ".")

    return render_template("car.html", data=data)


@app.route('/salvar_dados', methods=['POST', 'GET'])
def salvar_dados():

    if request.method == 'POST':

        conn = psycopg2.connect(
            dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST)
        cur = conn.cursor()

        tabela = request.form.get('tabela')
        tabela = json.loads(tabela)

        cliente = request.form.get('numeroCliente')
        status = request.form.get("statusCotacao")

        print(status, cliente)

        unique_id = str(uuid.uuid4())  # Gerar id unico

        representante = ""+session['user_id']+""

        tb_orcamento = pd.DataFrame(tabela)

        query = "SELECT nome_completo FROM users WHERE username = %s"

        cur.execute(query, (representante,))

        nome_completo = cur.fetchall()
        nome_completo = nome_completo[0][0]

        tb_orcamento['representante'] = nome_completo
        tb_orcamento['dataOrcamento'] = datetime.today()
        tb_orcamento['dataOrcamento'] = tb_orcamento['dataOrcamento'].dt.strftime(
            '%Y-%m-%d')
        tb_orcamento['cliente'] = cliente
        tb_orcamento['id'] = unique_id
        tb_orcamento['status'] = status

        tb_orcamento['precoFinal'] = tb_orcamento['precoFinal'].str.replace(
            "R\$", "").str.replace(".", "").str.replace(",", ".").astype(float)
        tb_orcamento['preco'] = tb_orcamento['preco'].str.replace(
            "R\$", "").str.replace(".", "").str.replace(",", ".").astype(float)

        print(tb_orcamento)

        # Cria uma lista de tuplas contendo os valores das colunas do DataFrame
        valores = list(zip(tb_orcamento['familia'], tb_orcamento['codigo'], tb_orcamento['descricao'], tb_orcamento['preco'], tb_orcamento['precoFinal'],
                           tb_orcamento['quantidade'].astype(
                               int), tb_orcamento['representante'], tb_orcamento['dataOrcamento'], tb_orcamento['cliente'], tb_orcamento['id'],
                           tb_orcamento['status']))

        # Cria a string de consulta SQL para a inserção
        consulta = "INSERT INTO tb_orcamento (familia, codigo, descricao, preco, precoFinal, quantidade, representante, dataOrcamento, cliente, id, status) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"

        # Abre uma transação explícita
        with conn:
            # Cria um cursor dentro do contexto da transação
            with conn.cursor() as cur:
                # Executa a inserção das linhas usando executemany
                cur.executemany(consulta, valores)

        return jsonify({'mensagem': 'Dados enviados com sucesso'})


@app.route('/move-carrinho/<string:id>', methods=['POST', 'GET'])
@login_required
def move_carrinho(id):

    conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER,
                            password=DB_PASS, host=DB_HOST)

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    representante = "'"+session['user_id']+"'"

    df = pd.read_sql_query(
        'SELECT * FROM tb_lista_precos WHERE id = {}'.format(id), conn)

    for coluna in df.columns:
        if df[coluna].dtype == 'object':
            df[coluna] = df[coluna].str.strip()

    df_carrinho = pd.read_sql_query(
        'SELECT * FROM tb_carrinho_representante WHERE representante = {}'.format(representante), conn)

    df_carrinho = df_carrinho['codigo'].values.tolist()

    representante = ""+session['user_id']+""

    if df['codigo'][0] not in df_carrinho:
        cur.execute("INSERT INTO tb_carrinho_representante (familia, codigo, descricao, preco, representante) VALUES (%s,%s,%s,%s,%s)",
                    (df['familia'][0], df['codigo'][0], df['descricao'][0], df['preco'][0], representante))
        conn.commit()
        conn.close()
    else:
        pass

    return redirect(url_for('lista'))


@app.route('/move-carrinho-favorito/<string:id>', methods=['POST', 'GET'])
@login_required
def move_carrinho_favorito(id):

    conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER,
                            password=DB_PASS, host=DB_HOST)

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    representante = "'"+session['user_id']+"'"

    df = pd.read_sql_query(
        'SELECT * FROM tb_favoritos WHERE id = {}'.format(id), conn)

    for coluna in df.columns:
        if df[coluna].dtype == 'object':
            df[coluna] = df[coluna].str.strip()

    df_carrinho = pd.read_sql_query(
        'SELECT * FROM tb_carrinho_representante WHERE representante = {}'.format(representante), conn)

    df_carrinho = df_carrinho['codigo'].values.tolist()

    representante = ""+session['user_id']+""

    if df['codigo'][0] not in df_carrinho:
        cur.execute("INSERT INTO tb_carrinho_representante (familia, codigo, descricao, preco, representante) VALUES (%s,%s,%s,%s,%s)",
                    (df['familia'][0], df['codigo'][0], df['descricao'][0], df['preco'][0], representante))
        conn.commit()
        conn.close()
    else:
        pass

    return redirect(url_for('lista_favoritos'))


@app.route('/remove-carrinho/<string:id>', methods=['POST', 'GET'])
@login_required
def remove_carrinho(id):

    conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER,
                            password=DB_PASS, host=DB_HOST)

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    representante = "'"+session['user_id']+"'"

    # representante = """Galo"""

    cur.execute('DELETE FROM tb_carrinho_representante WHERE id = {}'.format(id))

    conn.commit()

    conn.close()

    return redirect(url_for('adicionar_ao_carrinho'))


@app.route('/remove-all', methods=['POST', 'GET'])
@login_required
def remove_all():

    conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER,
                            password=DB_PASS, host=DB_HOST)

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    representante = "'"+session['user_id']+"'"

    # representante = """Galo"""

    cur.execute('DELETE FROM tb_carrinho_representante WHERE representante = {}'.format(
        representante))

    conn.commit()

    conn.close()

    return redirect(url_for('adicionar_ao_carrinho'))

##### Bloco de orçamentos #####


@app.route('/orcamentos', methods=['GET'])
@login_required
def orcamentos():

    conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER,
                            password=DB_PASS, host=DB_HOST)

    # filtro_cliente = request.args.get('cliente')
    filtro_data = request.args.get('filtro_data')
    filtro_cliente = request.args.get('filtro_cliente')
    filtro_status = request.args.get('filtro_status')
    representante = session['user_id']

    print(representante)

    # Conexão com o banco de dados PostgreSQL
    cur = conn.cursor()

    # Construindo a consulta com placeholder
    sql1 = "SELECT cliente, id, SUM(precofinal * quantidade) AS soma_total, SUM(quantidade) AS quantidade_total, status FROM tb_orcamento WHERE 1=1 AND representante = %s"
    sql2 = " GROUP BY cliente, id, status"

    placeholders = [representante]

    if filtro_data and filtro_data != '':
        if filtro_data != '':
            data_inicial, data_final = filtro_data.split(" - ")

            print(data_inicial, data_final)

            # Converter as strings em objetos de data
            data_inicial = datetime.strptime(data_inicial, "%Y-%m-%d").date()
            data_final = datetime.strptime(data_final, "%Y-%m-%d").date()

            # Adiciona um espaço em branco antes do AND
            sql1 += " AND dataOrcamento BETWEEN %s AND %s"
            placeholders.extend([data_inicial, data_final])

    if filtro_cliente and filtro_cliente != 'Todos':
        sql1 += " AND cliente = %s"  # Adiciona um espaço em branco antes do AND
        placeholders.append(filtro_cliente)

    if filtro_status and filtro_status != 'Todos':
        sql1 += " AND status = %s"  # Adiciona um espaço em branco antes do AND
        placeholders.append(filtro_status)

    # Executando a consulta com os placeholders
    cur.execute(sql1+sql2, placeholders)
    dados = cur.fetchall()

    for i, tupla in enumerate(dados):
        # Acessa o terceiro elemento da tupla (valor a ser formatado)
        valor = tupla[2]
        valor_formatado = format_currency(valor, 'BRL', locale='pt_BR')
        valor_formatado = valor_formatado.replace(
            "\xa0", " ")  # Remove o espaço em branco
        dados[i] = (*tupla[:2], valor_formatado, *tupla[3:])

    return render_template('orcamentos.html', dados=dados)


@app.route('/orcamento/<string:id>', methods=['POST', 'GET'])
@login_required
def item_orcamento(id):

    id = "'" + id + "'"

    conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER,
                            password=DB_PASS, host=DB_HOST)

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    representante = "'"+session['user_id']+"'"

    # representante = """Galo"""

    cur.execute('SELECT * FROM tb_orcamento WHERE id = {}'.format(id))

    dados = cur.fetchall()

    for dicionario in dados:
        # Acessa o valor do campo 'preco' no dicionário
        valor = dicionario['preco']
        valor_formatado = format_currency(valor, 'BRL', locale='pt_BR')
        valor_formatado = valor_formatado.replace(
            "\xa0", " ")  # Remove o espaço em branco
        dicionario['preco'] = valor_formatado

    # id = "'8397d602-ca7d-43c1-a838-378ff7640ba7'"

    status_atual = [dados[0]['status']]

    lista_status = ['Pendente', 'Em andamento', 'Aguardando aprovação', 'Aprovado', 'Rejeitado',
                    'Cancelado', 'Em negociação', 'Concluído', 'Convertido em venda']

    # Remover o status atual da lista
    lista_status.remove(status_atual[0])

    # Inserir o status atual na primeira posição
    lista_status.insert(0, status_atual[0])

    return render_template("orcamento_item.html", dados=dados, lista_status=lista_status,
                           status_atual=status_atual)


@app.route('/remover_item', methods=['POST'])
@login_required
def remover_item():
    id = request.form.get('id')  # Obtém o ID enviado na requisição

    conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER,
                            password=DB_PASS, host=DB_HOST)
    cur = conn.cursor()

    query = 'DELETE FROM tb_orcamento WHERE id_serial = %s'
    cur.execute(query, (id,))

    conn.commit()
    cur.close()
    conn.close()

    return jsonify({'message': 'Item removido com sucesso'})


@app.route("/checkbox", methods=['POST'])
def checkbox():

    dados_selecionados = request.get_json()

    # Faça o processamento dos dados selecionados aqui
    # Por exemplo, você pode imprimir os dados no console
    print(dados_selecionados)
    return 'Dados recebidos com sucesso!'


@app.route('/atualizar-dados', methods=['POST'])
def atualizar_dados():

    nome_cliente = request.form['filtro_nome']
    descricao = request.form['descricao']
    modelo = request.form['modelo']
    eixo = request.form['eixo']
    mola_freio = request.form['mola_freio']
    tamanho = request.form['tamanho']
    rodado = request.form['rodado']
    pneu = request.form['pneu']
    descricao_generica = request.form['descricao_generica']

    representante = session['user_id']

    df_precos = api_precos()

    df_produtos = api_lista_produtos()

    df = df_produtos.merge(df_precos, how='left', on='codigo')

    regiao = buscarRegiaoCliente(nome_cliente)

    df = df[df['lista_nova'] == regiao]

    # Inicialize um DataFrame vazio para conter os resultados
    resultados = pd.DataFrame()

    # Verifique cada variável de filtro e aplique a condição correspondente se o valor não for vazio
    if descricao != '':
        if not resultados.empty:
            resultados = resultados.loc[resultados['descGenerica'] == descricao]
        else:
            resultados = df.loc[df['descGenerica'] == descricao]

    if modelo != '':
        if not resultados.empty:
            resultados = resultados.loc[resultados['modelo'] == modelo]
        else:
            resultados = df.loc[df['modelo'] == modelo]

    if eixo != '':
        if not resultados.empty:
            resultados = resultados.loc[resultados['eixo'] == eixo]
        else:
            resultados = df.loc[df['eixo'] == eixo]

    if mola_freio != '':
        if not resultados.empty:
            resultados = resultados.loc[resultados['molaFreio'] == mola_freio]
        else:
            resultados = df.loc[df['molaFreio'] == mola_freio]

    if rodado != '':
        if not resultados.empty:
            resultados = resultados.loc[resultados['rodado'] == rodado]
        else:
            resultados = df.loc[df['rodado'] == rodado]

    if tamanho != '':
        if not resultados.empty:
            resultados = resultados.loc[resultados['tamanho_tratados'] == tamanho]
        else:
            resultados = df.loc[df['tamanho_tratados'] == tamanho]

    if pneu != '':
        if not resultados.empty:
            resultados = resultados.loc[resultados['pneu_tratado'] == pneu]
        else:
            resultados = df.loc[df['pneu_tratado'] == pneu]

    if descricao_generica != '':
        if not resultados.empty:
            resultados = resultados.loc[resultados['outras_caracteristicas_tratadas']
                                        == descricao_generica]
        else:
            resultados = df.loc[df['outras_caracteristicas_tratadas']
                                == descricao_generica]

    # O DataFrame 'resultados' agora contém as linhas que atendem a todas as condições de pesquisa

    if len(resultados) == 0:
        resultados = df
        df = resultados
    else:
        df = resultados

    # df = df.dropna(subset='lista_nova')
    print(df)


    regiao = buscarRegiaoCliente(nome_cliente)

    df = df[df['lista_nova'] == regiao]

    df['preco'] = df['preco'].apply(lambda x: "R$ {:,.2f}".format(
        x).replace(",", "X").replace(".", ",").replace("X", "."))

    descricao = df[['descGenerica']].drop_duplicates().values.tolist()
    modelo = df[['modelo']].drop_duplicates().values.tolist()
    eixo = df[['eixo']].drop_duplicates().values.tolist()
    mola_freio = df[['molaFreio']].drop_duplicates().values.tolist()
    tamanho = df[['tamanho_tratados']].drop_duplicates().values.tolist()
    rodado = df[['rodado']].drop_duplicates().values.tolist()
    pneu = df[['pneu_tratado']].drop_duplicates().values.tolist()
    descricao_generica = df[[
        'outras_caracteristicas_tratadas']].drop_duplicates().values.tolist()

    modelo = [item for item in modelo if item[0]]

    data = df.values.tolist()

    return jsonify(dados=data, descricao=descricao,
                   modelo=modelo, eixo=eixo,
                   mola_freio=mola_freio, tamanho=tamanho,
                   rodado=rodado, pneu=pneu,
                   descricao_generica=descricao_generica)


@app.route('/atualizar-cliente', methods=['POST'])
def atualizar_cliente():

    nameCliente = request.form['nome_cliente']

    print(nameCliente)

    lista_opcoes_cliente = chamadaCondicoes(nameCliente)

    opcoes = ['À prazo - 1x', 'À prazo - 2x', 'À prazo - 3x', 'À prazo - 4x',
              'À prazo - 5x', 'À prazo - 6x', 'À prazo - 7x', 'À prazo - 8x',
              'À prazo - 9x', 'À prazo - 10x', 'A Vista', 'Antecipado', 'Cartão de Crédito',
              'Personalizado']

    condicoes = obter_condicoes_pagamento(lista_opcoes_cliente, opcoes)

    print(condicoes)

    return jsonify(condicoes=condicoes)


@app.route('/enviarBackend', methods=['POST'])
def obs():

    linha = request.get_json()

    return 'Itens recebidos e processados com sucesso!'


@app.route('/receber-dados', methods=['POST'])
def process_data():
    data = request.get_json()

    conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER,
                            password=DB_PASS, host=DB_HOST)
    cur = conn.cursor()

    representante = session['user_id']

    query = "SELECT nome_completo FROM users WHERE username = %s"

    cur.execute(query, (representante,))

    nome_completo = cur.fetchall()
    nome_completo = nome_completo[0][0]

    items = data['items']
    nome = data['nome']
    contato = data['contato']
    formaPagamento = data['formaPagamento']
    observacoes = data['observacoes']
    nomeResponsavel = data['nomeResponsavel']

    unique_id = str(uuid.uuid4())  # Gerar id unico

    # Crie um DataFrame a partir dos dados dos itens
    df_items = pd.DataFrame(items)
    df_items['nome'] = nome
    df_items['contato'] = contato
    df_items['formaPagamento'] = formaPagamento
    df_items['observacoes'] = observacoes
    df_items['representante'] = nome_completo
    df_items['id'] = unique_id

    if nomeResponsavel == '':
        df_items['nomeResponsavel'] = nome_completo
    else:
        df_items['nomeResponsavel'] = nomeResponsavel

    df_items['quanti'] = df_items['quanti'].apply(lambda x: float(x.replace("R$","").replace(".","").replace(",",".")))
    df_items['valorReal'] = df_items['valorReal'].apply(lambda x: float(x.replace("R$","").replace(".","").replace(",",".")))

    df_items['percentDesconto'] = 1 - (df_items['quanti'] / df_items['valorReal'])

    descontoMaximo = (df_items['percentDesconto'] >= 0.192).any()

    criarProposta(df_items, descontoMaximo)

    query = """INSERT INTO tb_orcamento (id,nome_cliente,contato_cliente,forma_pagamento,observacoes,quantidade,preco_final,codigo,cor,representante) 
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"""

    # Cria uma lista de tuplas contendo os valores das colunas do DataFrame
    valores = list(zip(df_items['id'], df_items['nome'], df_items['contato'], df_items['formaPagamento'], df_items['observacoes'],
                       df_items['numeros'], df_items['quanti'], df_items['description'], df_items['cor'], df_items['representante'],
                       ))

    # Abre uma transação explícita
    with conn:
        # Cria um cursor dentro do contexto da transação
        with conn.cursor() as cur:
            # Executa a inserção das linhas usando executemany
            cur.executemany(query, valores)

    flash("Enviado com sucesso", 'success')

    return jsonify({'message': 'success'})


@app.route('/filtrar_regiao', methods=['POST'])
def atualizar_regiao():

    nome_cliente_regiao = request.form['nome_cliente_regiao']

    print('apenas_printando:', nome_cliente_regiao)

    return redirect(url_for('lista', nome_cliente=nome_cliente_regiao))


@app.route('/opcoes', methods=['GET', 'POST'])
@login_required
def opcoes():

    nomeRepresentante = session['user_id']

    if request.method == 'POST':

        selected_option = request.form['option']

        if selected_option == 'lista':
            return redirect(url_for('lista'))
        elif selected_option == 'consulta':
            return redirect(url_for('consulta'))

    lista_motivos = listarMotivos()
    data = listarOrcamentos(nomeRepresentante)



    return render_template('opcoes.html', data=data, lista_motivos=lista_motivos)


@app.route('/consulta')
@login_required
def consulta():

    conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER,
                            password=DB_PASS, host=DB_HOST)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    representante = session['user_id']

    df_precos = api_precos()

    df_produtos = api_lista_produtos()

    tb_favoritos = tabela_favoritos(representante)

    print(tb_favoritos)

    df = df_produtos.merge(df_precos, how='left', on='codigo')

    print(df)

    try :
        df = df.merge(tb_favoritos, how='left', on='codigo')

        print(df)   
    except:
        pass

    cur.execute(
        """select regiao from users where username = '{}'""".format(representante))

    regiao = cur.fetchall()
    regiao = regiao[0]['regiao']

    regiao = regiao.split(";")

    df = df[df['lista_nova'].isin(regiao)]

    # df = df.dropna(subset='lista_nova')
    df = df.reset_index(drop=True)

    # if regiao:
    #     df = df[df['lista_nova'] == regiao[0][0]]

    df['preco'] = df['preco'].apply(lambda x: "R$ {:,.2f}".format(
        x).replace(",", "X").replace(".", ",").replace("X", "."))

    df['pneu'] = df['pneu'].fillna('Sem pneu')

    try: 
        df = df.sort_values(by='favorito')
    except: 
        pass
    
    data = df.values.tolist()

    descricao_unique = df[['descGenerica']
                          ].drop_duplicates().values.tolist()
    modelo_unique = df[['modelo']].drop_duplicates().values.tolist()
    eixo_unique = df[['eixo']].drop_duplicates().values.tolist()
    mola_freio_unique = df[['molaFreio']].drop_duplicates().values.tolist()
    tamanho_unique = df[['tamanho_tratados']].drop_duplicates().values.tolist()
    rodado_unique = df[['rodado']].drop_duplicates().values.tolist()
    pneu_unique = df[['pneu_tratado']].drop_duplicates().values.tolist()
    descricao_generica_unique = df[[
        'outras_caracteristicas_tratadas']].drop_duplicates().values.tolist()
    lista_unique = df[['lista_nova']].drop_duplicates().values.tolist()

    return render_template('consulta.html', data=data,
                           descricao_unique=descricao_unique, modelo_unique=modelo_unique,
                           eixo_unique=eixo_unique, mola_freio_unique=mola_freio_unique,
                           tamanho_unique=tamanho_unique, rodado_unique=rodado_unique,
                           pneu_unique=pneu_unique, descricao_generica_unique=descricao_generica_unique,
                           lista_unique=lista_unique, representante=representante)


@app.route('/motivosPerda', methods=['GET'])
@login_required
def listarMotivosPerda():

    listaMotivos = listarMotivos()
    
    return jsonify(listaMotivos) 


@app.route('/atualizar-dados-sem-cliente', methods=['POST'])
def atualizar_dados_sem_cliente():

    descricao = request.form['descricao']
    modelo = request.form['modelo']
    eixo = request.form['eixo']
    mola_freio = request.form['mola_freio']
    tamanho = request.form['tamanho']
    rodado = request.form['rodado']
    pneu = request.form['pneu']
    descricao_generica = request.form['descricao_generica']
    lista_preco = request.form['lista_preco']

    print(lista_preco)

    # obter os valores selecionados em cada dropdown enviado pela solicitação AJAX

    # executar a lógica para atualizar o DataFrame com base nas opções selecionadas

    representante = session['user_id']

    df_precos = api_precos()

    df_produtos = api_lista_produtos()

    df = df_produtos.merge(df_precos, how='left', on='codigo')

    # # Realize a junção dos DataFrames e adicione uma coluna "_merge" para indicar a fonte de cada linha
    # merged = pd.merge(df_produtos, df_precos, on='codigo', how='left', indicator=True)

    # # Filtrar as linhas que estão apenas em df1 (indicado como 'left_only' no DataFrame merged)
    # result = merged[merged['_merge'] == 'left_only']['codigo']

    conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER,
                            password=DB_PASS, host=DB_HOST)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute(
        """select regiao from users where username = '{}'""".format(representante))

    regiao = cur.fetchall()
    regiao = regiao[0]['regiao']

    regiao = regiao.split(";")

    df = df[df['lista_nova'].isin(regiao)]

    # Inicialize um DataFrame vazio para conter os resultados
    resultados = pd.DataFrame()

    # Verifique cada variável de filtro e aplique a condição correspondente se o valor não for vazio
    if descricao != '':
        if not resultados.empty:
            resultados = resultados.loc[resultados['descGenerica'] == descricao]
        else:
            resultados = df.loc[df['descGenerica'] == descricao]

    if modelo != '':
        if not resultados.empty:
            resultados = resultados.loc[resultados['modelo'] == modelo]
        else:
            resultados = df.loc[df['modelo'] == modelo]

    if eixo != '':
        if not resultados.empty:
            resultados = resultados.loc[resultados['eixo'] == eixo]
        else:
            resultados = df.loc[df['eixo'] == eixo]

    if mola_freio != '':
        if not resultados.empty:
            resultados = resultados.loc[resultados['molaFreio'] == mola_freio]
        else:
            resultados = df.loc[df['molaFreio'] == mola_freio]

    if rodado != '':
        if not resultados.empty:
            resultados = resultados.loc[resultados['rodado'] == rodado]
        else:
            resultados = df.loc[df['rodado'] == rodado]

    if tamanho != '':
        if not resultados.empty:
            resultados = resultados.loc[resultados['tamanho_tratados'] == tamanho]
        else:
            resultados = df.loc[df['tamanho_tratados'] == tamanho]

    if pneu != '':
        if not resultados.empty:
            resultados = resultados.loc[resultados['pneu_tratado'] == pneu]
        else:
            resultados = df.loc[df['pneu_tratado'] == pneu]

    if descricao_generica != '':
        if not resultados.empty:
            resultados = resultados.loc[resultados['outras_caracteristicas_tratadas']
                                        == descricao_generica]
        else:
            resultados = df.loc[df['outras_caracteristicas_tratadas']
                                == descricao_generica]

    if lista_preco != '':
        if not resultados.empty:
            resultados = resultados.loc[resultados['lista_nova']
                                        == lista_preco]
        else:
            resultados = df.loc[df['lista_nova'] == lista_preco]

    # O DataFrame 'resultados' agora contém as linhas que atendem a todas as condições de pesquisa

    if len(resultados) == 0:
        resultados = df
        df = resultados
    else:
        df = resultados

    # df = df.dropna(subset='lista_nova')
    print(df)

    df['preco'] = df['preco'].apply(lambda x: "R$ {:,.2f}".format(
        x).replace(",", "X").replace(".", ",").replace("X", "."))

    descricao = df[['descGenerica']].drop_duplicates().values.tolist()
    modelo = df[['modelo']].drop_duplicates().values.tolist()
    eixo = df[['eixo']].drop_duplicates().values.tolist()
    mola_freio = df[['molaFreio']].drop_duplicates().values.tolist()
    tamanho = df[['tamanho_tratados']].drop_duplicates().values.tolist()
    rodado = df[['rodado']].drop_duplicates().values.tolist()
    pneu = df[['pneu_tratado']].drop_duplicates().values.tolist()
    descricao_generica = df[[
        'outras_caracteristicas_tratadas']].drop_duplicates().values.tolist()
    lista_preco = df[['lista_nova']].drop_duplicates().values.tolist()

    modelo = [item for item in modelo if item[0]]

    data = df.values.tolist()

    return jsonify(dados=data, descricao=descricao,
                   modelo=modelo, eixo=eixo,
                   mola_freio=mola_freio, tamanho=tamanho,
                   rodado=rodado, pneu=pneu,
                   descricao_generica=descricao_generica, lista_preco=lista_preco)


@app.route('/perda', methods=['POST'])
@login_required
def perda():
    
    data = request.get_json()  # Obtém os dados JSON do corpo da solicitação

    dealId = data.get('dealId')
    selectedOption = data.get('selectedMotivoId')

    print(dealId, selectedOption)

    perderNegocio(selectedOption, dealId)

    return render_template('opcoes.html')


@app.route('/ganhar', methods=['POST'])
@login_required
def ganhar():

    data = request.json

    print(data)

    dealId = data['dealId']
    idUltimaProposta = data['id']

    print(dealId, idUltimaProposta)

    ganharNegocio(dealId)
    criarVenda(dealId, idUltimaProposta)

    return render_template('opcoes.html')


def obter_condicoes_pagamento(lista_opcoes_cliente, opcoes):
    """Função para Criar as opções de pagamento"""

    condicoes_disponiveis = []
    for condicao in lista_opcoes_cliente:
        if condicao in opcoes:
            if "A Vista" in lista_opcoes_cliente and len(lista_opcoes_cliente) == 1:
                condicoes_disponiveis.append('A Vista')
            elif "Antecipado" in lista_opcoes_cliente and len(lista_opcoes_cliente) == 1:
                condicoes_disponiveis.append('Antecipado')
            elif "À prazo" in condicao:
                x = int(condicao[9:11].split()[0])
                condicoes_disponiveis.extend(
                    [f'À prazo - {i}x' for i in range(1, x + 1)])
                condicoes_disponiveis.append('A Vista')
                condicoes_disponiveis.append('Antecipado')
                condicoes_disponiveis = list(set(condicoes_disponiveis))
            else:
                condicoes_disponiveis.append(condicao)
                condicoes_disponiveis.append('A Vista')
                condicoes_disponiveis.append('Antecipado')
                condicoes_disponiveis = list(set(condicoes_disponiveis))
    condicoes_disponiveis = list(set(condicoes_disponiveis))
    condicoes_disponiveis.sort(key=lambda x: opcoes.index(x))
    return condicoes_disponiveis


def chamadaCondicoes(nameCliente):
    """Função para pegar as opções de pagamento disponível para o cliente x"""

    import requests

    url = "https://public-api2.ploomes.com/Contacts?$top=100&$select=Name&$expand=OtherProperties&$filter=Name+eq+'{}'".format(
        nameCliente)

    # Substitua "SEU_TOKEN_AQUI" com a chave de usuário gerada no passo 1
    headers = {
        "User-Key": "5151254EB630E1E946EA7D1F595F7A22E4D2947FA210A36AD214D0F98E4F45D3EF272EE07FCF09BB4AEAEA13976DCD5E1EE313316FD9A5359DA88975965931A3"
    }

    # Fazendo a requisição GET
    response = requests.get(url, headers=headers)

    # Verificando a resposta
    if response.status_code == 200:
        data = response.json()

        contacts = data['value']

        input_id = 189049  # O ID que você deseja filtrar

        lista_opcoes = []
        for contact in contacts:
            other_properties = contact['OtherProperties']
            for property in other_properties:
                if property['FieldId'] == input_id:
                    object_value_name = property['ObjectValueName']
                    lista_opcoes.append(object_value_name)

        return lista_opcoes

    else:
        print(f"Erro na requisição. Código de status: {response.status_code}")


def chamadaListaPreco(nameCliente):
    """Função para pegar a lista de preço de determinado cliente"""

    import requests

    url = "https://public-api2.ploomes.com/Contacts?$top=100&$select=Name&$expand=OtherProperties&$filter=Name+eq+'{}'".format(
        nameCliente)

    # Substitua "SEU_TOKEN_AQUI" com a chave de usuário gerada no passo 1
    headers = {
        "User-Key": "5151254EB630E1E946EA7D1F595F7A22E4D2947FA210A36AD214D0F98E4F45D3EF272EE07FCF09BB4AEAEA13976DCD5E1EE313316FD9A5359DA88975965931A3"
    }

    # Fazendo a requisição GET
    response = requests.get(url, headers=headers)

    # Verificando a resposta
    if response.status_code == 200:
        data = response.json()

        contacts = data['value']

        input_id = 219812  # O FieldKey para filtrar

        for contact in contacts:
            other_properties = contact['OtherProperties']
            for property in other_properties:
                try:
                    if property['FieldId'] == input_id:
                        lista_preco = property['ObjectValueName']
                except:
                    lista_preco = 'Lista Preço N e NE'

        return lista_preco

    else:
        print(f"Erro na requisição. Código de status: {response.status_code}")


def criarOrdem(nomeCliente, nomeContato, nomeRepresentante):
    """Função para gerar ordem de venda"""

    ContactId = id(nomeCliente)

    PersonId = idContatoCliente(nomeContato, ContactId)

    OwnerId = idRepresentante(nomeRepresentante)

    url = "https://public-api2.ploomes.com/Deals"

    headers = {
        "User-Key": "5151254EB630E1E946EA7D1F595F7A22E4D2947FA210A36AD214D0F98E4F45D3EF272EE07FCF09BB4AEAEA13976DCD5E1EE313316FD9A5359DA88975965931A3",
    }

    # Dados que você deseja enviar no corpo da solicitação POST

    if PersonId == 'Null':

        data = {
            "Title": nomeCliente,
            "ContactId": ContactId,
            "OwnerId": OwnerId,
        }

    else:

        data = {
            "Title": nomeCliente,
            "ContactId": ContactId,
            "OwnerId": OwnerId,
            "PersonId": PersonId
        }

    # Fazendo a requisição POST com os dados no corpo
    response = requests.post(url, headers=headers, json=data)

    # Verifica se a requisição foi bem-sucedida (código de status 201 indica criação)
    if response.status_code == 200:

        url = "https://public-api2.ploomes.com/Deals?$top=1&$filter=ContactId+eq+{}&$orderby=CreateDate desc".format(
            ContactId)

        headers = {
            "User-Key": "5151254EB630E1E946EA7D1F595F7A22E4D2947FA210A36AD214D0F98E4F45D3EF272EE07FCF09BB4AEAEA13976DCD5E1EE313316FD9A5359DA88975965931A3",
        }

        response = requests.get(url, headers=headers)

        ids = response.json()
        ids = ids['value']

        for IdDeal in ids:
            IdDeal = IdDeal['Id']

        return IdDeal

    else:
        return 'Erro ao criar a ordem'


def wrap_in_paragraph(text):
    """Função para transformar o texto em html"""

    return f"<p>{text}</p>\n"


def criarProposta(df, descontoMaximo):

    """Função para criar proposta"""

    nomeCliente = df['nome'][0]
    nomeContato = df['contato'][0]

    if nomeContato == '':
        nomeContato = 'Null'

    if df['nomeResponsavel'][0] == '':
        nomeRepresentante = df['representante'][0]
    else:
        nomeRepresentante = df['nomeResponsavel'][0]

    listaProdutos = df['description'].values.tolist()
    formaPagamento = df['formaPagamento'][0]
    listaCores = df['cor'].values.tolist()

    listaPreco = df['quanti'].values.tolist()

    df["observacoes"] = df["observacoes"].apply(wrap_in_paragraph)

    listaQuantidade = df['numeros'].values.tolist()
    listaPrecoUnitario = df['valorReal'].values.tolist()
    listaPercentDesconto = df['percentDesconto'].values.tolist()

    print(df)

    DealId = criarOrdem(nomeCliente, nomeContato, nomeRepresentante)

    atualizarEtapaProposta(DealId)

    idFormaPagamento = idFormaPagamentoF(formaPagamento)
    id_CondicaoPagamento = idCondicaoPagamento(formaPagamento)

    idRep = idRepresentante(nomeRepresentante)

    # Suas três listas
    ProductId = idCarretas(listaProdutos)
    color = idCores(listaCores)
    price = listaPreco
    quantidade = listaQuantidade
    precoUnitario = listaPrecoUnitario
    percentDesconto = listaPercentDesconto
    
    # Inicializar uma lista vazia
    lista_product = []

    # Criar um dicionário para cada conjunto de valores correspondentes e adicioná-lo à lista
    for i in range(len(ProductId)):
        product_info = {
            "ProductId": ProductId[i],
            "IdCor": color[i],
            "Price": price[i],
            "Quantity": quantidade[i],
            "UnitPrice": precoUnitario[i],
            "percentDesconto": percentDesconto[i]
        }

        lista_product.append(product_info)

    # Inicializar uma variável para o total em valor e total e quantidade de itens
    total = 0
    totalItens = 0

    # Calcular o total somando os preços
    for product in lista_product:
        total += product["Price"] * int(product['Quantity'])
        totalItens += int(product['Quantity'])

    # lista_product = df.to_dict(orient='records')
    # Estrutura JSON para cada produto
    products = []
    for i, product_id in enumerate(lista_product):
        product_json = {
            "Quantity": product_id["Quantity"],
            "UnitPrice": product_id["UnitPrice"],
            "Total": product_id["Price"] * int(product_id["Quantity"]),
            "ProductId": product_id["ProductId"],
            "Ordination": i,
            "OtherProperties": [
                {
                    "FieldKey": "quote_product_76A1F57A-B40F-4C4E-B412-44361EB118D8",  # Cor
                    "IntegerValue": product_id["IdCor"]
                },
                {
                    "FieldKey": "quote_product_E426CC8C-54CB-4B9C-8E4D-93634CF93455", # valor unit. c/ desconto
                    "DecimalValue": product_id["Price"]
                },
                {
                    "FieldKey": "quote_product_4D6B83EE-8481-46B2-A147-1836B287E14C",  # prazo dias
                    "StringValue": "45;"
                },
                {
                    "FieldKey": "quote_product_7FD5E293-CBB5-43C8-8ABF-B9611317DF75", # % de desconto no produto
                    "DecimalValue" : product_id["percentDesconto"] * 100
                }

            ]
        }
        products.append(product_json)

    # Estrutura JSON principal com a lista de produtos
    json_data = {
        "DealId": DealId,
        "OwnerId": idRep,
        "TemplateId": 196596,
        "Amount": total,
        "Discount": 0,
        "InstallmentsAmountFieldKey": "quote_amount",
        "Notes": df['observacoes'][0],
        "Sections": [
            {
                "Code": 0,
                "Total": total,
                "OtherProperties": [
                    {
                        "FieldKey": "quote_section_8136D2B9-1496-4C52-AB70-09B23A519286",  # Prazo conjunto
                        "StringValue": "045;"
                    },
                    {
                        "FieldKey": "quote_section_0F38DF78-FE65-471C-A391-9E8759470D4E",  # Total
                        "DecimalValue": total
                    },
                    {
                        "FieldKey": "quote_section_64320D57-6350-44AB-B849-6A6110354C79",  # Total de itens
                        "IntegerValue": totalItens
                    }
                ],
                "Products": products
            }
        ],
        "OtherProperties": [
            {
                "FieldKey": "quote_0FB9F0CB-2619-44C5-92BD-1A2D2D818BFE",  # Forma de pagamento
                "IntegerValue": idFormaPagamento
            },
            {
                "FieldKey": "quote_DE50A0F4-1FBE-46AA-9B5D-E182533E4B4A",  # Texto simples
                "StringValue": formaPagamento
            },
            {
                "FieldKey": "quote_E85539A9-D0D3-488E-86C5-66A49EAF5F3A",  # Condições de pagamento
                "IntegerValue": id_CondicaoPagamento
            },
            {
                "FieldKey": "quote_F879E39D-E6B9-4026-8B4E-5AD2540463A3",  # Tipo de frete
                "IntegerValue": 22886508
            },
            {
                "FieldKey": "quote_6D0FC2AB-6CCC-4A65-93DD-44BF06A45ABE",  # Validade
                "IntegerValue": 18826538
            },
            {
                "FieldKey": "quote_520B942C-F3FD-4C6F-B183-C2E8C3EB6A33",  # Dias para entrega
                "IntegerValue": 45
            }
        ]
    }
    
    # if descontoMaximo:
    #     json_data["ApprovalStatusId"] = 1
    #     json_data["ApprovalLevelId"] = 6216

    print(json_data)

    # Converte a estrutura JSON em uma string JSON
    # json_string = json.dumps(json_data, indent=2)
    # json_string = json.dumps(json_data, separators=(',', ':'))

    url = "https://public-api2.ploomes.com/Quotes"

    headers = {
        "User-Key": "5151254EB630E1E946EA7D1F595F7A22E4D2947FA210A36AD214D0F98E4F45D3EF272EE07FCF09BB4AEAEA13976DCD5E1EE313316FD9A5359DA88975965931A3",
    }

    requests.post(url, headers=headers, json=json_data)

    enviar_email(nomeRepresentante, nomeCliente, DealId)

    return "Proposta criada"


def id(nomeCliente):
    """Função para buscar o id do cliente"""

    url = "https://public-api2.ploomes.com/Contacts?$top=100&$select=Id&$filter=Name+eq+'{}'".format(
        nomeCliente)

    headers = {
        "User-Key": "5151254EB630E1E946EA7D1F595F7A22E4D2947FA210A36AD214D0F98E4F45D3EF272EE07FCF09BB4AEAEA13976DCD5E1EE313316FD9A5359DA88975965931A3"
    }

    response = requests.get(url, headers=headers)

    ids = response.json()
    ids = ids['value']

    for idCliente in ids:
        idCliente = idCliente['Id']

    return idCliente


def idContatoCliente(nomeContato, idCliente):
    """Função para buscar o id do contato"""

    url = "https://public-api2.ploomes.com/Contacts?$top=100&$select=Id&$filter=CompanyId+eq+{} and Name+eq+'{}'".format(
        idCliente, nomeContato)

    headers = {
        "User-Key": "5151254EB630E1E946EA7D1F595F7A22E4D2947FA210A36AD214D0F98E4F45D3EF272EE07FCF09BB4AEAEA13976DCD5E1EE313316FD9A5359DA88975965931A3"
    }

    response = requests.get(url, headers=headers)

    ids = response.json()
    ids = ids['value']

    if len(ids) == 0:
        idContato = 'Null'

    else:

        for idContato in ids:
            idContato = idContato['Id']

    return idContato


def idRepresentante(nomeRepresentante):
    """Função para buscar o id do representante"""

    url = "https://public-api2.ploomes.com/Users?$top=100&$select=Id&$filter=Name+eq+'{}'".format(
        nomeRepresentante)

    headers = {
        "User-Key": "5151254EB630E1E946EA7D1F595F7A22E4D2947FA210A36AD214D0F98E4F45D3EF272EE07FCF09BB4AEAEA13976DCD5E1EE313316FD9A5359DA88975965931A3"
    }

    response = requests.get(url, headers=headers)

    ids = response.json()
    ids = ids['value']

    for idRep in ids:
        idRep = idRep['Id']

    return idRep


def idCarretas(listaProdutos):
    """Função para buscar o id das carretas"""

    # Define a URL da API e os nomes dos produtos que você deseja buscar
    url = "https://public-api2.ploomes.com/Products?$top=10&$filter=Code+eq+'{}'&$select=Id"

    headers = {
        "User-Key": "5151254EB630E1E946EA7D1F595F7A22E4D2947FA210A36AD214D0F98E4F45D3EF272EE07FCF09BB4AEAEA13976DCD5E1EE313316FD9A5359DA88975965931A3",
    }

    # Inicializa uma lista para armazenar os IDs dos produtos encontrados
    product_ids = []

    # Realiza uma solicitação GET para cada nome de produto
    for product_name in listaProdutos:
        # Define a URL completa substituindo '{}' pelo nome do produto atual
        api_url = url.format(product_name)

        # Realiza a solicitação GET para o produto atual
        response = requests.get(api_url, headers=headers)

        # Verifica se a solicitação foi bem-sucedida (código de status 200)
        if response.status_code == 200:
            data = response.json()
            # Verifica se a resposta contém dados
            if "value" in data and data["value"]:
                # Acessa o ID do primeiro item encontrado
                product_id = data["value"][0]["Id"]
                product_ids.append((product_id))
            else:
                print(f"Nenhum ID encontrado para o produto '{product_name}'.")
        else:
            print(
                f"Erro na solicitação para o produto '{product_name}': Código de status {response.status_code}")

    return product_ids


def idCores(listaCores):
    """Função para buscar o id das cores"""

    # Define a URL da API e os nomes dos produtos que você deseja buscar
    url = "https://public-api2.ploomes.com/Fields@OptionsTables@Options?$select=Id&$filter=TableId+eq+36909 and Name+eq+'{}'"

    headers = {
        "User-Key": "5151254EB630E1E946EA7D1F595F7A22E4D2947FA210A36AD214D0F98E4F45D3EF272EE07FCF09BB4AEAEA13976DCD5E1EE313316FD9A5359DA88975965931A3",
    }

    # Inicializa uma lista para armazenar os IDs dos produtos encontrados
    cores_id = []

    # Realiza uma solicitação GET para cada nome de produto
    for lista_name in listaCores:
        # Define a URL completa substituindo '{}' pelo nome do produto atual
        api_url = url.format(lista_name)

        # Realiza a solicitação GET para o produto atual
        response = requests.get(api_url, headers=headers)

        # Verifica se a solicitação foi bem-sucedida (código de status 200)
        if response.status_code == 200:
            data = response.json()
            # Verifica se a resposta contém dados
            if "value" in data and data["value"]:
                # Acessa o ID do primeiro item encontrado
                product_id = data["value"][0]["Id"]
                cores_id.append((product_id))
            else:
                print(f"Nenhum ID encontrado para o produto '{lista_name}'.")
        else:
            print(
                f"Erro na solicitação para o produto '{lista_name}': Código de status {response.status_code}")

    return cores_id


def idFormaPagamentoF(formaPagamento):
    """Função para buscar o id da forma de pagamento"""

    # Define a URL da API e os nomes dos produtos que você deseja buscar
    url = "https://public-api2.ploomes.com/Fields@OptionsTables@Options?$select=Id&$filter=TableId+eq+31965 and Name+eq+'{}'".format(
        formaPagamento)

    headers = {
        "User-Key": "5151254EB630E1E946EA7D1F595F7A22E4D2947FA210A36AD214D0F98E4F45D3EF272EE07FCF09BB4AEAEA13976DCD5E1EE313316FD9A5359DA88975965931A3",
    }

    response = requests.get(url, headers=headers)

    forma_pagamento = response.json()
    forma_pagamento = forma_pagamento['value']
    idFormaPagamento = forma_pagamento[0]['Id']

    return idFormaPagamento


def idCondicaoPagamento(formaPagamento):
    """Função para buscar o id da condição de pagamento"""

    # Define a URL da API e os nomes dos produtos que você deseja buscar
    url = "https://public-api2.ploomes.com/Fields@OptionsTables@Options?$select=Id&$filter=TableId+eq+32062 and Name+eq+'{}'".format(
        formaPagamento)

    headers = {
        "User-Key": "5151254EB630E1E946EA7D1F595F7A22E4D2947FA210A36AD214D0F98E4F45D3EF272EE07FCF09BB4AEAEA13976DCD5E1EE313316FD9A5359DA88975965931A3",
    }

    response = requests.get(url, headers=headers)

    forma_pagamento = response.json()
    forma_pagamento = forma_pagamento['value']
    id_CondicaoPagamento = forma_pagamento[0]['Id']

    return id_CondicaoPagamento


def obterEmailRepresentante(nomeRepresentante):
    """Função para obter o email do representante dentro do postgres"""

    conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER,
                            password=DB_PASS, host=DB_HOST)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("select email from users where username = '{}'".format(
        nomeRepresentante), conn)

    emailRepresentante = cur.fetchall()
    emailRepresentante = emailRepresentante[0]['email']
    emailRepresentante = emailRepresentante.split(';')

    return emailRepresentante


def obterDocumentoPdf(DealId):
    """Função para buscar o pdf e aceite da proposta"""

    url = "https://public-api2.ploomes.com/Quotes?$top=10&$filter=DealId+eq+{}&$select=DocumentUrl,Key,ApprovalStatusId".format(
        DealId)

    headers = {
        "User-Key": "5151254EB630E1E946EA7D1F595F7A22E4D2947FA210A36AD214D0F98E4F45D3EF272EE07FCF09BB4AEAEA13976DCD5E1EE313316FD9A5359DA88975965931A3"
    }

    response = requests.get(url, headers=headers)

    documentos = response.json()
    documentos = documentos['value']

    for doc in documentos:
        pdf = doc['DocumentUrl']
        key = doc['Key']
        approver = doc['ApprovalStatusId']

    if approver == 1:
        
        corpo_email = "Aguardando aprovação do pedido. \n\n Proposta em pdf:{}".format(
            pdf)

    else:

        aceite = "https://documents.ploomes.com/?k={}&entity=quote".format(key)

        corpo_email = "Link de aceite: {} \n\n Proposta em pdf:{}".format(
            aceite, pdf)

    return corpo_email


def enviar_email(nomeRepresentante, nomeCliente, DealId):
    """Função para enviar email para os representantes"""

    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    email_representante = obterEmailRepresentante(nomeRepresentante)

    corpo_email = obterDocumentoPdf(DealId)

    # Configurações do servidor SMTP
    smtp_host = 'smtp.gmail.com'
    smtp_port = 587
    smtp_user = 'sistema@cemag.com.br'
    smtp_password = 'cem@1600'

    for email in email_representante:

        # Crie uma mensagem de e-mail
        mensagem = MIMEMultipart()
        mensagem['From'] = 'sistema@cemag.com.br'
        mensagem['To'] = email
        mensagem['Subject'] = 'Proposta Ploomes para o cliente {}'.format(
            nomeCliente)

        # Adicione o corpo do e-mail

        mensagem.attach(MIMEText(corpo_email, 'plain'))

        # Conecte-se ao servidor SMTP e envie o e-mail
        with smtplib.SMTP(smtp_host, smtp_port) as servidor_smtp:
            servidor_smtp.starttls()
            servidor_smtp.login(smtp_user, smtp_password)
            servidor_smtp.send_message(mensagem)
            print('E-mail enviado com sucesso!')

    return 'Sucess'


def buscarRegiaoCliente(nomeCliente):
    """Função para buscar a região por cliente"""

    url = "https://public-api2.ploomes.com/Contacts?$top=10&$filter=contains(Name,'{}')&$expand=OtherProperties($filter=FieldKey+eq+'contact_70883643-FFE7-4C84-8163-89242423A4EF')".format(
        nomeCliente)

    headers = {
        "User-Key": "5151254EB630E1E946EA7D1F595F7A22E4D2947FA210A36AD214D0F98E4F45D3EF272EE07FCF09BB4AEAEA13976DCD5E1EE313316FD9A5359DA88975965931A3"
    }

    response = requests.get(url, headers=headers)

    data = response.json()

    try:
        regiao = data['value'][0]['OtherProperties'][0]['ObjectValueName']
    except:
        regiao = 'Lista Preço SDE e COE'

    return regiao


def formatar_data(data_str):
    """Função para formatar data e hora"""

    # Divide a string em data/hora e deslocamento de tempo
    partes = data_str.split('T')
    # Converter a parte da data/hora em objeto datetime
    data_obj = datetime.fromisoformat(partes[0])
    data_formatada = data_obj.strftime('%d/%m/%Y')  # Formatar a data
    return data_formatada


def listarOrcamentos(nomeRepresentante):
    """Função para listar negócios de cada representante"""

    idRep = idRepresentante(nomeRepresentante)

    url = "https://public-api2.ploomes.com/Quotes?$top=50&$filter=OwnerId+eq+{}&$orderby=Date desc&$select=DealId,ExternallyAccepted,ApprovalStatusId".format(
        idRep)

    headers = {
        "User-Key": "5151254EB630E1E946EA7D1F595F7A22E4D2947FA210A36AD214D0F98E4F45D3EF272EE07FCF09BB4AEAEA13976DCD5E1EE313316FD9A5359DA88975965931A3"
    }

    response = requests.get(url, headers=headers)

    data = response.json()
    data1 = data['value']

    url = "https://public-api2.ploomes.com/Deals?$top=50&$filter=OwnerId+eq+{}&$orderby=LastUpdateDate desc&$select=StatusId,LastUpdateDate,Id,ContactName,Amount".format(
        idRep)

    headers = {
        "User-Key": "5151254EB630E1E946EA7D1F595F7A22E4D2947FA210A36AD214D0F98E4F45D3EF272EE07FCF09BB4AEAEA13976DCD5E1EE313316FD9A5359DA88975965931A3"
    }

    response = requests.get(url, headers=headers)

    data = response.json()
    data2 = data['value']

    # Crie um dicionário para mapear DealId para os itens no segundo JSON
    deal_id_mapping = {item2['Id']: item2 for item2 in data2}

    # Combine os JSONs com base em DealId
    combined_json = []
    for item1 in data1:
        deal_id = item1['DealId']
        if deal_id in deal_id_mapping:
            item2 = deal_id_mapping[deal_id]
            combined_item = {**item1, **item2}
            combined_json.append(combined_item)

    for item in combined_json:
        if item['ExternallyAccepted'] is None:
            item['ExternallyAccepted'] = "Não"
        elif item['ExternallyAccepted'] is True:
            item['ExternallyAccepted'] = "Sim"

    for item in combined_json:
        if item['LastUpdateDate']:
            item['LastUpdateDate'] = formatar_data(item['LastUpdateDate'])

    unique_set = set()
    unique_data = []

    for item in combined_json:
        if item['DealId'] not in unique_set:
            unique_set.add(item['DealId'])
            unique_data.append(item)

    data = unique_data
    print(data)

    # url = "https://public-api2.ploomes.com/Deals?$top=50&$filter=OwnerId+eq+{} and StatusId+eq+1&$orderby=LastUpdateDate desc&$select=Quotes&$expand=Quotes($select=Id,ContactName,DealId,QuoteNumber,Amount,ExternallyAccepted,CreateDate,DocumentUrl)".format(
    #     idRep)

    # headers = {
    #     "User-Key": "5151254EB630E1E946EA7D1F595F7A22E4D2947FA210A36AD214D0F98E4F45D3EF272EE07FCF09BB4AEAEA13976DCD5E1EE313316FD9A5359DA88975965931A3"
    # }
    
    # response = requests.get(url, headers=headers)
    
    # data = response.json()
    # data2 = data['value']

    # # Percorra a lista e faça a modificação
    # for item in data2:
    #     for quote in item.get('Quotes', []):
    #         if quote['ExternallyAccepted'] is None:
    #             quote['ExternallyAccepted'] = "Não"
    #         elif quote['ExternallyAccepted'] is True:
    #             quote['ExternallyAccepted'] = "Sim"

    # # Crie uma nova lista para armazenar os objetos internos
    # new_data = []

    # # Itere sobre os objetos originais e adicione apenas os objetos internos à nova lista
    # for item in data2:
    #     if 'Quotes' in item:
    #         new_data.append(item['Quotes'])

    # data = new_data

    

    return data


def listarMotivos():
    """Função para listar motivos de perda e seus respectivos ID"""

    url = "https://public-api2.ploomes.com/Deals@LossReasons?$filter=PipelineId+eq+37808&$select=Id,Name"

    headers = {
        "User-Key": "5151254EB630E1E946EA7D1F595F7A22E4D2947FA210A36AD214D0F98E4F45D3EF272EE07FCF09BB4AEAEA13976DCD5E1EE313316FD9A5359DA88975965931A3"
    }

    response = requests.get(url, headers=headers)

    data = response.json()
    listaMotivos = data['value']

    return listaMotivos


def perderNegocio(IdMotivo, DealId):
    """Função que faz perder o negócio"""

    json_data = {
        "LossReasonId": int(IdMotivo)
    }

    url = "https://public-api2.ploomes.com/Deals({})/Lose".format(DealId)

    headers = {
        "User-Key": "5151254EB630E1E946EA7D1F595F7A22E4D2947FA210A36AD214D0F98E4F45D3EF272EE07FCF09BB4AEAEA13976DCD5E1EE313316FD9A5359DA88975965931A3",
    }

    requests.post(url, headers=headers, json=json_data)

    return "Negócio perdido"


def buscarProdutosQuotes(dealId):
    """Função para buscar lista de produtos naquele pedido"""

    url = "https://public-api2.ploomes.com/Quotes?$filter=DealId+eq+{}&$expand=Products".format(
        dealId)

    header = {
        "User-Key": "5151254EB630E1E946EA7D1F595F7A22E4D2947FA210A36AD214D0F98E4F45D3EF272EE07FCF09BB4AEAEA13976DCD5E1EE313316FD9A5359DA88975965931A3",
    }

    response = requests.get(url, headers=header)

    data = response.json()
    json_produtos = data['value'][0]['Products']

    discount = 0
    amount = data['value'][0]['Amount']

    json_win = {
        "Order": {
            "Discount": discount,
            "Amount": amount,
            "Products": []
        }
    }

    # Loop através dos itens no primeiro JSON
    for product_item in json_produtos:
        # Crie um novo dicionário com os campos necessários
        new_product = {
            "ProductId": product_item['ProductId'],
            "Quantity": product_item['Quantity'],
            "CurrencyId": product_item['CurrencyId'],
            "UnitPrice": product_item['UnitPrice'],
            "Discount": product_item['Discount'],
            "Total": product_item['Total']
        }
        # Adicione o novo dicionário à lista de Products no segundo JSON
        json_win['Order']["Products"].append(new_product)

    return json_produtos


def ganharNegocio(DealId):
    """Função para ganhar negócio"""

    atualizarEtapaFechamento(DealId)

    json_data = buscarProdutosQuotes(DealId)

    url = "https://public-api2.ploomes.com/Deals({})/Win".format(DealId)

    headers = {
        "User-Key": "5151254EB630E1E946EA7D1F595F7A22E4D2947FA210A36AD214D0F98E4F45D3EF272EE07FCF09BB4AEAEA13976DCD5E1EE313316FD9A5359DA88975965931A3",
    }

    requests.post(url, headers=headers, json=json_data)

    return "Negócio ganho"


def atualizarEtapaProposta(DealId):

    url = "https://public-api2.ploomes.com/Deals({})".format(DealId)

    headers = {
        "User-Key": "5151254EB630E1E946EA7D1F595F7A22E4D2947FA210A36AD214D0F98E4F45D3EF272EE07FCF09BB4AEAEA13976DCD5E1EE313316FD9A5359DA88975965931A3",
    }

    json_data = {
        "StageId": 166905
    }

    requests.patch(url, headers=headers, json=json_data)

    return 'Deal atualizado'


def atualizarEtapaFechamento(DealId):

    url = "https://public-api2.ploomes.com/Deals({})".format(DealId)

    headers = {
        "User-Key": "5151254EB630E1E946EA7D1F595F7A22E4D2947FA210A36AD214D0F98E4F45D3EF272EE07FCF09BB4AEAEA13976DCD5E1EE313316FD9A5359DA88975965931A3",
    }

    json_data = {
        "StageId": 230240
    }

    requests.patch(url, headers=headers, json=json_data)

    return 'Deal atualizado'


@app.route('/escolherProposta', methods=['GET'])
def escolherProposta():

    dealId = request.args.get('dealId')

    print(dealId)

    url = "https://public-api2.ploomes.com/Quotes?$filter=DealId+eq+{}&$select=QuoteNumber,Id,Amount,DocumentUrl,Date".format(
        dealId)

    header = {
        "User-Key": "5151254EB630E1E946EA7D1F595F7A22E4D2947FA210A36AD214D0F98E4F45D3EF272EE07FCF09BB4AEAEA13976DCD5E1EE313316FD9A5359DA88975965931A3",
    }

    response = requests.get(url, headers=header)
    data = response.json()

    listaPropostas = data['value']

    print(listaPropostas)

    return jsonify(listaPropostas)


def criarVenda(dealId, idUltimaProposta):
    
    """
    Função para criar venda após ganhar a proposta.
    """

    url = "https://public-api2.ploomes.com/Quotes?$filter=DealId+eq+{}&$expand=Products($expand=OtherProperties)".format(
        dealId)

    header = {
        "User-Key": "5151254EB630E1E946EA7D1F595F7A22E4D2947FA210A36AD214D0F98E4F45D3EF272EE07FCF09BB4AEAEA13976DCD5E1EE313316FD9A5359DA88975965931A3",
    }

    response = requests.get(url, headers=header)

    data = response.json()

    ownerId = data['value'][0]['OwnerId']
    personId = data['value'][0]['PersonId']
    json_produtos = data['value'][0]['Products']
    contactId = data['value'][0]['ContactId']
    amount = data['value'][0]['Amount']
    notes = data['value'][0]['Notes']

    print(data)

    json1 = {
        "ContactId": contactId,
        "DealId": dealId,
        "PersonId": personId,
        "OwnerId": ownerId,
        "CurrencyId": 1,
        "Amount": amount,
        "OriginQuoteId": idUltimaProposta,
        "OtherProperties": [
            {
                "FieldKey": "order_7BB4AC64-8B0F-40AF-A854-CBE860A4B179", # Observação
                "BigStringValue": notes
            },
            {
                "FieldKey": "order_2A8B87D1-3E73-4C5A-94F5-29A53347FFC1", # Atualizar dados
                "BoolValue": True
            },
            {
                "FieldKey": "order_62D206E8-1881-4234-A341-F9E82C08885C", # Programação de entrega
                "DateTimeValue": prazoDias()
            },
            {
                "FieldKey": "order_7932F9F0-B3E8-40D3-9815-53C8613D33F1", # Valor Total
                "DecimalValue": amount
            },
            {
                "FieldKey": "order_377A29A2-69F9-4E34-9307-0764EE3D9A89", # Prazo Dias
                "IntegerValue": 45
            }
        ],
        "Date": dataHojeFormato(), # Hoje
        "Sections": [{"Products":[],"Total": amount}],
    }

    total = {"Total": amount}

    # Loop através dos itens no primeiro JSON
    for product_item in json_produtos:

        # Obter o valor do campo 'quote_product_7FD5E293-CBB5-43C8-8ABF-B9611317DF75'
        discount_value = None  # Valor padrão se não for encontrado
        for other_prop in product_item.get('OtherProperties', []):
            if other_prop.get('FieldKey') == 'quote_product_7FD5E293-CBB5-43C8-8ABF-B9611317DF75':
                discount_value = other_prop.get('DecimalValue')
                break  # Parar a busca após encontrar o valor desejado
            
        # Crie um novo dicionário com os campos necessários
        new_product = {
                "OtherProperties": [
                    {
                        "FieldKey": "order_table_product_69BAEC44-676C-4458-823A-C0F29E605B0F", # Valor unitário com desconto
                        "DecimalValue": product_item['Total'] / product_item['Quantity']
                    },
                    {
                        "FieldKey": "order_table_product_56BC6561-A0C8-4EA7-BF03-40ADC8D03899", # Previsão de Entrega
                        "DateTimeValue": prazoDias() # Hoje + 45 dias corridos
                    }
                ],
                                
                "Quantity": product_item['Quantity'],
                "UnitPrice": product_item['Total'] / product_item['Quantity'],
                "Total": product_item['Total'],
                "ProductId": product_item['ProductId'],
                "Discount": discount_value # aqui o valor do fieldKey: 'quote_product_7FD5E293-CBB5-43C8-8ABF-B9611317DF75'
            },

        # Crie uma nova seção para cada produto
        json1["Sections"][0]['Products'].append(new_product[0])


    print(json1)

    url = "https://public-api2.ploomes.com/Orders"

    requests.post(url, headers=header, json=json1)


def atualizarPedido():

    

    return 'Sucesso'

@app.route('/reenviarEmail', methods=['POST'])
@login_required
def reenviarEmail():
    """Função para reenviar e-mail"""

    data = request.get_json()

    # Extraia as variáveis do JSON
    deal_id = data.get('dealId')
    nomeCliente = data.get('nomeCliente')
    nome_representante = session['user_id']

    enviar_email(nome_representante, nomeCliente, deal_id)

    return 'E-mail reenviado'


def prazoDias():

    from datetime import datetime, timedelta

    # Obtenha a data atual
    hoje = datetime.now()

    # Adicione 45 dias à data atual
    data_futura = hoje + timedelta(days=45)

    # Formate a data no formato desejado
    data_formatada = data_futura.strftime("%Y-%m-%dT00:00:00-03:00")

    return data_formatada


def dataHojeFormato():

    from datetime import datetime, timedelta

    # Obtenha a data atual
    hoje = datetime.now()

    # Formate a data no formato desejado
    data_formatada = hoje.strftime("%Y-%m-%dT00:00:00-03:00")

    return data_formatada


if __name__ == '__main__':
    app.run(port=8000)