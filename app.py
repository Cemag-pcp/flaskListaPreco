from flask import Flask,render_template, redirect, url_for, request, session, flash
import psycopg2 #pip install psycopg2 
import psycopg2.extras
import pandas as pd
import numpy as np
import functools

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

    conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST)

    representante = "'"+session['user_id']+"'"

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM tb_lista_precos where representante = {}".format(representante))
    #data = pd.read_sql_query("SELECT * FROM tb_lista_precos", conn)
    data = cur.fetchall()

    return render_template('lista.html', data=data)

@app.route('/move/<string:id>', methods = ['POST','GET'])
@login_required
def move(id):

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    df = pd.read_sql_query('SELECT * FROM tb_lista_precos WHERE id = {}'.format(id), conn)

    for coluna in df.columns:
        if df[coluna].dtype == 'object':
            df[coluna] = df[coluna].str.strip()

    cur.execute("INSERT INTO tb_favoritos (id,codigo,representante) VALUES (%s,%s,%s)", (int(np.int64(df['id'][0])), df['codigo'][0], df['representante'][0]))

    cur.execute('DELETE FROM tb_lista_precos WHERE id = {0}'.format(id))

    conn.commit()
    
    return redirect(url_for('lista'))

@app.route('/favoritos')
@login_required
def lista_favoritos():

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM tb_favoritos")
    data = cur.fetchall()

    return render_template("favoritos.html", data=data)

@app.route('/remove/<string:id>', methods = ['POST','GET'])
@login_required
def remove(id):

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    df = pd.read_sql_query('SELECT * FROM tb_favoritos WHERE id = {}'.format(id), conn)

    for coluna in df.columns:
        if df[coluna].dtype == 'object':
            df[coluna] = df[coluna].str.strip()

    cur.execute("INSERT INTO tb_lista_precos (id,codigo,representante) VALUES (%s,%s,%s)", (int(np.int64(df['id'][0])), df['codigo'][0], df['representante'][0]))

    cur.execute('DELETE FROM tb_favoritos WHERE id = {0}'.format(id))

    conn.commit()
    
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

if __name__ == '__main__':
    app.run()