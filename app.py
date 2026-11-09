import streamlit as st
import pandas as pd
from supabase import create_client
from urllib.parse import quote
from datetime import date
from decimal import Decimal
from uuid import uuid4

# ==========================================
# CONFIGURAÇÃO
# ==========================================

st.set_page_config(
    page_title="CUBIA | Gestão",
    page_icon="🦁",
    layout="wide"
)

supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_KEY"]
)

WHATSAPP = st.secrets["WHATSAPP_NUMBER"]

if "cart" not in st.session_state:
    st.session_state.cart = {}

if "access_token" not in st.session_state:
    st.session_state.access_token = None

if "refresh_token" not in st.session_state:
    st.session_state.refresh_token = None

# ==========================================
# FUNÇÕES
# ==========================================

def money(value):
    return f"R$ {float(value or 0):,.2f}".replace(
        ",", "X"
    ).replace(".", ",").replace("X", ".")


def get_data(table, filters=None):
    query = supabase.table(table).select("*")
    if filters:
        for column, value in filters.items():
            query = query.eq(column, value)
    return query.execute().data or []


def save_data(table, data):
    return supabase.table(table).insert(data).execute()


def optional_money(value):
    return "Não informado" if value is None else money(value)


def payment_label(sale):
    received = sale.get("received_amount")
    total = sale.get("total_amount")
    if received is None:
        return "Não informado"
    received = Decimal(str(received))
    total = Decimal(str(total or 0))
    if received == 0:
        return "Pendente"
    if received < total:
        return "Parcial"
    return "Pago"


def upload_product_image(uploaded_file):
    """Envia a imagem para o bucket público product-images e retorna sua URL."""
    if uploaded_file is None:
        return None

    allowed_types = {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/webp": "webp"
    }
    if uploaded_file.type not in allowed_types:
        raise ValueError("Formato inválido. Use JPG, PNG ou WEBP.")

    extension = allowed_types[uploaded_file.type]
    file_path = f"products/{uuid4().hex}.{extension}"

    supabase.storage.from_("product-images").upload(
        file_path,
        uploaded_file.getvalue(),
        file_options={
            "content-type": uploaded_file.type,
            "cache-control": "3600"
        }
    )

    return supabase.storage.from_("product-images").get_public_url(file_path)


def admin_login():
    st.title("🦁 CUBIA | Administração")
    st.caption("Acesso exclusivo")

    with st.form("login"):
        email = st.text_input("E-mail")
        password = st.text_input(
            "Senha", type="password"
        )
        submitted = st.form_submit_button(
            "Entrar", use_container_width=True
        )

    if submitted:
        try:
            result = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })

            st.session_state.access_token = (
                result.session.access_token
            )
            st.session_state.refresh_token = (
                result.session.refresh_token
            )
