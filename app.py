import os
import mysql.connector
from datetime import datetime
from flask import (Flask, render_template, request, redirect,
                   url_for, flash, send_file, abort)
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions # Import google exceptions
from fpdf import FPDF

# --- Configuration ---
# Load sensitive data from environment variables for security
FLASK_SECRET_KEY = 'your_strong_random_secret_key'
GEMINI_API_KEY = "Enter your API key here"
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_USER = os.getenv('DB_USER', 'root')
DB_PASSWORD = os.getenv('DB_PASSWORD', '#Enter Pass') # Keep default if not set
DB_NAME = os.getenv('DB_DATABASE', 'payment_tracker') # Keep default if not set

# Flask App Configuration
app = Flask(__name__)
if not FLASK_SECRET_KEY:
    print("WARNING: FLASK_SECRET_KEY environment variable not set. Using a default insecure key.")
    app.secret_key = 'a-very-insecure-default-key' # Use a default only if necessary, not for production
else:
    app.secret_key = FLASK_SECRET_KEY

# Gemini Configuration
if not GEMINI_API_KEY:
    print("ERROR: GEMINI_API_KEY environment variable not set. AI features will fail.")
    # Depending on your needs, you might want to exit or disable AI features
    # exit("Gemini API Key required.")
    gemini_model = None # Flag that AI is unavailable
else:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        # Use a potentially more current/valid model name
        gemini_model = genai.GenerativeModel('gemini-1.5-flash-latest')
        # Test connection (optional, but good practice)
        gemini_model.generate_content("Hello", generation_config=genai.types.GenerationConfig(max_output_tokens=5))
        print("Gemini configured successfully.")
    except Exception as e:
        print(f"ERROR: Failed to configure Gemini AI: {e}")
        gemini_model = None # Flag that AI is unavailable

# Database Configuration
try:
    db = mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )
    # Check connection works
    if db.is_connected():
        print("Database connected successfully.")
    # Use dictionary=True for easier data handling
    # Create a new cursor for each request context or manage carefully
except mysql.connector.Error as err:
    print(f"ERROR: Database connection failed: {err}")
    # Exit or handle gracefully depending on application needs
    exit(f"Database connection failed: {err}")

def get_db_cursor():
    """Gets a new database cursor for a request."""
    # Reconnect if connection lost (optional, depends on setup)
    if not db.is_connected():
        db.reconnect()
    return db.cursor(dictionary=True)

# --- Utility Functions ---

def get_category_from_title(title: str) -> str:
    """Uses Gemini AI to determine the category for an expense title."""
    if not gemini_model:
        return "Miscellaneous" # Default if AI is unavailable

    prompt = f"""Analyze the expense title below. Return ONLY the single most appropriate spending category name from this list:
Food, Travel, Shopping, Utilities, Health, Entertainment, Education, Miscellaneous.

Expense Title: '{title}'

Return only the category name, nothing else."""
    try:
        response = gemini_model.generate_content(prompt)
        category = response.text.strip()
        # Basic validation if the returned category is in our list
        valid_categories = {"Food", "Travel", "Shopping", "Utilities", "Health", "Entertainment", "Education", "Miscellaneous"}
        if category in valid_categories:
            return category
        else:
            print(f"Warning: AI returned unexpected category '{category}'. Defaulting to Miscellaneous.")
            return "Miscellaneous"
    except (google_exceptions.GoogleAPIError, Exception) as e:
        print(f"ERROR: Gemini category generation failed: {e}")
        flash("Could not determine category automatically.", "warning")
        return "Miscellaneous" # Default category on error

def generate_insights() -> list:
    """Generates spending insights using Gemini AI based on recent expenses."""
    if not gemini_model:
        return [] # Return empty list if AI is unavailable

    cursor = get_db_cursor()
    try:
        cursor.execute("SELECT title, amount, category FROM expenses ORDER BY date_added DESC LIMIT 15")
        expense_list = cursor.fetchall()
        cursor.close()

        if not expense_list:
            return ["No expense data available to generate insights."]

        prompt = f"""
You are a friendly personal finance assistant analyzing these recent household spending entries: {expense_list}

Please provide exactly **3 brief, actionable bullet points** based *only* on the data provided:
1. One specific, data-driven suggestion on where the user might be able to reduce expenses.
2. One observation about the user's spending patterns or frequency in certain categories.
3. One practical budgeting or savings tip relevant to the observed spending.

Keep each point concise (under 25 words). Be encouraging and avoid generic advice.
Format the output as a numbered list (1., 2., 3.). Return ONLY the 3 numbered points, no introduction or conclusion.
Example:
1. Consider reducing dining out slightly, as Food is a significant category recently.
2. You seem to shop frequently online; maybe consolidate orders to save on shipping.
3. Try setting aside 5% of your next paycheck towards your savings goal.
"""
        response = gemini_model.generate_content(prompt)
        insights_text = response.text.strip()

        # Parse numbered points robustly
        insight_points = []
        for line in insights_text.split('\n'):
            line = line.strip()
            # Check if line starts with number + dot (e.g., "1.", "2.")
            if line and len(line) > 2 and line[0].isdigit() and line[1] == '.':
                point = line[2:].strip() # Get text after "N."
                if point: # Ensure there's actual text
                    insight_points.append(point)

        if len(insight_points) != 3:
             print(f"Warning: AI returned {len(insight_points)} insights instead of 3. Raw text: {insights_text}")
             # Optionally return raw text or a generic message if parsing fails
             # return ["Could not parse AI insights correctly."]

        return insight_points

    except (mysql.connector.Error, google_exceptions.GoogleAPIError, Exception) as e:
        print(f"ERROR: Failed to generate insights: {e}")
        if cursor: cursor.close()
        return ["Could not generate insights at this time."] # Return error message list

