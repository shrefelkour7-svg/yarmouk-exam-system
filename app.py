from datetime import datetime, timedelta
import os  # مكتبة للتعامل مع متغيرات البيئة في السيرفر والسحابة
from flask import Flask, jsonify, redirect, render_template, request, url_for
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# --- إعدادات قاعدة البيانات الذكية (تدعم المحلي والسحابي) ---
database_url = os.environ.get('DATABASE_URL')

if database_url:
  # إذا وجدنا رابط سحابي قادم من الاستضافة، نستخدمه
  # مع معالجة بسيطة لتوافق البادئة مع SQLAlchemy
  if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)
  app.config['SQLALCHEMY_DATABASE_URI'] = database_url
else:
  # إذا لم نكن على السحابة (أي نعمل محلياً على جهازك)، نستخدم الإعداد المحلي
  app.config['SQLALCHEMY_DATABASE_URI'] = (
      'postgresql+psycopg2://postgres:123456@localhost/exam_db'
  )

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


# --- 1. جداول قاعدة البيانات ---
class Student(db.Model):
  __tablename__ = 'students'
  id = db.Column(db.Integer, primary_key=True)
  full_name = db.Column(db.String(100), nullable=False)
  class_section = db.Column(db.String(50), nullable=False)

  results = db.relationship(
      'Result', backref='student', lazy=True, cascade='all, delete-orphan'
  )


class Result(db.Model):
  __tablename__ = 'results'
  id = db.Column(db.Integer, primary_key=True)
  student_id = db.Column(
      db.Integer, db.ForeignKey('students.id'), nullable=False
  )
  exam_title = db.Column(db.String(150), nullable=False)
  score = db.Column(db.Float, nullable=False)
  max_score = db.Column(db.Float, nullable=False)
  exam_date = db.Column(db.String(50), nullable=False)


with app.app_context():
  db.create_all()
# --- 2. الصفحة الرئيسية (الفهرس المركزي / لوحة التحكم) ---
@app.route('/')
def dashboard():
    # 1. عداد إجمالي الطلاب كما كان لديك
    total_students = Student.query.count()
    students_list = Student.query.all()
    
    # 2. جلب الفصول الموجودة في قاعدة البيانات تلقائياً
    raw_sections = db.session.query(Student.class_section.distinct()).all()
    existing_sections = [s[0] for s in raw_sections if s[0]]
    
    # 3. الترتيب المدرسي النموذجي للفصول
    school_order = {
        'تاسع أول': 1,
        'تاسع ثان': 2,
        'تاسع ثالث': 3,
        'تاسع رابع': 4,
        'تاسع خامس': 5,
        'تاسع سادس': 6
    }
    
    # فرز الفصول حسب الترتيب المدرسي (وأي فصل جديد يوضع في النهاية تلقائياً)
    sections_list = sorted(existing_sections, key=lambda x: school_order.get(x, 99))
    
    return render_template(
        'dashboard.html',
        total_students=total_students,
        students=students_list,
        sections=sections_list,
    )
# --- 3. لوحة إدارة الطلبة ---
@app.route('/admin/students', methods=['GET', 'POST'])
def manage_students():
  selected_student = None
  is_search_mode = False

  if request.method == 'POST':
    action = request.form.get('action')
    student_id = request.form.get('student_id')
    name = request.form.get('full_name')
    section = request.form.get('class_section')

    if action == 'search':
      if student_id:
        selected_student = Student.query.get(student_id)
        if selected_student:
          is_search_mode = True
    elif action == 'add':
      if name and section:
        new_student = Student(full_name=name, class_section=section)
        db.session.add(new_student)
        db.session.commit()
      return redirect(url_for('manage_students'))
    elif action == 'update':
      if student_id:
        student = Student.query.get(student_id)
        if student:
          student.full_name = name
          student.class_section = section
          db.session.commit()
      return redirect(url_for('manage_students'))
    elif action == 'delete':
      if student_id:
        student = Student.query.get(student_id)
        if student:
          db.session.delete(student)
          db.session.commit()
      return redirect(url_for('manage_students'))

    students_list = Student.query.all()
  return render_template(
      'admin_students.html',
      students=Student.query.all(),
      student=selected_student,
      is_search_mode=is_search_mode,
  )


