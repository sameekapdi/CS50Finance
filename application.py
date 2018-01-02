from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import mkdtemp

from helpers import *

# configure application
app = Flask(__name__)

# ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# custom filter
app.jinja_env.filters["usd"] = usd

# configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

@app.route("/")
@login_required
def index():
    """Show users homepage which is a list of their current stocks."""
    #retrieve users stocks
    old_stocks = db.execute("SELECT shares,symbol FROM portfolio WHERE user = :userid", userid=session["user_id"])
    #check to see if they have any stocks
    if not old_stocks:
        return render_template("index.html", stocks=False)
    else:
        total_cash=0
        #iterate through the stocks and get the updated price
        for old_stock in old_stocks:
            symbol = old_stock["symbol"]
            shares = old_stock["shares"]
            stock = lookup(symbol)
            if not stock:
                return apology("Sorry an error occurred")
                break;
            stock_price=stock['price']
            total = shares*stock_price
            #running total of asset prices
            total_cash += total
            #update portfolio with the update prices
            db.execute("UPDATE portfolio SET price=:price,total=:total WHERE user=:userid AND symbol=:symbol", price=usd(stock["price"]), total=usd(total),userid=session["user_id"],symbol=symbol)

        #get user cash and total asset amount
        new_cash = db.execute("SELECT cash FROM users WHERE id=:userid", userid=session["user_id"])
        total_cash += new_cash[0]["cash"]
        #get the new,updated stock info
        new_stocks = db.execute("SELECT * FROM portfolio WHERE user=:userid", userid=session["user_id"])
        #render the homepage
        return render_template("index.html", stocks=new_stocks, cash=usd(new_cash[0]["cash"]), total=usd(total_cash))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock."""

    # if user reached route via POST
    if request.method == "POST":

        #ensure symbol was entered
        if not request.form.get("symbol"):
            return apology("invalid symbol")

        #ensure share was entered
        if not request.form.get("shares"):
            return apology("missing shares")
        # ensure proper number of shares
        try:
            shares = int(request.form.get("shares"))
            if shares <= 0:
                return apology("Shares must be positive integer")
        except:
            return apology("Shares must be positive integer")

        # get quote information
        quote = lookup(request.form.get("symbol"))
        if not quote:
            return apology("Enter a valid Symbol")
        price = quote["price"]
        name = quote["name"]
        symbol = quote["symbol"]
        total =  float(shares) * float(price)

        #check to see if user can afford stock
        cash = db.execute("SELECT cash FROM users WHERE id = :userid", userid=session["user_id"])
        if cash[0]["cash"] >= total:
            #add bought stock to history table
            result = db.execute("INSERT INTO history (user,symbol,shares,price) VALUES(:user, :symbol,:shares, :price)", user=session["user_id"], symbol=symbol,shares=shares,price=usd(price))
            if not result:
                return apology("unable to process transaction")

            else:
                #update user cash
                updatecash = db.execute("UPDATE users SET cash = cash-:newcash WHERE id=:userid",userid=session["user_id"],newcash = total)
                if not updatecash:
                    apology("unable to update user info")

            #get user portfolio
            user_shares = db.execute("SELECT shares FROM portfolio WHERE user=:userid AND symbol=:symbol", userid=session["user_id"],symbol=symbol)

            #check to see if shares exists for user
            if not user_shares:
                db.execute("INSERT INTO portfolio (user, symbol,name, shares,price,total) VALUES(:userid,:symbol,:name,:shares,:price,:total)",userid=session["user_id"],symbol=symbol,name=name,shares=shares,price=usd(price),total=usd(total))

            else:
                shares_total = user_shares[0]["shares"] + shares
                db.execute("UPDATE portfolio SET shares=:shares WHERE user=:userid AND symbol=:symbol", shares=shares_total,userid=session["user_id"],symbol=symbol)

        else:
            return apology("insufficient funds")

        # redirect user to home page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("buy.html")

@app.route("/history")
@login_required
def history():
    """Show history of transactions."""
    history = db.execute("SELECT * FROM history WHERE user = :userid", userid=session["user_id"])
    if not history:
        return apology("error")
    else:
        return render_template("history.html", history=history)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        # ensure username exists and password is correct
        if len(rows) != 1 or not pwd_context.verify(request.form.get("password"), rows[0]["hash"]):
            return apology("invalid username and/or password")

        # remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # redirect user to home page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out."""

    # forget any user_id
    session.clear()

    # redirect user to login form
    return redirect(url_for("login"))

