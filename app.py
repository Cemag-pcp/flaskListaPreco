from flask import Flask,render_template, redirect, url_for, request, session, flash, make_response, Response
from flask import render_template_string, jsonify
import psycopg2 #pip install psycopg2 
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
from bs4 import BeautifulSoup
from datetime import date
import json
from datetime import datetime
import uuid
from sqlalchemy import create_engine
import warnings
from babel.numbers import format_currency

warnings.filterwarnings("ignore")

app = Flask(__name__)
app.secret_key = "listaPreco"

# DB_HOST = "localhost"
DB_HOST = "database-2.cdcogkfzajf0.us-east-1.rds.amazonaws.com"
DB_NAME = "postgres"
DB_USER = "postgres"
DB_PASS = "15512332"
 
conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST)

engine = create_engine(f'postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{5432}/{DB_NAME}')

@app.route('/login', methods=['GET', 'POST'])
def login():
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Verifique se o usuário existe no banco de dados
        user = cur.execute("SELECT * FROM users WHERE username = {} AND password = {}".format("'"+username+"'", "'"+password+"'"))
        user = cur.fetchone()

        if len(user) > 0:
            # Salve o ID do usuário na sessão
            session['user_id'] = user['username']
            print(session['user_id'])
            flash('Logged in successfully.')
            return redirect(url_for('lista'))

        flash('Invalid username or password.')

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        # Verifique se o nome de usuário já está em uso
        cur.execute('SELECT id FROM users WHERE username = {}'.format("'"+username+"'"))
        verific = cur.fetchall()
        if len(verific) > 0:
            flash('Username {} is already taken.'.format(username))
        else:
            # Insira o novo usuário no banco de dados
            cur.execute("INSERT INTO users (username, email, password) VALUES (%s, %s, %s)", (username, email, password))
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

@app.route('/')
@login_required
def lista():

    conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST)

    representante = "'"+session['user_id']+"'"
    representante = """'Galo'"""

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    query = """ SELECT DISTINCT t1.*, t2.preco
        FROM tb_produtos AS t1
        LEFT JOIN tb_lista_precos AS t2 ON t1.codigo = t2.codigo
        WHERE t1.crm = 'T' and t2.preco is not null; 
    """

    df = pd.read_sql_query(query, conn)

    df['preco'] = df['preco'].apply(lambda x: "R$ {:,.2f}".format(x).replace(",", "X").replace(".", ",").replace("X", "."))

    data = df.values.tolist()

    descricao_unique = df[['descricao_generica']].drop_duplicates().values.tolist()
    modelo_unique = df[['modelo']].drop_duplicates().values.tolist()
    eixo_unique = df[['eixo']].drop_duplicates().values.tolist()
    mola_freio_unique = df[['mola_freio']].drop_duplicates().values.tolist()
    tamanho_unique = df[['tamanho']].drop_duplicates().values.tolist()
    rodado_unique = df[['rodado']].drop_duplicates().values.tolist()
    pneu_unique = df[['pneu']].drop_duplicates().values.tolist()
    descricao_generica_unique = df[['outras_caracteristicas']].drop_duplicates().values.tolist()

    query2 = """ SELECT nome, contatos FROM tb_clientes_contatos """
    cur.execute(query2)
    cliente_contatos = cur.fetchall()
    df_cliente_contatos = pd.DataFrame(cliente_contatos)

    nome_cliente = df_cliente_contatos[['nome']].values.tolist()
    contatos_cliente = df_cliente_contatos[['contatos']].values.tolist()

    return render_template('lista.html', data=data,
                           descricao_unique=descricao_unique,modelo_unique=modelo_unique,
                           eixo_unique=eixo_unique,mola_freio_unique=mola_freio_unique,
                           tamanho_unique=tamanho_unique,rodado_unique=rodado_unique,
                           pneu_unique=pneu_unique, descricao_generica_unique=descricao_generica_unique,
                           nome_cliente=nome_cliente,contatos_cliente=contatos_cliente)

