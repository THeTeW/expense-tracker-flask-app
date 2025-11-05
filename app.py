import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask import render_template, request, redirect, url_for, flash
from datetime import datetime

from sqlalchemy import func


# --- 1. ตั้งค่าแอปพลิเคชัน (App Setup) ---
app = Flask(__name__)

# (สำคัญ!) เปลี่ยน YOUR_CONNECTION_STRING เป็นกุญแจจาก Neon
# นี่คือการบอก Flask ว่าฐานข้อมูลของเราอยู่ที่ไหน

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('SQLALCHEMY_DATABASE_URI')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')

# ตั้งค่า Secret Key สำหรับรักษาความปลอดภัยของ Session (จำเป็นสำหรับ Flask-Login)
# ใส่ข้อความอะไรก็ได้ที่คุณคิดขึ้นมาเอง
app.config['SECRET_KEY'] = 'a_very_secret_key_that_no_one_knows'

# --- 2. เริ่มใช้งานเครื่องมือ (Initialize Extensions) ---

# สร้าง "ล่าม" แปล Python เป็น SQL
db = SQLAlchemy(app)

# สร้าง "เครื่องเข้ารหัส" รหัสผ่าน
bcrypt = Bcrypt(app)

# สร้าง "ผู้จัดการการล็อกอิน"
login_manager = LoginManager(app)
# (ยังไม่ต้องทำอะไรต่อ แค่สร้างไว้ก่อน)
# ... หลังบรรทัด login_manager = LoginManager(app) ...

@login_manager.user_loader
def load_user(user_id):
    # Flask-Login จะใช้ฟังก์ชันนี้เพื่อดึงข้อมูลผู้ใช้จาก ID ที่เก็บใน Session
    return User.query.get(int(user_id))

# --- 3. สร้าง "Route" หรือหน้าเว็บแรก (Homepage) ---
# --- 3. สร้าง "โมเดล" (Database Models) ---

########################################################################################
MONTH_NAMES = [
    (1, 'มกราคม'), (2, 'กุมภาพันธ์'), (3, 'มีนาคม'), (4, 'เมษายน'),
    (5, 'พฤษภาคม'), (6, 'มิถุนายน'), (7, 'กรกฎาคม'), (8, 'สิงหาคม'),
    (9, 'กันยายน'), (10, 'ตุลาคม'), (11, 'พฤศจิกายน'), (12, 'ธันวาคม')
]
########################################################################################
########################################################################################

# db.Model คือคลาสพื้นฐานจาก SQLAlchemy
# UserMixin คือคลาสช่วยเหลือจาก Flask-Login
class User(db.Model, UserMixin):
    # บอก SQLAlchemy ว่าคลาสนี้เชื่อมโยงกับตารางชื่อ 'users'
    __tablename__ = 'users'

    # จับคู่ตัวแปรใน Class ให้ตรงกับคอลัมน์ในฐานข้อมูล
    user_id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.Text, nullable=False)

    # ฟังก์ชันที่ Flask-Login ใช้เพื่อหา ID ที่ไม่ซ้ำกัน
    def get_id(self):
        return (self.user_id)

########################################################################################

class Wallet(db.Model):
    __tablename__ = 'wallets'

    wallet_id = db.Column(db.Integer, primary_key=True)
    wallet_name = db.Column(db.String(100), nullable=False)

    # --- นี่คือหัวใจของความสัมพันธ์ ---
    # 1. กำหนด Foreign Key ที่ชี้ไปหาตาราง users
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)

    # 2. (Optional แต่แนะนำ) สร้าง "Back Reference"
    #    เพื่อให้เราเรียก .wallets จากฝั่ง User ได้ (เช่น current_user.wallets)
    user = db.relationship('User', backref='wallets')

########################################################################################

class Transaction(db.Model):
    __tablename__ = 'transactions'

    transaction_id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.Text, nullable=True)  # รายละเอียด
    amount = db.Column(db.Numeric(10, 2), nullable=False)  # จำนวนเงิน
    date = db.Column(db.Date, nullable=False)  # วันที่

    # ประเภท ('income' หรือ 'expense')
    type = db.Column(db.String(10), nullable=False)

    # --- หัวใจของความสัมพันธ์ ---
    # 1. Foreign Key ที่ชี้ไปหาตาราง wallets
    wallet_id = db.Column(db.Integer, db.ForeignKey('wallets.wallet_id'), nullable=False)

    # 2. Back Reference
    wallet = db.relationship('Wallet', backref='transactions')

    # --- (เพิ่มส่วนนี้เข้าไป!) ---
    # Foreign Key ที่ชี้ไปหา categories (จาก create_tables.py)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.category_id'), nullable=True)
    # Back Reference
    category = db.relationship('Category', backref='transactions')
    # --- (จบส่วนที่เพิ่ม) ---

