import google.generativeai as genai
from fpdf import FPDF
from datetime import datetime
import mysql.connector
from datetime import datetime
from tabulate import tabulate

genai.configure(api_key="Enter Key here")
global model 
model = genai.GenerativeModel('gemini-2.0-flash')
def get_category_from_title(title: str) -> str:
    prompt = f"Based on the title below, return only the most appropriate spending category from the following options: Food, Travel, Shopping, Utilities, Health, Entertainment, Education, Miscellaneous.\n\nTitle: '{title}'\n\nOnly return the category name."    
    response = model.generate_content(prompt)
    return response.text.strip()

class PDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 14)
        self.cell(0, 10, "Monthly Spending Report", ln=True, align="C")

def generate_pdf(expenses, total, month_year):
    pdf = PDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)

    for e in expenses:
        line = f"{e[1]} - ₹{e[2]} ({e[3]})"
        pdf.cell(0, 10, line.encode('latin-1', 'replace').decode('latin-1'), ln=True)

    pdf.ln()
    total_line = f"Total Spending: ₹{total}"
    pdf.cell(0, 10, total_line.encode('latin-1', 'replace').decode('latin-1'), ln=True)
    pdf.output(f"Spending_Report_{month_year}.pdf")


def generate_insights(expense_list):
    
    prompt = f"""
You are analyzing monthly personal expenses for a domestic user. The data is not from a business or organization.

Here is the list of spending entries: {expense_list}

Please provide the following in a polite and practical manner:
1. Areas where the user could consider reducing spending.
2. A short, clear analysis of their overall spending behavior.
3. Friendly, AI-generated suggestions for better budgeting and saving in daily life.

Keep the tone warm, simple, and easy to understand — suitable for personal or household budgeting.
"""
    response = model.generate_content(prompt)
    return response.text.strip()

# DB Connect
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="1234",
    database="payment_tracker"
)
cursor = db.cursor()

def set_budget():
    month_year = datetime.now().strftime("%Y-%m")
    amount = float(input("Enter monthly budget: ₹"))
    cursor.execute("REPLACE INTO budget (month_year, amount) VALUES (%s, %s)", (month_year, amount))
    db.commit()
    print("✅ Budget set successfully.\n")

def add_expense():
    title = input("Enter payment title: ")
    amount = float(input("Enter payment amount: ₹"))
    category = get_category_from_title(title)
    print(f"🧠 AI-detected category: {category}")

    cursor.execute("INSERT INTO expenses (title, amount, category) VALUES (%s, %s, %s)", (title, amount, category))
    db.commit()
    print("✅ Expense added.\n")

def check_budget():
    month_year = datetime.now().strftime("%Y-%m")
    cursor.execute("SELECT SUM(amount) FROM expenses WHERE DATE_FORMAT(date_added, '%Y-%m') = %s", (month_year,))
    total = cursor.fetchone()[0] or 0

    cursor.execute("SELECT amount FROM budget WHERE month_year = %s", (month_year,))
    result = cursor.fetchone()
    budget = result[0] if result else 0

    print(f"📊 Total Spending: ₹{total} / Budget: ₹{budget}")
    if total > budget:
        print("❗ Warning: You have exceeded your monthly budget!\n")
    else:
        print(" You are within your budget.\n")

def download_report():
    month_year = datetime.now().strftime("%Y-%m")
    cursor.execute("SELECT * FROM expenses WHERE DATE_FORMAT(date_added, '%Y-%m') = %s", (month_year,))
    data = cursor.fetchall()
    cursor.execute("SELECT SUM(amount) FROM expenses WHERE DATE_FORMAT(date_added, '%Y-%m') = %s", (month_year,))
    total = cursor.fetchone()[0] or 0

    generate_pdf(data, total, month_year)
    print(f"📄 Report saved as Spending_Report_{month_year}.pdf\n")

def ai_insights():
    cursor.execute("SELECT title, amount, category FROM expenses ORDER BY date_added DESC LIMIT 15")
    data = cursor.fetchall()
    insights = generate_insights(data)
    print("📌 AI Insights:\n")
    print(insights)
    print()

def main_menu():
    while True:
        print("=== 💰 Payment Tracker ===")
        print("1. Set Monthly Budget")
        print("2. Add Payment")
        print("3. Check Budget Status")
        print("4. Download Monthly Report (PDF)")
        print("5. AI Insights")
        print("6. Exit")
        choice = input("Select an option (1–6): ")

        if choice == '1':
            set_budget()
        elif choice == '2':
            add_expense()
        elif choice == '3':
            check_budget()
        elif choice == '4':
            download_report()
        elif choice == '5':
            ai_insights()
        elif choice == '6':
            print("Exiting...")
            break
        else:
            print("Invalid choice. Try again.\n")

if __name__ == "__main__":
    main_menu()