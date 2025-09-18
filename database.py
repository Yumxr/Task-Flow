from pymongo import MongoClient
from datetime import datetime, timedelta
import bcrypt
from bson.objectid import ObjectId
import os

# Configuración de MongoDB
MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')
DATABASE_NAME = 'taskflow_db'

# Cliente de MongoDB
client = MongoClient(MONGODB_URI)
db = client[DATABASE_NAME]

# Colecciones
users_collection = db.users
categories_collection = db.categories
tasks_collection = db.tasks

def init_db():
    """Inicializar índices y configuración de la base de datos"""
    try:
        # Crear índices únicos
        users_collection.create_index("email", unique=True)
        users_collection.create_index("username", unique=True)
        
        # Índices para mejor rendimiento
        tasks_collection.create_index([("user_id", 1), ("created_at", -1)])
        categories_collection.create_index("user_id")
        
        print("Base de datos MongoDB inicializada correctamente")
        return True
    except Exception as e:
        print(f"Error al inicializar la base de datos: {e}")
        return False

def register_user(email, username, password, birth_date):
    """Registrar un nuevo usuario"""
    try:
        # Verificar si el usuario o email ya existe
        if users_collection.find_one({"$or": [{"email": email}, {"username": username}]}):
            return False, "El usuario o email ya existe"
        
        # Hash de la contraseña
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        
        # Crear documento del usuario
        user_data = {
            "email": email,
            "username": username,
            "password": password_hash,
            "birth_date": datetime.strptime(birth_date, '%Y-%m-%d') if birth_date else None,
            "telegram_chat_id": None,
            "created_at": datetime.now(),
            "last_login": None
        }
        
        result = users_collection.insert_one(user_data)
        
        # Crear categorías por defecto
        default_categories = ["Personal", "Trabajo", "Estudios", "Hogar"]
        for category_name in default_categories:
            categories_collection.insert_one({
                "name": category_name,
                "user_id": result.inserted_id,
                "created_at": datetime.now()
            })
        
        return True, "Usuario registrado exitosamente"
        
    except Exception as e:
        return False, f"Error al registrar usuario: {str(e)}"

def authenticate_user(username_or_email, password):
    """Autenticar usuario por email o username"""
    try:
        # Buscar usuario por email o username
        user = users_collection.find_one({
            "$or": [{"email": username_or_email}, {"username": username_or_email}]
        })
        
        if not user:
            return None, "Usuario no encontrado"
        
        # Verificar contraseña
        if bcrypt.checkpw(password.encode('utf-8'), user['password']):
            # Actualizar último login
            users_collection.update_one(
                {"_id": user["_id"]},
                {"$set": {"last_login": datetime.now()}}
            )
            return user, "Login exitoso"
        else:
            return None, "Contraseña incorrecta"
            
    except Exception as e:
        return None, f"Error en autenticación: {str(e)}"

def get_user_by_id(user_id):
    """Obtener usuario por ID"""
    try:
        if isinstance(user_id, str):
            user_id = ObjectId(user_id)
        return users_collection.find_one({"_id": user_id})
    except Exception as e:
        print(f"Error al obtener usuario: {e}")
        return None

def get_user_tasks(user_id, status_filter=None, category_filter=None):
    """Obtener tareas del usuario con filtros opcionales"""
    try:
        if isinstance(user_id, str):
            user_id = ObjectId(user_id)
        
        # Construir query
        query = {"user_id": user_id}
        if status_filter:
            query["status"] = status_filter
        if category_filter:
            query["category_id"] = ObjectId(category_filter)
        
        # Obtener tareas con información de categoría
        pipeline = [
            {"$match": query},
            {"$lookup": {
                "from": "categories",
                "localField": "category_id",
                "foreignField": "_id",
                "as": "category"
            }},
            {"$sort": {"created_at": -1}}
        ]
        
        tasks = list(tasks_collection.aggregate(pipeline))
        
        # Procesar resultados
        for task in tasks:
            task['id'] = str(task['_id'])
            task['category_name'] = task['category'][0]['name'] if task['category'] else None
            # Formatear fechas
            if task.get('start_date'):
                task['start_date'] = task['start_date'].strftime('%Y-%m-%d')
            if task.get('end_date'):
                task['end_date'] = task['end_date'].strftime('%Y-%m-%d')
        
        return tasks
        
    except Exception as e:
        print(f"Error al obtener tareas: {e}")
        return []

def get_user_categories(user_id):
    """Obtener categorías del usuario"""
    try:
        if isinstance(user_id, str):
            user_id = ObjectId(user_id)
        
        categories = list(categories_collection.find({"user_id": user_id}).sort("name", 1))
        
        # Convertir ObjectId a string
        for category in categories:
            category['id'] = str(category['_id'])
        
        return categories
        
    except Exception as e:
        print(f"Error al obtener categorías: {e}")
        return []

def add_task(title, description, category_id, user_id, start_date, end_date=None):
    """Agregar nueva tarea"""
    try:
        if isinstance(user_id, str):
            user_id = ObjectId(user_id)
        if category_id and isinstance(category_id, str):
            category_id = ObjectId(category_id)
        
        task_data = {
            "title": title,
            "description": description,
            "status": "no iniciado",
            "category_id": category_id,
            "user_id": user_id,
            "start_date": datetime.strptime(start_date, '%Y-%m-%d') if start_date else None,
            "end_date": datetime.strptime(end_date, '%Y-%m-%d') if end_date else None,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "completed_at": None
        }
        
        result = tasks_collection.insert_one(task_data)
        return True, str(result.inserted_id)
        
    except Exception as e:
        return False, f"Error al agregar tarea: {str(e)}"