# --- 4. المسار الذكي لتوجيه روابط الاختبارات مع فحص الـ 7 أيام مسبقاً ---
@app.route('/exam/<exam_type>/<exam_name>')
def render_exam(exam_type, exam_name):
  student_id = request.args.get('student_id')

  # تنظيم وربط عناوين الاختبارات (تدعم الإنجليزية والعربية لضمان عدم الخطأ)
  # تنظيم وربط عناوين الاختبارات (يدعم الاختصارات والأسماء الكاملة والعربية)
  # تنظيم وربط عناوين الاختبارات (يدعم الاختصارات، الأسماء الكاملة، والعربية)
  exam_titles_map = {
      'problem_steps': 'خطوات حل المشكلة',
      'steps': 'خطوات حل المشكلة',
      'خطوات حل المشكلة': 'خطوات حل المشكلة',
      
      'algo_concept': 'مفهوم الخوارزميات',
      'algorithm_concept': 'مفهوم الخوارزميات',
      'مفهوم الخوارزميات': 'مفهوم الخوارزميات',
      
      'algo_create': 'إنشاء خوارزمية',
      'create_algorithm': 'إنشاء خوارزمية',
      'إنشاء خوارزمية': 'إنشاء خوارزمية',
      
      'flow_concept': 'مفهوم المخططات الانسيابية',
      'flowchart_concept': 'مفهوم المخططات الانسيابية',
      'مفهوم المخططات الانسيابية': 'مفهوم المخططات الانسيابية',
      
      'flow_create': 'إنشاء مخططات انسيابية',
      'create_flowchart': 'إنشاء مخططات انسيابية',
      'إنشاء مخططات انسيابية': 'إنشاء مخططات انسيابية',
      
      'flow_errors': 'اكتشاف الأخطاء',
      'flowchart_errors': 'اكتشاف الأخطاء',
      'errors': 'اكتشاف الأخطاء',
      'اكتشاف الأخطاء': 'اكتشاف الأخطاء',
      
      'algo_creation': 'إنشاء خوارزمية وتصميم مخططات',
      'algorithm_creation': 'إنشاء خوارزمية وتصميم مخططات',
      'algorithm': 'إنشاء خوارزمية وتصميم مخططات',
      'إنشاء خوارزمية وتصميم مخططات': 'إنشاء خوارزمية وتصميم مخططات',
  }

  # تنظيم وربط قوالب الصفحات HTML (تدعم كافة الاختصارات والأسماء)
  # تنظيم وربط عناوين الاختبارات (شامل كافة الاختصارات والمسارات)
  exam_titles_map = {
      'problem_steps': 'خطوات حل المشكلة',
      'steps': 'خطوات حل المشكلة',
      'خطوات حل المشكلة': 'خطوات حل المشكلة',
      
      'algo_concept': 'مفهوم الخوارزميات',
      'algorithm_concept': 'مفهوم الخوارزميات',
      'مفهوم الخوارزميات': 'مفهوم الخوارزميات',
      
      'algo_create': 'إنشاء خوارزمية',
      'create_algorithm': 'إنشاء خوارزمية',
      'إنشاء خوارزمية': 'إنشاء خوارزمية',
      
      'flow_concept': 'مفهوم المخططات الانسيابية',
      'flowchart_concept': 'مفهوم المخططات الانسيابية',
      'مفهوم المخططات الانسيابية': 'مفهوم المخططات الانسيابية',
      
      'flow_create': 'إنشاء مخططات انسيابية',
      'create_flowchart': 'إنشاء مخططات انسيابية',
      'إنشاء مخططات انسيابية': 'إنشاء مخططات انسيابية',
      
      'flow_errors': 'اكتشاف الأخطاء',
      'flowchart_errors': 'اكتشاف الأخطاء',
      'errors': 'اكتشاف الأخطاء',
      'اكتشاف الأخطاء': 'اكتشاف الأخطاء',
      
      'algo_creation': 'إنشاء خوارزمية وتصميم مخططات',
      'algorithm_creation': 'إنشاء خوارزمية وتصميم مخططات',
      'algorithms_track': 'إنشاء خوارزمية وتصميم مخططات',
      'algorithm': 'إنشاء خوارزمية وتصميم مخططات',
      'إنشاء خوارزمية وتصميم مخططات': 'إنشاء خوارزمية وتصميم مخططات',
  }

  # تنظيم وربط قوالب الصفحات HTML
 # القاموس الموحد والمثبت لاختبارات المنظومة (شامل اختبارات التفاعل والمهارة العملية)
  exam_titles_map = {
      'problem_steps': 'خطوات حل المشكلة',
      'steps': 'خطوات حل المشكلة',
      'خطوات حل المشكلة': 'خطوات حل المشكلة',
      
      'algo_concept': 'مفهوم الخوارزميات',
      'algorithm_concept': 'مفهوم الخوارزميات',
      'مفهوم الخوارزميات': 'مفهوم الخوارزميات',
      
      'algo_create': 'إنشاء خوارزمية',
      'create_algorithm': 'إنشاء خوارزمية',
      'إنشاء خوارزمية': 'إنشاء خوارزمية',
      
      'flow_concept': 'مفهوم المخططات الانسيابية',
      'flowchart_concept': 'مفهوم المخططات الانسيابية',
      'مفهوم المخططات الانسيابية': 'مفهوم المخططات الانسيابية',
      
      'flow_create': 'إنشاء مخططات انسيابية',
      'create_flowchart': 'إنشاء مخططات انسيابية',
      'إنشاء مخططات انسيابية': 'إنشاء مخططات انسيابية',
      
      'flow_errors': 'اكتشاف الأخطاء',
      'flowchart_errors': 'اكتشاف الأخطاء',
      'errors': 'اكتشاف الأخطاء',
      'اكتشاف الأخطاء': 'اكتشاف الأخطاء',
      
      'sort_algorithms': 'ترتيب الخوارزميات',
      'arrange_algorithms': 'ترتيب الخوارزميات',
      'ترتيب الخوارزميات': 'ترتيب الخوارزميات',
      
      'algo_creation': 'تتبع تنفيذ الخوارزميات',
      'algorithm_creation': 'تتبع تنفيذ الخوارزميات',
      'algorithms_track': 'تتبع تنفيذ الخوارزميات',
      'algorithm': 'تتبع تنفيذ الخوارزميات',
      'تتبع تنفيذ الخوارزميات': 'تتبع تنفيذ الخوارزميات',
  }

  exam_templates = {
      'problem_steps': 'steps_to_solve.html',
      'steps': 'steps_to_solve.html',
      'خطوات حل المشكلة': 'steps_to_solve.html',
      
      'algo_concept': 'algorithm_concept.html',
      'algorithm_concept': 'algorithm_concept.html',
      'مفهوم الخوارزميات': 'algorithm_concept.html',
      
      'algo_create': 'create_algorithm.html',
      'create_algorithm': 'create_algorithm.html',
      'إنشاء خوارزمية': 'create_algorithm.html',
      
      'flow_concept': 'flowchart_concept.html',
      'flowchart_concept': 'flowchart_concept.html',
      'مفهوم المخططات الانسيابية': 'flowchart_concept.html',
      
      'flow_create': 'create_flowchart.html',
      'create_flowchart': 'create_flowchart.html',
      'إنشاء مخططات انسيابية': 'create_flowchart.html',
      
      'flow_errors': 'flowchart_errors.html',
      'flowchart_errors': 'flowchart_errors.html',
      'errors': 'flowchart_errors.html',
      'اكتشاف الأخطاء': 'flowchart_errors.html',
      
      'algorithms_drag': 'sort_algorithms.html',
      'sort_algorithms': 'sort_algorithms.html',
      'arrange_algorithms': 'sort_algorithms.html',
      'ترتيب الخوارزميات': 'sort_algorithms.html',
      
      'algo_creation': 'algorithm_creation.html',
      'algorithm_creation': 'algorithm_creation.html',
      'algorithms_track': 'algorithm_creation.html',
      'algorithm': 'algorithm_creation.html',
      'تتبع تنفيذ الخوارزميات': 'algorithm_creation.html',
  }
  exam_title = exam_titles_map.get(exam_name, 'اختبار برمجي')
  template_file = exam_templates.get(exam_name, 'steps_to_solve.html')

  # فحص شرط الـ 7 أيام قبل السماح بدخول الاختبار
  if student_id:
    student = Student.query.get(student_id)
    if student:
      last_result = (
          Result.query.filter_by(student_id=student.id, exam_title=exam_title)
          .order_by(Result.id.desc())
          .first()
      )
      if last_result:
        last_date = datetime.strptime(last_result.exam_date, '%Y-%m-%d %H:%M')
        target_date = last_date + timedelta(days=7)
        time_difference = target_date - datetime.now()

        if time_difference.total_seconds() > 0:
          days_left = time_difference.days
          hours_left = int(time_difference.seconds / 3600)

          time_msg = f'{days_left} أيام' if days_left > 0 else 'أقل من يوم'
          if days_left > 0 and hours_left > 0:
            time_msg = f'{days_left} يوم و {hours_left} ساعة'

          return render_template(
              'restricted_access.html',
              student_name=student.full_name,
              exam_title=exam_title,
              exam_date=last_result.exam_date,
              time_msg=time_msg,
          )

  return render_template(template_file)


