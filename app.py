import streamlit as st
import pandas as pd
import os
import io
import folium
from streamlit_folium import st_folium
from geopy.distance import geodesic

st.set_page_config(page_title="Professional Intelligence CDR Analyzer", layout="wide")

st.title("🛡️ Professional CDR, IPDR, IMEI & Cell-Site Intelligence Analyzer")
st.caption("একধিক CDR এনালাইসিস, বিটিএস ম্যাপ ট্র্যাকিং ও ইন্টেলিজেন্স রিপোর্ট জেনারেটর")

# -------------------------------------------------------------
# ফাইল আপলোড সাইডবার (CDR এবং BTS ফাইল উভয়টি ম্যানুয়ালি বা অটো দেওয়া যাবে)
# -------------------------------------------------------------
st.sidebar.header("📁 ফাইল আপলোড মেনু")

uploaded_cdrs = st.sidebar.file_uploader(
    "১. এক বা একাধিক CDR ফাইল আপলোড করুন (Excel/CSV)", 
    type=['csv', 'xlsx'], 
    accept_multiple_files=True
)

uploaded_bts = st.sidebar.file_uploader(
    "২. সাইডবার থেকেও BTS ফাইল দিতে পারেন (ঐচ্ছিক)", 
    type=['csv', 'xlsx']
)

# অটো-লোড ব্যাকআপ BTS
@st.cache_data
def load_master_bts():
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    excel_path = os.path.join(BASE_DIR, "bts_master.xlsx")
    csv_path = os.path.join(BASE_DIR, "bts_master.csv")
    
    if os.path.exists(excel_path):
        return pd.read_excel(excel_path)
    elif os.path.exists(csv_path):
        return pd.read_csv(csv_path)
    return None

bts_df = None
if uploaded_bts:
    bts_df = pd.read_csv(uploaded_bts) if uploaded_bts.name.endswith('.csv') else pd.read_excel(uploaded_bts)
    st.sidebar.success("✅ সাইডবার থেকে BTS ডাটা লোড হয়েছে!")
else:
    bts_df = load_master_bts()
    if bts_df is not None:
        st.sidebar.success("✅ ফোল্ডার থেকে অটোমেটিক BTS লোড হয়েছে!")

if bts_df is not None:
    bts_df.columns = bts_df.columns.astype(str).str.strip()

all_dfs = {}
if uploaded_cdrs:
    for file in uploaded_cdrs:
        df = pd.read_csv(file) if file.name.endswith('.csv') else pd.read_excel(file)
        df.columns = df.columns.astype(str).str.strip()
        all_dfs[file.name] = df

# -------------------------------------------------------------
# মূল ৫টি অপশন / ট্যাব
# -------------------------------------------------------------
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📍 CDR ডাটা এনরিচমেন্ট & ৩ডি ম্যাপ",
    "📊 ইন্টেলিজেন্স সামারি & এক্সেল এক্সপোর্ট",
    "🔗 কমন B-Party & IMEI", 
    "🎯 লেক সেল সার্চ & দূরত্ব নির্ণয়",
    "⏱️ নতুন B-Party অ্যানালাইসিস"
])