def get_dashboard_data() -> dict:
    """Fetches all necessary data for the dashboard template."""
    cursor = get_db_cursor()
    data = {
        "budget": 0.0,
        "total_spent": 0.0,
        "expenses": [],
        "over_budget": False
    }
    try:
        # Get total spent
        cursor.execute("SELECT SUM(amount) as total FROM expenses")
        total_spent_row = cursor.fetchone()
        if total_spent_row and total_spent_row.get('total') is not None:
            data['total_spent'] = float(total_spent_row['total'])

        # Get recent expenses
        cursor.execute("SELECT title, amount, category, DATE_FORMAT(date_added, '%Y-%m-%d %H:%i') as formatted_date FROM expenses ORDER BY date_added DESC LIMIT 10")
        data['expenses'] = cursor.fetchall()

        # Get current budget (assuming one budget entry per month/period is managed elsewhere or latest is fine)
        cursor.execute("SELECT amount FROM budget ORDER BY id DESC LIMIT 1") # Or filter by current month_year if needed
        budget_row = cursor.fetchone()
        if budget_row and budget_row.get('amount') is not None:
            data['budget'] = float(budget_row['amount'])

        # Calculate over_budget status
        if data['budget'] > 0:
            data['over_budget'] = data['total_spent'] > data['budget']

        cursor.close()
        return data

    except mysql.connector.Error as err:
        print(f"ERROR: Database error fetching dashboard data: {err}")
        flash("Error fetching dashboard data from database.", "error")
        if cursor: cursor.close()
        # Return default data structure on error
        return data
    except Exception as e:
        print(f"ERROR: Unexpected error fetching dashboard data: {e}")
        flash("An unexpected error occurred while fetching dashboard data.", "error")
        if cursor: cursor.close()
        return data


# --- PDF Generation Class ---
class PDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 14)
        self.cell(0, 10, "Monthly Spending Report", ln=True, align="C")
        self.ln(5) # Add a little space after header

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}", 0, 0, "C")

def generate_pdf_report() -> str:
    """Generates a PDF report of the current month's expenses."""
    cursor = get_db_cursor()
    try:
        month_year = datetime.now().strftime("%Y-%m")
        # Fetch expenses for the current month
        cursor.execute("""
            SELECT title, amount, category, DATE_FORMAT(date_added, '%Y-%m-%d') as formatted_date
            FROM expenses
            WHERE DATE_FORMAT(date_added, '%Y-%m') = %s
            ORDER BY date_added ASC
        """, (month_year,))
        expenses = cursor.fetchall()

        # Fetch total for the current month - USE ALIAS
        cursor.execute("""
            SELECT SUM(amount) as monthly_total
            FROM expenses
            WHERE DATE_FORMAT(date_added, '%Y-%m') = %s
        """, (month_year,))
        total_row = cursor.fetchone()
        total = total_row.get('monthly_total') if total_row and total_row.get('monthly_total') is not None else 0.0
        cursor.close()

        pdf = PDF(orientation="P", unit="mm", format="A4")
        pdf.add_page()
        pdf.set_font("Helvetica", size=11)

        # Add table header
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(80, 10, "Title", border=1)
        pdf.cell(40, 10, "Category", border=1)
        pdf.cell(30, 10, "Date", border=1)
        pdf.cell(30, 10, "Amount (INR)", border=1, ln=True, align="R")
        pdf.set_font("Helvetica", size=11)

        # Add table rows
        for e in expenses:
            # Handle potential encoding issues carefully for FPDF core fonts
            title = e.get('title', 'N/A').encode('latin-1', 'replace').decode('latin-1')
            category = e.get('category', 'N/A').encode('latin-1', 'replace').decode('latin-1')
            date_str = e.get('formatted_date', 'N/A')
            amount_str = f"{e.get('amount', 0.0):.2f}" # Format amount

            pdf.cell(80, 10, title, border=1)
            pdf.cell(40, 10, category, border=1)
            pdf.cell(30, 10, date_str, border=1)
            pdf.cell(30, 10, amount_str, border=1, ln=True, align="R")

        pdf.ln(10) # Add space before total

        # Add total
        pdf.set_font("Helvetica", "B", 12)
        total_line = f"Total Spending for {datetime.now().strftime('%B %Y')}: INR {total:.2f}"
        pdf.cell(0, 10, total_line.encode('latin-1', 'replace').decode('latin-1'), ln=True, align="R")

        # Use OS-independent path joining (safer)
        report_dir = os.path.join(app.root_path, 'reports') # Store in a 'reports' subdir
        os.makedirs(report_dir, exist_ok=True) # Create dir if it doesn't exist
        filename = os.path.join(report_dir, f"Spending_Report_{month_year}.pdf")

        pdf.output(filename)
        return filename

    except (mysql.connector.Error, Exception) as e:
        print(f"ERROR: Failed to generate PDF report: {e}")
        if cursor: cursor.close()
        return None # Return None indicates failure