########################################################################################

# (เพิ่ม Class ใหม่นี้เข้าไป)
class Category(db.Model):
    __tablename__ = 'categories'

    category_id = db.Column(db.Integer, primary_key=True)
    category_name = db.Column(db.String(100), nullable=False)
    # ประเภท ('income' หรือ 'expense')
    type = db.Column(db.String(10), nullable=False)

    # Foreign Key ที่ชี้ไปหา users
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)

    # Back Reference
    user = db.relationship('User', backref='categories')

########################################################################################
####################################home####################################################

# --- 4. สร้าง Routes (หน้าเว็บ) ---

# แก้ไขฟังก์ชัน @app.route("/") เดิม
@app.route("/")
def home():
    # ตรวจสอบว่าผู้ใช้ล็อกอินอยู่หรือไม่
    if current_user.is_authenticated:
        # ถ้าล็อกอินแล้ว ให้ส่งไปหน้า Dashboard เลย
        return redirect(url_for('dashboard'))

    # ถ้ายังไม่ล็อกอิน ให้แสดงหน้าต้อนรับ
    return render_template('landing.html')

####################################register#######################################################

# (เพิ่ม Route ใหม่นี้เข้ามา)
@app.route("/register", methods=['GET', 'POST'])
def register():
    # ตรวจสอบว่าเป็นการ "ส่งข้อมูล" (POST) หรือแค่ "เปิดหน้าเว็บ" (GET)
    if request.method == 'POST':
        # 1. ดึงข้อมูลจากฟอร์ม
        username = request.form.get('username')
        password = request.form.get('password')

        # 2. ตรวจสอบว่ามี username นี้ในระบบหรือยัง
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('ชื่อผู้ใช้นี้มีคนใช้แล้ว กรุณาเลือกชื่ออื่น', 'danger')
            return redirect(url_for('register'))

        # 3. เข้ารหัสรหัสผ่าน (Hashing)
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

        # 4. สร้างผู้ใช้ใหม่ (ด้วย Model) และบันทึกลงฐานข้อมูล
        new_user = User(username=username, password_hash=hashed_password)
        db.session.add(new_user)
        db.session.commit()

        flash('ลงทะเบียนสำเร็จ! กรุณาล็อกอิน', 'success')
        return redirect(url_for('login')) # (เดี๋ยวเราจะสร้างหน้า login ต่อไป)

    # 5. ถ้าเป็นการเปิดหน้าเว็บ (GET) ให้แสดงไฟล์ HTML
    return render_template('register.html')

#######################################login#################################################

@app.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # 1. ดึงข้อมูลจากฟอร์ม
        username = request.form.get('username')
        password = request.form.get('password')

        # 2. ค้นหาผู้ใช้ในฐานข้อมูล
        user = User.query.filter_by(username=username).first()

        # 3. ตรวจสอบผู้ใช้และรหัสผ่าน
        # (ตรวจสอบว่า user มีอยู่จริง และ รหัสผ่านที่เข้ารหัสไว้ ตรงกับ รหัสผ่านที่กรอกมา)
        if user and bcrypt.check_password_hash(user.password_hash, password):
            # 4. ล็อกอินผู้ใช้สำเร็จ (Flask-Login จะสร้าง Session)
            login_user(user)
            flash('ล็อกอินสำเร็จ!', 'success')
            return redirect(url_for('dashboard')) # (เดี๋ยวเราจะสร้างหน้า dashboard ต่อไป)
        else:
            flash('ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง', 'danger')
            return redirect(url_for('login'))

    # 5. ถ้าเป็น GET (เปิดหน้าเว็บ) ให้แสดงไฟล์ HTML
    return render_template('login.html')

####################################dashboard########################################################

