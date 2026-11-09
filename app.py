
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
            st.rerun()

        except Exception:
            st.error("E-mail ou senha inválidos.")


def register_sale(client_id, selected, quantities,
                  sale_date, desired_date, received,
                  payment_status, delivery_status,
                  notes, deduct_stock):

    products = get_data("products")
    product_map = {p["id"]: p for p in products}

    total = Decimal("0")
    cost = Decimal("0")

    for product_id in selected:
        p = product_map[product_id]
        qty = quantities[product_id]

        if deduct_stock and p["stock_qty"] < qty:
            raise ValueError(
                f"Estoque insuficiente: {p['name']}"
            )

        total += Decimal(str(p["price"])) * qty
        cost += Decimal(str(p["cost_price"])) * qty

    if Decimal(str(received)) > total:
        raise ValueError(
            "O valor recebido não pode superar o total da venda."
        )

    if payment_status == "Pago":
        received = float(total)

    if payment_status == "Pendente":
        received = 0

    sale = save_data("sales", {
        "client_id": client_id,
        "sale_date": str(sale_date),
        "desired_date": (
            str(desired_date) if desired_date else None
        ),
        "total_amount": float(total),
        "total_cost": float(cost),
        "received_amount": float(received),
        "payment_status": payment_status,
        "delivery_status": delivery_status,
        "notes": notes
    }).data[0]

    for product_id in selected:
        p = product_map[product_id]
        qty = quantities[product_id]

        save_data("sale_items", {
            "sale_id": sale["id"],
            "product_id": product_id,
            "product_name": p["name"],
            "quantity": qty,
            "unit_price": p["price"],
            "unit_cost": p["cost_price"]
        })

        if deduct_stock:
            new_stock = p["stock_qty"] - qty

            supabase.table("products").update({
                "stock_qty": new_stock
            }).eq("id", product_id).execute()

            save_data("stock_movements", {
                "product_id": product_id,
                "movement_type": "Venda",
                "quantity": -qty,
                "notes": f"Pedido {sale['id']}"
            })

    return sale


# ==========================================
# LOJA PÚBLICA
# ==========================================

def public_store():
    st.title("🦁 CUBIA")
    st.subheader("Ideias que ganham forma.")
    st.write(
        "Laboratório 3D e soluções inteligentes."
    )

    page = st.radio(
        "Navegação",
        ["Produtos", "Meu carrinho", "Sobre a Cubia"],
        horizontal=True
    )

    if page == "Produtos":
        products = supabase.table(
            "products"
        ).select("*").eq(
            "active", True
        ).order("name").execute().data or []

        if not products:
            st.info("Nosso catálogo está sendo preparado.")
            return

        cols = st.columns(3)

        for i, p in enumerate(products):
            with cols[i % 3]:
                if p.get("image_url"):
                    st.image(
                        p["image_url"],
                        use_container_width=True
                    )

                st.subheader(p["name"])
                st.caption(p.get("category") or "")
                st.write(p.get("description") or "")
                st.markdown(f"### {money(p['price'])}")

                if st.button(
                    "Adicionar ao carrinho",
                    key=f"add_{p['id']}",
                    use_container_width=True
                ):
                    cart = st.session_state.cart
                    if p["id"] in cart:
                        cart[p["id"]]["quantity"] += 1
                    else:
                        cart[p["id"]] = {
                            "name": p["name"],
                            "price": float(p["price"]),
                            "quantity": 1
                        }
                    st.success("Produto adicionado!")

    elif page == "Meu carrinho":
        cart = st.session_state.cart

        if not cart:
            st.info("Seu carrinho está vazio.")
            return

        total = 0

        for product_id, item in list(cart.items()):
            c1, c2, c3 = st.columns([3, 2, 1])

            with c1:
                st.write(item["name"])

            with c2:
                qty = st.number_input(
                    "Quantidade",
                    min_value=0,
                    value=item["quantity"],
                    key=f"qty_{product_id}"
                )
                item["quantity"] = qty

            with c3:
                subtotal = qty * item["price"]
                st.write(money(subtotal))
                total += subtotal

        st.markdown(f"## Total: {money(total)}")

        if st.button("Limpar carrinho"):
            st.session_state.cart = {}
            st.rerun()

        if st.button(
            "Finalizar pelo WhatsApp",
            type="primary",
            use_container_width=True
        ):
            message = "Olá! Gostaria de fazer um pedido na CUBIA:\n\n"

            for item in cart.values():
                if item["quantity"] > 0:
                    message += (
                        f"- {item['name']} | "
                        f"{item['quantity']} unidade(s) | "
                        f"{money(item['price'] * item['quantity'])}\n"
                    )

            message += f"\nTotal: {money(total)}"
            message += "\n\nGostaria de confirmar meu pedido!"

            url = (
                f"https://wa.me/{WHATSAPP}"
                f"?text={quote(message)}"
            )

            st.link_button(
                "Abrir conversa no WhatsApp",
                url,
                use_container_width=True
            )

    else:
        st.title("Sobre a CUBIA")
        st.write(
            """
            A CUBIA é um laboratório 3D e de soluções
            inteligentes.

            Trabalhamos com impressão 3D, produtos
            personalizados, inteligência artificial,
            automação e tecnologia.
            """
        )

        st.write("Instagram: @cubia_impressao_3d")