# -------------------------------------------------------------
# TAB 1: CDR ডাটা এনরিচমেন্ট & ৩ডি ম্যাপ
# -------------------------------------------------------------
with tab1:
    st.header("📍 সিডিআরে অটোমেটিক Lat, Lon, Azimuth ও Google 3D Map লিঙ্ক যোগ")
    if not uploaded_cdrs:
        st.info("👈 শুরু করতে বামপাশের সাইডবার থেকে CDR ফাইল আপলোড করুন।")
    elif bts_df is None:
        st.error("⚠️ BTS ডাটাবেজ পাওয়া যায়নি! সাইডবার থেকে BTS ফাইল আপলোড করুন অথবা প্রজেক্ট ফোল্ডারে 'bts_master.xlsx' রাখুন।")
    else:
        selected_file = st.selectbox("অ্যানালাইসিসের জন্য CDR ফাইল বেছে নিন:", list(all_dfs.keys()), key="t1_file")
        cdr_df = all_dfs[selected_file].copy()
        
        st.subheader("⚙️ কলাম সিলেকশন (CDR ও BTS মিলাতে):")
        col_c1, col_b1, col_b2, col_b3, col_b4, col_b5 = st.columns(6)
        cdr_cell_col = col_c1.selectbox("CDR-এর Cell ID/CGI:", cdr_df.columns, key="c_cell")
        bts_cell_col = col_b1.selectbox("BTS-এর Cell ID/CGI:", bts_df.columns, key="b_cell")
        bts_lat_col = col_b2.selectbox("BTS - Latitude:", bts_df.columns, key="b_lat")
        bts_lon_col = col_b3.selectbox("BTS - Longitude:", bts_df.columns, key="b_lon")
        bts_azi_col = col_b4.selectbox("BTS - Azimuth:", bts_df.columns, key="b_azi")
        bts_op_col = col_b5.selectbox("BTS - Operator (ঐচ্ছিক):", [None] + list(bts_df.columns), key="b_op")

        if st.button("🚀 প্রসেস করুন ও লেট/লন/ম্যাপ লিঙ্ক তৈরি করুন"):
            target_bts = bts_df.copy()
            
            cdr_df['match_key'] = cdr_df[cdr_cell_col].astype(str).str.strip().str.split('.').str[0]
            target_bts['match_key'] = target_bts[bts_cell_col].astype(str).str.strip().str.split('.').str[0]

            merged = pd.merge(cdr_df, target_bts[['match_key', bts_lat_col, bts_lon_col, bts_azi_col]], 
                              on='match_key', how='left')
            
            def make_google_map_link(row):
                lat = row[bts_lat_col]
                lon = row[bts_lon_col]
                if pd.notnull(lat) and pd.notnull(lon):
                    return f"https://www.google.com/maps/@{lat},{lon},200m/data=!3m1!1e3"
                return ""

            merged['Latitude'] = merged[bts_lat_col]
            merged['Longitude'] = merged[bts_lon_col]
            merged['Azimuth'] = merged[bts_azi_col]
            merged['Google 3D Map Link'] = merged.apply(make_google_map_link, axis=1)
            
            merged = merged.drop(columns=['match_key', bts_lat_col, bts_lon_col, bts_azi_col], errors='ignore')
            
            matched_count = merged['Latitude'].notnull().sum()
            st.success(f"সফলভাবে প্রসেস করা হয়েছে! মোট {len(merged)} টির মধ্যে {matched_count} টি সেলের লোকেশন ম্যাচ করেছে।")
            
            st.dataframe(
                merged,
                column_config={
                    "Google 3D Map Link": st.column_config.LinkColumn(
                        "Google 3D Map Link",
                        display_text="View in 3D Map 🗺️"
                    )
                }
            )

# -------------------------------------------------------------
# TAB 2: ইন্টেলিজেন্স সামারি & এক্সেল এক্সপোর্ট
# -------------------------------------------------------------
with tab2:
    st.header("📊 বি-পার্টি র‍্যাংকিং, আইএমইআই ইউজেজ ও লোকেশন ফ্রিকোয়েন্সি সামারি")
    if not uploaded_cdrs:
        st.info("👈 রিপোর্ট তৈরি করতে বামপাশের সাইডবার থেকে CDR ফাইল আপলোড করুন।")
    else:
        sel_file_sum = st.selectbox("সামারি রিপোর্ট তৈরির জন্য CDR বেছে নিন:", list(all_dfs.keys()), key="sum_file")
        df_sum = all_dfs[sel_file_sum]
        
        sc1, sc2, sc3, sc4 = st.columns(4)
        bparty_col_s = sc1.selectbox("BPARTY (বি-পার্টি কলাম):", df_sum.columns, key="s_bp")
        imei_col_s = sc2.selectbox("IMEI কলাম (যদি থাকে):", [None] + list(df_sum.columns), key="s_im")
        loc_col_s = sc3.selectbox("Cell ID / Location কলাম:", df_sum.columns, key="s_loc")
        date_col_s = sc4.selectbox("Date / START DateTime কলাম:", df_sum.columns, key="s_dt")
        
        if st.button("📊 ১-ক্লিকে সম্পূর্ণ ইনভেস্টিগেশন রিপোর্ট তৈরি করুন"):
            bparty_summary = df_sum[bparty_col_s].astype(str).value_counts().reset_index()
            bparty_summary.columns = ['B-Party Number', 'Total Calls / Count']
            
            if imei_col_s:
                df_sum['Temp_Date'] = pd.to_datetime(df_sum[date_col_s], errors='coerce')
                imei_summary = df_sum.groupby(imei_col_s)['Temp_Date'].agg(
                    First_Used_Date='min',
                    Last_Used_Date='max',
                    Total_Calls='count'
                ).reset_index()
                imei_summary = imei_summary.sort_values(by='Total_Calls', ascending=False)
            else:
                imei_summary = pd.DataFrame()

            loc_summary = df_sum[loc_col_s].astype(str).value_counts().reset_index()
            loc_summary.columns = ['Cell ID / Location', 'Total Hits / Frequency']

            st.subheader("🔝 ১. B-Party কলার র‍্যাংকিং (সবচেয়ে বেশি কল করা নম্বর)")
            st.dataframe(bparty_summary.head(10))
            
            if not imei_summary.empty:
                st.subheader("📱 ২. IMEI ইউজেজ টাইমলাইন")
                st.dataframe(imei_summary)
                
            st.subheader("📍 ৩. লোকেশন / টাওয়ার ফ্রিকোয়েন্সি")
            st.dataframe(loc_summary.head(10))

            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_sum.to_excel(writer, sheet_name='Main_CDR_Data', index=False)
                bparty_summary.to_excel(writer, sheet_name='BParty_Frequency', index=False)
                if not imei_summary.empty:
                    imei_summary.to_excel(writer, sheet_name='IMEI_Timeline', index=False)
                loc_summary.to_excel(writer, sheet_name='Top_Locations', index=False)
            
            output.seek(0)
            st.download_button(
                label="📥 সম্পূর্ণ ইনভেস্টিগেশন এক্সেল রিপোর্ট ডাউনলোড করুন (Master Excel)",
                data=output,
                file_name=f"Intelligence_Report_{sel_file_sum}.xlsx",
                mime="application/vstack.openxmlformats-officedocument.spreadsheetml.sheet"
            )