@app.route('/move/<string:id>', methods = ['POST','GET'])
@login_required
def move(id):

    conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST)

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    representante = ""+session['user_id']+""

    df = pd.read_sql_query('SELECT * FROM tb_lista_precos WHERE id = {}'.format(id), conn)

    for coluna in df.columns:
        if df[coluna].dtype == 'object':
            df[coluna] = df[coluna].str.strip()

    cur.execute("INSERT INTO tb_favoritos (id, familia, codigo, descricao, representante, preco) VALUES (%s,%s,%s,%s,%s,%s)", (int(np.int64(df['id'][0])), df['familia'][0], df['codigo'][0], df['descricao'][0], representante, df['preco'][0]))
    cur.execute('DELETE FROM tb_lista_precos WHERE id = {0}'.format(id))
    conn.commit()
    conn.close()
    
    return redirect(url_for('lista'))

@app.route('/favoritos')
@login_required
def lista_favoritos():

    conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST)

    representante = "'"+session['user_id']+"'"
    # representante = """'Galo'"""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM tb_favoritos where representante = {}".format(representante))
    data = cur.fetchall()

    for row in data:
        row['preco'] = "R$ {:,.2f}".format(row['preco']).replace(",", "X").replace(".", ",").replace("X", ".")
  
    return render_template("favoritos.html", data=data)

@app.route('/remove/<string:id>', methods = ['POST','GET'])
@login_required
def remove(id):

    conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST)

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    representante = ""+session['user_id']+""

    representante = """Galo"""

    df = pd.read_sql_query('SELECT * FROM tb_favoritos WHERE id = {}'.format(id), conn)

    for coluna in df.columns:
        if df[coluna].dtype == 'object':
            df[coluna] = df[coluna].str.strip()

    cur.execute("INSERT INTO tb_lista_precos (id, familia, codigo, descricao, representante, preco) VALUES (%s,%s,%s,%s,%s,%s)", (int(np.int64(df['id'][0])), df['familia'][0], df['codigo'][0], df['descricao'][0], representante, df['preco'][0]))

    cur.execute('DELETE FROM tb_favoritos WHERE id = {0}'.format(id))

    conn.commit()
    conn.close()

    return redirect(url_for('lista_favoritos'))

@app.route('/logout')
@login_required
def logout():
    session.clear() # limpa as informações da sessão
    return redirect(url_for('login')) # redireciona para a página de login

@app.route('/teste')
@login_required
def teste():
    return render_template("teste.html")

@app.route('/export/pdf')
def export_pdf():
    # Dados da tabela

    representante = "'"+session['user_id']+"'"

    # representante = "'Galo'"
    conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST)

    s = "SELECT familia,codigo,descricao,preco FROM tb_favoritos where representante = {}".format(representante)
    data = pd.read_sql_query(s,conn)

    data['codigo'] = data['codigo'].str.strip()
    data['descricao'] = data['descricao'].str.strip()
    data['familia'] = data['familia'].str.strip()

    header = ['Família','Código','Descrição', 'Preço']

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
    response.headers.set('Content-Disposition', 'attachment', filename='tabela-produtos.pdf')
    buff = BytesIO()
    # doc = SimpleDocTemplate(buff, pagesize=landscape(letter))

    doc_width, doc_height = landscape(letter)  # Mudar a orientação para paisagem
    doc = SimpleDocTemplate(buff, pagesize=(doc_width, doc_height))  # Passar o tamanho do documento
    
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
    conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST)

    s = "SELECT familia,codigo,descricao,preco FROM tb_lista_precos where representante = {}".format(representante)
    data = pd.read_sql_query(s,conn)

    data['codigo'] = data['codigo'].str.strip()
    data['descricao'] = data['descricao'].str.strip()
    data['familia'] = data['familia'].str.strip()

    header = ['Família','Código','Descrição', 'Preço']

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
    response.headers.set('Content-Disposition', 'attachment', filename='tabela-produtos-all.pdf')
    buff = BytesIO()
    # doc = SimpleDocTemplate(buff, pagesize=landscape(letter))

    doc_width, doc_height = landscape(letter)  # Mudar a orientação para paisagem
    doc = SimpleDocTemplate(buff, pagesize=(doc_width, doc_height))  # Passar o tamanho do documento
    
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
    
    conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST)

    representante = "'"+session['user_id']+"'"
    # representante = """'Galo'"""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM tb_carrinho_representante where representante = {}".format(representante))
    data = cur.fetchall()

    for row in data:
        preco = float(row['preco'])
        row['preco'] = "R$ {:,.2f}".format(preco).replace(",", "X").replace(".", ",").replace("X", ".")

    return render_template("car.html", data=data)

