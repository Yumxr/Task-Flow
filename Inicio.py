import subprocess
import sys
import os

# Cambiar al directorio correcto
os.chdir(r"D:\Doc\git-y-github\To-do-list")

# Instalar dependencias
subprocess.run([sys.executable, "-m", "pip", "install", "flask", "pymongo", "bcrypt", "dnspython"])

# Crear directorio templates si no existe
os.makedirs("templates", exist_ok=True)

# Ejecutar aplicación
subprocess.run([sys.executable, "app.py"])