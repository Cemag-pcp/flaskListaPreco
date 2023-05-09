from flask import Flask,render_template, redirect, url_for, request, session, flash, make_response, Response
from flask import render_template_string
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
import locale

app = Flask(__name__)
app.secret_key = "listaPreco"

# DB_HOST = "localhost"
DB_HOST = "database-1.cdcogkfzajf0.us-east-1.rds.amazonaws.com"
DB_NAME = "postgres"
DB_USER = "postgres"
DB_PASS = "15512332"
 
conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST)

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

    locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')

    conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST)

    representante = "'"+session['user_id']+"'"

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM tb_lista_precos where representante = {}".format(representante))
    #data = pd.read_sql_query("SELECT * FROM tb_lista_precos", conn)
    data = cur.fetchall()

    for row in data:
        preco = locale.currency(row['preco'], grouping=True, symbol='R$')
        row['preco'] = preco    

    return render_template('lista.html', data=data)

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

    locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')

    conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST)

    representante = "'"+session['user_id']+"'"
    # representante = """'Galo'"""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM tb_favoritos where representante = {}".format(representante))
    data = cur.fetchall()

    for row in data:
        preco = locale.currency(row['preco'], grouping=True, symbol='R$')
        row['preco'] = preco    

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

# conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST)
# cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

# df = pd.read_csv('carga_Galo.csv', sep=';')

# df.reset_index(inplace=True)
# df = df.rename(columns={'index':'id'})
# # df.drop(columns={'Unnamed: 4'}, inplace=True)

# # df = df.iloc[[0,1],:]

# # Inserir os dados do dataframe na tabela
# for index, row in df.iterrows():
#     cur.execute('INSERT INTO tb_lista_precos (id, familia, codigo, descricao, representante, preco) VALUES (%s, %s, %s, %s, %s, %s)', (row['id'], row['familia'], row['codigo'], row['descricao'], row['representante'], row['preco']))

# # Salvar as alterações no banco de dados
# conn.commit()

# # Fechar a conexão com o banco de dados
# conn.close()

if __name__ == '__main__':
    app.run()