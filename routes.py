from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from flask_mysqldb import MySQL
import hashlib

main = Blueprint("main", __name__)
mysql = MySQL()

@main.route("/")
def index():
    return render_template("index.html")

@main.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name")
        account_number = request.form.get("account_number")
        transaction_pin = request.form.get("transaction_pin")
        email = request.form.get("email")
        password = request.form.get("password")

        # Hash password for security
        password_hash = hashlib.sha256(password.encode()).hexdigest()

        try:
            cursor = mysql.connection.cursor()
            cursor.execute("""
                INSERT INTO users (name, account_number, transaction_pin, email, password_hash, balance)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (name, account_number, transaction_pin, email, password_hash, 0.00))

            mysql.connection.commit()
            cursor.close()

            # Auto-login after successful registration
            session["user"] = email

            flash("Registration successful! Redirecting to dashboard...", "success")
            return redirect(url_for("main.dashboard"))

        except Exception as e:
            flash(f"Error: {str(e)}", "danger")

    return render_template("register.html")

@main.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        cursor = mysql.connection.cursor()
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        cursor.execute("SELECT * FROM users WHERE email = %s AND password_hash = %s", (email, password_hash))

        user = cursor.fetchone()
        cursor.close()

        if user:
            session["user"] = email  # Store user session
            flash("Login successful!", "success")
            return redirect(url_for("main.dashboard"))
        else:
            flash("Invalid credentials. Please try again.", "danger")

    return render_template("login.html")

@main.route("/dashboard")
def dashboard():
    if "user" not in session:
        flash("Please log in first!", "warning")
        return redirect(url_for("main.login"))

    cursor = mysql.connection.cursor()
    cursor.execute("SELECT name, balance FROM users WHERE email = %s", (session["user"],))
    user_data = cursor.fetchone()
    cursor.close()

    if not user_data:
        flash("User not found!", "danger")
        return redirect(url_for("main.logout"))

    return render_template("dashboard.html", name=user_data[0], balance=user_data[1])

@main.route("/deposit", methods=["GET", "POST"])
def deposit():
    if "user" not in session:
        flash("Please log in first!", "warning")
        return redirect(url_for("main.login"))

    if request.method == "POST":
        try:
            amount = float(request.form.get("amount"))
            if amount <= 0:
                flash("Invalid deposit amount!", "danger")
                return redirect(url_for("main.deposit"))

            cursor = mysql.connection.cursor()

            # Update balance
            cursor.execute("UPDATE users SET balance = balance + %s WHERE email = %s", (amount, session["user"]))

            # Get user's account number
            cursor.execute("SELECT account_number FROM users WHERE email = %s", (session["user"],))
            account_number = cursor.fetchone()[0]

            # Insert transaction record
            cursor.execute("""
                INSERT INTO transactions (account_number, amount, type)
                VALUES (%s, %s, 'deposit')
            """, (account_number, amount))

            mysql.connection.commit()
            cursor.close()

            flash(f"Successfully deposited ${amount:.2f}!", "success")
            return redirect(url_for("main.dashboard"))

        except Exception as e:
            flash(f"Error: {str(e)}", "danger")

    return render_template("deposit.html")

@main.route("/transactions", methods=["GET", "POST"])
def transactions():
    if "user" not in session:
        flash("Please log in first!", "warning")
        return redirect(url_for("main.login"))

    cursor = mysql.connection.cursor()

    # Fetch the user's account number and transaction PIN using their email
    cursor.execute("SELECT account_number, transaction_pin FROM users WHERE email = %s", (session["user"],))
    result = cursor.fetchone()

    transactions = []
    
    if result:
        account_number = result[0]  # Extract account number
        stored_pin = result[1]  # Extract stored transaction PIN
        session['user_account_number'] = account_number
        
        if request.method == "POST":
            recipient_account = request.form.get("account_number")
            amount = request.form.get("amount")
            entered_pin = request.form.get("transaction_pin")  # Get entered PIN

            if not recipient_account or not amount or not entered_pin:
                flash("Please fill in all fields.", "danger")
                return redirect(url_for("main.transactions"))

            try:
                amount = float(amount)
                if amount <= 0:
                    flash("Amount must be greater than zero.", "danger")
                    return redirect(url_for("main.transactions"))
            except ValueError:
                flash("Invalid amount entered.", "danger")
                return redirect(url_for("main.transactions"))

            # Check if recipient exists
            cursor.execute("SELECT * FROM users WHERE account_number = %s", (recipient_account,))
            recipient = cursor.fetchone()
            if not recipient:
                flash("Recipient account not found.", "danger")
                return redirect(url_for("main.transactions"))

            # Verify transaction PIN
            if entered_pin != stored_pin:
                flash("Invalid transaction PIN!", "danger")
                return redirect(url_for("main.transactions"))

            # Check sender balance
            cursor.execute("SELECT balance FROM users WHERE account_number = %s", (account_number,))
            sender_balance = cursor.fetchone()[0]
            if sender_balance < amount:
                flash("Insufficient balance.", "danger")
                return redirect(url_for("main.transactions"))

            # Deduct from sender & Add to recipient
            cursor.execute("UPDATE users SET balance = balance - %s WHERE account_number = %s", (amount, account_number))
            cursor.execute("UPDATE users SET balance = balance + %s WHERE account_number = %s", (amount, recipient_account))

            # Record transaction with PIN
            cursor.execute(
                "INSERT INTO transactions (account_number, recipient_account, amount, transaction_pin, type) VALUES (%s, %s, %s, %s, %s)",
                (account_number, recipient_account, amount, entered_pin, 'transfer'),
            )

            mysql.connection.commit()
            flash("Transaction successful!", "success")
            return redirect(url_for("main.transactions"))

        # Fetch transaction history for both sent and received transactions
        cursor.execute("""
            SELECT * FROM transactions 
            WHERE account_number = %s OR recipient_account = %s
            ORDER BY created_at DESC
        """, (account_number, account_number))
        transactions = cursor.fetchall()

    cursor.close()

    return render_template("transactions.html", transactions=transactions)

@main.route("/balance")
def balance():
    if "user" not in session:
        flash("Please log in first!", "warning")
        return redirect(url_for("main.login"))

    cursor = mysql.connection.cursor()

    cursor.execute("SELECT account_number, balance FROM users WHERE email = %s", (session["user"],))
    result = cursor.fetchone()

    if not result:
        flash("User not found!", "danger")
        return redirect(url_for("main.logout"))

    account_number, balance = result

    # Get recent transactions
    cursor.execute("""
        SELECT amount, created_at 
        FROM transactions 
        WHERE account_number = %s OR recipient_account = %s 
        ORDER BY created_at DESC 
        LIMIT 5
    """, (account_number, account_number))
    transactions = cursor.fetchall()

    # Calculate total deposits and withdrawals (only when user is sender)
    cursor.execute("""
        SELECT 
            SUM(CASE WHEN type = 'deposit' THEN amount ELSE 0 END) AS total_deposit,
            SUM(CASE WHEN type = 'withdrawal' OR type = 'transfer' THEN ABS(amount) ELSE 0 END) AS total_withdrawal
        FROM transactions
        WHERE account_number = %s
    """, (account_number,))


    totals = cursor.fetchone()
    total_deposit = totals[0] or 0
    total_withdrawal = totals[1] or 0


    # Prevent divide by zero
    total_money = total_deposit + total_withdrawal
    spent_percent = round((total_withdrawal / total_money) * 100, 2) if total_money > 0 else 0
    saved_percent = 100 - spent_percent if total_money > 0 else 0

    cursor.close()

    return render_template(
        "balance.html",
        balance=balance,
        transactions=transactions,
        total_deposit=total_deposit,
        total_withdrawal=total_withdrawal,
        spent_percent=spent_percent,
        saved_percent=saved_percent
    )

@main.route("/profile")
def profile():
    if "user" not in session:
        flash("Please log in first!", "warning")
        return redirect(url_for("main.login"))

    cursor = mysql.connection.cursor()
    cursor.execute("SELECT name, email, account_number, balance FROM users WHERE email = %s", (session["user"],))
    user_data = cursor.fetchone()
    cursor.close()

    return render_template("profile.html", user=user_data)

@main.route("/logout")
def logout():
    session.pop("user", None)
    flash("You have been logged out.", "info")
    return redirect(url_for("main.index"))