@app.route("/dashboard")
@login_required
def dashboard():
    # --- 1. (อัปเกรด!) อ่านค่า Filter จาก URL ---
    # ใช้ .get() เพื่อดึงค่า 'date_from' และ 'date_to'
    date_from_str = request.args.get('date_from')
    date_to_str = request.args.get('date_to')
    selected_wallet_id = request.args.get('wallet_id', type=int)

    # --- 2. (อัปเกรด!) ตั้งค่าวันที่เริ่มต้น ---
    today = datetime.now()
    if date_from_str:
        date_from_obj = datetime.strptime(date_from_str, '%Y-%m-%d').date()
    else:
        # ถ้าไม่ได้เลือก ให้เริ่มจากวันแรกของเดือนปัจจุบัน
        date_from_obj = today.replace(day=1).date()

    if date_to_str:
        date_to_obj = datetime.strptime(date_to_str, '%Y-%m-%d').date()
    else:
        # ถ้าไม่ได้เลือก ให้ใช้Tวันปัจจุบัน
        date_to_obj = today.date()

    # --- 3. ดึงข้อมูลพื้นฐาน (เหมือนเดิม) ---
    user_wallets = Wallet.query.filter_by(user_id=current_user.user_id).all()
    wallet_ids = [wallet.wallet_id for wallet in user_wallets]
    categories = Category.query.filter_by(user_id=current_user.user_id).order_by(Category.category_name).all()
    income_categories = [c for c in categories if c.type == 'income']
    expense_categories = [c for c in categories if c.type == 'expense']

    # --- 4. (อัปเกรด!) สร้าง Query ธุรกรรม ---
    query = Transaction.query.filter(Transaction.wallet_id.in_(wallet_ids))
    if selected_wallet_id:
        query = query.filter(Transaction.wallet_id == selected_wallet_id)

    # (ใหม่!) กรองตามช่วงวันที่
    query = query.filter(Transaction.date.between(date_from_obj, date_to_obj))

    all_transactions = query.order_by(Transaction.date.desc()).all()

    # --- 5. คำนวณยอด (เหมือนเดิม) ---
    total_income = sum(float(t.amount) for t in all_transactions if t.type == 'income')
    total_expense = sum(float(t.amount) for t in all_transactions if t.type == 'expense')
    total_balance = total_income - total_expense

    # (โค้ดส่วนคำนวณ wallet_data เหมือนเดิม ไม่ต้องแก้)
    wallet_data = []
    for wallet in user_wallets:
        all_wallet_tx = Transaction.query.filter_by(wallet_id=wallet.wallet_id).all()
        wallet_income = sum(float(t.amount) for t in all_wallet_tx if t.type == 'income')
        wallet_expense = sum(float(t.amount) for t in all_wallet_tx if t.type == 'expense')
        wallet_balance = wallet_income - wallet_expense
        wallet_data.append({
            'id': wallet.wallet_id,
            'name': wallet.wallet_name,
            'balance': wallet_balance
        })

    today_date = datetime.now().strftime('%Y-%m-%d')

    # --- 6. ส่งข้อมูลไป HTML (อัปเกรด!) ---
    return render_template('dashboard.html',
                           wallet_data=wallet_data,
                           transactions=all_transactions,
                           total_balance=total_balance,
                           today_date=today_date,
                           # (ใหม่!) ส่งค่าวันที่ที่เลือกกลับไปให้ฟอร์ม
                           date_from=date_from_obj.strftime('%Y-%m-%d'),
                           date_to=date_to_obj.strftime('%Y-%m-%d'),
                           selected_wallet_id=selected_wallet_id,
                           income_categories=income_categories,
                           expense_categories=expense_categories
                           )

###################################wallet#####################################################

@app.route("/add_wallet", methods=['POST'])
@login_required # ต้องล็อกอินก่อนถึงจะสร้างได้
def add_wallet():
    # 1. ดึงชื่อกระเป๋าจากฟอร์ม
    wallet_name = request.form.get('wallet_name')

    if wallet_name:
        # 2. สร้าง Object ใหม่
        new_wallet = Wallet(wallet_name=wallet_name, user_id=current_user.user_id)

        # 3. บันทึกลงฐานข้อมูล
        db.session.add(new_wallet)
        db.session.commit()
        flash('สร้างกระเป๋าเงินใหม่สำเร็จ!', 'success')

    # 4. กลับไปหน้า Dashboard (ซึ่งจะโหลดข้อมูลใหม่)
    return redirect(url_for('dashboard'))

