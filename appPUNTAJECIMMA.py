import streamlit as st
import pandas as pd
import io
import json
import smtplib
import random
import string
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formatdate
import gspread
from google.oauth2.service_account import Credentials

# ==============================
# CONFIGURACIÓN DE SECRETS
# ==============================
def verificar_secrets():
    required = ["google", "EMAIL", "admin"]
    for r in required:
        if r not in st.secrets:
            st.error(f"❌ Falta la sección '{r}' en los secrets.")
            return False
    return True

# ==============================
# VALIDACIÓN DE NUEVA CLAVE
# ==============================
def validate_new_2fa_key(key):
    """Valida que la nueva clave cumpla con requisitos mínimos."""
    if len(key) < 8:
        return False, "La clave debe tener al menos 8 caracteres."
    if not any(c.isupper() for c in key) or not any(c.isdigit() for c in key):
        return False, "La clave debe incluir al menos una mayúscula y un número."
    return True, ""

# ==============================
# ENVÍO DE CORREO 2FA
# ==============================
def send_2fa_email(to_email, code):
    try:
        msg = MIMEMultipart()
        msg["From"] = st.secrets["EMAIL"]["sender_email"]
        msg["To"] = to_email
        msg["Subject"] = "🔐 Código de Verificación - Sistema PAES"
        msg["Date"] = formatdate(localtime=True)
        body = f"""
        Hola,

        Tu código de verificación para acceder al sistema PAES es:

        🔑 {code}

        Este código expira en 10 minutos.

        Saludos,
        Equipo PAES - Preuniversitario CIMMA
        """
        msg.attach(MIMEText(body, "plain"))
        server = smtplib.SMTP(st.secrets["EMAIL"]["smtp_server"], int(st.secrets["EMAIL"]["smtp_port"]))
        server.starttls()
        server.login(st.secrets["EMAIL"]["sender_email"], st.secrets["EMAIL"]["sender_password"])
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        st.error(f"❌ Error al enviar email 2FA: {e}")
        return False

# ==============================
# ENVÍO DE NUEVA CLAVE DE DOBLE SEGURIDAD
# ==============================
def send_new_2fa_key_email(to_email, new_key):
    """Envía la nueva clave de doble seguridad al correo del administrador."""
    try:
        msg = MIMEMultipart()
        msg["From"] = st.secrets["EMAIL"]["sender_email"]
        msg["To"] = to_email
        msg["Subject"] = "🔑 Nueva Clave de Doble Seguridad - Sistema PAES"
        msg["Date"] = formatdate(localtime=True)
        body = f"""
        Hola,

        Se ha registrado una nueva clave de doble seguridad para tu cuenta de administrador en el sistema PAES:

        🔑 Nueva clave de doble seguridad: {new_key}

        Por seguridad, guarda esta clave en un lugar seguro. No compartas este correo.

        Esta clave será utilizada para futuros accesos al sistema junto con tu código de verificación.

        Saludos,
        Equipo PAES - Preuniversitario CIMMA
        """
        msg.attach(MIMEText(body, "plain"))
        server = smtplib.SMTP(st.secrets["EMAIL"]["smtp_server"], int(st.secrets["EMAIL"]["smtp_port"]))
        server.starttls()
        server.login(st.secrets["EMAIL"]["sender_email"], st.secrets["EMAIL"]["sender_password"])
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        st.error(f"❌ Error al enviar la nueva clave: {e}")
        return False