@app.route('/salvar_dados', methods=['POST','GET'])
def salvar_dados():

    if request.method == 'POST':


        conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST)   

        cur = conn.cursor

        tabela = request.form.get('tabela')
        tabela = json.loads(tabela)

        cliente = request.form.get('numeroCliente')
        status = request.form.get("statusCotacao")

        print(status, cliente)

        unique_id = str(uuid.uuid4())  # Gerar id unico

        tb_orcamento = pd.DataFrame(tabela)
        tb_orcamento['representante'] = ""+session['user_id']+""
        tb_orcamento['dataOrcamento'] = datetime.today()
        tb_orcamento['dataOrcamento'] = tb_orcamento['dataOrcamento'].dt.strftime('%Y-%m-%d')
        tb_orcamento['cliente'] = cliente
        tb_orcamento['id'] = unique_id
        tb_orcamento['status'] = status

        tb_orcamento['precoFinal'] = tb_orcamento['precoFinal'].str.replace("R\$","").str.replace(".","").str.replace(",",".").astype(float)
        tb_orcamento['preco'] = tb_orcamento['preco'].str.replace("R\$","").str.replace(".","").str.replace(",",".").astype(float)
        
        print(tb_orcamento)

        # Cria uma lista de tuplas contendo os valores das colunas do DataFrame
        valores = list(zip(tb_orcamento['familia'], tb_orcamento['codigo'], tb_orcamento['descricao'], tb_orcamento['preco'], tb_orcamento['precoFinal'],
                        tb_orcamento['quantidade'].astype(int), tb_orcamento['representante'], tb_orcamento['dataOrcamento'], tb_orcamento['cliente'], tb_orcamento['id'],
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

@app.route('/move-carrinho/<string:id>', methods = ['POST','GET'])
@login_required
def move_carrinho(id):

    conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST)

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    representante = "'"+session['user_id']+"'"
    
    df = pd.read_sql_query('SELECT * FROM tb_lista_precos WHERE id = {}'.format(id), conn)

    for coluna in df.columns:
        if df[coluna].dtype == 'object':
            df[coluna] = df[coluna].str.strip()

    df_carrinho = pd.read_sql_query('SELECT * FROM tb_carrinho_representante WHERE representante = {}'.format(representante), conn)

    df_carrinho = df_carrinho['codigo'].values.tolist()

    representante = ""+session['user_id']+""

    if df['codigo'][0] not in df_carrinho:
        cur.execute("INSERT INTO tb_carrinho_representante (familia, codigo, descricao, preco, representante) VALUES (%s,%s,%s,%s,%s)", (df['familia'][0], df['codigo'][0], df['descricao'][0], df['preco'][0], representante))
        conn.commit()
        conn.close()
    else:
        pass

    return redirect(url_for('lista'))

@app.route('/move-carrinho-favorito/<string:id>', methods = ['POST','GET'])
@login_required
def move_carrinho_favorito(id):

    conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST)

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    representante = "'"+session['user_id']+"'"
    
    df = pd.read_sql_query('SELECT * FROM tb_favoritos WHERE id = {}'.format(id), conn)

    for coluna in df.columns:
        if df[coluna].dtype == 'object':
            df[coluna] = df[coluna].str.strip()

    df_carrinho = pd.read_sql_query('SELECT * FROM tb_carrinho_representante WHERE representante = {}'.format(representante), conn)

    df_carrinho = df_carrinho['codigo'].values.tolist()

    representante = ""+session['user_id']+""

    if df['codigo'][0] not in df_carrinho:
        cur.execute("INSERT INTO tb_carrinho_representante (familia, codigo, descricao, preco, representante) VALUES (%s,%s,%s,%s,%s)", (df['familia'][0], df['codigo'][0], df['descricao'][0], df['preco'][0], representante))
        conn.commit()
        conn.close()
    else:
        pass

    return redirect(url_for('lista_favoritos'))

