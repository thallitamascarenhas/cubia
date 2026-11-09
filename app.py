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
        password = st.text_input("Senha", type="password")
        submitted = st.form_submit_button("Entrar", use_container_width=True)

    if submitted:
        try:
            result = supabase.auth.sign_in_with_password(
                {"email": email, "password": password}
            )
            st.session_state.access_token = result.session.access_token
            st.session_state.refresh_token = result.session.refresh_token
            st.rerun()
        except Exception as error:
            st.error(f"E-mail ou senha inválidos. Detalhe: {error}")


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

        st.divider()
        if st.button(
            "← Voltar à loja pública",
            use_container_width=True,
            type="primary"
        ):
            try:
                supabase.auth.sign_out()
            except Exception:
                # Mesmo se o encerramento remoto da sessão falhar,
                # removemos os tokens locais e voltamos à vitrine.
                pass
            st.session_state.access_token = None
            st.session_state.refresh_token = None
            st.session_state.show_login = False
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
        payments = get_data("sale_payments")
        filament_movements = get_data("filament_movements")

        today_month = date.today().strftime("%Y-%m")
        month_sales = [s for s in sales if (s.get("sale_date") or "")[:7] == today_month]
        month_expenses = [e for e in expenses if (e.get("competence_month") or "")[:7] == today_month]
        month_payments = [p for p in payments if (p.get("payment_date") or "")[:7] == today_month]

        total_sold = sum(float(s.get("total_amount") or 0) for s in month_sales)
        received_month = sum(float(p.get("amount") or 0) for p in month_payments)
        expense_total = sum(float(e.get("amount") or 0) for e in month_expenses)

        known_receivables = [s for s in sales if s.get("received_amount") is not None and s.get("total_amount") is not None]
        pending_receivable = sum(
            max(0, float(s["total_amount"]) - float(s["received_amount"]))
            for s in known_receivables
        )
        unknown_receivables = [s for s in sales if s.get("received_amount") is None]

        known_cost_sales = [s for s in month_sales if s.get("total_cost") is not None]
        unknown_cost_sales = [s for s in month_sales if s.get("total_cost") is None]
        known_production_cost = sum(float(s["total_cost"]) for s in known_cost_sales)
        estimated_result = total_sold - known_production_cost
        total_sold_all = sum(float(s.get("total_amount") or 0) for s in sales)
        total_received_known = sum(float(s.get("received_amount") or 0) for s in sales if s.get("received_amount") is not None)

        pending_production = sum(1 for s in sales if s.get("production_status") in ("Pendente de fabricação", "Em fabricação"))
        unknown_production = sum(1 for s in sales if s.get("production_status") is None)
        ready_waiting_delivery = sum(
            1 for s in sales
            if s.get("production_status") == "Fabricado"
            and s.get("delivery_status") in ("Pendente de entrega", "Pronto")
        )
        pending_delivery = sum(
            1 for s in sales
            if s.get("delivery_status") is not None
            and s.get("delivery_status") != "Entregue"
        )
        unknown_delivery = sum(1 for s in sales if s.get("delivery_status") is None)

        st.subheader("Movimentação do mês")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Vendido no mês", money(total_sold))
        c2.metric("Recebido no mês", money(received_month))
        c3.metric("Vendido acumulado", money(total_sold_all))
        c4.metric("Recebido acumulado conhecido", money(total_received_known))

        c1, c2, c3 = st.columns(3)
        c1.metric("Despesas do mês", money(expense_total))
        c2.metric("Custos de produção informados", money(known_production_cost))
        c3.metric("Margem estimada antes das despesas", money(estimated_result))

        st.caption(
            "A margem estimada considera vendas do mês menos custos de produção informados, antes das despesas. "
            "As despesas são exibidas separadamente porque compras de filamento podem já estar refletidas nos custos de produção. "
            "Não somamos novamente as movimentações de consumo de filamento. Custos e recebimentos desconhecidos permanecem distintos de zero."
        )

        st.divider()
        st.subheader("Contas a receber e produção")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("A receber conhecido", money(pending_receivable))
        c2.metric("Pedidos com recebimento desconhecido", len(unknown_receivables))
        c3.metric("Pendentes de fabricação", pending_production)
        c4.metric("Fabricados, não entregues", ready_waiting_delivery)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Custos de produção informados no mês", money(known_production_cost))
        c2.metric("Pedidos sem custo informado no mês", len(unknown_cost_sales))
        c3.metric("Entregas pendentes", pending_delivery)
        c4.metric("Situação de produção/entrega não informada", unknown_production + unknown_delivery)

        st.caption(
            f"Clientes cadastrados: {len(clients)} | Produtos cadastrados: {len(products)} | "
            f"Movimentações de filamento: {len(filament_movements)}. "
            "Os custos de filamento permanecem no histórico próprio e não são adicionados automaticamente aos custos dos pedidos."
        )

        st.subheader("Vendas e despesas por mês")
        if sales or expenses:
            chart_data = {}
            if sales:
                df_sales = pd.DataFrame(sales)
                df_sales["mes"] = df_sales["sale_date"].astype(str).str[:7]
                chart_data["Vendas"] = df_sales.groupby("mes")["total_amount"].sum(min_count=1)
            if expenses:
                df_expenses = pd.DataFrame(expenses)
                df_expenses["mes"] = df_expenses["competence_month"].astype(str).str[:7]
                chart_data["Despesas"] = df_expenses.groupby("mes")["amount"].sum(min_count=1)
            if chart_data:
                st.bar_chart(pd.DataFrame(chart_data).fillna(0))

        st.subheader("Recebimentos por mês")
        if payments:
            df_payments = pd.DataFrame(payments)
            df_payments = df_payments[df_payments["payment_date"].notna()]
            if not df_payments.empty:
                df_payments["mes"] = df_payments["payment_date"].astype(str).str[:7]
                st.bar_chart(df_payments.groupby("mes")["amount"].sum())
            else:
                st.info("Há pagamentos sem data informada. Eles não entram no gráfico mensal.")
        else:
            st.info("Ainda não há pagamentos individualizados registrados.")

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
        st.caption(
            "Cadastre, consulte e atualize os dados dos clientes da CUBIA. "
            "O histórico de vendas fica vinculado ao cadastro."
        )

        with st.form("new_client", clear_on_submit=True):
            st.subheader("Novo cliente")
            name = st.text_input("Nome completo")
            phone = st.text_input("Telefone / WhatsApp")
            notes = st.text_area("Observações")
            submitted = st.form_submit_button(
                "Cadastrar cliente", type="primary"
            )

        if submitted:
            if not name.strip() or not phone.strip():
                st.error("Preencha nome e telefone.")
            else:
                try:
                    save_data("clients", {
                        "name": name.strip(),
                        "phone": phone.strip(),
                        "notes": notes.strip()
                    })
                    st.success("Cliente cadastrado com sucesso!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Não foi possível cadastrar o cliente: {e}")

        st.divider()
        st.subheader("Clientes cadastrados")

        clients = get_data("clients")
        sales = get_data("sales")

        if not clients:
            st.info("Ainda não há clientes cadastrados.")
        else:
            search_client = st.text_input(
                "Buscar cliente por nome ou telefone",
                placeholder="Digite um nome ou número..."
            ).strip().lower()

            filtered_clients = [
                c for c in clients
                if search_client in (c.get("name") or "").lower()
                or search_client in (c.get("phone") or "").lower()
            ]

            st.caption(
                f"Exibindo {len(filtered_clients)} de {len(clients)} cliente(s)."
            )

            for client in filtered_clients:
                client_sales = [
                    s for s in sales
                    if s.get("client_id") == client["id"]
                ]
                total_purchases = sum(
                    float(s.get("total_amount") or 0)
                    for s in client_sales
                )

                with st.expander(
                    f"{client.get('name', 'Sem nome')} | "
                    f"{client.get('phone', 'Sem telefone')} "
                    f"| {len(client_sales)} venda(s)"
                ):
                    metric1, metric2 = st.columns(2)
                    metric1.metric("Total em compras", money(total_purchases))
                    metric2.metric("Quantidade de vendas", len(client_sales))

                    st.markdown("**Editar cadastro**")
                    with st.form(f"edit_client_{client['id']}"):
                        edit_name = st.text_input(
                            "Nome completo",
                            value=client.get("name") or "",
                            key=f"client_name_{client['id']}"
                        )
                        edit_phone = st.text_input(
                            "Telefone / WhatsApp",
                            value=client.get("phone") or "",
                            key=f"client_phone_{client['id']}"
                        )
                        edit_notes = st.text_area(
                            "Observações",
                            value=client.get("notes") or "",
                            key=f"client_notes_{client['id']}"
                        )
                        update_client = st.form_submit_button(
                            "Salvar alterações"
                        )

                    if update_client:
                        if not edit_name.strip() or not edit_phone.strip():
                            st.error("Nome e telefone são obrigatórios.")
                        else:
                            try:
                                supabase.table("clients").update({
                                    "name": edit_name.strip(),
                                    "phone": edit_phone.strip(),
                                    "notes": edit_notes.strip()
                                }).eq("id", client["id"]).execute()
                                st.success("Cadastro atualizado!")
                                st.rerun()
                            except Exception as e:
                                st.error(
                                    f"Não foi possível atualizar o cliente: {e}"
                                )

                    st.markdown("**Histórico de compras**")
                    if not client_sales:
                        st.info("Este cliente ainda não possui vendas.")
                    else:
                        for sale in sorted(
                            client_sales,
                            key=lambda item: item.get("sale_date") or "",
                            reverse=True
                        ):
                            st.markdown(
                                f"**Pedido {sale['id'][:8]}** | "
                                f"{sale.get('sale_date', 'Sem data')} | "
                                f"{money(sale.get('total_amount'))}"
                            )
                            st.caption(
                                f"Pagamento: {sale.get('payment_status', 'Não informado')} "
                                f"• Entrega: {sale.get('delivery_status', 'Não informado')}"
                            )
                            sale_items = get_data(
                                "sale_items", {"sale_id": sale["id"]}
                            )
                            if sale_items:
                                for item in sale_items:
                                    st.write(
                                        f"• {item.get('product_name', 'Produto')} "
                                        f"x {item.get('quantity', 0)}"
                                    )
                            st.divider()

            if not filtered_clients:
                st.warning("Nenhum cliente encontrado com essa busca.")

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
        st.title("Pedidos e pagamentos")
        st.caption("Pedidos personalizados, independentes do catálogo. Valores de custo e venda são totais por pedido.")

        clients = get_data("clients")
        client_labels = {"Sem cliente identificado": None}
        for c in clients:
            client_labels[f"{c.get('name', 'Sem nome')} | {c.get('phone', 'Sem telefone')} | {c['id'][:8]}"] = c["id"]

        with st.expander("＋ Cadastrar novo pedido", expanded=True):
            with st.form("new_custom_order", clear_on_submit=True):
                order_date = st.date_input("Data do pedido", value=date.today())
                order_description = st.text_area("Descrição do pedido", placeholder="Descreva livremente o item ou serviço")
                order_quantity_input = st.number_input("Quantidade (0 = não informada)", min_value=0, step=1, value=0)
                client_label = st.selectbox("Cliente (opcional)", list(client_labels.keys()))
                sale_total = st.number_input("Valor TOTAL da venda (R$)", min_value=0.01, step=1.0, format="%.2f")
                has_cost = st.checkbox("Informar custo total da produção")
                production_cost = st.number_input("Custo TOTAL da produção (R$)", min_value=0.0, step=1.0, format="%.2f", disabled=not has_cost)
                has_deadline = st.checkbox("Informar prazo de entrega")
                desired_date = st.date_input("Prazo de entrega", value=date.today(), disabled=not has_deadline)
                production_status = st.selectbox("Situação da fabricação", ["Pendente de fabricação", "Em fabricação", "Fabricado"])
                delivery_status = st.selectbox("Situação da entrega", ["Pendente de entrega", "Entregue"])
                initial_receipt_mode = st.selectbox(
                    "Informação inicial de recebimento",
                    ["Ainda não informado", "Nenhum valor recebido", "Registrar pagamento agora"]
                )
                initial_receipt = st.number_input(
                    "Valor do pagamento inicial (R$)", min_value=0.01, step=1.0,
                    format="%.2f", disabled=initial_receipt_mode != "Registrar pagamento agora"
                )
                initial_payment_date = st.date_input(
                    "Data do pagamento inicial", value=date.today(),
                    disabled=initial_receipt_mode != "Registrar pagamento agora"
                )
                initial_payment_method = st.text_input(
                    "Forma de pagamento", disabled=initial_receipt_mode != "Registrar pagamento agora"
                )
                order_notes = st.text_area("Observações")
                create_order = st.form_submit_button("Cadastrar pedido", type="primary", use_container_width=True)

            if create_order:
                if not order_description.strip():
                    st.error("Informe a descrição do pedido.")
                elif initial_receipt_mode == "Registrar pagamento agora" and initial_receipt > sale_total:
                    st.error("O pagamento inicial não pode superar o valor total da venda.")
                else:
                    try:
                        new_sale = {
                            "client_id": client_labels[client_label],
                            "sale_date": str(order_date),
                            "desired_date": str(desired_date) if has_deadline else None,
                            "total_amount": float(sale_total),
                            "total_cost": float(production_cost) if has_cost else None,
                            "received_amount": None if initial_receipt_mode == "Ainda não informado" else 0,
                            "payment_status": None if initial_receipt_mode == "Ainda não informado" else "Pendente",
                            "delivery_status": delivery_status,
                            "notes": order_notes.strip() or None,
                            "order_description": order_description.strip(),
                            "order_quantity": int(order_quantity_input) if order_quantity_input > 0 else None,
                            "production_status": production_status
                        }
                        created = save_data("sales", new_sale).data[0]
                        if initial_receipt_mode == "Registrar pagamento agora":
                            save_data("sale_payments", {
                                "sale_id": created["id"],
                                "amount": float(initial_receipt),
                                "payment_date": str(initial_payment_date),
                                "payment_method": initial_payment_method.strip() or None,
                                "notes": "Pagamento registrado no cadastro do pedido"
                            })
                        st.success(f"Pedido cadastrado: {created['id']}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Não foi possível cadastrar o pedido: {e}")

        st.divider()
        st.subheader("Histórico de pedidos")
        sales = get_data("sales")
        all_payments = get_data("sale_payments")
        sales = sorted(sales, key=lambda x: x.get("sale_date") or "", reverse=True)

        if not sales:
            st.info("Nenhum pedido cadastrado.")

        for sale in sales:
            sale_id = sale["id"]
            description = sale.get("order_description") or "Pedido antigo vinculado ao catálogo"
            title = f"{description[:55]} | {money(sale.get('total_amount'))} | {sale.get('sale_date', 'Sem data')}"
            with st.expander(title):
                linked_client = next((c for c in clients if c.get("id") == sale.get("client_id")), None)
                received_value = sale.get("received_amount")
                total_value = sale.get("total_amount")
                balance = None if received_value is None or total_value is None else max(0, float(total_value) - float(received_value))

                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Valor total da venda", money(total_value))
                m2.metric("Recebido", optional_money(received_value))
                m3.metric("Saldo a receber", "Desconhecido" if balance is None else money(balance))
                m4.metric("Custo total", optional_money(sale.get("total_cost")))
                st.caption(
                    f"Pagamento: {payment_label(sale)} | Fabricação: {sale.get('production_status') or 'Não informada'} | "
                    f"Entrega: {sale.get('delivery_status') or 'Não informada'}"
                )

                legacy_items = get_data("sale_items", {"sale_id": sale_id})
                if legacy_items:
                    st.markdown("**Itens originais do catálogo (histórico preservado)**")
                    for legacy in legacy_items:
                        st.write(
                            f"• {legacy.get('product_name') or 'Produto'} | "
                            f"Quantidade: {legacy.get('quantity')} | "
                            f"Preço unitário histórico: {money(legacy.get('unit_price'))}"
                        )

                st.markdown("**Editar pedido**")
                current_client_label = "Sem cliente identificado"
                if linked_client:
                    current_client_label = next(
                        (label for label, cid in client_labels.items() if cid == linked_client["id"]),
                        "Sem cliente identificado"
                    )
                with st.form(f"edit_order_{sale_id}"):
                    edit_date = st.date_input("Data do pedido", value=date.fromisoformat(str(sale.get("sale_date") or date.today())[:10]), key=f"edate_{sale_id}")
                    edit_description = st.text_area("Descrição", value=sale.get("order_description") or description, key=f"edesc_{sale_id}")
                    edit_qty = st.number_input("Quantidade (0 = não informada)", min_value=0, value=int(sale.get("order_quantity") or 0), step=1, key=f"eqty_{sale_id}")
                    edit_client_label = st.selectbox("Cliente", list(client_labels.keys()), index=list(client_labels.keys()).index(current_client_label) if current_client_label in client_labels else 0, key=f"eclient_{sale_id}")
                    edit_total = st.number_input("Valor TOTAL da venda (R$)", min_value=0.01, value=float(sale.get("total_amount") or 0.01), step=1.0, format="%.2f", key=f"etotal_{sale_id}")
                    edit_cost_known = st.checkbox("Custo total informado", value=sale.get("total_cost") is not None, key=f"ecostknown_{sale_id}")
                    edit_cost = st.number_input("Custo TOTAL da produção (R$)", min_value=0.0, value=float(sale.get("total_cost") or 0), step=1.0, format="%.2f", disabled=not edit_cost_known, key=f"ecost_{sale_id}")
                    edit_deadline_known = st.checkbox("Prazo de entrega informado", value=sale.get("desired_date") is not None, key=f"edeadlineknown_{sale_id}")
                    existing_deadline = date.fromisoformat(str(sale.get("desired_date") or date.today())[:10])
                    edit_deadline = st.date_input("Prazo de entrega", value=existing_deadline, disabled=not edit_deadline_known, key=f"edeadline_{sale_id}")
                    production_options = ["Pendente de fabricação", "Em fabricação", "Fabricado"]
                    old_production = sale.get("production_status")
                    if old_production and old_production not in production_options:
                        production_options.append(old_production)
                    edit_production = st.selectbox("Situação da fabricação", production_options, index=production_options.index(old_production) if old_production in production_options else 0, key=f"eproduction_{sale_id}")
                    delivery_options = ["Pendente de entrega", "Entregue"]
                    old_delivery = sale.get("delivery_status")
                    if old_delivery and old_delivery not in delivery_options:
                        delivery_options.append(old_delivery)
                    edit_delivery = st.selectbox("Situação da entrega", delivery_options, index=delivery_options.index(old_delivery) if old_delivery in delivery_options else 0, key=f"edelivery_{sale_id}")
                    edit_notes = st.text_area("Observações", value=sale.get("notes") or "", key=f"enotes_{sale_id}")
                    update_order = st.form_submit_button("Salvar alterações do pedido")

                if update_order:
                    if not edit_description.strip():
                        st.error("A descrição do pedido é obrigatória.")
                    else:
                        try:
                            supabase.table("sales").update({
                                "sale_date": str(edit_date),
                                "order_description": edit_description.strip(),
                                "order_quantity": int(edit_qty) if edit_qty > 0 else None,
                                "client_id": client_labels[edit_client_label],
                                "total_amount": float(edit_total),
                                "total_cost": float(edit_cost) if edit_cost_known else None,
                                "desired_date": str(edit_deadline) if edit_deadline_known else None,
                                "production_status": edit_production,
                                "delivery_status": edit_delivery,
                                "notes": edit_notes.strip() or None
                            }).eq("id", sale_id).execute()
                            st.success("Pedido atualizado.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Não foi possível atualizar o pedido: {e}")

                st.markdown("**Histórico de pagamentos**")
                sale_payments = [p for p in all_payments if p.get("sale_id") == sale_id]
                if sale_payments:
                    for payment in sorted(sale_payments, key=lambda x: x.get("payment_date") or ""):
                        pc1, pc2, pc3 = st.columns([2, 2, 1])
                        pc1.write(money(payment.get("amount")))
                        pc2.write(f"{payment.get('payment_date') or 'Data não informada'} | {payment.get('payment_method') or 'Forma não informada'}")
                        pc3.write(f"ID {payment['id'][:8]}")
                else:
                    st.info("Nenhum pagamento individual registrado. O recebimento pode continuar desconhecido ou ser zero conhecido, conforme o cadastro do pedido.")

                with st.form(f"new_payment_{sale_id}", clear_on_submit=True):
                    st.markdown("**Registrar novo pagamento**")
                    payment_amount = st.number_input("Valor recebido (R$)", min_value=0.01, step=1.0, format="%.2f", key=f"pamount_{sale_id}")
                    payment_date = st.date_input("Data do recebimento", value=date.today(), key=f"pdate_{sale_id}")
                    payment_method = st.text_input("Forma de pagamento", key=f"pmethod_{sale_id}")
                    payment_notes = st.text_input("Observação do pagamento", key=f"pnotes_{sale_id}")
                    add_payment = st.form_submit_button("Registrar pagamento")
                if add_payment:
                    try:
                        current_received = sale.get("received_amount")
                        if current_received is not None and float(current_received) + float(payment_amount) > float(sale.get("total_amount") or 0) + 0.000001:
                            st.error("O pagamento ultrapassa o saldo conhecido do pedido.")
                        else:
                            save_data("sale_payments", {
                                "sale_id": sale_id,
                                "amount": float(payment_amount),
                                "payment_date": str(payment_date),
                                "payment_method": payment_method.strip() or None,
                                "notes": payment_notes.strip() or None
                            })
                            st.success("Pagamento registrado. O banco recalculou o recebido e a situação.")
                            st.rerun()
                    except Exception as e:
                        st.error(f"Não foi possível registrar o pagamento: {e}")

                if sale_payments:
                    payment_options = {
                        f"{money(p.get('amount'))} | {p.get('payment_date') or 'Sem data'} | ID {p['id'][:8]}": p["id"]
                        for p in sale_payments
                    }
                    with st.form(f"delete_payment_{sale_id}"):
                        selected_payment_label = st.selectbox("Pagamento para excluir", list(payment_options.keys()), key=f"delpayselect_{sale_id}")
                        confirm_delete_payment = st.checkbox("Confirmo a exclusão deste pagamento", key=f"delpayconfirm_{sale_id}")
                        delete_payment = st.form_submit_button("Excluir pagamento selecionado")
                    if delete_payment:
                        if not confirm_delete_payment:
                            st.warning("Marque a confirmação para excluir.")
                        else:
                            try:
                                supabase.table("sale_payments").delete().eq("id", payment_options[selected_payment_label]).execute()
                                st.success("Pagamento excluído. O total recebido foi recalculado automaticamente.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Não foi possível excluir o pagamento: {e}")

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
    except Exception as e:
        st.session_state.access_token = None
        st.session_state.refresh_token = None
        st.error(f"A sessão administrativa expirou ou houve falha de acesso: {e}")
        admin_login()
else:
    public_store()

    with st.sidebar:
        st.divider()
        if st.button("Área administrativa"):
            st.session_state.show_login = True

    if st.session_state.get("show_login", False):
        admin_login()