# ==============================
# AUTENTICACIÓN CON 2FA Y REGISTRO DE NUEVA CLAVE
# ==============================
def autenticacion_admin():
    # Inicializar estados en session_state
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.awaiting_2fa = False
        st.session_state.awaiting_new_2fa_registration = False
        st.session_state.tfa_code = None
        st.session_state.tfa_time = None
        st.session_state.admin_2fa_key = None  # Para futuras verificaciones

    if st.session_state.authenticated:
        return True

    # Paso 1: Iniciar sesión con usuario y contraseña
    if not st.session_state.awaiting_2fa and not st.session_state.awaiting_new_2fa_registration:
        st.subheader("🔐 Inicio de Sesión - Administrador")
        st.info("📝 Ingresa tus credenciales de administrador para acceder al sistema.")
        
        col1, col2 = st.columns([1, 3])
        with col1:
            st.markdown("### 👤 Credenciales")
        with col2:
            user = st.text_input("Usuario", value="", help="Tu nombre de usuario de administrador")
            pwd = st.text_input("Contraseña", type="password", help="Tu contraseña de administrador")
        
        col_btn1, col_btn2 = st.columns([1, 1])
        with col_btn1:
            if st.button("🚪 Ingresar", use_container_width=True):
                if user == st.secrets["admin"]["username"] and pwd == st.secrets["admin"]["password"]:
                    code = ''.join(random.choices(string.digits, k=6))
                    email = st.secrets["admin"]["email"]
                    if send_2fa_email(email, code):
                        st.session_state.tfa_code = code
                        st.session_state.tfa_time = datetime.now()
                        st.session_state.awaiting_2fa = True
                        st.success(f"✅ Código de verificación enviado a {email[:3]}***@...")
                        st.rerun()
                    else:
                        st.error("❌ Falló el envío del código de verificación.")
                else:
                    st.error("❌ Usuario o contraseña incorrectos.")
        
        with col_btn2:
            if st.button("ℹ️ Ayuda", use_container_width=True):
                st.info("""
                **Instrucciones:**
                1. Ingresa tu usuario y contraseña de administrador
                2. Revisa tu correo para el código de verificación
                3. Ingresa el código de 6 dígitos recibido
                4. Configura tu clave de doble seguridad
                """)
    
    # Paso 2: Verificar código 2FA
    elif st.session_state.awaiting_2fa:
        st.subheader("🔐 Verificación en Dos Pasos")
        st.info(f"📧 Se ha enviado un código de 6 dígitos a {st.secrets['admin']['email'][:3]}***@...")
        st.warning("⏰ El código expira en 10 minutos")
        
        col1, col2, col3 = st.columns([1, 3, 1])
        with col1:
            st.markdown("### 🔑 Código")
        with col2:
            code_input = st.text_input(
                "Ingresa el código de 6 dígitos", 
                max_chars=6, 
                key="code_input",
                help="Ingresa exactamente el código recibido en tu correo"
            )
        with col3:
            st.markdown("### ⏱️ Tiempo restante")
            elapsed = (datetime.now() - st.session_state.tfa_time).total_seconds()
            remaining = max(0, 600 - elapsed)
            st.metric("Tiempo", f"{int(remaining//60)}:{int(remaining%60):02d}")
        
        col_btn1, col_btn2 = st.columns([1, 1])
        with col_btn1:
            if st.button("✅ Verificar Código", use_container_width=True):
                if (datetime.now() - st.session_state.tfa_time).total_seconds() > 600:
                    st.error("❌ Código expirado. Inicia sesión nuevamente.")
                    # Resetear estado
                    st.session_state.awaiting_2fa = False
                    st.session_state.tfa_code = None
                    st.session_state.tfa_time = None
                    st.rerun()
                elif code_input == st.session_state.tfa_code:
                    st.success("✅ Código verificado correctamente!")
                    st.session_state.awaiting_2fa = False
                    st.session_state.awaiting_new_2fa_registration = True
                    st.rerun()
                else:
                    st.error("❌ Código incorrecto. Verifica tu correo.")
                    if len(code_input) == 6 and code_input.isdigit():
                        st.warning("💡 Revisa que el código sea exactamente el que recibiste")
        
        with col_btn2:
            if st.button("🔄 Reenviar Código", use_container_width=True):
                code = ''.join(random.choices(string.digits, k=6))
                email = st.secrets["admin"]["email"]
                if send_2fa_email(email, code):
                    st.session_state.tfa_code = code
                    st.session_state.tfa_time = datetime.now()
                    st.success(f"✅ Nuevo código enviado a {email[:3]}***@...")
                    st.rerun()
                else:
                    st.error("❌ Error al reenviar código")
    
    # Paso 3: Registrar nueva clave de doble seguridad
    else:  # awaiting_new_2fa_registration
        st.subheader("🔑 Configurar Clave de Doble Seguridad")
        st.info("""
        **¿Por qué necesitas esta clave?**
        - Esta clave adicional protege tu cuenta contra accesos no autorizados
        - Se usará junto con tu código de verificación en futuros accesos
        - La clave será enviada a tu correo para que la guardes de forma segura
        """)
        
        col1, col2 = st.columns([1, 3])
        with col1:
            st.markdown("### 🔐 Nueva Clave")
        with col2:
            new_2fa_key = st.text_input(
                "Ingresa tu nueva clave de doble seguridad", 
                type="password", 
                key="new_2fa_key",
                help="Mínimo 8 caracteres, debe incluir mayúsculas y números"
            )
            st.markdown("### 📋 Requisitos:")
            st.markdown("- Mínimo 8 caracteres")
            st.markdown("- Al menos una letra mayúscula")
            st.markdown("- Al menos un número")
        
        col_btn1, col_btn2 = st.columns([1, 1])
        with col_btn1:
            if st.button("📤 Registrar y Enviar", use_container_width=True):
                if not new_2fa_key:
                    st.error("❌ Debes ingresar una clave.")
                else:
                    is_valid, error_msg = validate_new_2fa_key(new_2fa_key)
                    if not is_valid:
                        st.error(f"❌ {error_msg}")
                    else:
                        email = st.secrets["admin"]["email"]
                        if send_new_2fa_key_email(email, new_2fa_key):
                            st.success(f"✅ Clave registrada y enviada a {email[:3]}***@...")
                            # Guardar la clave en session_state para futuras verificaciones
                            st.session_state.admin_2fa_key = new_2fa_key
                            st.session_state.authenticated = True
                            st.session_state.awaiting_new_2fa_registration = False
                            st.balloons()
                            st.rerun()
                        else:
                            st.error("❌ Error al enviar la clave. Intenta de nuevo.")
        
        with col_btn2:
            if st.button("➡️ Continuar sin configurar", use_container_width=True):
                st.warning("⚠️ Continúas sin clave de doble seguridad. Tu cuenta es menos segura.")
                st.session_state.authenticated = True
                st.session_state.awaiting_new_2fa_registration = False
                st.session_state.admin_2fa_key = None
                st.rerun()

    return False