#################################delete_wallet###################################################

@app.route("/delete_wallet/<int:wallet_id>", methods=['POST'])
@login_required
def delete_wallet(wallet_id):
    # 1. ค้นหากระเป๋า และตรวจสอบว่าเป็นของ User ที่ล็อกอินอยู่
    wallet_to_delete = Wallet.query.filter_by(
        wallet_id=wallet_id,
        user_id=current_user.user_id
    ).first_or_404()  # first_or_404 ปลอดภัยกว่า

    # 2. (สำคัญ!) ฐานข้อมูลของเราตั้งค่า ON DELETE CASCADE
    #    หมายความว่า "ถ้าลบกระเป๋า ให้ลบธุรกรรมทั้งหมดในกระเป๋านี้ด้วย"
    #    SQLAlchemy จะจัดการเรื่องนี้ให้เราอัตโนมัติ

    db.session.delete(wallet_to_delete)
    db.session.commit()

    flash(f'ลบกระเป๋าเงิน "{wallet_to_delete.wallet_name}" เรียบร้อยแล้ว (ธุรกรรมทั้งหมดในกระเป๋านี้ถูกลบด้วย)',
          'success')
    return redirect(url_for('dashboard'))

#################################edit_wallet###################################################

@app.route("/edit_wallet/<int:wallet_id>", methods=['GET', 'POST'])
@login_required
def edit_wallet(wallet_id):
    # 1. ค้นหากระเป๋า และตรวจสอบเจ้าของ
    wallet_to_edit = Wallet.query.filter_by(
        wallet_id=wallet_id,
        user_id=current_user.user_id
    ).first_or_404()

    # 2. ถ้าเป็นการ POST (กดบันทึก)
    if request.method == 'POST':
        new_name = request.form.get('wallet_name')
        if new_name:
            wallet_to_edit.wallet_name = new_name
            db.session.commit()
            flash('อัปเดตชื่อกระเป๋าเงินเรียบร้อยแล้ว', 'success')
            return redirect(url_for('dashboard'))

    # 3. ถ้าเป็นการ GET (เปิดหน้าครั้งแรก)
    #    ให้แสดงหน้า HTML สำหรับแก้ไข
    return render_template('edit_form_template.html',
                           item=wallet_to_edit,
                           title="แก้ไขกระเป๋าเงิน",
                           form_url=url_for('edit_wallet', wallet_id=wallet_id),
                           label="ชื่อกระเป๋าเงินใหม่:",
                           value=wallet_to_edit.wallet_name,
                           name_field="wallet_name")

###################################transaction######################################################

@app.route("/add_transaction", methods=['POST'])
@login_required
def add_transaction():
    # 1. ดึงข้อมูลทั้งหมดจากฟอร์ม
    wallet_id = request.form.get('wallet_id')
    description = request.form.get('description')
    amount = request.form.get('amount')
    date_str = request.form.get('date') # ได้มาเป็น string
    type = request.form.get('type')
    category_id = request.form.get('category_id')  # <-- (เพิ่ม!) บรรทัดที่ 1/2

    # 2. (สำคัญ) ตรวจสอบว่ากระเป๋านี้เป็นของผู้ใช้จริงหรือไม่ (ป้องกันการปลอมแปลง)
    wallet = Wallet.query.filter_by(wallet_id=wallet_id, user_id=current_user.user_id).first()

    # 3. แปลง string วันที่เป็น object date
    date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()

    # (อัปเกรด!) ตรวจสอบ category_id ด้วย
    if wallet and amount and date_obj and type and category_id:
        # 4. สร้าง Object ธุรกรรมใหม่
        new_trans = Transaction(
            description=description,
            amount=amount,
            date=date_obj,
            type=type,
            wallet_id=wallet_id,
            category_id=category_id  # <-- (เพิ่ม!) บรรทัดที่ 2/2
        )
        db.session.add(new_trans)
        db.session.commit()
        flash('บันทึกธุรกรรมสำเร็จ!', 'success')
    else:
        flash('ข้อมูลไม่ถูกต้อง หรือคุณไม่ได้เลือกหมวดหมู่', 'danger')

    return redirect(url_for('dashboard'))


