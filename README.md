# 💸 Smart Expense Splitter

A full-stack web application to manage group expenses and split bills efficiently among multiple users.

---

## 🚀 Live Demo
👉 https://smart-expense-splitter-dsjo.onrender.com

---

## 📌 Features
- Add and manage group expenses  
- Automatic balance calculation  
- Fair settlement between participants  
- Real-time updates  
- Edit & delete users and expenses  

---

## 🛠️ Tech Stack
- Backend: Python (Flask)  
- Database: SQLite  
- Frontend: HTML, CSS, JavaScript  
- Deployment: Render  
- Tools: Docker, Git  

---

## 📂 Project Structure
backend/
│── app.py
│── calculations.py
│── database.py
│── expenses.db
│── templates/
│ └── index.html
│── static/
│ └── (CSS/JS files)


---

## ⚙️ Setup Instructions

### 1. Clone the repository
git clone https://github.com/DevashreeA/smart-expense-splitter

cd smart-expense-splitter


### 2. Create virtual environment
python -m venv venv
venv\Scripts\activate


### 3. Install dependencies
pip install -r requirements.txt


### 4. Run the application
python backend/app.py


---

## 🔗 API Endpoints

- GET /users → Get all users  
- POST /users → Add user  
- GET /expenses → Get all expenses  
- POST /expenses → Add expense  
- PUT /expenses/<id> → Update expense  
- DELETE /expenses/<id> → Delete expense  
- GET /summary → View balances  
- GET /settle → Simplify debts  

---

## 🎯 Future Improvements
- User authentication (login/signup)  
- Improved UI/UX  
- Cloud database (PostgreSQL)  
- Mobile responsiveness  

---

## 👩‍💻 Author
**Devashree Agnihotri**  
GitHub: https://github.com/DevashreeA  
LinkedIn: https://www.linkedin.com/in/devashree14/

---

## ⭐ If you like this project
Give it a star ⭐ on GitHub!
