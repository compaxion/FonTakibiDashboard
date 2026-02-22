import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from data_engine import fetch_live_fund_data, calculate_metrics
from database import init_db, add_transaction, get_portfolio_summary, get_all_transactions, clear_database, add_tracked_fund, remove_tracked_fund, get_tracked_funds
from prediction import run_monte_carlo_simulation, run_prophet_forecast

st.set_page_config(page_title="Fon Takibi", layout="wide")
init_db()
st.title("Fon Takibi")
st.markdown("---")

if 'core_funds' not in st.session_state or 'satellite_funds' not in st.session_state:
    db_core, db_sat = get_tracked_funds()
    st.session_state.core_funds = db_core
    st.session_state.satellite_funds = db_sat

st.sidebar.header("Portföy Yönetimi")

if st.sidebar.button("Piyasa Verilerini Yenile"):
    st.cache_data.clear()
    st.sidebar.success("Önbellek temizlendi. Canlı veriler çekiliyor...")
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("Yeni Fon Ekle")
new_fund_code = st.sidebar.text_input("Fon Kodu (Örn: MAC, ACC, IIH):").upper()
# Arayüzdeki şık ve uzun metinlerin kalabilir
new_fund_cat = st.sidebar.selectbox("Kategori Seçin:", ["Core - Uzun Vade", "Satellite - Al-Sat"])

if st.sidebar.button("Fonu Ekle"):
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
            st.sidebar.success(f"{', '.join(eklenenler)} -> {internal_cat} listesine eklendi.")
            st.rerun()
        else:
            st.sidebar.warning("Girdiğiniz fon(lar) zaten listede mevcut veya geçersiz.")

st.sidebar.markdown("---")
st.sidebar.subheader("Fon Çıkar")
all_current_funds = st.session_state.core_funds + st.session_state.satellite_funds
fund_to_remove = st.sidebar.selectbox("Kaldırılacak Fonu Seçin:", ["Seçiniz..."] + all_current_funds)

if st.sidebar.button("Fonu Kaldır"):
    if fund_to_remove != "Seçiniz...":
        if fund_to_remove in st.session_state.core_funds:
            st.session_state.core_funds.remove(fund_to_remove)
        elif fund_to_remove in st.session_state.satellite_funds:
            st.session_state.satellite_funds.remove(fund_to_remove)

        remove_tracked_fund(fund_to_remove)
        st.sidebar.success(f"{fund_to_remove} listeden çıkarıldı ve veritabanı güncellendi.")
        st.rerun()

my_funds = st.session_state.core_funds + st.session_state.satellite_funds

if not my_funds:
    st.warning("Takip listesinde hiç fon bulunmuyor. Lütfen sol menüden fon ekleyin.")