# --- 5. مسارات داعمة إضافية ---
@app.route('/exam/steps')
def steps_to_solve():
  return render_template('steps_to_solve.html')


@app.route('/exam/errors')
def flowchart_errors():
  return render_template('flowchart_errors.html')


@app.route('/exam/algorithm')
def algorithm_creation():
  return render_template('algorithm_creation.html')


# --- 6. واجهة API لرصد وتخزين الدرجات مع فحص الـ 7 أيام ---
@app.route('/api/save_score', methods=['POST'])
def save_score():
    data = request.get_json()
    student_id = data.get('student_id')
    exam_title = data.get('exam_title')
    score = data.get('score')
    max_score = data.get('max_score')

    if not student_id:
        return jsonify({'status': 'error', 'message': 'يرجى اختيار اسم الطالب!'}), 400

    student = Student.query.get(student_id)
    if not student:
        return jsonify({'status': 'error', 'message': 'رقم الطالب غير مسجل في النظام!'}), 404

    # 1. التحقق عما إذا كان هذا الطلب مجرد فحص مسبق (درجة سالبة)
    is_check_only = score is not None and score < 0

    last_result = (
        Result.query.filter_by(student_id=student.id, exam_title=exam_title)
        .order_by(Result.id.desc())
        .first()
    )

    if last_result:
        last_date = datetime.strptime(last_result.exam_date, '%Y-%m-%d %H:%M')
        target_date = last_date + timedelta(days=7)
        time_difference = target_date - datetime.now()

        if time_difference.total_seconds() > 0:
            days_left = time_difference.days
            hours_left = int(time_difference.seconds / 3600)
            time_msg = f'{days_left} أيام' if days_left > 0 else 'أقل من يوم'
            if days_left > 0 and hours_left > 0:
                time_msg = f'{days_left} يوم و {hours_left} ساعة'

            return jsonify({
                'status': 'error',
                'message': (
                    f'عذراً، لقد اجتزت هذا الاختبار مسبقاً بتاريخ ({last_result.exam_date}). '
                    f'المتبقي لك لتستطيع الدخول مجدداً هو: {time_msg}.'
                ),
            }), 400

    # 2. إذا كان الطلب عبارة عن فحص فقط (قيمة سالبة)، نتوقف هنا ولا نحفظ شيئاً في القاعدة
    if is_check_only:
        return jsonify({'status': 'success', 'message': 'مسموح بالدخول للاختبار'})

    # 3. حفظ الدرجة الحقيقية للطالب (عند إنهاء الاختبار الفعلي)
    new_result = Result(
        student_id=student.id,
        exam_title=exam_title,
        score=score,
        max_score=max_score,
        exam_date=datetime.now().strftime('%Y-%m-%d %H:%M'),
    )
    db.session.add(new_result)
    db.session.commit()

    return jsonify({
        'status': 'success',
        'message': f'تم رصد درجة الطالب ({student.full_name}) بنجاح: {score}/{max_score}',
    })
