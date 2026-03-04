import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import datetime
from data_engine import fetch_live_fund_data, calculate_metrics
from database import init_db, add_transaction, get_portfolio_summary, get_all_transactions, clear_database, \
    add_tracked_fund, remove_tracked_fund, get_tracked_funds
from prediction import run_monte_carlo_simulation, run_prophet_forecast
from translations import LANG

if 'language' not in st.session_state:
    st.session_state['language'] = 'TR'

selected_lang = st.sidebar.radio(
    "🌍 Dil / Language",
    options=["TR", "EN"],
    index=0 if st.session_state['language'] == 'TR' else 1,
    horizontal=True
)

st.session_state['language'] = selected_lang


def _(text_key):
    return LANG[st.session_state['language']].get(text_key, text_key)


st.set_page_config(page_title=_("app_title"), layout="wide")
init_db()
st.title(_("app_title"))
st.markdown("---")

if 'core_funds' not in st.session_state or 'satellite_funds' not in st.session_state:
    db_core, db_sat = get_tracked_funds()
    st.session_state.core_funds = db_core
    st.session_state.satellite_funds = db_sat

st.sidebar.header(_("portfolio_dist"))

if st.sidebar.button(_("refresh_data")):
    st.cache_data.clear()
    st.sidebar.success(_("clear_cache_success"))
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader(_("add_new_fund"))
new_fund_code = st.sidebar.text_input(_("new_fund_code")).upper()
new_fund_cat = st.sidebar.selectbox(_("choose_category"), ["Core", "Satellite"])

if st.sidebar.button(_("add_the_fund")):
    if new_fund_code:
        fund_list = [f.strip() for f in new_fund_code.split(',') if f.strip()]
        eklenenler = []

        internal_cat = "Core" if "Core" in new_fund_cat else "Satellite"

        for fund in fund_list:
            if internal_cat == "Core" and fund not in st.session_state.core_funds:
                st.session_state.core_funds.append(fund)
                add_tracked_fund(fund, "Core")
                eklenenler.append(fund)
            elif internal_cat == "Satellite" and fund not in st.session_state.satellite_funds:
                st.session_state.satellite_funds.append(fund)
                add_tracked_fund(fund, "Satellite")
                eklenenler.append(fund)

        if eklenenler:
            st.sidebar.success(f"{', '.join(eklenenler)} -> {internal_cat} " + _("added_to_the_list"))
            st.rerun()
        else:
            st.sidebar.warning(_("error_adding_existing"))

st.sidebar.markdown("---")
st.sidebar.subheader(_("delete_fund"))
all_current_funds = st.session_state.core_funds + st.session_state.satellite_funds
fund_to_remove = st.sidebar.selectbox(_("fund_to_removed"), [_("choose")] + all_current_funds)

if st.sidebar.button(_("remove_the_fund")):
    if fund_to_remove != _("choose"):
        if fund_to_remove in st.session_state.core_funds:
            st.session_state.core_funds.remove(fund_to_remove)
        elif fund_to_remove in st.session_state.satellite_funds:
            st.session_state.satellite_funds.remove(fund_to_remove)

        remove_tracked_fund(fund_to_remove)
        st.sidebar.success(f"{fund_to_remove}" + _("has_been_removed"))
        st.rerun()

my_funds = st.session_state.core_funds + st.session_state.satellite_funds

if not my_funds:
    st.warning(_("warning_no_fund"))