@app.route('/remove-carrinho/<string:id>', methods = ['POST','GET'])
@login_required
def remove_carrinho(id):

    conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST)

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    representante = "'"+session['user_id']+"'"

    # representante = """Galo"""

    cur.execute('DELETE FROM tb_carrinho_representante WHERE id = {}'.format(id))

    conn.commit()
    
    conn.close()

    return redirect(url_for('adicionar_ao_carrinho'))

@app.route('/remove-all', methods = ['POST','GET'])
@login_required
def remove_all():

    conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST)

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    representante = "'"+session['user_id']+"'"

    # representante = """Galo"""

    cur.execute('DELETE FROM tb_carrinho_representante WHERE representante = {}'.format(representante))

    conn.commit()
    
    conn.close()

    return redirect(url_for('adicionar_ao_carrinho'))

##### Bloco de orçamentos #####

@app.route('/orcamentos', methods=['GET'])
@login_required
def orcamentos():

    conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST)

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

            sql1 += " AND dataOrcamento BETWEEN %s AND %s"  # Adiciona um espaço em branco antes do AND
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
        valor = tupla[2]  # Acessa o terceiro elemento da tupla (valor a ser formatado)
        valor_formatado = format_currency(valor, 'BRL', locale='pt_BR')
        valor_formatado = valor_formatado.replace("\xa0", " ")  # Remove o espaço em branco
        dados[i] = (*tupla[:2], valor_formatado, *tupla[3:])

    return render_template('orcamentos.html', dados=dados)

@app.route('/orcamento/<string:id>', methods = ['POST','GET'])
@login_required
def item_orcamento(id):

    id = "'" + id + "'"

    conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST)

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    representante = "'"+session['user_id']+"'"

    # representante = """Galo"""

    cur.execute('SELECT * FROM tb_orcamento WHERE id = {}'.format(id))

    dados = cur.fetchall()

    for dicionario in dados:
        valor = dicionario['preco']  # Acessa o valor do campo 'preco' no dicionário
        valor_formatado = format_currency(valor, 'BRL', locale='pt_BR')
        valor_formatado = valor_formatado.replace("\xa0", " ")  # Remove o espaço em branco
        dicionario['preco'] = valor_formatado
    
    #id = "'8397d602-ca7d-43c1-a838-378ff7640ba7'"

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

    conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST)
    cur = conn.cursor()

    query = 'DELETE FROM tb_orcamento WHERE id_serial = %s'
    cur.execute(query, (id,))

    conn.commit()
    cur.close()
    conn.close()

    return jsonify({'message': 'Item removido com sucesso'})

@app.route("/checkbox", methods=['POST'] )
def checkbox():
    
    dados_selecionados = request.get_json()
    
    # Faça o processamento dos dados selecionados aqui
    # Por exemplo, você pode imprimir os dados no console
    print(dados_selecionados)
    return 'Dados recebidos com sucesso!'

@app.route('/atualizar-dados', methods=['POST'])
def atualizar_dados():
    descricao = request.form['descricao']
    modelo = request.form['modelo']
    eixo = request.form['eixo']
    mola_freio = request.form['mola_freio']
    tamanho = request.form['tamanho']
    rodado = request.form['rodado']
    pneu = request.form['pneu']
    descricao_generica = request.form['descricao_generica']
    
    # obter os valores selecionados em cada dropdown enviado pela solicitação AJAX

    # executar a lógica para atualizar o DataFrame com base nas opções selecionadas

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    placeholders = []

    query = """ SELECT DISTINCT t1.*, t2.preco
        FROM tb_produtos AS t1
        LEFT JOIN tb_lista_precos AS t2 ON t1.codigo = t2.codigo
        WHERE t1.crm = 'T' and t2.preco is not null
    """

    if descricao:
        query += " AND descricao_generica = %s"
        placeholders.append(descricao)

    if modelo:
        query += " AND modelo = %s"
        placeholders.append(modelo)

    if eixo:
        query += " AND eixo = %s"
        placeholders.append(eixo)

    if mola_freio:
        query += " AND mola_freio = %s"
        placeholders.append(mola_freio)

    if tamanho:
        query += " AND tamanho = %s"
        placeholders.append(tamanho)

    if rodado:
        query += " AND rodado = %s"
        placeholders.append(rodado)

    if pneu:
        query += " AND pneu = %s"
        placeholders.append(pneu)

    if descricao_generica:
        query += " AND outras_caracteristicas = %s"
        placeholders.append(descricao_generica)

    cur.execute(query, placeholders)
    data = cur.fetchall()
    df = pd.DataFrame(data)

    df['preco'] = df['preco'].apply(lambda x: "R$ {:,.2f}".format(x).replace(",", "X").replace(".", ",").replace("X", "."))

    descricao = df[['descricao_generica']].drop_duplicates().values.tolist()
    modelo = df[['modelo']].drop_duplicates().values.tolist()
    eixo = df[['eixo']].drop_duplicates().values.tolist()
    mola_freio = df[['mola_freio']].drop_duplicates().values.tolist()
    tamanho = df[['tamanho']].drop_duplicates().values.tolist()
    rodado = df[['rodado']].drop_duplicates().values.tolist()
    pneu = df[['pneu']].drop_duplicates().values.tolist()
    descricao_generica = df[['outras_caracteristicas']].drop_duplicates().values.tolist()

    data = df.values.tolist()

    return jsonify(dados=data, descricao=descricao,
                    modelo=modelo, eixo=eixo,
                    mola_freio=mola_freio, tamanho=tamanho,
                    rodado=rodado, pneu=pneu,
                    descricao_generica=descricao_generica)