#####################################wallet_detail##########################################

@app.route("/wallet/<int:wallet_id>")
@login_required
def wallet_detail(wallet_id):
    # 1. ตรวจสอบความปลอดภัย: ดึงกระเป๋าที่ ID ตรงกัน "และ" เป็นของ user ที่ล็อกอินอยู่
    wallet = Wallet.query.filter_by(wallet_id=wallet_id, user_id=current_user.user_id).first_or_404()

    # 2. ดึงธุรกรรมเฉพาะของกระเป๋านี้
    transactions = Transaction.query.filter_by(wallet_id=wallet_id).order_by(Transaction.date.desc()).all()

    # 3. คำนวณยอดคงเหลือเฉพาะของกระเป๋านี้
    total_income = sum(float(t.amount) for t in transactions if t.type == 'income')
    total_expense = sum(float(t.amount) for t in transactions if t.type == 'expense')
    balance = total_income - total_expense

    # 4. ส่งข้อมูลไปแสดงผลที่ template ใหม่
    return render_template('wallet_detail.html',
                           wallet=wallet,
                           transactions=transactions,
                           balance=balance)

###############################category################################################

@app.route("/add_category", methods=['POST'])
@login_required
def add_category():
    category_name = request.form.get('category_name')
    category_type = request.form.get('category_type')  # 'income' หรือ 'expense'

    if category_name and category_type:
        new_category = Category(
            category_name=category_name,
            type=category_type,
            user_id=current_user.user_id
        )
        db.session.add(new_category)
        db.session.commit()
        flash('สร้างหมวดหมู่ใหม่สำเร็จ!', 'success')
    else:
        flash('ข้อมูลไม่ครบถ้วน', 'danger')

    return redirect(url_for('dashboard'))


@app.route("/delete_category/<int:category_id>", methods=['POST'])
@login_required
def delete_category(category_id):
    # 1. ค้นหาหมวดหมู่ และตรวจสอบว่าเป็นของ User ที่ล็อกอินอยู่
    cat_to_delete = Category.query.filter_by(
        category_id=category_id,
        user_id=current_user.user_id
    ).first_or_404()

    # 2. (สำคัญ!) ฐานข้อมูลของเราตั้งค่า ON DELETE SET NULL
    #    หมายความว่า "ถ้าลบหมวดหมู่ ให้ตั้งค่า category_id ใน transactions เป็น NULL"
    #    SQLAlchemy จะจัดการเรื่องนี้ให้เราอัตโนมัติ

    db.session.delete(cat_to_delete)
    db.session.commit()

    flash(f'ลบหมวดหมู่ "{cat_to_delete.category_name}" เรียบร้อยแล้ว (ธุรกรรมเก่าจะถูกตั้งเป็น "ไม่มีหมวดหมู่")',
          'success')
    return redirect(url_for('dashboard'))

###############################edit_category################################################

@app.route("/edit_category/<int:category_id>", methods=['GET', 'POST'])
@login_required
def edit_category(category_id):
    # 1. ค้นหาหมวดหมู่ และตรวจสอบเจ้าของ
    cat_to_edit = Category.query.filter_by(
        category_id=category_id,
        user_id=current_user.user_id
    ).first_or_404()

    # 2. ถ้าเป็นการ POST (กดบันทึก)
    if request.method == 'POST':
        new_name = request.form.get('category_name')
        # (เราสามารถเพิ่มการแก้ไข type ได้ แต่ตอนนี้เอาแค่ชื่อก่อน)
        if new_name:
            cat_to_edit.category_name = new_name
            db.session.commit()
            flash('อัปเดตชื่อหมวดหมู่เรียบร้อยแล้ว', 'success')
            return redirect(url_for('dashboard'))

    # 3. ถ้าเป็นการ GET (เปิดหน้าครั้งแรก)
    #    (อัจฉริยะ!) เราใช้ Template อเนกประสงค์เดิมได้เลย!
    return render_template('edit_form_template.html',
                           item=cat_to_edit,
                           title="แก้ไขหมวดหมู่",
                           form_url=url_for('edit_category', category_id=category_id),
                           label="ชื่อหมวดหมู่ใหม่:",
                           value=cat_to_edit.category_name,
                           name_field="category_name")

###############################delete_transaction################################################