else:
    with st.spinner('Piyasa verileri canlı olarak işleniyor...'):
        live_df = fetch_live_fund_data(my_funds)

    if live_df is not None and not live_df.empty:
        FUND_DICT = live_df.drop_duplicates(subset=['code']).set_index('code')['title'].to_dict()

        metrics_data = calculate_metrics(live_df)
        metrics_data = metrics_data.reset_index()

        metrics_data['Fon Adı'] = metrics_data['code'].apply(lambda x: FUND_DICT.get(x, f"{x} Fonu"))
        metrics_data['Kategori'] = metrics_data['code'].apply(
            lambda x: "Core" if x in st.session_state.core_funds else "Satellite")


        def highlight_negatives(val):
            if isinstance(val, (int, float)) and val < 0:
                return 'color: #ff4b4b; font-weight: bold;'
            return ''


        aktif_sekme = st.radio(
            "Modüller",
            ["Canlı Analiz ve Dağılım", "Kişisel Portföyüm ve İşlemler", "Monte Carlo Simülasyonu","Prophet Trend Analizi"],
            horizontal=True,
            label_visibility="collapsed"
        )
        st.markdown("---")

        if aktif_sekme == "Canlı Analiz ve Dağılım":
            col1, col2 = st.columns(2)
            best_fund = metrics_data.sort_values(by='1 Yıllık Getiri (%)', ascending=False).iloc[0]
            col1.metric(f"Lider Fon (1 Yıllık) -> {best_fund['code']}", f"%{best_fund['1 Yıllık Getiri (%)']}",
                        f"Fiyat: {best_fund['Güncel Fiyat (TL)']} TL")
            col2.metric("Sistem Başlangıç", "13 Mart 2026")

            st.markdown("---")
            st.subheader("Zaman Serisi Analizi")

            selected_metric = st.radio(
                "Grafikte Gösterilecek Periyodu Seçin:",
                ["Haftalık Getiri (%)", "Aylık Getiri (%)", "3 Aylık Getiri (%)", "YTD (%)", "1 Yıllık Getiri (%)"],
                index=4, horizontal=True
            )


            def belirle_grafik_rengi(row):
                if row[selected_metric] < 0:
                    return "Zarar"
                return row["Kategori"]


            metrics_data['Renk_Grubu'] = metrics_data.apply(belirle_grafik_rengi, axis=1)
            c1, c2 = st.columns(2)

            with c1:
                fig_bar = px.bar(
                    metrics_data.sort_values(selected_metric, ascending=False),
                    x="code", y=selected_metric, color="Renk_Grubu",
                    text="Güncel Fiyat (TL)", hover_data=["Fon Adı"],
                    color_discrete_map={"Core": "#2ecc71", "Satellite": "#3498db", "Zarar": "#e74c3c"}
                )
                fig_bar.update_traces(textposition='outside')
                st.plotly_chart(fig_bar, width='stretch')

            with c2:
                st.write("**Stratejik Hedef Dağılımı**")

                core_ratio = st.slider("Core (Uzun Vade) Ağırlığı (%)", min_value=10, max_value=90, value=60, step=5)
                sat_ratio = 100 - core_ratio

                fig_pie = px.pie(values=[core_ratio, sat_ratio],
                                 names=[f"Core (%{core_ratio})", f"Satellite (%{sat_ratio})"],
                                 hole=0.4, color_discrete_sequence=["#27ae60", "#2980b9"])
                st.plotly_chart(fig_pie, width='stretch')

            st.markdown("---")
            st.subheader("Kapsamlı Sistem Tablosu")

            display_df = metrics_data[
                ['code', 'Fon Adı', 'Kategori', 'Güncel Fiyat (TL)', 'Haftalık Getiri (%)', 'Aylık Getiri (%)',
                 '3 Aylık Getiri (%)', 'YTD (%)', '1 Yıllık Getiri (%)', 'Volatilite (Risk %)',
                 'Sharpe Oranı']].set_index('code')
            st.dataframe(
                display_df.style
                .map(highlight_negatives,
                     subset=['Haftalık Getiri (%)', 'Aylık Getiri (%)', '3 Aylık Getiri (%)', 'YTD (%)',
                             '1 Yıllık Getiri (%)', 'Sharpe Oranı'])
                .highlight_max(subset=['1 Yıllık Getiri (%)', 'Sharpe Oranı'], color='rgba(46, 204, 113, 0.3)'),
                width='stretch'
            )

            st.markdown("---")
            st.subheader("Akıllı Portföy Dağıtıcısı (Sharpe Optimizasyonu)")
            yatirim_tutari = st.number_input("Dağıtılacak Toplam Tutarı Girin (TL):", min_value=1000, value=350000,
                                             step=10000)

            core_sermaye = yatirim_tutari * (core_ratio / 100)
            satellite_sermaye = yatirim_tutari * (sat_ratio / 100)

            metrics_data['Optimum_Agirlik'] = metrics_data['Sharpe Oranı'].clip(lower=0.05)

            core_df = metrics_data[metrics_data['Kategori'] == 'Core'].copy()
            sat_df = metrics_data[metrics_data['Kategori'] == 'Satellite'].copy()

            core_df['Dağılım Oranı (%)'] = (core_df['Optimum_Agirlik'] / core_df['Optimum_Agirlik'].sum()) * 100
            sat_df['Dağılım Oranı (%)'] = (sat_df['Optimum_Agirlik'] / sat_df['Optimum_Agirlik'].sum()) * 100
            core_df['Hedef Bütçe (TL)'] = (core_df['Dağılım Oranı (%)'] / 100) * core_sermaye
            sat_df['Hedef Bütçe (TL)'] = (sat_df['Dağılım Oranı (%)'] / 100) * satellite_sermaye

            lot_df = pd.concat([core_df, sat_df])
            lot_df['Alınacak Adet (Lot)'] = lot_df['Hedef Bütçe (TL)'] / lot_df['Güncel Fiyat (TL)']

            final_lot_df = lot_df[
                ['code', 'Fon Adı', 'Kategori', 'Dağılım Oranı (%)', 'Hedef Bütçe (TL)', 'Alınacak Adet (Lot)']].copy()
            final_lot_df['Dağılım Oranı (%)'] = final_lot_df['Dağılım Oranı (%)'].apply(lambda x: f"% {x:.1f}")
            final_lot_df['Hedef Bütçe (TL)'] = final_lot_df['Hedef Bütçe (TL)'].apply(lambda x: f"{x:,.2f} TL")
            final_lot_df['Alınacak Adet (Lot)'] = final_lot_df['Alınacak Adet (Lot)'].apply(lambda x: f"{x:,.3f}")

            st.dataframe(final_lot_df.set_index('code').sort_values(by=['Kategori', 'Dağılım Oranı (%)'],
                                                                    ascending=[True, False]), width='stretch')

        elif aktif_sekme == "Kişisel Portföyüm ve İşlemler":
            st.subheader("Anlık Portföy Durumu (Kâr / Zarar)")
            port_df = get_portfolio_summary()
            if not port_df.empty:
                merged_port = pd.merge(port_df, metrics_data[['code', 'Güncel Fiyat (TL)']], left_on='Fon Kodu', right_on='code', how='left')
                merged_port['Güncel Değer (TL)'] = merged_port['Sahip Olunan Lot'] * merged_port['Güncel Fiyat (TL)']
                merged_port['Net Kâr/Zarar (TL)'] = merged_port['Güncel Değer (TL)'] - merged_port['Yatırılan Ana Para (TL)']
                merged_port['Getiri Oranı (%)'] = (merged_port['Net Kâr/Zarar (TL)'] / merged_port['Yatırılan Ana Para (TL)']) * 100
                display_port = merged_port[
                    ['Fon Kodu', 'Sahip Olunan Lot', 'Ortalama Maliyet (TL)', 'Güncel Fiyat (TL)', 'Yatırılan Ana Para (TL)', 'Güncel Değer (TL)', 'Net Kâr/Zarar (TL)', 'Getiri Oranı (%)']]
                st.dataframe(display_port.set_index('Fon Kodu').style.map(highlight_negatives,
                                                                          subset=['Net Kâr/Zarar (TL)', 'Getiri Oranı (%)']).format("{:.2f}",
                                                                                                                                    subset=['Ortalama Maliyet (TL)', 'Güncel Fiyat (TL)', 'Yatırılan Ana Para (TL)', 'Güncel Değer (TL)', 'Net Kâr/Zarar (TL)', 'Getiri Oranı (%)']), width='stretch')
                m1, m2, m3 = st.columns(3)
                m1.metric("Toplam Yatırılan Ana Para", f"{display_port['Yatırılan Ana Para (TL)'].sum():,.2f} TL")
                m2.metric("Portföyün Güncel Değeri", f"{display_port['Güncel Değer (TL)'].sum():,.2f} TL")
                m3.metric("Toplam Kâr / Zarar", f"{(display_port['Güncel Değer (TL)'].sum() - display_port['Yatırılan Ana Para (TL)'].sum()):,.2f} TL")
            else:
                st.info("Henüz sisteme işlenmiş bir alım-satım kaydı bulunmuyor.")

            st.markdown("---")
            c_form, c_history = st.columns([1, 2])
            with c_form:
                st.subheader("Yeni İşlem Gir")
                with st.form("islem_ekle_form"):
                    islem_tarihi = st.date_input("İşlem Tarihi")
                    islem_fon = st.selectbox("Fon Kodu", my_funds)
                    islem_tipi = st.selectbox("İşlem Tipi", ["ALIM", "SATIM"])
                    islem_tutar = st.number_input("İşlem Tutarı (TL)", min_value=1.0, step=100.0)
                    islem_fiyat = st.number_input("Gerçekleşen Birim Fiyat (TL)", min_value=0.0001, step=0.01, format="%.4f")
                    if st.form_submit_button("İşlemi Kaydet"):
                        add_transaction(islem_fon, islem_tipi, islem_tutar,
                                        (islem_tutar / islem_fiyat if islem_fiyat > 0 else 0), islem_fiyat, islem_tarihi.strftime("%Y-%m-%d"))
                        st.success("İşlem başarıyla veritabanına kaydedildi.")
                        st.rerun()
            with c_history:
                st.subheader("İşlem Geçmişi (Ledger)")
                history_df = get_all_transactions()
                if not history_df.empty:
                    st.dataframe(history_df.sort_values(by="id", ascending=False).set_index("id"), width='stretch')
                    with st.expander("Veritabanı Yönetimi (Tehlikeli Bölge)"):
                        st.warning("Tüm işlem geçmişiniz kalıcı olarak silinecektir. Bu işlem geri alınamaz!")
                        if st.button("Tüm Veritabanını Sıfırla"):
                            clear_database()
                            st.success("Veritabanı başarıyla temizlendi!")
                            st.rerun()
                else:
                    st.write("Kayıt bulunamadı.")

        elif aktif_sekme == "Monte Carlo Simülasyonu":
            st.subheader("Monte Carlo Simülasyonu (30 Günlük Tahmin)")
            st.info(
                "Bu model fonun geçmiş volatilitesini kullanarak önümüzdeki 30 gün için 1.000 farklı rastgele fiyat senaryosu hesaplar.")
            with st.form("monte_carlo_form"):
                selected_pred_fund = st.selectbox("Simülasyon Yapılacak Fonu Seçin:", my_funds)
                submit_mc = st.form_submit_button("Simülasyonu Başlat")
            if submit_mc:
                with st.spinner(f"{selected_pred_fund} için 1.000 farklı paralel evren hesaplanıyor..."):
                    fund_history = live_df[live_df['code'] == selected_pred_fund]['price']
                    if len(fund_history) < 30:
                        st.warning("Bu fon için yeterli geçmiş veri bulunamadı.")
                    else:
                        st.session_state['mc_results'] = run_monte_carlo_simulation(fund_history, days_to_simulate=30, num_simulations=1000)
                        st.session_state['mc_fund'] = selected_pred_fund

            if 'mc_results' in st.session_state and st.session_state.get('mc_fund') == selected_pred_fund:
                mc_results = st.session_state['mc_results']

                st.markdown(f"**{selected_pred_fund} Fonu - 30 Gün Sonraki Olası Fiyat Dağılımı (Güven Aralıkları)**")

                c1, c2, c3, c4, c5 = st.columns(5)
                c1.metric("En Kötü (%5)", f"{mc_results['worst']:.4f}",
                          f"{((mc_results['worst'] / mc_results['last_price']) - 1) * 100:.2f}%")
                c2.metric("Alt Çeyrek (%25)", f"{mc_results['p25']:.4f}",
                          f"{((mc_results['p25'] / mc_results['last_price']) - 1) * 100:.2f}%")
                c3.metric("Medyan (%50)", f"{mc_results['median']:.4f}",
                          f"{((mc_results['median'] / mc_results['last_price']) - 1) * 100:.2f}%")
                c4.metric("Üst Çeyrek (%75)", f"{mc_results['p75']:.4f}",
                          f"{((mc_results['p75'] / mc_results['last_price']) - 1) * 100:.2f}%")
                c5.metric("En İyi (%95)", f"{mc_results['best']:.4f}",
                          f"{((mc_results['best'] / mc_results['last_price']) - 1) * 100:.2f}%")

                st.markdown("---")

                col_hist, col_lines = st.columns([1, 1])

                with col_hist:
                    st.write("**Simülasyon Sonu Fiyat Yığılması (Histogram)**")
                    final_prices = mc_results['simulations'][-1, :]
                    fig_hist = px.histogram(
                        x=final_prices, nbins=50,
                        labels={'x': '30. Gün Fiyatı (TL)', 'y': 'Frekans (Olasılık)'},
                        color_discrete_sequence=['#9b59b6']
                    )
                    fig_hist.add_vline(x=mc_results['last_price'], line_dash="dot", line_color="white",
                                       annotation_text="Şu Anki Fiyat")
                    fig_hist.update_layout(showlegend=False, xaxis_title="Olası Fiyat (TL)",
                                           yaxis_title="Senaryo Sayısı")
                    st.plotly_chart(fig_hist, width='stretch', key="hist")

                with col_lines:
                    st.write("**Olası Fiyat Yolları (Rastgele 50 Senaryo)**")
                    sim_df = pd.DataFrame(mc_results['simulations'][:, :50])
                    fig_mc = px.line(sim_df, labels={"value": "Fiyat (TL)", "index": "Günler", "variable": "Senaryo"})
                    fig_mc.update_layout(showlegend=False, xaxis_title="Gün", yaxis_title="Fiyat (TL)")
                    fig_mc.add_hline(y=mc_results['last_price'], line_dash="dot", line_color="white", annotation_text="Şu Anki Fiyat")
                    st.plotly_chart(fig_mc, width='stretch', key="lines")

        elif aktif_sekme == "Prophet Trend Analizi":
            st.subheader("Facebook Prophet Zaman Serisi Analizi")
            st.info("Bu makine öğrenmesi modeli, fonun geçmiş fiyatlarındaki döngüsel hareketleri (haftalık, aylık, yıllık trendler) öğrenerek gelecek 30 gün için tahmin yürütür ve bir güvenlik konisi çizer.")

            with st.form("prophet_form"):
                selected_prophet_fund = st.selectbox("Modelin Eğitileceği Fonu Seçin:", my_funds)
                submit_prophet = st.form_submit_button("Tahmin Üret")

            if submit_prophet:
                with st.spinner(f"{selected_prophet_fund} verileriyle Prophet sinir ağı eğitiliyor..."):
                    fund_data = live_df[live_df['code'] == selected_prophet_fund].copy()

                    if len(fund_data) < 60:
                        st.warning(
                            "Bu fon için yeterli geçmiş veri bulunamadı. Makine öğrenmesi algoritmaları en az 2 aylık veriyle daha sağlıklı çalışır.")
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

                st.markdown(f"**{selected_prophet_fund} Fonu - 30 Günlük Model Beklentisi**")

                p1, p2, p3 = st.columns(3)
                p1.metric("Şu Anki Gerçek Fiyat", f"{last_actual_price:.4f} TL")
                p2.metric("30 Gün Sonraki Trend Hedefi", f"{future_30d_price:.4f} TL",
                          f"{((future_30d_price / last_actual_price) - 1) * 100:.2f}%", delta_color="normal")
                p3.metric("Prophet Güven Aralığı", f"{future_30d_lower:.4f} - {future_30d_upper:.4f} TL")

                st.markdown("---")

                fig_prophet = go.Figure()

                # 1. Gerçek Fiyat Çizgisi
                fig_prophet.add_trace(
                    go.Scatter(x=historical['date'], y=historical['price'], mode='lines', name='Gerçek Fiyat',
                               line=dict(color='#2ecc71', width=2)))

                # 2. Gelecek Tahmin Çizgisi (yhat)
                future_forecast = forecast[forecast['ds'] > historical['date'].max()]
                fig_prophet.add_trace(
                    go.Scatter(x=future_forecast['ds'], y=future_forecast['yhat'], mode='lines', name='Prophet Trendi',
                               line=dict(color='#e74c3c', dash='dash', width=2)))

                # 3. Güvenlik Konisi
                fig_prophet.add_trace(go.Scatter(
                    x=pd.concat([future_forecast['ds'], future_forecast['ds'][::-1]]),
                    y=pd.concat([future_forecast['yhat_upper'], future_forecast['yhat_lower'][::-1]]),
                    fill='toself',
                    fillcolor='rgba(231, 76, 60, 0.2)',
                    line=dict(color='rgba(255,255,255,0)'),
                    hoverinfo="skip",
                    showlegend=True,
                    name='Güvenlik Konisi'
                ))

                fig_prophet.update_layout(title=f"{selected_prophet_fund} Geçmiş Trend ve Gelecek Projeksiyonu", xaxis_title="Tarih", yaxis_title="Fiyat (TL)")
                fig_prophet.add_vline(x=historical['date'].max(), line_dash="dot", line_color="white")

                st.plotly_chart(fig_prophet, width='stretch')
    else:
        st.error("Veri çekilemedi. Terminalde bir hata oluşmuş olabilir.")