@app.route('/atualizar-cliente', methods=['POST'])
def atualizar_cliente():

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    nome_cliente = request.form['nome_cliente']
    contato_cliente = request.form['contato_cliente']

    query2 = """SELECT nome, contatos FROM tb_clientes_contatos WHERE 1=1"""

    placeholders = []
    if nome_cliente:
        query2 += " AND nome = %s"
        placeholders.append(nome_cliente)
        
    # if contato_cliente:
    #     query2 += " AND contatos = %s"
    #     placeholders.append(contato_cliente)

    cur.execute(query2, placeholders)
    data = cur.fetchall()
    df_clientes = pd.DataFrame(data)

    # Divide a coluna 'contatos' em várias linhas com base no delimitador ';'
    df_contatos = df_clientes['contatos'].str.split(';', expand=True).stack().reset_index(level=1, drop=True).rename('contatos')

    # Reorganiza o DataFrame para ter um contato por linha
    df_clientes = df_clientes.drop('contatos', axis=1).join(df_contatos)

    # Limpa os espaços em branco antes e depois dos contatos
    df_clientes['contatos'] = df_clientes['contatos'].str.strip()

    nome_cliente = df_clientes[['nome']].drop_duplicates().values.tolist()
    contato_cliente = df_clientes[['contatos']].drop_duplicates().values.tolist()

    return jsonify(nome_cliente=nome_cliente,contato_cliente=contato_cliente)

@app.route('/enviarBackend', methods=['POST'])
def obs():

    linha = request.get_json()

    
    return 'Itens recebidos e processados com sucesso!'

@app.route('/rota-do-backend', methods=['POST'])
def process_data():
    data = request.get_json()
    linha = request.get_json()
    
    lista_description = []
    lista_quantidade = []
    lista_preco = []
    
    # Iterar sobre a lista de itens recebidos
    for item in data:
        description = item.get('description')
        quantity = item.get('quantity')
        precoElement = item.get('preco')
        
        lista_description.append(description)
        lista_quantidade.append(quantity)
        lista_preco.append(precoElement)
        
        # Faça o processamento necessário com os dados
    
    print(lista_description)
    print(lista_quantidade)
    print(lista_preco)

    lista_nome = []
    lista_contato = []
    lista_pagamento = []
    lista_observacao = []

    # Iterar sobre a lista de itens recebidos
    for ob in linha:
        filtroNome = ob.get('filtroNome')
        filtroContato = ob.get('filtroContato')
        filtroPagamento = ob.get('filtroPagamento')
        filtroObservacao = ob.get('filtroObservacao')
        
        lista_nome.append(filtroNome)
        lista_contato.append(filtroContato)
        lista_pagamento.append(filtroPagamento)
        lista_observacao.append(filtroObservacao)

    print(lista_nome)
    print(lista_contato)
    print(lista_pagamento)
    print(lista_observacao)

    # Retorne uma resposta para o frontend
    return 'Itens recebidos e processados com sucesso!'

if __name__ == '__main__':
    app.run()