else:
    with st.spinner(_("data_fetching")):
        live_df = fetch_live_fund_data(my_funds)

    if live_df is not None and not live_df.empty:
        FUND_DICT = live_df.drop_duplicates(subset=['code']).set_index('code')['title'].to_dict()

        metrics_data = calculate_metrics(live_df)
        metrics_data = metrics_data.reset_index()

        # Dinamik DataFrame Sütunları
        metrics_data[_("fund_name")] = metrics_data['code'].apply(lambda x: FUND_DICT.get(x, f"{x} " + _("fund")))
        metrics_data[_("category")] = metrics_data['code'].apply(
            lambda x: "Core" if x in st.session_state.core_funds else "Satellite")


        def highlight_negatives(val):
            if isinstance(val, (int, float)) and val < 0:
                return 'color: #ff4b4b; font-weight: bold;'
            return ''


        aktif_sekme = st.radio(
            _("modules"),
            [_("live_analysis"), _("personal_portfolio"), _("monte_carlo_sim"), _("prophet_analysis")],
            horizontal=True,
            label_visibility="collapsed"
        )
        st.markdown("---")

        # Sekmeler dil seçimine göre değişeceği için çeviri fonksiyonuyla kontrol:
        if aktif_sekme == _("live_analysis"):

            metric_mapping = {
                _("weekly_return"): "Haftalık Getiri (%)",
                _("monthly_return"): "Aylık Getiri (%)",
                _("3month_return"): "3 Aylık Getiri (%)",
                _("ytd_return"): "YTD (%)",
                _("yearly_return"): "1 Yıllık Getiri (%)"
            }

            col1, col2 = st.columns(2)
            best_fund = metrics_data.sort_values(by='1 Yıllık Getiri (%)', ascending=False).iloc[0]
            col1.metric(f"{_('leader_fund')} -> {best_fund['code']}", f"%{best_fund['1 Yıllık Getiri (%)']}",
                        f"{_('price')}: {best_fund['Güncel Fiyat (TL)']} TL")
            bugun = datetime.date.today()

            if st.session_state['language'] == 'TR':
                aylar_tr = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
                            "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
                dinamik_tarih = f"{bugun.day} {aylar_tr[bugun.month - 1]} {bugun.year}"
            else:
                aylar_en = ["January", "February", "March", "April", "May", "June",
                            "July", "August", "September", "October", "November", "December"]
                dinamik_tarih = f"{aylar_en[bugun.month - 1]} {bugun.day}, {bugun.year}"

            col2.metric(_("system_date"), dinamik_tarih)

            st.markdown("---")
            st.subheader(_("time_series_analysis"))

            selected_label = st.radio(
                _("select_period"),
                list(metric_mapping.keys()),
                index=4, horizontal=True
            )
            selected_metric = metric_mapping[selected_label]

            def grafik_renk_belirle(row):
                if row[selected_metric] < 0:
                    return _("loss")
                return row[_("category")]

            metrics_data[_("color_group")] = metrics_data.apply(grafik_renk_belirle, axis=1)

            metrics_data["Bar_Text"] = metrics_data.apply(
                lambda x: f"{x['Güncel Fiyat (TL)']:.4f} TL (%{x[selected_metric]:.2f})", axis=1
            )

            c1, c2 = st.columns(2)

            with c1:
                fig_bar = px.bar(
                    metrics_data.sort_values(selected_metric, ascending=False),
                    x="code", y=selected_metric, color=_("color_group"),
                    text="Bar_Text",
                    hover_data=[_("fund_name"), "Güncel Fiyat (TL)"],
                    color_discrete_map={"Core": "#2ecc71", "Satellite": "#3498db", _("loss"): "#e74c3c"},
                    labels={
                        selected_metric: selected_label,
                        "code": _("code"),
                        "Güncel Fiyat (TL)": _("current_price")
                    }
                )
                fig_bar.update_traces(textposition='outside')
                st.plotly_chart(fig_bar, width='stretch')

            with c2:
                st.write(f"**{_('strategic_target')}**")

                core_ratio = st.slider(_("core_weight"), min_value=10, max_value=90, value=60, step=5)
                sat_ratio = 100 - core_ratio

                fig_pie = px.pie(values=[core_ratio, sat_ratio],
                                 names=[f"Core (%{core_ratio})", f"Satellite (%{sat_ratio})"],
                                 hole=0.4, color_discrete_sequence=["#27ae60", "#2980b9"])
                st.plotly_chart(fig_pie, width='stretch')

            st.markdown("---")
            st.subheader(_("comprehensive_table"))

            # dinamik sütun isimleriyle dataframe oluşturma:
            display_df = metrics_data[
                ['code', _("fund_name"), _("category"), 'Güncel Fiyat (TL)', 'Haftalık Getiri (%)', 'Aylık Getiri (%)',
                 '3 Aylık Getiri (%)', 'YTD (%)', '1 Yıllık Getiri (%)', 'Volatilite (Risk %)',
                 'Sharpe Oranı']].set_index('code')

            display_columns_map = {
                'Güncel Fiyat (TL)': _("current_price"),
                'Haftalık Getiri (%)': _("weekly_return"),
                'Aylık Getiri (%)': _("monthly_return"),
                '3 Aylık Getiri (%)': _("3month_return"),
                'YTD (%)': _("ytd_return"),
                '1 Yıllık Getiri (%)': _("yearly_return"),
                'Volatilite (Risk %)': _("volatility"),
                'Sharpe Oranı': _("sharpe_ratio")
            }
            display_df = display_df.rename(columns=display_columns_map)

            st.dataframe(
                display_df.style
                .map(highlight_negatives,
                     subset=[_("weekly_return"), _("monthly_return"), _("3month_return"), _("ytd_return"),
                             _("yearly_return"), _("sharpe_ratio")])
                .highlight_max(subset=[_("yearly_return"), _("sharpe_ratio")], color='rgba(46, 204, 113, 0.3)'),
                width='stretch'
            )

            st.markdown("---")
            st.subheader(_("smart_allocator"))
            yatirim_tutari = st.number_input(_("total_amount"), min_value=1000, value=350000, step=10000)

            core_sermaye = yatirim_tutari * (core_ratio / 100)
            satellite_sermaye = yatirim_tutari * (sat_ratio / 100)

            metrics_data['Optimum_Agirlik'] = metrics_data['Sharpe Oranı'].clip(lower=0.05)

            core_df = metrics_data[metrics_data[_("category")] == 'Core'].copy()
            sat_df = metrics_data[metrics_data[_("category")] == 'Satellite'].copy()

            core_df['Dağılım Oranı (%)'] = (core_df['Optimum_Agirlik'] / core_df['Optimum_Agirlik'].sum()) * 100
            sat_df['Dağılım Oranı (%)'] = (sat_df['Optimum_Agirlik'] / sat_df['Optimum_Agirlik'].sum()) * 100
            core_df['Hedef Bütçe (TL)'] = (core_df['Dağılım Oranı (%)'] / 100) * core_sermaye
            sat_df['Hedef Bütçe (TL)'] = (sat_df['Dağılım Oranı (%)'] / 100) * satellite_sermaye

            lot_df = pd.concat([core_df, sat_df])
            lot_df['Alınacak Adet (Lot)'] = lot_df['Hedef Bütçe (TL)'] / lot_df['Güncel Fiyat (TL)']

            final_lot_df = lot_df[
                ['code', _("fund_name"), _("category"), 'Dağılım Oranı (%)', 'Hedef Bütçe (TL)',
                 'Alınacak Adet (Lot)']].copy()
            final_lot_df['Dağılım Oranı (%)'] = final_lot_df['Dağılım Oranı (%)'].apply(lambda x: f"% {x:.1f}")
            final_lot_df['Hedef Bütçe (TL)'] = final_lot_df['Hedef Bütçe (TL)'].apply(lambda x: f"{x:,.2f} TL")
            final_lot_df['Alınacak Adet (Lot)'] = final_lot_df['Alınacak Adet (Lot)'].apply(lambda x: f"{x:,.3f}")

            final_lot_df = final_lot_df.rename(columns={
                'Dağılım Oranı (%)': _("allocation_ratio"),
                'Hedef Bütçe (TL)': _("target_budget"),
                'Alınacak Adet (Lot)': _("lot_to_buy")
            })

            st.dataframe(final_lot_df.set_index('code').sort_values(by=[_("category"), _("allocation_ratio")],
                                                                    ascending=[True, False]), width='stretch')

        elif aktif_sekme == _("personal_portfolio"):

            st.subheader(_("current_portfolio_status"))

            port_df = get_portfolio_summary()

            if not port_df.empty:

                merged_port = pd.merge(port_df, metrics_data[['code', 'Güncel Fiyat (TL)']], left_on='Fon Kodu', right_on='code', how='left')
                merged_port['Güncel Değer (TL)'] = merged_port['Sahip Olunan Lot'] * merged_port['Güncel Fiyat (TL)']

                merged_port['Net Kâr/Zarar (TL)'] = merged_port['Güncel Değer (TL)'] - merged_port[
                    'Yatırılan Ana Para (TL)']

                merged_port['Getiri Oranı (%)'] = (merged_port['Net Kâr/Zarar (TL)'] / merged_port[
                    'Yatırılan Ana Para (TL)']) * 100

                display_port = merged_port[
                    ['Fon Kodu', 'Sahip Olunan Lot', 'Ortalama Maliyet (TL)', 'Güncel Fiyat (TL)',
                     'Yatırılan Ana Para (TL)', 'Güncel Değer (TL)', 'Net Kâr/Zarar (TL)', 'Getiri Oranı (%)']]

                port_columns_map = {
                    'Fon Kodu': _("code"),
                    'Sahip Olunan Lot': _("owned_lots"),
                    'Ortalama Maliyet (TL)': _("avg_cost"),
                    'Güncel Fiyat (TL)': _("current_price"),
                    'Yatırılan Ana Para (TL)': _("invested_principal"),
                    'Güncel Değer (TL)': _("current_value"),
                    'Net Kâr/Zarar (TL)': _("net_profit_loss"),
                    'Getiri Oranı (%)': _("return_rate")
                }

                display_port = display_port.rename(columns=port_columns_map)
                st.dataframe(display_port.set_index(_("code")).style.map(highlight_negatives,
                                                                         subset=[_("net_profit_loss"),
                                                                                 _("return_rate")]).format("{:.2f}",

                                                                                                           subset=[
                                                                                                               _("avg_cost"),
                                                                                                               _("current_price"),
                                                                                                               _("invested_principal"),
                                                                                                               _("current_value"),
                                                                                                               _("net_profit_loss"),
                                                                                                               _("return_rate")]),
                             width='stretch')

                m1, m2, m3 = st.columns(3)
                m1.metric(_("total_invested"), f"{merged_port['Yatırılan Ana Para (TL)'].sum():,.2f} TL")
                m2.metric(_("current_portfolio_value"), f"{merged_port['Güncel Değer (TL)'].sum():,.2f} TL")
                m3.metric(_("total_profit_loss"),
                          f"{(merged_port['Güncel Değer (TL)'].sum() - merged_port['Yatırılan Ana Para (TL)'].sum()):,.2f} TL")

            else:
                st.info(_("no_transactions"))
            st.markdown("---")
            c_form, c_history = st.columns([1, 2])
            with c_form:
                st.subheader(_("new_transaction"))
                with st.form("islem_ekle_form"):
                    islem_tarihi = st.date_input(_("transaction_date"))
                    islem_fon = st.selectbox(_("fund_code_label"), my_funds)
                    islem_tipi_ui = st.selectbox(_("transaction_type"), [_("buy"), _("sell")])
                    islem_tutar = st.number_input(_("transaction_amount"), min_value=1.0, step=100.0)
                    islem_fiyat = st.number_input(_("unit_price"), min_value=0.0001, step=0.01, format="%.4f")

                    if st.form_submit_button(_("save_transaction")):
                        db_islem_tipi = "ALIM" if islem_tipi_ui == _("buy") else "SATIM"

                        add_transaction(islem_fon, db_islem_tipi, islem_tutar,
                                        (islem_tutar / islem_fiyat if islem_fiyat > 0 else 0), islem_fiyat,
                                        islem_tarihi.strftime("%Y-%m-%d"))
                        st.success(_("transaction_saved"))
                        st.rerun()

            with c_history:
                st.subheader(_("transaction_history"))
                history_df = get_all_transactions()
                if not history_df.empty:
                    st.dataframe(history_df.sort_values(by="id", ascending=False).set_index("id"), width='stretch')
                    with st.expander(_("db_management")):
                        st.warning(_("db_warning"))
                        if st.button(_("reset_db")):
                            clear_database()
                            st.success(_("db_cleared"))
                            st.rerun()
                else:
                    st.write(_("no_records"))

        elif aktif_sekme == _("monte_carlo_sim"):
            st.subheader(_("mc_title"))
            st.info(_("mc_info"))
            with st.form("monte_carlo_form"):
                selected_pred_fund = st.selectbox(_("select_fund_mc"), my_funds)
                submit_mc = st.form_submit_button(_("start_sim"))
            if submit_mc:
                with st.spinner(f"{selected_pred_fund} {_('calculating_mc')}"):
                    fund_history = live_df[live_df['code'] == selected_pred_fund]['price']
                    if len(fund_history) < 30:
                        st.warning(_("insufficient_data"))
                    else:
                        st.session_state['mc_results'] = run_monte_carlo_simulation(fund_history, days_to_simulate=30,
                                                                                    num_simulations=1000)
                        st.session_state['mc_fund'] = selected_pred_fund

            if 'mc_results' in st.session_state and st.session_state.get('mc_fund') == selected_pred_fund:
                mc_results = st.session_state['mc_results']
                st.markdown(f"**{selected_pred_fund} {_('price_dist_30d')}**")
                c1, c2, c3, c4, c5 = st.columns(5)
                c1.metric(_("worst") + " (%5)", f"{mc_results['worst']:.4f}",
                          f"{((mc_results['worst'] / mc_results['last_price']) - 1) * 100:.2f}%")
                c2.metric(_("lower_quartile") + " (%25)", f"{mc_results['p25']:.4f}",
                          f"{((mc_results['p25'] / mc_results['last_price']) - 1) * 100:.2f}%")
                c3.metric(_("median") + " (%50)", f"{mc_results['median']:.4f}",
                          f"{((mc_results['median'] / mc_results['last_price']) - 1) * 100:.2f}%")
                c4.metric(_("upper_quartile") + " (%75)", f"{mc_results['p75']:.4f}",
                          f"{((mc_results['p75'] / mc_results['last_price']) - 1) * 100:.2f}%")
                c5.metric(_("best") + " (%95)", f"{mc_results['best']:.4f}",
                          f"{((mc_results['best'] / mc_results['last_price']) - 1) * 100:.2f}%")

                st.markdown("---")
                col_hist, col_lines = st.columns([1, 1])

                with col_hist:
                    st.write(f"**{_('histogram_title')}**")
                    final_prices = mc_results['simulations'][-1, :]
                    fig_hist = px.histogram(
                        x=final_prices, nbins=50,
                        labels={'x': _('possible_price'), 'y': _('scenario_count')},
                        color_discrete_sequence=['#9b59b6']
                    )
                    fig_hist.add_vline(x=mc_results['last_price'], line_dash="dot", line_color="white",
                                       annotation_text=_("current_price_line"))
                    fig_hist.update_layout(showlegend=False, xaxis_title=_("possible_price"),
                                           yaxis_title=_("scenario_count"))
                    st.plotly_chart(fig_hist, width='stretch', key="hist")

                with col_lines:
                    st.write(f"**{_('possible_paths')}**")
                    sim_df = pd.DataFrame(mc_results['simulations'][:, :50])
                    fig_mc = px.line(sim_df, labels={"value": _("price"), "index": _("days"), "variable": "Senaryo"})
                    fig_mc.update_layout(showlegend=False, xaxis_title=_("days"), yaxis_title=_("price"))
                    fig_mc.add_hline(y=mc_results['last_price'], line_dash="dot", line_color="white",
                                     annotation_text=_("current_price_line"))
                    st.plotly_chart(fig_mc, width='stretch', key="lines")

        elif aktif_sekme == _("prophet_analysis"):
            st.subheader(_("prophet_title"))
            st.info(_("prophet_info"))

            with st.form("prophet_form"):
                selected_prophet_fund = st.selectbox(_("select_fund_prophet"), my_funds)
                submit_prophet = st.form_submit_button(_("generate_forecast"))

            if submit_prophet:
                with st.spinner(f"{selected_prophet_fund} {_('training_prophet')}"):
                    fund_data = live_df[live_df['code'] == selected_prophet_fund].copy()

                    if len(fund_data) < 60:
                        st.warning(_("insufficient_data_prophet"))
                    else:
                        forecast, model = run_prophet_forecast(fund_data, days_to_predict=30)
                        st.session_state['prophet_forecast'] = forecast
                        st.session_state['prophet_fund'] = selected_prophet_fund
                        st.session_state['prophet_historical'] = fund_data

            if 'prophet_forecast' in st.session_state and st.session_state.get('prophet_fund') == selected_prophet_fund:
                forecast = st.session_state['prophet_forecast']
                historical = st.session_state['prophet_historical']

                last_actual_price = historical['price'].iloc[-1]
                future_30d_price = forecast['yhat'].iloc[-1]
                future_30d_lower = forecast['yhat_lower'].iloc[-1]
                future_30d_upper = forecast['yhat_upper'].iloc[-1]

                st.markdown(f"**{selected_prophet_fund} {_('prophet_30d_exp')}**")

                p1, p2, p3 = st.columns(3)
                p1.metric(_("current_actual_price"), f"{last_actual_price:.4f} TL")
                p2.metric(_("trend_target_30d"), f"{future_30d_price:.4f} TL",
                          f"{((future_30d_price / last_actual_price) - 1) * 100:.2f}%", delta_color="normal")
                p3.metric(_("prophet_confidence"), f"{future_30d_lower:.4f} - {future_30d_upper:.4f} TL")

                st.markdown("---")

                fig_prophet = go.Figure()

                # Gerçek Fiyat Çizgisi
                fig_prophet.add_trace(
                    go.Scatter(x=historical['date'], y=historical['price'], mode='lines', name=_("actual_price"),
                               line=dict(color='#2ecc71', width=2)))

                # Gelecek Tahmin Çizgisi
                future_forecast = forecast[forecast['ds'] > historical['date'].max()]
                fig_prophet.add_trace(
                    go.Scatter(x=future_forecast['ds'], y=future_forecast['yhat'], mode='lines',
                               name=_("prophet_trend"),
                               line=dict(color='#e74c3c', dash='dash', width=2)))

                # Güvenlik Konisi
                fig_prophet.add_trace(go.Scatter(
                    x=pd.concat([future_forecast['ds'], future_forecast['ds'][::-1]]),
                    y=pd.concat([future_forecast['yhat_upper'], future_forecast['yhat_lower'][::-1]]),
                    fill='toself',
                    fillcolor='rgba(231, 76, 60, 0.2)',
                    line=dict(color='rgba(255,255,255,0)'),
                    hoverinfo="skip",
                    showlegend=True,
                    name=_("confidence_cone")
                ))

                fig_prophet.update_layout(title=f"{selected_prophet_fund} {_('past_trend_future_proj')}",
                                          xaxis_title=_("date"), yaxis_title=_("price"))
                fig_prophet.add_vline(x=historical['date'].max(), line_dash="dot", line_color="white")

                st.plotly_chart(fig_prophet, width='stretch')
    else:
        st.error(_("fetch_error"))