@app.route("/delete_transaction/<int:transaction_id>", methods=['POST'])
@login_required
def delete_transaction(transaction_id):
    # 1. ค้นหาธุรกรรมที่ต้องการลบ
    transaction_to_delete = Transaction.query.get(transaction_id)

    if not transaction_to_delete:
        flash('ไม่พบธุรกรรมที่ต้องการลบ', 'danger')
        return redirect(url_for('dashboard'))

    # 2. (สำคัญ!) ตรวจสอบความปลอดภัย
    #    เช็กว่าธุรกรรมนี้ อยู่ในกระเป๋าที่เป็นของผู้ใช้ที่ล็อกอินอยู่หรือไม่
    wallet_owner = Wallet.query.filter_by(
        wallet_id=transaction_to_delete.wallet_id,
        user_id=current_user.user_id
    ).first()

    if wallet_owner:
        # 3. ถ้าเป็นเจ้าของจริง ให้ลบ
        db.session.delete(transaction_to_delete)
        db.session.commit()
        flash('ลบธุรกรรมเรียบร้อยแล้ว', 'success')
    else:
        # 4. ถ้าพยายามลบของคนอื่น
        flash('คุณไม่มีสิทธิ์ลบธุรกรรมนี้', 'danger')

    # 5. กลับไปหน้า Dashboard
    # (เราสามารถทำให้มันฉลาดขึ้นโดยการ redirect กลับไปหน้าที่มาได้ แต่ตอนนี้เอาแบบง่ายก่อน)
    return redirect(url_for('dashboard'))

##########################edit_transaction################################################

@app.route("/edit_transaction/<int:transaction_id>", methods=['GET', 'POST'])
@login_required
def edit_transaction(transaction_id):
    # 1. ค้นหาธุรกรรม
    transaction_to_edit = Transaction.query.get(transaction_id)
    if not transaction_to_edit:
        flash('ไม่พบธุรกรรม', 'danger')
        return redirect(url_for('dashboard'))

    # 2. ตรวจสอบความปลอดภัย (เหมือนตอนลบ)
    wallet_owner = Wallet.query.filter_by(
        wallet_id=transaction_to_edit.wallet_id,
        user_id=current_user.user_id
    ).first()
    if not wallet_owner:
        flash('คุณไม่มีสิทธิ์แก้ไขธุรกรรมนี้', 'danger')
        return redirect(url_for('dashboard'))

    # 3. ดึงข้อมูลสำหรับ Dropdown (กระเป๋า, หมวดหมู่)
    user_wallets = Wallet.query.filter_by(user_id=current_user.user_id).all()
    categories = Category.query.filter_by(user_id=current_user.user_id).all()
    income_categories = [c for c in categories if c.type == 'income']
    expense_categories = [c for c in categories if c.type == 'expense']

    # 4. ถ้าเป็นการ POST (กดบันทึกการแก้ไข)
    if request.method == 'POST':
        # 5. ดึงข้อมูลใหม่จากฟอร์ม
        transaction_to_edit.wallet_id = request.form.get('wallet_id')
        transaction_to_edit.description = request.form.get('description')
        transaction_to_edit.amount = request.form.get('amount')
        transaction_to_edit.date = datetime.strptime(request.form.get('date'), '%Y-%m-%d').date()
        transaction_to_edit.type = request.form.get('type')
        transaction_to_edit.category_id = request.form.get('category_id')

        # 6. บันทึก (Commit) การเปลี่ยนแปลง
        db.session.commit()
        flash('อัปเดตธุรกรรมเรียบร้อยแล้ว', 'success')
        return redirect(url_for('dashboard'))

    # 7. ถ้าเป็นการ GET (เปิดหน้าแก้ไขครั้งแรก)
    #    ให้แสดง HTML พร้อมข้อมูลเก่า
    return render_template('edit_transaction.html',
                           transaction=transaction_to_edit,
                           user_wallets=user_wallets,
                           income_categories=income_categories,
                           expense_categories=expense_categories)

###############################logout################################################

@app.route("/logout")
@login_required
def logout():
    logout_user() # ล้าง Session ของผู้ใช้
    flash('ออกจากระบบเรียบร้อยแล้ว', 'info')
    return redirect(url_for('login'))

###############################################################################

# --- 4. ส่วนสำหรับรันแอป ---
if __name__ == "__main__":
    app.run(debug=True)