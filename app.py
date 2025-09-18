from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from database import (
    init_db, register_user, authenticate_user, get_user_by_id, 
    get_user_tasks, get_user_categories, add_task, update_task_status,
    add_category, get_task_statistics, delete_task, update_task, delete_category
)
import datetime
import re

app = Flask(__name__)
app.secret_key = 'tu_clave_secreta_aqui_cambiar_en_produccion'  # Cambiar en producción

# Inicializar base de datos
init_db()

def validate_email(email):
    """Validar formato de email"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_password(password):
    """Validar que la contraseña tenga al menos 6 caracteres"""
    return len(password) >= 6

@app.route('/favicon.ico')
def favicon():
    """Ruta para evitar errores 404 del favicon"""
    return '', 204  # Respuesta vacía sin error

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('tasks'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username_or_email = request.form['username_or_email'].strip()
        password = request.form['password']
        
        if not username_or_email or not password:
            flash('Por favor completa todos los campos', 'danger')
            return render_template('login.html')
        
        user, message = authenticate_user(username_or_email, password)
        
        if user:
            session['user_id'] = str(user['_id'])
            session['username'] = user['username']
            session['email'] = user['email']
            flash('Inicio de sesión exitoso!', 'success')
            # CORRECCIÓN: Asegurar redirección correcta
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('tasks'))
        else:
            flash(message, 'danger')
            return render_template('login.html')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        username = request.form['username'].strip()
        password = request.form['password']
        confirm_password = request.form.get('confirm_password', '')
        birth_date = request.form.get('birth_date', '')
        
        # Validaciones
        if not all([email, username, password]):
            flash('Por favor completa todos los campos obligatorios', 'danger')
            return render_template('register.html')
        
        # CORRECCIÓN: Validar confirmación de contraseña
        if password != confirm_password:
            flash('Las contraseñas no coinciden', 'danger')
            return render_template('register.html')
        
        if not validate_email(email):
            flash('Por favor ingresa un email válido', 'danger')
            return render_template('register.html')
        
        if not validate_password(password):
            flash('La contraseña debe tener al menos 6 caracteres', 'danger')
            return render_template('register.html')
        
        if len(username) < 3:
            flash('El nombre de usuario debe tener al menos 3 caracteres', 'danger')
            return render_template('register.html')
        
        # Validar fecha de nacimiento si se proporciona
        if birth_date:
            try:
                birth_date_obj = datetime.datetime.strptime(birth_date, '%Y-%m-%d')
                if birth_date_obj > datetime.datetime.now():
                    flash('La fecha de nacimiento no puede ser futura', 'danger')
                    return render_template('register.html')
                
                age = datetime.datetime.now().year - birth_date_obj.year
                if age < 13:
                    flash('Debes tener al menos 13 años para registrarte', 'danger')
                    return render_template('register.html')
            except ValueError:
                flash('Formato de fecha inválido', 'danger')
                return render_template('register.html')
        
        success, message = register_user(email, username, password, birth_date)
        if success:
            flash('Registro exitoso! Ahora puedes iniciar sesión.', 'success')
            return redirect(url_for('login'))
        else:
            flash(message, 'danger')
    
    return render_template('register.html')

@app.route('/tasks')
def tasks():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    
    # Obtener filtros de la URL
    status_filter = request.args.get('status')
    category_filter = request.args.get('category')
    
    # Obtener tareas, categorías y estadísticas
    tasks = get_user_tasks(user_id, status_filter, category_filter)
    categories = get_user_categories(user_id)
    stats = get_task_statistics(user_id)
    
    return render_template('tasks.html', 
                         tasks=tasks, 
                         categories=categories, 
                         stats=stats,
                         current_status=status_filter,
                         current_category=category_filter)

@app.route('/add_task', methods=['POST'])
def add_task_route():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    title = request.form['title'].strip()
    description = request.form.get('description', '').strip()
    category_id = request.form.get('category_id')
    start_date = request.form.get('start_date')
    end_date = request.form.get('end_date')
    user_id = session['user_id']
    
    # Validaciones
    if not title:
        flash('El título es obligatorio', 'danger')
        return redirect(url_for('tasks'))
    
    # Convertir valores vacíos a None
    if category_id == '':
        category_id = None
    if start_date == '':
        start_date = None
    if end_date == '':
        end_date = None
    
    # Validar fechas
    if start_date and end_date:
        try:
            start = datetime.datetime.strptime(start_date, '%Y-%m-%d')
            end = datetime.datetime.strptime(end_date, '%Y-%m-%d')
            if start > end:
                flash('La fecha de inicio no puede ser posterior a la fecha de fin', 'danger')
                return redirect(url_for('tasks'))
        except ValueError:
            flash('Formato de fecha inválido', 'danger')
            return redirect(url_for('tasks'))
    
    try:
        success, result = add_task(title, description, category_id, user_id, start_date, end_date)
        if success:
            flash('Tarea agregada correctamente', 'success')
        else:
            flash(f'Error al agregar tarea: {result}', 'danger')
    except Exception as e:
        flash(f'Error al agregar tarea: {str(e)}', 'danger')
    
    return redirect(url_for('tasks'))

@app.route('/update_task_status/<task_id>', methods=['POST'])
def update_task_status_route(task_id):
    if 'user_id' not in session:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        data = request.get_json()
        status = data.get('status')
        user_id = session['user_id']
        
        if not status:
            return jsonify({'error': 'Estado requerido'}), 400
        
        valid_statuses = ['no iniciado', 'en proceso', 'finalizado', 'en problemas']
        if status not in valid_statuses:
            return jsonify({'error': 'Estado inválido'}), 400
        
        success = update_task_status(task_id, status, user_id)
        if success:
            return jsonify({'success': True, 'message': 'Estado actualizado'})
        else:
            return jsonify({'error': 'No se pudo actualizar el estado'}), 400
        
    except Exception as e:
        return jsonify({'error': f'Error del servidor: {str(e)}'}), 500

@app.route('/update_task/<task_id>', methods=['POST'])
def update_task_route(task_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    
    # Obtener datos del formulario
    update_data = {}
    if 'title' in request.form and request.form['title'].strip():
        update_data['title'] = request.form['title'].strip()
    if 'description' in request.form:
        update_data['description'] = request.form['description'].strip()
    if 'category_id' in request.form and request.form['category_id']:
        update_data['category_id'] = request.form['category_id']
    if 'start_date' in request.form and request.form['start_date']:
        update_data['start_date'] = request.form['start_date']
    if 'end_date' in request.form and request.form['end_date']:
        update_data['end_date'] = request.form['end_date']
    if 'status' in request.form:
        update_data['status'] = request.form['status']
    
    try:
        success = update_task(task_id, user_id, **update_data)
        if success:
            flash('Tarea actualizada correctamente', 'success')
        else:
            flash('No se pudo actualizar la tarea', 'danger')
    except Exception as e:
        flash(f'Error al actualizar tarea: {str(e)}', 'danger')
    
    return redirect(url_for('tasks'))

@app.route('/delete_task/<task_id>', methods=['POST'])
def delete_task_route(task_id):
    if 'user_id' not in session:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        user_id = session['user_id']
        success = delete_task(task_id, user_id)
        
        if success:
            return jsonify({'success': True, 'message': 'Tarea eliminada'})
        else:
            return jsonify({'error': 'No se pudo eliminar la tarea'}), 400
            
    except Exception as e:
        return jsonify({'error': f'Error del servidor: {str(e)}'}), 500

@app.route('/add_category', methods=['POST'])
def add_category_route():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    name = request.form.get('category_name', '').strip()
    user_id = session['user_id']
    
    if not name:
        flash('El nombre de la categoría es obligatorio', 'danger')
        return redirect(url_for('tasks'))
    
    try:
        success, result = add_category(name, user_id)
        if success:
            flash(f'Categoría "{name}" agregada correctamente', 'success')
        else:
            flash(result, 'danger')
    except Exception as e:
        flash(f'Error al agregar categoría: {str(e)}', 'danger')
    
    return redirect(url_for('tasks'))

# CORRECCIÓN: Nueva ruta para eliminar categorías
@app.route('/delete_category/<category_id>', methods=['POST'])
def delete_category_route(category_id):
    if 'user_id' not in session:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        user_id = session['user_id']
        success = delete_category(category_id, user_id)
        
        if success:
            return jsonify({'success': True, 'message': 'Categoría eliminada'})
        else:
            return jsonify({'error': 'No se pudo eliminar la categoría'}), 400
            
    except Exception as e:
        return jsonify({'error': f'Error del servidor: {str(e)}'}), 500

@app.route('/api/stats')
def api_stats():
    if 'user_id' not in session:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        user_id = session['user_id']
        stats = get_task_statistics(user_id)
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    user = get_user_by_id(user_id)
    
    if not user:
        flash('Usuario no encontrado', 'danger')
        return redirect(url_for('login'))
    
    stats = get_task_statistics(user_id)
    
    return render_template('profile.html', user=user, stats=stats)

@app.route('/logout')
def logout():
    session.clear()
    flash('Has cerrado sesión', 'info')
    return redirect(url_for('login'))

# Filtros de plantilla personalizados
@app.template_filter('format_date')
def format_date(date_obj):
    """Formatear fecha para mostrar"""
    if isinstance(date_obj, str):
        return date_obj
    if date_obj:
        return date_obj.strftime('%d/%m/%Y')
    return 'Sin fecha'

@app.template_filter('days_until')
def days_until(date_str):
    """Calcular días hasta una fecha"""
    if not date_str:
        return None
    try:
        if isinstance(date_str, str):
            target_date = datetime.datetime.strptime(date_str, '%Y-%m-%d')
        else:
            target_date = date_str
        
        today = datetime.datetime.now().date()
        delta = target_date.date() - today
        return delta.days
    except:
        return None

# Manejo de errores
@app.errorhandler(404)
def page_not_found(e):
    return render_template('error.html', error_code=404, error_message="Página no encontrada"), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('error.html', error_code=500, error_message="Error interno del servidor"), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)