from flask import Flask,render_template, redirect, url_for
import psycopg2 #pip install psycopg2 
import psycopg2.extras
import pandas as pd

app = Flask(__name__)
app.secret_key = "listaPreco"

# DB_HOST = "localhost"
DB_HOST = "database-1.cdcogkfzajf0.us-east-1.rds.amazonaws.com"
DB_NAME = "postgres"
DB_USER = "postgres"
DB_PASS = "15512332"
 
conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST)

@app.route('/')
def lista():

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM tb_lista_precos")
    #data = pd.read_sql_query("SELECT * FROM tb_lista_precos", conn)
    data = cur.fetchall()

    return render_template('lista.html', data=data)

@app.route('/move/<string:id>', methods = ['POST','GET'])
def move(id):

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    print(id)

    df = pd.read_sql_query('SELECT * FROM tb_lista_precos WHERE id = {}'.format(id), conn)

    for coluna in df.columns:
        if df[coluna].dtype == 'object':
            df[coluna] = df[coluna].str.strip()

    df = df.values.tolist()

    cur.execute("INSERT INTO tb_favoritos (id,codigo,representante) VALUES (%s,%s,%s)", (df[0][0], df[0][1], df[0][2]))

    cur.execute('DELETE FROM tb_lista_precos WHERE id = {0}'.format(id))

    # conn.commit()
    return redirect(url_for('lista'))

@app.route('/favoritos')
def lista_favoritos():

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM tb_favoritos")
    data = cur.fetchall()

    return render_template("favoritos.html", data=data)

if __name__ == '__main__':
    app.run()