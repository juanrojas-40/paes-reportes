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
# AUTENTICACIÓN CON 2FA
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

def autenticacion_admin():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.awaiting_2fa = False
        st.session_state.tfa_code = None
        st.session_state.tfa_time = None

    if st.session_state.authenticated:
        return True

    if not st.session_state.awaiting_2fa:
        st.subheader("🔐 Inicio de Sesión (Administrador)")
        user = st.text_input("Usuario", value="")
        pwd = st.text_input("Contraseña", type="password")
        if st.button("Ingresar"):
            if user == st.secrets["admin"]["username"] and pwd == st.secrets["admin"]["password"]:
                code = ''.join(random.choices(string.digits, k=6))
                email = st.secrets["admin"]["email"]
                if send_2fa_email(email, code):
                    st.session_state.tfa_code = code
                    st.session_state.awaiting_2fa = True
                    st.session_state.tfa_time = datetime.now()
                    st.success(f"✅ Código enviado a {email[:3]}***@...")
                    # 🚫 NO HACER RERUN AQUÍ. Deja que el usuario ingrese el código.
                else:
                    st.error("❌ Falló el envío del código.")
            else:
                st.error("❌ Usuario o contraseña incorrectos.")
    else:
        # ✅ MOSTRAR EL CAMPO PARA INGRESAR EL CÓDIGO
        st.subheader("🔐 Verificación en Dos Pasos")
        st.info(f"Se ha enviado un código de 6 dígitos a {st.secrets['admin']['email']}")
        code_input = st.text_input("Ingresa el código de 6 dígitos", max_chars=6, type="password")
        if st.button("Verificar"):
            if (datetime.now() - st.session_state.tfa_time).total_seconds() > 600:
                st.error("❌ Código expirado. Inicia sesión nuevamente.")
                st.session_state.awaiting_2fa = False
            elif code_input == st.session_state.tfa_code:
                st.session_state.authenticated = True
                st.session_state.awaiting_2fa = False
                st.rerun()
            else:
                st.error("❌ Código incorrecto.")

    return False





# ==============================
# GOOGLE SHEETS: CARGA DE CORREOS
# ==============================
@st.cache_resource
def get_gspread_client():
    creds_dict = json.loads(st.secrets["google"]["credentials"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=[
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ])
    return gspread.authorize(creds)

def load_guardian_emails():
    """Carga el mapeo de ZipGrade ID a correo de apoderado desde la hoja 'PAESREPORTES'"""
    try:
        client = get_gspread_client()
        sheet = client.open_by_key(st.secrets["google"]["sheet_id"]).worksheet("PAESREPORTES") # <-- HOJA CORRECTA
        records = sheet.get_all_records()
        email_map = {}
        for r in records:
            zid = str(r.get("ZipGrade ID", "")).strip()
            if zid:
                email_map[zid] = {
                    "student_name": f"{r.get('First Name', '')} {r.get('Last Name', '')}".strip(),
                    "guardian_email": r.get("MAIL APODERADO", "").strip() # <-- NOMBRE DE COLUMNA CORRECTO
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
st.set_page_config(page_title="Sistema PAES - Administrador", layout="wide")
st.title("📊 Sistema de Registro y Reporte de Resultados PAES")

if not verificar_secrets():
    st.stop()

if not autenticacion_admin():
    st.info("Por favor, inicia sesión como administrador.")
    st.stop()

st.success(f"✅ Bienvenido, {st.secrets['admin']['username']}")

# Cargar correos de apoderados
email_map = load_guardian_emails()
if not email_map:
    st.warning("⚠️ No se cargaron correos de apoderados. Verifica la hoja 'PAESREPORTES' en Google Sheets.")

# Interfaz de carga
uploaded_files = st.file_uploader("Sube archivos CSV de ensayos PAES", type="csv", accept_multiple_files=True)
upload_date = st.date_input("Fecha de subida", value=None)

if st.button("🚀 Procesar y Enviar Resultados") and uploaded_files and upload_date:
    all_dfs = []
    for f in uploaded_files:
        df, _ = process_file(f, upload_date)
        if df is not None:
            all_dfs.append(df)

    if not all_dfs:
        st.error("❌ No se procesó ningún archivo válido.")
        st.stop()

    combined = pd.concat(all_dfs, ignore_index=True)
    st.subheader("✅ Datos Procesados")
    st.dataframe(combined)

    # Agregar columna de correo de apoderado
    combined['Mail Apoderado'] = combined['ZipGrade ID'].astype(str).map(
        lambda zid: email_map.get(zid, {}).get("guardian_email", "")
    )

    # Agrupar por estudiante (ZipGrade ID)
    grouped = combined.groupby('ZipGrade ID')
    emails_enviados = 0

    for zid, group in grouped:
        zid_str = str(zid).strip()
        if zid_str not in email_map:
            st.warning(f"📧 No se encontró correo para ZipGrade ID: {zid_str}")
            continue

        info = email_map[zid_str]
        guardian_email = info["guardian_email"]
        student_name = info["student_name"]

        if not guardian_email:
            st.warning(f"📧 Correo vacío para {student_name} (ID: {zid_str})")
            continue

        if send_result_email(guardian_email, student_name, group[['Test Type', 'Total Correct', 'PAES Score', 'Date Uploaded']]):
            emails_enviados += 1
            st.success(f"✅ Enviado a {student_name} ({guardian_email})")

    st.balloons()
    st.metric("📧 Correos enviados", emails_enviados)

    # Descarga
    csv = combined.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Descargar CSV completo", csv, "resultados_paes.csv", "text/csv")

st.markdown("---")
st.caption("Sistema PAES - Preuniversitario CIMMA | Solo para uso administrativo")