# ==============================
# GOOGLE SHEETS: CARGA DE CORREOS
# ==============================
@st.cache_resource
def get_gspread_client():
    # Manejar tanto string JSON como dict
    google_creds = st.secrets["google"]
    if "credentials" in google_creds:
        # Si es string JSON
        creds_dict = json.loads(google_creds["credentials"])
    else:
        # Si ya es un dict en los secrets
        creds_dict = google_creds
    
    creds = Credentials.from_service_account_info(creds_dict, scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ])
    return gspread.authorize(creds)

def load_guardian_emails():
    """Carga el mapeo de ZipGrade ID a correo de apoderado desde la hoja 'PAESREPORTES'"""
    try:
        client = get_gspread_client()
        sheet = client.open_by_key(st.secrets["google"]["sheet_id"]).worksheet("PAESREPORTES")
        records = sheet.get_all_records()
        email_map = {}
        for r in records:
            zid = str(r.get("ZipGrade ID", "")).strip()
            if zid:
                email_map[zid] = {
                    "student_name": f"{r.get('First Name', '')} {r.get('Last Name', '')}".strip(),
                    "guardian_email": r.get("MAIL APODERADO", "").strip()
                }
        return email_map
    except Exception as e:
        st.error(f"❌ Error al cargar correos desde Google Sheets: {e}")
        return {}

