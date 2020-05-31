from flask import Flask, render_template, flash, redirect, url_for, session, request, logging
import traceback
from flask import Flask, render_template, flash, redirect, url_for, session, request, logging
from flask_mysqldb import MySQL
from wtforms import Form, StringField, TextAreaField, PasswordField, validators
from passlib.hash import sha256_crypt
from functools import wraps
import datetime
import time
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
import json



from OpenSSL import SSL
context = SSL.Context(SSL.TLSv1_2_METHOD)
context.use_privatekey_file('parrot.key')
context.use_certificate_file('parrot.crt')

f = '%Y-%m-%d %H:%M:%S'

app = Flask(__name__)
app.secret_key = 'super secret key'
socketio = SocketIO(app)

# Channel Data Global Variables
channel_list = {'general': [] }
present_channel = {'initial':'general'}


# Config MySQL
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'HomeApp'
app.config['MYSQL_PASSWORD'] = 'home123'
app.config['MYSQL_DB'] = 'HomeApp'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'
app.config['SECRET_KEY'] = 'super secret key'
# init MYSQL
mysql = MySQL(app)

def loadData():
    with open('data.txt') as json_file:
        data = json.load(json_file)
    return data

# with open('data.txt', 'w+') as outfile:
#     data = {
#   'familyname': 'Family Name',
#   'callendarID': 'Calendar Name'
# }
#     json.dump(data, outfile)


data = loadData()



@app.route('/')
def home():
    return render_template('home.html',data=data)
    
@app.route('/about')
def about():
    return render_template('about.html',data=data)
    




# Register Form Class
class Registerform(Form):
    name = StringField('Name', [validators.Length(min=1, max=50)])
    username = StringField('Username', [validators.Length(min=4, max=25)])
    email = StringField('Email', [validators.Length(min=6, max=50)])
   
    password = PasswordField('Password', [
        validators.DataRequired(),
        validators.EqualTo('confirm', message='Passwords do not match')
    ])
    confirm = PasswordField('Confirm Password')
    
class Dataform(Form):
    familyname = StringField('Family Name', [validators.Length(min=1, max=50)])
    calendarID = StringField('Calendar ID')
    parentOnlyChatSymbol =  StringField('Parent Only Message Symbol', [validators.Length(min=1, max=50)])


# User Register
@app.route('/register', methods=['GET', 'POST'])
def register():
    
    form = Registerform(request.form)
    
    if request.method == 'POST' and form.validate():
        name = form.name.data
        email = form.email.data
        username = form.username.data
        password = sha256_crypt.encrypt(str(form.password.data))

        # Create cursor
        cur = mysql.connection.cursor()

        # Execute query
        cur.execute('INSERT INTO users(name, email, username, password) VALUES(%s, %s, %s, %s)', (name, email, username, password))

        # Commit to DB
        mysql.connection.commit()

        # Close connection
        cur.close()

        flash('You are now registered and can log in', 'success')

        return redirect(url_for('login'))
    
    return render_template('register.html', form=form,data=data)


# User login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Get Form Fields
        username = request.form['username']
        password_candidate = request.form['password']

        # Create cursor
        cur = mysql.connection.cursor()

        # Get user by username
        result = cur.execute('SELECT * FROM users WHERE username = %s', [username])

        if result > 0:
            # Get stored hash
            sqldata = cur.fetchone()
            password = sqldata['password']
            parent = sqldata['admin']

            # Compare Passwords
            if sha256_crypt.verify(password_candidate, password):
                # Passed
                session['logged_in'] = True
                session['username'] = username
                if parent == 1:
                    session['parent'] = True
                else:
                    session['parent'] = False
                    
                
                flash('You are now logged in', 'success')
                return redirect(url_for('home'))
            else:
                error = 'Invalid login'
                return render_template('login.html', error=error,data=data)
            # Close connection
            cur.close()
        else:
            error = 'Username not found'
            return render_template('login.html', error=error,data=data)

    return render_template('login.html',data=data)