# ==========================================
# ADMINISTRAÇÃO
# ==========================================

def admin_panel():

    supabase.auth.set_session(
        st.session_state.access_token,
        st.session_state.refresh_token
    )

    with st.sidebar:
        st.title("🦁 CUBIA")
        st.caption("Painel administrativo")

        menu = st.radio(
            "Menu",
            [
                "Dashboard",
                "Produtos",
                "Clientes",
                "Despesas",
                "Vendas",
                "Estoque de produtos",
                "Filamentos"
            ]
        )

        if st.button("Sair", use_container_width=True):
            try:
                supabase.auth.sign_out()
            finally:
                st.session_state.access_token = None
                st.session_state.refresh_token = None
                st.rerun()

    # ======================================
    # DASHBOARD
    # ======================================

    if menu == "Dashboard":
        st.title("Visão geral da CUBIA")

        sales = get_data("sales")
        expenses = get_data("expenses")
        clients = get_data("clients")
        products = get_data("products")

        today_month = date.today().strftime("%Y-%m")

        month_sales = [
            s for s in sales
            if s["sale_date"][:7] == today_month
        ]

        month_expenses = [
            e for e in expenses
            if e["competence_month"][:7] == today_month
        ]

        revenue = sum(
            float(s["total_amount"]) for s in month_sales
        )

        received = sum(
            float(s["received_amount"]) for s in month_sales
        )

        costs = sum(
            float(s["total_cost"]) for s in month_sales
        )

        expense_total = sum(
            float(e["amount"]) for e in month_expenses
        )

        pending_receivable = sum(
            float(s["total_amount"]) -
            float(s["received_amount"])
            for s in sales
        )

        pending_delivery = sum(
            1 for s in sales
            if s["delivery_status"] != "Entregue"
        )

        c1, c2, c3, c4 = st.columns(4)

        c1.metric("Vendas do mês", money(revenue))
        c2.metric("Recebido no mês", money(received))
        c3.metric("Despesas do mês", money(expense_total))
        c4.metric("A receber", money(pending_receivable))

        st.divider()

        c1, c2, c3 = st.columns(3)

        c1.metric("Lucro bruto estimado", money(revenue - costs))
        c2.metric("Clientes cadastrados", len(clients))
        c3.metric("Entregas pendentes", pending_delivery)

        st.caption(
            "Os indicadores são valores gerenciais preliminares. "
            "O resultado financeiro definitivo será calculado "
            "separando datas de competência e pagamento."
        )

        st.subheader("Vendas e despesas por mês")

        if sales or expenses:
            df_sales = pd.DataFrame(sales)
            df_expenses = pd.DataFrame(expenses)

            chart_data = {}

            if not df_sales.empty:
                df_sales["mes"] = df_sales["sale_date"].str[:7]
                chart_data["Vendas"] = (
                    df_sales.groupby("mes")["total_amount"].sum()
                )

            if not df_expenses.empty:
                df_expenses["mes"] = (
                    df_expenses["competence_month"].str[:7]
                )
                chart_data["Despesas"] = (
                    df_expenses.groupby("mes")["amount"].sum()
                )

            df = pd.DataFrame(chart_data).fillna(0)
            st.bar_chart(df)

    # ======================================
    # PRODUTOS
    # ======================================

    elif menu == "Produtos":
        st.title("Cadastro de produtos")

        with st.form("new_product"):
            name = st.text_input("Nome do produto")
            category = st.text_input("Categoria")
            description = st.text_area("Descrição")
            uploaded_image = st.file_uploader(
                "Foto do produto",
                type=["jpg", "jpeg", "png", "webp"],
                help="Escolha uma imagem da galeria do celular ou do computador."
            )
            if uploaded_image is not None:
                st.image(uploaded_image, caption="Prévia da imagem", width=220)

            price = st.number_input(
                "Preço de venda (R$)", min_value=0.0, step=1.0
            )
            cost = st.number_input(
                "Preço de custo unitário (R$)", min_value=0.0, step=0.5
            )
            stock = st.number_input(
                "Estoque inicial", min_value=0, step=1
            )
            active = st.checkbox("Produto ativo", value=True)
            submitted = st.form_submit_button("Salvar produto")

        if submitted:
            if not name.strip():
                st.error("Informe o nome do produto.")
            else:
                try:
                    image_url = upload_product_image(uploaded_image)
                    save_data("products", {
                        "name": name.strip(),
                        "category": category,
                        "description": description,
                        "image_url": image_url,
                        "price": price,
                        "cost_price": cost,
                        "stock_qty": stock,
                        "active": active
                    })
                    st.success("Produto cadastrado!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Não foi possível cadastrar o produto: {e}")

        st.divider()
        st.subheader("Produtos cadastrados")

        for p in get_data("products"):
            with st.expander(p["name"]):
                if p.get("image_url"):
                    st.image(p["image_url"], width=180)

                st.write("Categoria:", p.get("category"))
                st.write("Venda:", money(p["price"]))
                st.write("Custo:", money(p["cost_price"]))
                st.write("Estoque:", p["stock_qty"])
                st.write("Ativo:", p["active"])

                st.markdown("**Editar produto**")
                with st.form(f"edit_product_{p['id']}"):
                    edit_name = st.text_input(
                        "Nome do produto", value=p.get("name") or "",
                        key=f"name_{p['id']}"
                    )
                    edit_category = st.text_input(
                        "Categoria", value=p.get("category") or "",
                        key=f"category_{p['id']}"
                    )
                    edit_description = st.text_area(
                        "Descrição", value=p.get("description") or "",
                        key=f"description_{p['id']}"
                    )
                    replacement_image = st.file_uploader(
                        "Trocar foto (opcional)",
                        type=["jpg", "jpeg", "png", "webp"],
                        key=f"image_{p['id']}",
                        help="Sem uma nova foto, a imagem atual será mantida."
                    )
                    if replacement_image is not None:
                        st.image(
                            replacement_image,
                            caption="Prévia da nova imagem",
                            width=180
                        )

                    edit_price = st.number_input(
                        "Preço de venda (R$)", min_value=0.0,
                        value=float(p.get("price") or 0), step=1.0,
                        key=f"price_{p['id']}"
                    )
                    edit_cost = st.number_input(
                        "Preço de custo unitário (R$)", min_value=0.0,
                        value=float(p.get("cost_price") or 0), step=0.5,
                        key=f"cost_{p['id']}"
                    )
                    edit_stock = st.number_input(
                        "Estoque", min_value=0,
                        value=int(p.get("stock_qty") or 0), step=1,
                        key=f"stock_{p['id']}"
                    )
                    edit_active = st.checkbox(
                        "Produto ativo", value=bool(p.get("active")),
                        key=f"active_{p['id']}"
                    )
                    update_submitted = st.form_submit_button(
                        "Salvar alterações"
                    )

                if update_submitted:
                    if not edit_name.strip():
                        st.error("Informe o nome do produto.")
                    else:
                        try:
                            updated_image_url = p.get("image_url")
                            if replacement_image is not None:
                                updated_image_url = upload_product_image(
                                    replacement_image
                                )

                            supabase.table("products").update({
                                "name": edit_name.strip(),
                                "category": edit_category,
                                "description": edit_description,
                                "image_url": updated_image_url,
                                "price": edit_price,
                                "cost_price": edit_cost,
                                "stock_qty": edit_stock,
                                "active": edit_active
                            }).eq("id", p["id"]).execute()

                            st.success("Produto atualizado!")
                            st.rerun()
                        except Exception as e:
                            st.error(
                                f"Não foi possível atualizar o produto: {e}"
                            )

    # CLIENTES
    # ======================================

    elif menu == "Clientes":
        st.title("Cadastro de clientes")

        with st.form("new_client"):
            name = st.text_input("Nome")
            phone = st.text_input("Telefone / WhatsApp")
            notes = st.text_area("Observações")
            submitted = st.form_submit_button("Cadastrar cliente")

        if submitted:
            if name.strip() and phone.strip():
                save_data("clients", {
                    "name": name,
                    "phone": phone,
                    "notes": notes
                })
                st.success("Cliente cadastrado!")
                st.rerun()
            else:
                st.error("Preencha nome e telefone.")

        st.divider()

        clients = get_data("clients")

        if clients:
            st.dataframe(
                pd.DataFrame(clients)[
                    ["name", "phone", "notes"]
                ],
                use_container_width=True,
                hide_index=True
            )

    # ======================================
    # DESPESAS
    # ======================================

    elif menu == "Despesas":
        st.title("Registro de despesas")

        with st.form("new_expense"):
            expense_date = st.date_input(
                "Data do gasto", value=date.today()
            )
            competence = st.date_input(
                "Mês de competência",
                value=date.today().replace(day=1)
            )
            item = st.text_input("Item / descrição")
            quantity = st.number_input(
                "Quantidade", min_value=0.001,
                value=1.0, step=1.0
            )
            amount = st.number_input(
                "Valor total (R$)", min_value=0.0,
                step=1.0
            )
            notes = st.text_area("Observações")

            submitted = st.form_submit_button("Registrar despesa")

        if submitted:
            if item.strip() and amount > 0:
                save_data("expenses", {
                    "expense_date": str(expense_date),
                    "competence_month": str(competence),
                    "item": item,
                    "quantity": quantity,
                    "amount": amount,
                    "notes": notes
                })
                st.success("Despesa registrada!")
                st.rerun()
            else:
                st.error("Informe o item e o valor.")

        st.divider()
        expenses = get_data("expenses")

        if expenses:
            st.dataframe(
                pd.DataFrame(expenses),
                use_container_width=True,
                hide_index=True
            )

    # ======================================
    # VENDAS
    # ======================================

    elif menu == "Vendas":
        st.title("Registro de vendas")

        clients = get_data("clients")
        products = get_data("products")

        if not clients or not products:
            st.warning(
                "Cadastre pelo menos um cliente e um produto primeiro."
            )
        else:
            client_options = {
                f"{c['name']} | {c['phone']}": c["id"]
                for c in clients
            }

            product_options = {
                f"{p['name']} | {money(p['price'])}": p["id"]
                for p in products
            }

            client_label = st.selectbox(
                "Cliente", list(client_options.keys())
            )

            selected_labels = st.multiselect(
                "Produtos vendidos",
                list(product_options.keys())
            )

            quantities = {}

            for label in selected_labels:
                pid = product_options[label]
                quantities[pid] = st.number_input(
                    f"Quantidade: {label}",
                    min_value=1, value=1, step=1,
                    key=f"sale_{pid}"
                )

            sale_date = st.date_input(
                "Data da venda", value=date.today()
            )

            desired_date = st.date_input(
                "Data desejada pelo cliente",
                value=date.today()
            )

            received = st.number_input(
                "Valor recebido (R$)",
                min_value=0.0, step=1.0
            )

            payment_status = st.selectbox(
                "Situação do pagamento",
                ["Pendente", "Parcial", "Pago"]
            )

            delivery_status = st.selectbox(
                "Situação da entrega",
                ["Pendente", "Em produção", "Pronto", "Entregue"]
            )

            deduct_stock = st.checkbox(
                "Dar baixa no estoque dos produtos vendidos",
                value=True
            )

            notes = st.text_area("Observações")

            if st.button("Registrar venda", type="primary"):
                if not selected_labels:
                    st.error("Selecione pelo menos um produto.")
                else:
                    try:
                        sale = register_sale(
                            client_options[client_label],
                            [product_options[x] for x in selected_labels],
                            quantities,
                            sale_date,
                            desired_date,
                            received,
                            payment_status,
                            delivery_status,
                            notes,
                            deduct_stock
                        )
                        st.success(
                            f"Venda registrada! Pedido: {sale['id']}"
                        )
                        st.rerun()
                    except Exception as e:
                        st.error(f"Não foi possível registrar: {e}")

        st.divider()
        st.subheader("Histórico de vendas")

        sales = get_data("sales")

        if sales:
            for s in sales:
                with st.expander(
                    f"Pedido {s['id'][:8]} | {money(s['total_amount'])}"
                ):
                    client = next(
                        (c for c in clients if c["id"] == s["client_id"]),
                        None
                    )
                    st.write(
                        "Cliente:",
                        client["name"] if client else "Não identificado"
                    )
                    st.write("Data:", s["sale_date"])
                    st.write("Total:", money(s["total_amount"]))
                    st.write("Custo:", money(s["total_cost"]))
                    st.write("Recebido:", money(s["received_amount"]))
                    st.write("Pagamento:", s["payment_status"])
                    st.write("Entrega:", s["delivery_status"])
                    st.write("Observações:", s.get("notes") or "")

    # ======================================
    # ESTOQUE DE PRODUTOS
    # ======================================

    elif menu == "Estoque de produtos":
        st.title("Estoque de produtos")

        products = get_data("products")

        if products:
            for p in products:
                with st.expander(p["name"]):
                    st.write("Saldo atual:", p["stock_qty"])

                    adjustment = st.number_input(
                        "Quantidade de entrada (+) ou saída (-)",
                        value=0, step=1,
                        key=f"adjust_{p['id']}"
                    )

                    reason = st.text_input(
                        "Motivo da movimentação",
                        key=f"reason_{p['id']}"
                    )

                    if st.button(
                        "Confirmar movimentação",
                        key=f"move_{p['id']}"
                    ):
                        new_stock = p["stock_qty"] + adjustment

                        if adjustment == 0:
                            st.warning("Informe uma quantidade.")
                        elif new_stock < 0:
                            st.error("Estoque insuficiente.")
                        else:
                            supabase.table("products").update({
                                "stock_qty": new_stock
                            }).eq("id", p["id"]).execute()

                            save_data("stock_movements", {
                                "product_id": p["id"],
                                "movement_type": "Ajuste manual",
                                "quantity": adjustment,
                                "notes": reason
                            })

                            st.success("Estoque atualizado!")
                            st.rerun()

    # ======================================
    # FILAMENTOS
    # ======================================

    elif menu == "Filamentos":
        st.title("Estoque de filamentos")

        tab1, tab2, tab3 = st.tabs([
            "Cadastrar entrada",
            "Registrar consumo",
            "Consultar estoque"
        ])

        with tab1:
            with st.form("new_filament"):
                material = st.selectbox(
                    "Material", ["PLA", "PETG", "ABS", "TPU", "Outro"]
                )
                brand = st.text_input("Marca")
                color = st.text_input("Cor")
                grams = st.number_input(
                    "Quantidade comprada (g)",
                    min_value=1.0, value=1000.0
                )
                purchase_cost = st.number_input(
                    "Valor pago (R$)",
                    min_value=0.0, step=1.0
                )
                purchase_date = st.date_input(
                    "Data da compra", value=date.today()
                )
                notes = st.text_area("Observações")
                submitted = st.form_submit_button("Registrar entrada")

            if submitted:
                if color.strip() and purchase_cost > 0:
                    lot = save_data("filament_lots", {
                        "material": material,
                        "brand": brand,
                        "color": color,
                        "initial_grams": grams,
                        "remaining_grams": grams,
                        "purchase_cost": purchase_cost,
                        "purchase_date": str(purchase_date),
                        "notes": notes
                    }).data[0]

                    save_data("filament_movements", {
                        "lot_id": lot["id"],
                        "movement_type": "Entrada",
                        "quantity_grams": grams,
                        "unit_cost_snapshot": purchase_cost / grams,
                        "total_cost": purchase_cost,
                        "notes": "Compra de filamento"
                    })

                    st.success("Filamento cadastrado!")
                    st.rerun()
                else:
                    st.error("Informe cor e valor da compra.")

        with tab2:
            lots = get_data("filament_lots")
            products = get_data("products")

            available_lots = [
                l for l in lots if float(l["remaining_grams"]) > 0
            ]

            if not available_lots:
                st.info("Não há filamentos disponíveis.")
            else:
                lot_options = {
                    f"{l['material']} | {l['brand']} | {l['color']} | "
                    f"{float(l['remaining_grams']):.1f} g": l
                    for l in available_lots
                }

                selected_lot_label = st.selectbox(
                    "Filamento utilizado",
                    list(lot_options.keys())
                )

                selected_lot = lot_options[selected_lot_label]

                product_options = {
                    p["name"]: p["id"] for p in products
                }

                product_name = st.selectbox(
                    "Produto fabricado",
                    ["Não especificado"] + list(product_options.keys())
                )

                used_grams = st.number_input(
                    "Quantidade consumida (g)",
                    min_value=0.01, step=1.0
                )

                production_date = st.date_input(
                    "Data da produção", value=date.today()
                )

                production_notes = st.text_area(
                    "Observações da produção"
                )

                if st.button("Registrar consumo", type="primary"):
                    remaining = (
                        float(selected_lot["remaining_grams"])
                        - used_grams
                    )

                    if remaining < 0:
                        st.error("Quantidade maior que o saldo disponível.")
                    else:
                        unit_cost = (
                            float(selected_lot["purchase_cost"])
                            / float(selected_lot["initial_grams"])
                        )

                        total_cost = used_grams * unit_cost

                        product_id = (
                            product_options.get(product_name)
                            if product_name != "Não especificado"
                            else None
                        )

                        supabase.table("filament_lots").update({
                            "remaining_grams": remaining
                        }).eq("id", selected_lot["id"]).execute()

                        save_data("filament_movements", {
                            "lot_id": selected_lot["id"],
                            "movement_type": "Consumo",
                            "quantity_grams": used_grams,
                            "unit_cost_snapshot": unit_cost,
                            "total_cost": total_cost,
                            "product_id": product_id,
                            "production_date": str(production_date),
                            "notes": production_notes
                        })

                        st.success(
                            f"Consumo registrado! Custo: {money(total_cost)}"
                        )
                        st.rerun()

        with tab3:
            lots = get_data("filament_lots")

            if lots:
                df = pd.DataFrame(lots)
                df = df[[
                    "material", "brand", "color",
                    "initial_grams", "remaining_grams",
                    "purchase_cost", "purchase_date"
                ]]
                st.dataframe(
                    df,
                    use_container_width=True,
                    hide_index=True
                )

            st.subheader("Histórico de movimentações")

            movements = get_data("filament_movements")

            if movements:
                st.dataframe(
                    pd.DataFrame(movements),
                    use_container_width=True,
                    hide_index=True
                )


# ==========================================
# EXECUÇÃO
# ==========================================

st.sidebar.caption("CUBIA | Laboratório 3D e soluções inteligentes")

if st.session_state.access_token:
    try:
        admin_panel()
    except Exception:
        st.session_state.access_token = None
        st.session_state.refresh_token = None
        st.error("Sua sessão expirou. Entre novamente.")
        admin_login()
else:
    public_store()

    with st.sidebar:
        st.divider()
        if st.button("Área administrativa"):
            st.session_state.show_login = True

    if st.session_state.get("show_login", False):
        admin_login()