# --- مسارات المنظومة لديك (الصفحات أو الـ APIs السابقة) ---
@app.route('/')
def index():
    return render_template('index.html')
# ========================================================
# --- 📌 أضف مسار شاشة رصد التقارير الجديد هنا بالكامل ---
# ========================================================
@app.route('/teacher/reports')
def teacher_reports():
    try:
        students = Student.query.all()
        students_data = []

        unique_sections = set()

        for student in students:
            # تهيئة الدرجات الثمانية بقيم فارغة
            scores = {f'p{i}': None for i in range(1, 9)}
            
            # جلب كل نتائج الطالب من قاعدة البيانات
            student_results = Result.query.filter_by(student_id=student.id).all()
            
            for res in student_results:
                title = str(res.exam_title).strip()
                score_val = res.score
                
                # تخطي القيم الفارغة
                if score_val is None:
                    continue
                
                # إذا كانت الدرجة سالبة (مثل خطأ برمجي سابق)، نعالجها أو نعرضها كقيمة صحيحة حسب الحاجة
                # (يمكنك تعديل هذا الشرط إذا أردت إظهارها أو تصفيرها)
                clean_score = float(score_val)

                # مطابقة دقيقة لكل اختبار بناءً على كلماته الفريدة لضمان عدم التداخل
                if "خطوات" in title or "المشكلة" in title:
                    scores['p1'] = clean_score
                elif "مفهوم" in title and ("خوارزم" in title):
                    scores['p2'] = clean_score
                elif "إنشاء" in title and ("خوارزم" in title):
                    scores['p3'] = clean_score
                elif "مفهوم" in title and ("مخطط" in title or "تدفق" in title):
                    scores['p4'] = clean_score
                elif "إنشاء" in title and ("مخطط" in title or "تدفق" in title):
                    scores['p5'] = clean_score
                elif "ترتيب" in title:
                    scores['p6'] = clean_score
                elif "اكتشاف" in title or "الأخطاء" in title or "أخطاء" in title:
                    scores['p7'] = clean_score
                elif "تتبع" in title or "محاكاة" in title:
                    scores['p8'] = clean_score

            # حساب المجموع الكلي للدرجات المرصودة (مع تجاهل الـ None)
            total_score = sum(val for val in scores.values() if val is not None)

            student_name = getattr(student, 'full_name', 'بدون اسم')
            class_name = getattr(student, 'class_section', 'غير محدد')
            
            if class_name and class_name != 'غير محدد':
                unique_sections.add(class_name)

            students_data.append({
                'id': student.id,
                'name': student_name,
                'class_name': class_name,
                'scores': scores,
                'total': total_score
            })

        return render_template(
            'teacher_reports.html', 
            students_data=students_data, 
            sections=sorted(list(unique_sections))
        )

    except Exception as e:
        print(f"Error loading reports: {e}")
        return f"حدث خطأ أثناء تحميل السجلات: {e}"