# --- Routes ---

@app.route('/')
def dashboard():
    """Displays the main dashboard with expenses, budget, and insights."""
    dashboard_info = get_dashboard_data()
    # Generate insights only if AI is available
    insights_list = generate_insights() if gemini_model else ["AI Insights currently unavailable."]

    return render_template('index.html', **dashboard_info, insights=insights_list)

@app.route('/add', methods=['GET', 'POST'])
def add_expense():
    """Handles adding a new expense (displays form on GET, processes on POST)."""
    if request.method == 'POST':
        title = request.form.get('title')
        amount_str = request.form.get('amount')

        # Basic validation
        if not title or not amount_str:
            flash("Title and amount are required.", "error")
            return render_template('add.html') # Show form again

        try:
            amount = float(amount_str)
            if amount <= 0:
                 flash("Amount must be positive.", "error")
                 return render_template('add.html')

            # Get category using AI (or default)
            category = get_category_from_title(title)

            # Insert into database
            cursor = get_db_cursor()
            sql = "INSERT INTO expenses (title, amount, category, date_added) VALUES (%s, %s, %s, %s)"
            val = (title, amount, category, datetime.now())
            cursor.execute(sql, val)
            db.commit() # Commit the transaction
            cursor.close()

            flash(f"Expense '{title}' added! Category assigned: {category}", "success")
            return redirect(url_for('dashboard'))

        except ValueError:
             flash("Invalid amount entered. Please use numbers.", "error")
             return render_template('add.html')
        except mysql.connector.Error as err:
             print(f"ERROR: Database error adding expense: {err}")
             flash("Database error adding expense. Please try again.", "error")
             db.rollback() # Rollback on error
             if cursor: cursor.close()
             return render_template('add.html') # Show form again
        except Exception as e:
            print(f"ERROR: Unexpected error adding expense: {e}")
            flash("An unexpected error occurred while adding the expense.", "error")
            db.rollback() # Rollback on error
            if cursor: cursor.close()
            return render_template('add.html') # Show form again

    # For GET request:
    return render_template('add.html')

@app.route('/set_budget', methods=['POST'])
def set_budget():
    """Sets or updates the monthly budget."""
    budget_str = request.form.get('budget')
    if not budget_str:
        flash("Budget amount is required.", "error")
        return redirect(url_for('dashboard'))

    try:
        budget = float(budget_str)
        if budget < 0:
             flash("Budget cannot be negative.", "error")
             return redirect(url_for('dashboard'))

        month_year = datetime.now().strftime("%Y-%m") # Or use a specific logic for budget period
        cursor = get_db_cursor()
        # Using REPLACE assumes 'month_year' is a unique key or primary key for budget periods
        # Adjust schema/query if you need multiple budget entries per month or different logic
        sql = "REPLACE INTO budget (month_year, amount) VALUES (%s, %s)"
        val = (month_year, budget)
        cursor.execute(sql, val)
        db.commit()
        cursor.close()
        flash(f"Monthly budget set to INR {budget:.2f}!", "success")

    except ValueError:
        flash("Invalid budget amount entered. Please use numbers.", "error")
    except mysql.connector.Error as err:
        print(f"ERROR: Database error setting budget: {err}")
        flash("Database error setting budget. Please try again.", "error")
        db.rollback()
        if cursor: cursor.close()
    except Exception as e:
        print(f"ERROR: Unexpected error setting budget: {e}")
        flash("An unexpected error occurred while setting the budget.", "error")
        db.rollback()
        if cursor: cursor.close()

    return redirect(url_for('dashboard'))

@app.route('/download_report')
def download_report():
    """Generates and serves the monthly expense report PDF."""
    try:
        filename = generate_pdf_report()
        if filename and os.path.exists(filename):
             # send_file needs the absolute path
            return send_file(filename, as_attachment=True)
        else:
            flash("Could not generate the PDF report.", "error")
            return redirect(url_for('dashboard'))
    except Exception as e:
        print(f"ERROR: Failed to send PDF report: {e}")
        flash("An error occurred while preparing the download.", "error")
        return redirect(url_for('dashboard'))

# --- Main Execution ---
if __name__ == '__main__':
    print("Starting Flask application...")
    print("Ensure environment variables FLASK_SECRET_KEY and GEMINI_API_KEY are set.")
    print("Database connection details can also be set via DB_HOST, DB_USER, DB_PASSWORD, DB_NAME env vars.")
    # Consider host='0.0.0.0' to make accessible on network if needed
    app.run(debug=True, host='127.0.0.1', port=5000)