# -------------------------------------------------------------
# TAB 3: কমন B-Party & IMEI
# -------------------------------------------------------------
with tab3:
    st.header("🔗 একাধিক CDR-এর মধ্যে কমন B-Party ও IMEI সনাক্তকরণ")
    if len(all_dfs) < 2:
        st.warning("কমন টার্গেট বের করার জন্য সাইডবার থেকে কমপক্ষে ২টি CDR ফাইল আপলোড করুন।")
    else:
        c_b, c_i = st.columns(2)
        with c_b:
            st.subheader("কমন B-Party সনাক্তকরণ")
            b_cols = {f: st.selectbox(f"B-Party ({f}):", df.columns, key=f"b_{f}") for f, df in all_dfs.items()}
            if st.button("🔍 কমন B-Party খুঁজুন"):
                sets = [set(all_dfs[f][b_cols[f]].dropna().astype(str)) for f in all_dfs]
                common = set.intersection(*sets)
                st.success(f"কমন নম্বর পাওয়া গেছে: {len(common)} টি")
                st.write(list(common))
        with c_i:
            st.subheader("কমন IMEI সনাক্তকরণ")
            i_cols = {f: st.selectbox(f"IMEI ({f}):", [None]+list(df.columns), key=f"i_{f}") for f, df in all_dfs.items()}
            if st.button("🔍 কমন IMEI খুঁজুন"):
                sets = [set(all_dfs[f][i_cols[f]].dropna().astype(str).str.split('.').str[0]) for f, df in all_dfs if i_cols[f]]
                if len(sets) >= 2:
                    common_i = set.intersection(*sets)
                    st.success(f"কমন IMEI পাওয়া গেছে: {len(common_i)} টি")
                    st.write(list(common_i))