@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    #if user reached via POST
    if request.method == "POST":

        # ensure field is not empty
        if not request.form.get("symbol"):
            return apology("invalid symbol")
        # get quote via lookup
        quote = lookup(request.form.get("symbol"))

        # display quote information if its valid
        if not quote:
            return apology("invalid symbol")
        else:
            return render_template("quoted.html", quote=quote)
    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("quote.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user."""
    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # ensure confirm password was submitted
        elif not request.form.get("confirm-password"):
            return apology("must confirm password")

        # ensure password match
        if request.form.get("password") != request.form.get("confirm-password"):
            return apology("passwords must match")

        # encrypt password
        hash_pw = pwd_context.hash(request.form.get("password"))

        # add user to database
        result = db.execute("INSERT INTO users (username,hash) VALUES(:username, :hashpw)", username=request.form.get("username"), hashpw = hash_pw)
        if not result:
            return apology("user already exists")

        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        # ensure username exists and password is correct
        if len(rows) != 1 or not pwd_context.verify(request.form.get("password"), rows[0]["hash"]):
            return apology("invalid username and/or password")

        # remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # redirect user to home page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock."""

    if request.method == "POST":


        #ensure symbol is selected.
        if not request.form.get("symbol"):
            return apology("Select a stock to sell")
        #ensure shares is valid
        if not request.form.get("shares"):
            return apology("Enter number of shares.")
        # ensure proper number of shares
        try:
            shares = int(request.form.get("shares"))
            if shares <= 0:
                return apology("Shares must be positive integer")
        except:
            return apology("Shares must be positive integer")

        #declare variables
        quote = lookup(request.form.get("symbol"))
        price = quote["price"]
        name = quote["name"]
        symbol = quote["symbol"]
        total =  float(shares) * float(price)
        #get user stock info
        user_shares = db.execute("SELECT shares FROM portfolio WHERE user=:userid AND symbol=:symbol", userid=session["user_id"],symbol=symbol)
        #ensure user has enough stock
        if not user_shares or int(user_shares[0]["shares"])<shares:
            return apology("You don't have enough shares")
        #update history
        result = db.execute("INSERT INTO history (user,symbol,shares,price) VALUES(:user, :symbol,:shares, :price)", user=session["user_id"], symbol=symbol,shares=-shares,price=usd(price))
        if not result:
            return apology("unable to process transaction")
        #update user cash
        db.execute("UPDATE users SET cash= cash+:sold WHERE id=:userid",userid=session["user_id"],sold=total)
        #decrement shares
        share_total = int(user_shares[0]["shares"]) - shares
        #check if shares in portfolio is <0
        if share_total <=0:
            #if so delete it
            db.execute("DELETE FROM portfolio WHERE user=:userid AND symbol=:symbol",userid=session["user_id"],symbol=symbol)

        #if not update user portolio
        else:
            db.execute("UPDATE portfolio SET shares=:shares WHERE user=:userid and symbol=:symbol",shares=share_total,userid=session["user_id"],symbol=symbol)
        return redirect(url_for("index"))
    else:
        stocks = db.execute("SELECT symbol FROM portfolio WHERE user=:userid", userid=session["user_id"])
        return render_template("sell.html",stocks=stocks)

@app.route("/cash", methods=["GET", "POST"])
@login_required
def cash():
    """Get extra cash."""
    if request.method == "POST":
        #ensure field has been entered.
        if not request.form.get("cash"):
            return apology("Enter an amount")
        #ensure valid entry
        try:
            cash = int(request.form.get("cash"))
            if cash <= 0:
                return apology("Cash must be positive integer")
        except:
            return apology("Cash must be positive integer")
        #add transaction to history
        db.execute("INSERT INTO history (user,symbol,price) VALUES(:user, :symbol, :price)", user=session["user_id"], symbol="CASH",price=usd(cash))
        #update user cash
        db.execute("UPDATE users SET cash = cash+:new_cash WHERE id=:userid",new_cash=cash,userid=session["user_id"])

        return redirect(url_for('index'))
    else:
        return render_template("cash.html")