@app.route('/save-students-batch', methods=['POST'])
def save_students_batch():
    data = request.get_json()
    class_section = data.get('class_section') # الفصل الرئيسي المختار في الأعلى
    incoming_students = data.get('students', [])  # قائمة الطلاب القادمة من الشبكة التفاعلية
    
    if not class_section:
        return jsonify({'status': 'error', 'message': 'يرجى تحديد الفصل الدراسي أولاً'})
    
    lmsg = []  # قائمة لتخزين التنبيهات
    
    # جلب الطلاب الموجودين حالياً في هذا الفصل من قاعدة البيانات
    existing_students = Student.query.filter_by(class_section=class_section).all()
    existing_dict = {s.id: s for s in existing_students}
    
    incoming_ids = set()
    
    # 2. معالجة (الإضافة)، (التعديل)، و (النقل إلى فصل آخر)
    for item in incoming_students:
        stu_id = item.get('id')
        stu_name = item.get('full_name', '').strip()
        stu_new_section = item.get('class_section', class_section).strip() # الفصل الجديد إن وجد في الصف
        
        # تجاهل الصفوف الفارغة التي لم يُكتب فيها اسم
        if not stu_name:
            continue
            
        if stu_id and str(stu_id).isdigit():
            stu_id = int(stu_id)
            incoming_ids.add(stu_id)
            
            # إذا كان الطالب موجوداً مسبقاً -> تحديث اسمه أو نقله لفصل جديد (UPDATE / MOVE)
            student_obj = Student.query.get(stu_id)
            if student_obj:
                student_obj.full_name = stu_name
                if stu_new_section and stu_new_section != student_obj.class_section:
                    student_obj.class_section = stu_new_section # تنفيذ عملية النقل بأمان تام وحفظ النتائج!
        else:
            # إذا لم يكن له ID -> إضافة طالب جديد (INSERT) بالفصل المختار
            new_student = Student(full_name=stu_name, class_section=class_section)
            db.session.add(new_student)
            
    # 3. معالجة الحذف المشروط (للطلاب الذين تم مسحهم من الشبكة لهذا الفصل)
    for s_id, student_obj in existing_dict.items():
        if s_id not in incoming_ids:
            # فحص ما إذا كان للطالب سجلات درجات مرتبطة في جدول النتائج
            if student_obj.results:  
                lmsg.append(f"تعذر حذف الطالب ({student_obj.full_name}) لوجود سجلات اختبارات سابقة مرتبطة به.")
            else:
                # ليس له درجات -> يُحذف بأمان تام
                db.session.delete(student_obj)
                
    try:
        db.session.commit()
        return jsonify({
            'status': 'success',
            'message': 'تم حفظ التعديلات ونقل الطلاب وتحديث القائمة بنجاح',
            'warnings': lmsg
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': f'حدث خطأ أثناء الحفظ: {str(e)}'
        })
@app.route('/get-students-by-section')
def get_students_by_section():
    section = request.args.get('section', '')
    students = Student.query.filter_by(class_section=section).all()
    
    # تحويل البيانات إلى صيغة مناسبة للشبكة التفاعلية
    students_list = [{'id': s.id, 'full_name': s.full_name} for s in students]
    return jsonify({'students': students_list})
@app.route('/manage-students-page')
def manage_students_page():
    return render_template('manage_students.html')
if __name__ == '__main__':
  app.run(debug=True)