# -------------------------------------------------------------
# TAB 4: লেক সেল সার্চ & দূরত্ব নির্ণয়
# -------------------------------------------------------------
with tab4:
    st.header("🎯 লেক সেল ম্যানুয়াল সার্চ এবং দূরত্ব (Distance) নির্ণয়")
    if bts_df is None:
        st.error("BTS ডাটা পাওয়া যায়নি।")
    else:
        c1, c2, c3 = st.columns(3)
        b_cell_col = c1.selectbox("BTS Cell ID কলাম বেছে নিন:", bts_df.columns, key="t4_cell")
        b_lat_c = c2.selectbox("BTS Lat কলাম বেছে নিন:", bts_df.columns, key="t4_lat")
        b_lon_c = c3.selectbox("BTS Lon কলাম বেছে নিন:", bts_df.columns, key="t4_lon")

        search_input = st.text_input("এক বা একাধিক Cell ID দিন (কমা দিয়ে আলাদা করুন, যেমন: 4521, 8824):")
        
        if st.button("🔍 সেল সার্চ ও ম্যাপে চিহ্নিত করুন"):
            if search_input:
                search_cells = [x.strip() for x in search_input.split(',')]
                
                bts_copy = bts_df.copy()
                bts_copy['search_key'] = bts_copy[b_cell_col].astype(str).str.strip().str.split('.').str[0]
                result_bts = bts_copy[bts_copy['search_key'].isin(search_cells)]
                
                if len(result_bts) == 0:
                    st.warning("কোনো তথ্য পাওয়া যায়নি। Cell ID সঠিকভাবে পরীক্ষা করুন।")
                else:
                    st.success(f"মোট {len(result_bts)} টি সেলের ডাটা পাওয়া গেছে।")
                    st.dataframe(result_bts.drop(columns=['search_key'], errors='ignore'))
                    
                    points = []
                    for idx, r in result_bts.iterrows():
                        points.append((r[b_lat_c], r[b_lon_c], str(r[b_cell_col])))
                    
                    if len(points) >= 2:
                        st.subheader("📏 সেল সাইটগুলোর মধ্যকার দূরত্ব:")
                        for i in range(len(points)-1):
                            p1 = (points[i][0], points[i][1])
                            p2 = (points[i+1][0], points[i+1][1])
                            dist = geodesic(p1, p2).km
                            st.write(f"📍 **Cell {points[i][2]}** থেকে **Cell {points[i+1][2]}** এর দূরত্ব: **{dist:.2f} কিমি**")

                    avg_lat = pd.to_numeric(result_bts[b_lat_c], errors='coerce').mean()
                    avg_lon = pd.to_numeric(result_bts[b_lon_c], errors='coerce').mean()
                    
                    if pd.notnull(avg_lat) and pd.notnull(avg_lon):
                        m = folium.Map(location=[avg_lat, avg_lon], zoom_start=12)
                        line_coords = []
                        for idx, r in result_bts.iterrows():
                            l_lat = pd.to_numeric(r[b_lat_c], errors='coerce')
                            l_lon = pd.to_numeric(r[b_lon_c], errors='coerce')
                            if pd.notnull(l_lat) and pd.notnull(l_lon):
                                coord = (l_lat, l_lon)
                                line_coords.append(coord)
                                folium.Marker(location=coord, popup=f"Cell ID: {r[b_cell_col]}").add_to(m)
                        
                        if len(line_coords) > 1:
                            folium.PolyLine(line_coords, color="red", weight=3).add_to(m)
                            
                        st_folium(m, width=1000, height=450)

# -------------------------------------------------------------
# TAB 5: নতুন B-Party অ্যানালাইসিস
# -------------------------------------------------------------
with tab5:
    st.header("⏱️ নির্দিষ্ট তারিখ ও সময়ের পর নতুন B-Party চিহ্নিতকরণ")
    if not uploaded_cdrs:
        st.info("👈 সাইডবার থেকে CDR ফাইল আপলোড করুন।")
    else:
        selected_f = st.selectbox("CDR বেছে নিন:", list(all_dfs.keys()), key="t5_file")
        df_time = all_dfs[selected_f]
        
        tc1, tc2 = st.columns(2)
        b_party_c = tc1.selectbox("BPARTY (বি-পার্টি) কলাম:", df_time.columns, key="t5_bp")
        date_time_c = tc2.selectbox("START / Date Time কলাম:", df_time.columns, key="t5_dt")
        
        df_time['Clean_DateTime'] = pd.to_datetime(df_time[date_time_c], errors='coerce')
        min_dt = df_time['Clean_DateTime'].min()
        if pd.isnull(min_dt):
            min_dt = pd.Timestamp.now()
            
        cut_off_date = st.date_input("তারিখ বেছে নিন:", value=min_dt.date())
        cut_off_time = st.time_input("সময় বেছে নিন:", value=min_dt.time())
        
        if st.button("🔍 নতুন B-Party কলার বের করুন"):
            cut_off_datetime = pd.to_datetime(f"{cut_off_date} {cut_off_time}")
            
            before_df = df_time[df_time['Clean_DateTime'] < cut_off_datetime]
            after_df = df_time[df_time['Clean_DateTime'] >= cut_off_datetime]
            
            before_bparties = set(before_df[b_party_c].dropna().astype(str))
            after_bparties = set(after_df[b_party_c].dropna().astype(str))
            
            new_bparties = after_bparties - before_bparties
            st.success(f"{cut_off_datetime} এর পর মোট **{len(new_bparties)} টি নতুন B-Party** কল পাওয়া গেছে!")
            
            new_calls_df = after_df[after_df[b_party_c].astype(str).isin(new_bparties)]
            st.dataframe(new_calls_df)