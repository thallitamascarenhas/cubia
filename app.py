                    ["Não especificado"] + list(product_options.keys())
                )

                used_grams = st.number_input(
                    "Quantidade consumida (g)",
                    min_value=0.01, step=1.0
                )

                production_date = st.date_input(
                    "Data da produção", value=date.today(), format="DD/MM/YYYY"
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

                        flash_success(
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
                if "purchase_date" in df.columns:
                    df["purchase_date"] = df["purchase_date"].apply(format_date)
                st.dataframe(
                    df,
                    use_container_width=True,
                    hide_index=True
                )

            st.subheader("Histórico de movimentações")

            movements = get_data("filament_movements")

            if movements:
                movements_df = pd.DataFrame(movements)
                for date_col in ("production_date",):
                    if date_col in movements_df.columns:
                        movements_df[date_col] = movements_df[date_col].apply(format_date)
                st.dataframe(
                    movements_df,
                    use_container_width=True,
                    hide_index=True
                )


# ==========================================
# EXECUÇÃO
# ==========================================

if st.session_state.access_token:
    try:
        admin_panel()
    except Exception as e:
        st.session_state.access_token = None
        st.session_state.refresh_token = None
        st.session_state.show_login = True
        st.error(f"A sessão administrativa expirou ou houve falha de acesso: {e}")
        admin_login()
elif st.session_state.get("show_login", False):
    admin_login()
else:
    public_store()
    with st.sidebar:
        st.divider()
        if st.button("Área administrativa", use_container_width=True):
            st.session_state.show_login = True
            st.rerun()
