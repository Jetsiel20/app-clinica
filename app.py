from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date # Importamos 'date' también

import os

app = Flask(__name__)

# --- Configuración de la Base de Datos SQLite ---
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(app.instance_path, 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'tu_clave_secreta_aqui'

db = SQLAlchemy(app)

# --- Modelos de la Base de Datos ---
class Paciente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    cedula = db.Column(db.String(20), unique=True, nullable=False)
    # Cambiado a db.Date para almacenar solo la fecha
    fecha_nacimiento = db.Column(db.Date, nullable=False) 
    
    citas = db.relationship('Cita', backref='paciente', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Paciente {self.nombre} ({self.cedula})>'

class Cita(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # Cambiado a db.DateTime para almacenar fecha y hora
    fecha_cita = db.Column(db.DateTime, nullable=False) 
    motivo = db.Column(db.String(200), nullable=False)
    
    # Clave foránea para relacionar la cita con un paciente
    paciente_cedula = db.Column(db.String(20), db.ForeignKey('paciente.cedula'), nullable=False)

    def __repr__(self):
        return f'<Cita {self.fecha_cita} para {self.paciente_cedula}>'

# --- Rutas de la Aplicación ---

@app.route('/')
def index():
    """
    Ruta principal que muestra la lista de pacientes en la página de inicio.
    """
    pacientes = Paciente.query.all() 
    return render_template('index.html', pacientes=pacientes)

@app.route('/registrar', methods=['GET', 'POST'])
def registrar():
    """
    Maneja el registro de nuevos pacientes.
    Si el método es POST, guarda el paciente; de lo contrario, muestra el formulario.
    """
    if request.method == 'POST':
        nombre = request.form['nombre']
        cedula = request.form['cedula']
        fecha_nacimiento_str = request.form['fecha_nacimiento']

        # Convertir la cadena de fecha a un objeto date
        try:
            # El formato de input type="date" es 'YYYY-MM-DD'
            fecha_nacimiento = datetime.strptime(fecha_nacimiento_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Formato de fecha de nacimiento inválido. Use AAAA-MM-DD.', 'danger')
            return render_template('registrar.html', nombre=nombre, cedula=cedula, fecha_nacimiento=fecha_nacimiento_str)

        # Validar que no se repita la cédula
        paciente_existente = Paciente.query.filter_by(cedula=cedula).first()
        if paciente_existente:
            flash('La cédula ya está registrada. Por favor, ingrese una cédula diferente.', 'danger')
            return render_template('registrar.html', nombre=nombre, cedula=cedula, fecha_nacimiento=fecha_nacimiento_str)
        
        # Crea una nueva instancia de Paciente y la añade a la base de datos
        nuevo_paciente = Paciente(nombre=nombre, cedula=cedula, fecha_nacimiento=fecha_nacimiento)
        db.session.add(nuevo_paciente)
        db.session.commit()
        
        flash('Paciente registrado exitosamente!', 'success')
        return redirect(url_for('index'))
    
    return render_template('registrar.html')

@app.route('/citas', methods=['GET', 'POST'])
def citas():
    """
    Maneja el agendamiento de nuevas citas y muestra las citas existentes.
    """
    pacientes = Paciente.query.all()
    # Ordena las citas por fecha descendente
    citas = Cita.query.order_by(Cita.fecha_cita.desc()).all() 

    if request.method == 'POST':
        paciente_cedula = request.form['paciente_cedula']
        fecha_cita_str = request.form['fecha_cita'] # Formato 'YYYY-MM-DDTHH:MM' de input datetime-local
        motivo = request.form['motivo']

        # Convertir la cadena de fecha y hora a un objeto datetime
        try:
            fecha_cita = datetime.strptime(fecha_cita_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            flash('Formato de fecha y hora de cita inválido. Use AAAA-MM-DDTHH:MM.', 'danger')
            return render_template('citas.html', pacientes=pacientes, citas=citas, fecha_cita=fecha_cita_str, motivo=motivo)


        # Validar que el paciente exista
        paciente_existente = Paciente.query.filter_by(cedula=paciente_cedula).first()
        if not paciente_existente:
            flash('El paciente seleccionado no existe.', 'danger')
            return render_template('citas.html', pacientes=pacientes, citas=citas, fecha_cita=fecha_cita_str, motivo=motivo)
        
        # Crea una nueva instancia de Cita y la añade a la base de datos
        nueva_cita = Cita(paciente_cedula=paciente_cedula, fecha_cita=fecha_cita, motivo=motivo)
        db.session.add(nueva_cita)
        db.session.commit()

        # Lógica para limpiar citas si excede el límite de 20
        # Obtener todas las citas ordenadas por fecha ascendente
        todas_las_citas = Cita.query.order_by(Cita.fecha_cita.asc()).all() 
        if len(todas_las_citas) > 20:
            citas_a_eliminar_count = len(todas_las_citas) - 20
            for i in range(citas_a_eliminar_count):
                db.session.delete(todas_las_citas[i]) # Elimina las citas más antiguas
            db.session.commit()
            flash(f"Se eliminaron {citas_a_eliminar_count} citas antiguas para mantener el límite.", 'info')

        flash('Cita agendada exitosamente!', 'success')
        return redirect(url_for('citas'))
    
    return render_template('citas.html', pacientes=pacientes, citas=citas)

@app.route('/pacientes_registrados')
def pacientes_registrados():
    """
    Muestra una lista detallada de todos los pacientes registrados.
    """
    pacientes = Paciente.query.all()
    return render_template('pacientes_registrados.html', pacientes=pacientes)

@app.route('/modificar_paciente/<string:cedula>', methods=['GET', 'POST'])
def modificar_paciente(cedula):
    """
    Permite modificar los datos de un paciente existente.
    GET: Muestra el formulario con los datos actuales del paciente.
    POST: Procesa la actualización de los datos del paciente.
    """
    # Busca el paciente por su cédula
    paciente_a_modificar = Paciente.query.filter_by(cedula=cedula).first()

    if not paciente_a_modificar:
        flash('Paciente no encontrado.', 'danger')
        return redirect(url_for('pacientes_registrados'))

    if request.method == 'POST':
        nuevo_nombre = request.form['nombre']
        nueva_cedula = request.form['cedula']
        nueva_fecha_nacimiento_str = request.form['fecha_nacimiento']

        # Convertir la cadena de fecha a un objeto date
        try:
            nueva_fecha_nacimiento = datetime.strptime(nueva_fecha_nacimiento_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Formato de fecha de nacimiento inválido. Use AAAA-MM-DD.', 'danger')
            return render_template('modificar_paciente.html', paciente=paciente_a_modificar)

        # Validar si la nueva cédula ya existe y no es la del propio paciente
        if nueva_cedula != cedula:
            paciente_con_nueva_cedula = Paciente.query.filter_by(cedula=nueva_cedula).first()
            if paciente_con_nueva_cedula:
                flash('La nueva cédula ya está registrada por otro paciente.', 'danger')
                return render_template('modificar_paciente.html', paciente=paciente_a_modificar)

        # Actualizar los datos del paciente
        paciente_a_modificar.nombre = nuevo_nombre
        paciente_a_modificar.cedula = nueva_cedula
        paciente_a_modificar.fecha_nacimiento = nueva_fecha_nacimiento
        
        db.session.commit() # Guarda los cambios en la base de datos
        flash('Paciente modificado exitosamente!', 'success')
        return redirect(url_for('pacientes_registrados'))
    
    # Si es GET, simplemente renderiza el formulario con los datos actuales
    # Aseguramos que la fecha se formatee correctamente para el input type="date"
    paciente_a_modificar.fecha_nacimiento_str = paciente_a_modificar.fecha_nacimiento.strftime('%Y-%m-%d')
    return render_template('modificar_paciente.html', paciente=paciente_a_modificar)

@app.route('/eliminar_paciente/<string:cedula>', methods=['POST'])
def eliminar_paciente(cedula):
    """
    Elimina un paciente de la base de datos.
    """
    paciente_a_eliminar = Paciente.query.filter_by(cedula=cedula).first()

    if paciente_a_eliminar:
        db.session.delete(paciente_a_eliminar)
        db.session.commit() # Guarda los cambios
        flash('Paciente eliminado exitosamente!', 'success')
    else:
        flash('Paciente no encontrado para eliminar.', 'danger')
    
    return redirect(url_for('pacientes_registrados'))

# --- Inicialización de la Base de Datos ---
# Este bloque se ejecuta una vez cuando la aplicación se inicia
# Si la base de datos no existe, la crea junto con las tablas
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    # Ejecuta la aplicación Flask en modo depuración
    app.run(debug=True)