# ==============================
# ENVÍO DE CORREO A APODERADOS
# ==============================
def send_result_email(to_email, student_name, results_df):
    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = st.secrets["EMAIL"]["sender_email"]
        msg["To"] = to_email
        msg["Subject"] = f"📊 Resultados PAES - {student_name}"
        msg["Date"] = formatdate(localtime=True)

        # Construir cuerpo HTML
        rows = ""
        for _, row in results_df.iterrows():
            test = row.get("Test Type", "N/A")
            score = row.get("PAES Score", "N/A")
            correct = row.get("Total Correct", "N/A")
            date = row.get("Date Uploaded", "N/A")
            rows += f"<tr><td>{test}</td><td>{correct}</td><td>{score}</td><td>{date}</td></tr>"

        html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 700px; margin: auto; padding: 20px;">
            <h2>🎓 Resultados de Ensayos PAES</h2>
            <p>Estimado apoderado/a,</p>
            <p>A continuación, los resultados de <strong>{student_name}</strong>:</p>
            <table border="1" cellpadding="8" cellspacing="0" style="width:100%; border-collapse: collapse;">
                <thead>
                    <tr style="background-color: #f2f2f2;">
                        <th>Ensayo</th>
                        <th>Correctas</th>
                        <th>Puntaje PAES</th>
                        <th>Fecha</th>
                    </tr>
                </thead>
                <tbody>
                    {rows}
                </tbody>
            </table>
            <p style="margin-top: 20px; font-style: italic;">
                Este es un mensaje automático. Por favor, no responda.
            </p>
            <hr>
            <p>Preuniversitario CIMMA - Sistema PAES 2025</p>
        </div>
        """
        msg.attach(MIMEText(html, "html"))
        
        # Configuración SMTP mejorada
        server = smtplib.SMTP(st.secrets["EMAIL"]["smtp_server"], int(st.secrets["EMAIL"]["smtp_port"]))
        server.starttls()
        server.login(st.secrets["EMAIL"]["sender_email"], st.secrets["EMAIL"]["sender_password"])
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        st.error(f"❌ Error al enviar email a {to_email}: {e}")
        return False

# ==============================
# LÓGICA DE PUNTAJES PAES
# ==============================
SCORE_RANGES = {
    "CLE8": {0:150,10:200,20:300,30:400,40:500,50:600,60:700},
    "M1E8": {0:150,10:200,20:300,30:400,40:500,50:600,60:700,65:750},
    "M2E8": {0:150,10:200,20:300,30:400,40:500,50:600,60:700,65:750},
    "CFE8": {0:150,10:200,20:300,30:400,40:500,50:600,60:700},
    "CBE8": {0:150,10:200,20:300,30:400,40:500,50:600,60:700},
    "CQE8": {0:150,10:200,20:300,30:400,40:500,50:600,60:700},
}

def get_paes_score(correct, test_type):
    if test_type not in SCORE_RANGES:
        return None
    ranges = SCORE_RANGES[test_type]
    keys = sorted(ranges.keys())
    for i in range(len(keys) - 1):
        if keys[i] <= correct < keys[i+1]:
            return ranges[keys[i]]
    return ranges[keys[-1]] if correct >= keys[-1] else ranges[keys[0]]

def process_file(uploaded_file, date_uploaded):
    try:
        df = pd.read_csv(uploaded_file)
        quiz_name = df['Quiz Name'].iloc[0] if 'Quiz Name' in df.columns else ""
        test_type = "UNKNOWN"
        for key in SCORE_RANGES:
            if key in quiz_name:
                test_type = key
                break

        required = ['ZipGrade ID', 'First Name', 'Last Name']
        for col in required:
            if col not in df.columns:
                st.error(f"Falta columna '{col}' en {uploaded_file.name}")
                return None, None

        q_cols = [c for c in df.columns if c.startswith('Q') and c[1:].isdigit()]
        df['Total Correct'] = df[q_cols].sum(axis=1)
        df['PAES Score'] = df['Total Correct'].apply(lambda x: get_paes_score(x, test_type))
        df['Test Type'] = test_type
        df['Date Uploaded'] = date_uploaded

        return df[['ZipGrade ID', 'First Name', 'Last Name', 'Total Correct', 'PAES Score', 'Test Type', 'Date Uploaded']], test_type
    except Exception as e:
        st.error(f"Error procesando {uploaded_file.name}: {e}")
        return None, None

# ==============================
# APP PRINCIPAL
# ==============================
st.set_page_config(page_title="Sistema PAES - Administrador", layout="wide", page_icon="logo.gif")
st.image("logo.gif", width=200)

# Verificar secrets
if not verificar_secrets():
    st.stop()

# Autenticación
if not autenticacion_admin():
    st.info("🔒 Por favor, completa el proceso de autenticación para acceder al sistema.")
    st.stop()

# Mostrar información de autenticación exitosa
st.success(f"✅ Bienvenido, {st.secrets['admin']['username']}!")
st.info(f"🔐 Estado de seguridad: {'🛡️️ Con clave de doble seguridad' if st.session_state.get('admin_2fa_key') else '⚠️ Sin clave de doble seguridad'}")

# Botón para cerrar sesión
if st.button("🚪 Cerrar Sesión"):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

# Cargar correos de apoderados
with st.spinner("🔄 Cargando información de estudiantes desde Google Sheets..."):
    email_map = load_guardian_emails()

if not email_map:
    st.warning("⚠️ No se cargaron correos de apoderados. Verifica la hoja 'PAESREPORTES' en Google Sheets.")
else:
    st.success(f"✅ Cargados {len(email_map)} estudiantes correctamente")

# Interfaz de carga de archivos
st.subheader("📤 Subir Resultados de Ensayos PAES")
col_file, col_date = st.columns([3, 1])
with col_file:
    uploaded_files = st.file_uploader(
        "📁 Sube archivos CSV de ensayos PAES", 
        type="csv", 
        accept_multiple_files=True,
        help="Selecciona uno o más archivos CSV generados por ZipGrade"
    )
with col_date:
    upload_date = st.date_input(
        "📅 Fecha de subida", 
        value=datetime.now().date(),
        help="Fecha en que se realizó el ensayo"
    )

# Mostrar información de archivos cargados
if uploaded_files:
    st.info(f"📁 Archivos cargados: **{len(uploaded_files)}** archivo(s)")
    for file in uploaded_files:
        st.write(f"• {file.name}")

if st.button("🚀 Procesar y Enviar Resultados", type="primary", disabled=not uploaded_files) and uploaded_files and upload_date:
    all_dfs = []
    processed_files = 0
    test_types_found = set()
    
    with st.spinner("⚙️ Procesando archivos CSV..."):
        for f in uploaded_files:
            df, test_type = process_file(f, upload_date)
            if df is not None:
                all_dfs.append(df)
                processed_files += 1
                test_types_found.add(test_type)
                st.success(f"✅ {f.name} - Tipo: {test_type} ({len(df)} estudiantes)")
            else:
                st.error(f"❌ Error procesando {f.name}")

    if not all_dfs:
        st.error("❌ No se pudo procesar ningún archivo válido. Verifica el formato de los CSV.")
        st.stop()

    # Combinar todos los datos
    combined = pd.concat(all_dfs, ignore_index=True)
    
    st.subheader("📊 Vista Previa de Datos Procesados")
    st.dataframe(combined, use_container_width=True, height=300)
    
    # Estadísticas básicas
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📄 Archivos procesados", processed_files)
    with col2:
        st.metric("👥 Estudiantes únicos", combined['ZipGrade ID'].nunique())
    with col3:
        st.metric("📈 Promedio puntaje", f"{combined['PAES Score'].mean():.1f}")
    with col4:
        st.metric("🎯 Tipos de ensayo", len(test_types_found))
    
    # Agregar columna de correo de apoderado
    st.info("🔗 Mapeando correos de apoderados...")
    combined['Mail Apoderado'] = combined['ZipGrade ID'].astype(str).map(
        lambda zid: email_map.get(zid, {}).get("guardian_email", "")
    )
    
    # Filtrar estudiantes con correo válido
    students_with_email = combined[combined['Mail Apoderado'].notna() & (combined['Mail Apoderado'] != '')]
    students_without_email = combined[~combined['ZipGrade ID'].astype(str).isin(students_with_email['ZipGrade ID'].astype(str))]
    
    if len(students_without_email) > 0:
        st.warning(f"⚠️ {len(students_without_email)} estudiantes sin correo de apoderado registrado")
        if st.button("📋 Mostrar estudiantes sin correo"):
            st.dataframe(students_without_email[['ZipGrade ID', 'First Name', 'Last Name']].drop_duplicates())
    
    # Agrupar por estudiante (ZipGrade ID) para envío de correos
    grouped = students_with_email.groupby('ZipGrade ID')
    emails_enviados = 0
    errores_envio = 0

    st.subheader("📧 Envío de Resultados a Apoderados")
    st.info(f"Enviando resultados a **{len(grouped)}** apoderados únicos...")
    
    progress_container = st.container()
    progress_bar = progress_container.progress(0)
    status_container = st.container()
    
    for i, (zid, group) in enumerate(grouped):
        zid_str = str(zid).strip()
        info = email_map[zid_str]
        guardian_email = info["guardian_email"]
        student_name = info["student_name"]

        with status_container:
            if send_result_email(guardian_email, student_name, group[['Test Type', 'Total Correct', 'PAES Score', 'Date Uploaded']]):
                emails_enviados += 1
                st.success(f"✅ Enviado a {student_name} ({guardian_email[:15]}...)")
            else:
                errores_envio += 1
                st.error(f"❌ Error enviando a {student_name}")
        
        progress_bar.progress((i + 1) / len(grouped))

    # Resultados finales
    st.subheader("📊 Resumen de Envíos")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📧 Correos enviados exitosamente", emails_enviados, delta_color="normal")
    with col2:
        st.metric("❌ Errores de envío", errores_envio, delta_color="inverse")
    with col3:
        st.metric("👥 Apoderados contactados", len(grouped))
    
    if emails_enviados > 0:
        st.balloons()
        st.success(f"🎉 ¡Proceso completado! Se enviaron {emails_enviados} correos exitosamente.")
    
    # Opción de descarga
    st.subheader("📥 Descargar Resultados Completos")
    csv_buffer = io.StringIO()
    combined.to_csv(csv_buffer, index=False)
    csv_data = csv_buffer.getvalue().encode('utf-8')
    
    col_download1, col_download2 = st.columns(2)
    with col_download1:
        st.download_button(
            label="📊 Descargar CSV Completo",
            data=csv_data,
            file_name=f"resultados_paes_{upload_date.strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True,
            help="Descarga todos los resultados procesados"
        )
    
    with col_download2:
        # Descarga solo estudiantes sin correo
        if len(students_without_email) > 0:
            no_email_csv = students_without_email[['ZipGrade ID', 'First Name', 'Last Name', 'Test Type', 'Total Correct', 'PAES Score', 'Date Uploaded']].drop_duplicates()
            no_email_data = no_email_csv.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="⚠️ Descargar Estudiantes sin Correo",
                data=no_email_data,
                file_name=f"estudiantes_sin_correo_{upload_date.strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True,
                help="Descarga la lista de estudiantes sin correo registrado"
            )

# Información adicional y pie de página
st.markdown("---")
col_footer1, col_footer2, col_footer3 = st.columns(3)

with col_footer1:
    st.markdown("### 🔒 Seguridad")
    st.markdown(f"- Autenticación 2FA: ✅ Activa")
    st.markdown(f"- Clave adicional: {'✅ Configurada' if st.session_state.get('admin_2fa_key') else '⚠️ Pendiente'}")

with col_footer2:
    st.markdown("### 📊 Sistema")
    st.markdown("- **Preuniversitario CIMMA**")
    st.markdown("- Sistema PAES 2025")
    st.markdown("- Versión: 2.0")

with col_footer3:
    st.markdown("### 📧 Soporte")
    st.markdown("- Reportar problemas")
    st.markdown("- Solicitar ayuda")
    st.markdown("- Contacto técnico")

st.caption("🔐 Sistema PAES - Preuniversitario CIMMA | Solo para uso administrativo | © 2025")