def update_task_status(task_id, status, user_id):
    """Actualizar estado de tarea"""
    try:
        if isinstance(task_id, str):
            task_id = ObjectId(task_id)
        if isinstance(user_id, str):
            user_id = ObjectId(user_id)
        
        update_data = {
            "status": status,
            "updated_at": datetime.now()
        }
        
        # Si se marca como finalizado, agregar fecha de completado
        if status == "finalizado":
            update_data["completed_at"] = datetime.now()
        elif status != "finalizado":
            update_data["completed_at"] = None
        
        result = tasks_collection.update_one(
            {"_id": task_id, "user_id": user_id},
            {"$set": update_data}
        )
        
        return result.modified_count > 0
        
    except Exception as e:
        print(f"Error al actualizar estado: {e}")
        return False

def update_task(task_id, user_id, **kwargs):
    """Actualizar tarea completa"""
    try:
        if isinstance(task_id, str):
            task_id = ObjectId(task_id)
        if isinstance(user_id, str):
            user_id = ObjectId(user_id)
        
        # Preparar datos de actualización
        update_data = {"updated_at": datetime.now()}
        
        for key, value in kwargs.items():
            if value is not None:
                if key in ['start_date', 'end_date'] and isinstance(value, str):
                    update_data[key] = datetime.strptime(value, '%Y-%m-%d')
                elif key == 'category_id' and value:
                    update_data[key] = ObjectId(value)
                else:
                    update_data[key] = value
        
        result = tasks_collection.update_one(
            {"_id": task_id, "user_id": user_id},
            {"$set": update_data}
        )
        
        return result.modified_count > 0
        
    except Exception as e:
        print(f"Error al actualizar tarea: {e}")
        return False

def delete_task(task_id, user_id):
    """Eliminar tarea"""
    try:
        if isinstance(task_id, str):
            task_id = ObjectId(task_id)
        if isinstance(user_id, str):
            user_id = ObjectId(user_id)
        
        result = tasks_collection.delete_one({"_id": task_id, "user_id": user_id})
        return result.deleted_count > 0
        
    except Exception as e:
        print(f"Error al eliminar tarea: {e}")
        return False

def add_category(name, user_id):
    """Agregar nueva categoría"""
    try:
        if isinstance(user_id, str):
            user_id = ObjectId(user_id)
        
        # Verificar si la categoría ya existe para este usuario
        if categories_collection.find_one({"name": name, "user_id": user_id}):
            return False, "La categoría ya existe"
        
        category_data = {
            "name": name,
            "user_id": user_id,
            "created_at": datetime.now()
        }
        
        result = categories_collection.insert_one(category_data)
        return True, str(result.inserted_id)
        
    except Exception as e:
        return False, f"Error al agregar categoría: {str(e)}"

# NUEVA FUNCIÓN: Eliminar categoría
def delete_category(category_id, user_id):
    """Eliminar categoría"""
    try:
        if isinstance(category_id, str):
            category_id = ObjectId(category_id)
        if isinstance(user_id, str):
            user_id = ObjectId(user_id)
        
        # Verificar que la categoría pertenece al usuario
        category = categories_collection.find_one({"_id": category_id, "user_id": user_id})
        if not category:
            return False
        
        # Actualizar todas las tareas que usan esta categoría
        tasks_collection.update_many(
            {"category_id": category_id, "user_id": user_id},
            {"$set": {"category_id": None}}
        )
        
        # Eliminar la categoría
        result = categories_collection.delete_one({"_id": category_id, "user_id": user_id})
        return result.deleted_count > 0
        
    except Exception as e:
        print(f"Error al eliminar categoría: {e}")
        return False

def get_task_statistics(user_id):
    """Obtener estadísticas de tareas del usuario"""
    try:
        if isinstance(user_id, str):
            user_id = ObjectId(user_id)
        
        pipeline = [
            {"$match": {"user_id": user_id}},
            {"$group": {
                "_id": "$status",
                "count": {"$sum": 1}
            }}
        ]
        
        stats = list(tasks_collection.aggregate(pipeline))
        
        # Procesar estadísticas
        result = {
            "total": 0,
            "no iniciado": 0,
            "en proceso": 0,
            "finalizado": 0,
            "en problemas": 0
        }
        
        for stat in stats:
            result[stat["_id"]] = stat["count"]
            result["total"] += stat["count"]
        
        return result
        
    except Exception as e:
        print(f"Error al obtener estadísticas: {e}")
        return {"total": 0, "no iniciado": 0, "en proceso": 0, "finalizado": 0, "en problemas": 0}

def get_upcoming_tasks(user_id, days=7):
    """Obtener tareas próximas a vencer"""
    try:
        if isinstance(user_id, str):
            user_id = ObjectId(user_id)
        
        future_date = datetime.now() + timedelta(days=days)
        
        query = {
            "user_id": user_id,
            "status": {"$ne": "finalizado"},
            "end_date": {
                "$gte": datetime.now(),
                "$lte": future_date
            }
        }
        
        tasks = list(tasks_collection.find(query).sort("end_date", 1))
        
        # Procesar resultados
        for task in tasks:
            task['id'] = str(task['_id'])
            if task.get('end_date'):
                task['end_date'] = task['end_date'].strftime('%Y-%m-%d')
        
        return tasks
        
    except Exception as e:
        print(f"Error al obtener tareas próximas: {e}")
        return []

def update_user_telegram(user_id, telegram_chat_id):
    """Actualizar chat ID de Telegram del usuario"""
    try:
        if isinstance(user_id, str):
            user_id = ObjectId(user_id)
        
        result = users_collection.update_one(
            {"_id": user_id},
            {"$set": {"telegram_chat_id": telegram_chat_id}}
        )
        
        return result.modified_count > 0
        
    except Exception as e:
        print(f"Error al actualizar Telegram: {e}")
        return False