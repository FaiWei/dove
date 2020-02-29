import os

#set FLASK_APP=application.py
#set DATABASE_URL=

from flask import Flask, session, redirect, render_template, request
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from functools import wraps
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))


def apology(message, code=400):
    """Render message as an apology to user."""
    def escape(s):
        """
        Escape special characters.
        https://github.com/jacebrowning/memegen#special-characters
        """
        for old, new in [("-", "--"), (" ", "-"), ("_", "__"), ("?", "~q"),
                         ("%", "~p"), ("#", "~h"), ("/", "~s"), ("\"", "''")]:
            s = s.replace(old, new)
        return s
    return render_template("apology.html", top=code, bottom=escape(message)), code

def login_required(f):
    """
    Decorate routes to require login.
    http://flask.pocoo.org/docs/1.0/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function



@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    """Show main page with search or search results"""  

    if request.method == "POST":
        #get user search request
        search_request = request.form.get("search_request")
        request_splitted = search_request.split()
        print(type(request_splitted))
        print(type(request_splitted[0]))
        print(request_splitted[0])
        liked_req = phraseforlike(request_splitted)
        print(liked_req)
        # derive search results by to_tsvector-to_tsquery
        smart_req = db.execute("SELECT * FROM practice.books WHERE to_tsvector(title) || to_tsvector(author) || to_tsvector(isbn) @@ plainto_tsquery(:search_request) ORDER BY title ASC", {"search_request": search_request}).fetchall()
        # derive search results by LIKE
        simple_req = db.execute("SELECT * FROM practice.books WHERE title || author || isbn LIKE :search_request ORDER BY title ASC", {"search_request": liked_req}).fetchall()
        # merge them there to_tsvector-to_tsquery goes first
        for row_s in simple_req:
            for row in smart_req:
                if row_s == row:
                    simple_req.remove(row_s)
        smart_req.extend(simple_req)
        
        #if search result "None" return different page
        if not smart_req:
            return apology("Results not found")
        return render_template("search.html", rows=smart_req)

    else:
        # derive username database
        username = db.execute("SELECT username FROM practice.users \
                                WHERE id = :id", {"id": session["user_id"]}).fetchone()    
        return render_template("index.html", username=username.username)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        row = db.execute("SELECT * FROM practice.users WHERE username = :username",
                          {"username":request.form.get("username")}).fetchone()


        # Ensure username exists and password is correct
        if row is None or not check_password_hash(row.password, request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = row.id

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")

@app.route("/register", methods=["GET", "POST"])
def register():

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        name = request.form.get("username")

        exists_username = db.execute("SELECT username FROM practice.users WHERE username = :username", {"username":name}).fetchone()

        if exists_username:
            return apology("username already exists", 400)
        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)
        # Ensure password check was submitted
        elif not request.form.get("confirmation"):
            return apology("must provide password check", 400)
        # Ensure password check was submitted
        elif request.form.get("confirmation") != request.form.get("password"):
            return apology("passwords do not match", 400)

        # insert new info in db
        passhash = generate_password_hash(request.form.get("password"))
        db.execute(
            "INSERT INTO practice.users (username,password) VALUES (:username, :password)",
            {"username": name, "password": passhash})
        db.commit()

        # log into session
        fetchid = db.execute("SELECT id FROM practice.users WHERE username = :username", {"username":name}).fetchone()
        session["user_id"] = fetchid.id

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")

        
def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)

#create search variable for LIKE
def phraseforlike(words):
    x = '%'
    a = 1
    for word in words:
        if a == 1:
            x = x + word + '%'
            a = 0
        else:
            x = x + ' AND %' + word + '%'
    return x

# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