# Check if user logged in
def is_logged_in(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'logged_in' in session:
            return f(*args, **kwargs)
        else:
            flash('Unauthorized, Please login', 'danger')
            return redirect(url_for('login'))
    return wrap


def is_parent(g):
    @wraps(g)
    def wrap(*args, **kwargs):
        if session['parent'] == True:
            return g(*args, **kwargs)
        else:
            flash('Not parent', 'danger')
            return redirect(url_for('home'))
    return wrap


# Logout
@app.route('/logout')
@is_logged_in
def logout():
    session.clear()
    flash('You are now logged out', 'success')
    return redirect(url_for('login'))


@app.route('/dashboard', methods=['GET', 'POST'])
@is_logged_in
def dashboard():
    if request.method == 'POST':
        try:
            option = request.form['user_status']
            try: 
                option = int(option)
            except:
                option = request.form['stat_other']
            cur = mysql.connection.cursor()
            cur.execute('UPDATE users SET user_status = %s WHERE username = %s', (option, session['username']))
            mysql.connection.commit()
            cur.close()
            flash('Success', 'success')
            return render_template('dashboard.html',data=data)
        except:
            sys.exit()
    return render_template('dashboard.html',data=data)


#@app.route('/notifications.js')
#@is_logged_in
#def meassages():
#    return 

@app.route('/messages')
@is_logged_in
def meassages():
    '''Chat room. The user's name and room must be stored in
    the session.'''
    name = session['username']
    session['room'] = 'Family'
    room = session['room']
    if name == '' or room == '':
        return redirect('/')
    return render_template('messages.html', name=name, room=room,data=data)
    return render_template('messages.html',data=data)

@app.route('/status',methods=['GET', 'POST'])
@is_logged_in
def status():
    if request.method == 'GET':
        #get all users from table and there status
        #displays them
        #Option to edit your own down the side
        #cur.execute('UPDATE users SET user_status = %s WHERE username = %s', (2, session['username']))
        #mysql.connection.commit()
        entries = []
        cur = mysql.connection.cursor()
        cur.execute('SELECT COUNT(*) FROM users')
        sqldata = cur.fetchone()
        num = sqldata['COUNT(*)']
        for i in range(1,num+1):
            cur.execute('SELECT name, user_status, last_update FROM users WHERE id = %s', [i])
            sqldata = cur.fetchone()
            name= sqldata['name']
            user_status= sqldata['user_status']
            try: 
                user_status = int(user_status)
            except:
                pass
            last_update = sqldata['last_update']
            entries.append({
                'username': name,
                'status': user_status,
                'lastUpdate': last_update
            })
        cur.close()
        return render_template('status.html',entries=entries,data=data)
    if request.method == 'POST':
        option = request.form['user_status']
        try: 
            option = int(option)
        except:
            option = request.form['stat_other']
        cur = mysql.connection.cursor()     
        ts = time.time()
        timestamp = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
        cur.execute('UPDATE users SET user_status = %s, last_update = %s WHERE username = %s', (option,timestamp, session['username']))
        mysql.connection.commit()
        cur.close()
        return redirect(url_for('status'))



@app.route('/parent', methods=['GET', 'POST'])
@is_logged_in
def ParentControlls():
    global data
    form = Dataform(request.form)
    if request.method == 'GET': 
        form.familyname.default = data['familyname']
        form.calendarID.default = data['calendarID']
        form.parentOnlyChatSymbol.default = data['parentOnlyChatSymbol']
        form.process()
        entries = []
        cur = mysql.connection.cursor()
        cur.execute('SELECT COUNT(*) FROM users')
        sqldata = cur.fetchone()
        num = sqldata['COUNT(*)']
        for i in range(1,num+1):
            cur.execute('SELECT name, user_status, last_update FROM users WHERE id = %s', [i])
            sqldata = cur.fetchone()
            name= sqldata['name']
            entries.append({
                'username': name,
            })
        cur.close()
        return render_template('parent.html',form=form, data=data, entries=entries)
    if request.method == 'POST'and form.validate():
        newData = {
           'familyname': form.familyname.data,
           'calendarID': form.calendarID.data,
           'parentOnlyChatSymbol': form.parentOnlyChatSymbol.data
        }
        with open('data.txt', 'w+') as outfile:
            json.dump(newData, outfile)
        
        data = loadData()
    return redirect(url_for('ParentControlls'))
    #return render_template('parent.html',form=form, data=data)



@app.route('/calendar')
def calendar():
    return render_template('calendar.html',data=data)








@socketio.on('joined', namespace='/chat')
def joined(message):
    room = session.get('room')
    join_room(room)
    emit('status', {'msg': session.get('username') + ' has entered the room.'}, room=room)


@socketio.on('text', namespace='/chat')
def text(message):
    room = session.get('room')
    
    emit('message', {'msg': session.get('username') + ':' + message['msg'], 'parentOnly':message['msg'].startswith(data['parentOnlyChatSymbol'])}, room=room)



@socketio.on('left', namespace='/chat')
def left(message):
    room = session.get('room')
    leave_room(room)
    emit('status', {'msg': session.get('username') + ' has left the room.'}, room=room)





if __name__ == '__main__':
    app.secret_key = 'super secret key'
    #context = ('parrot.crt', 'parrot.key')
    app.run(debug=False, host='0.0.0.0')#, ssl_context=context)
