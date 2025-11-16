import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection

# Configuración de la página
st.set_page_config(
    page_title="Control de Stock - Fiambrería",
    page_icon="🧀",
    layout="wide"
)

# Título principal
st.title("🧀 Sistema de Control de Stock - Fiambrería")
st.markdown("---")

# Función para cargar datos desde Google Sheets
@st.cache_data(ttl=600)
def cargar_datos_sheets():
    """
    Carga los datos de las pestañas 'stock' y 'mapeo_productos' desde Google Sheets.
    Usa caché para evitar recargas innecesarias.
    """
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        
        # Cargar pestaña de stock
        df_stock = conn.read(worksheet="stock")
        
        # Cargar pestaña de mapeo
        df_mapeo = conn.read(worksheet="mapeo_productos")
        
        return df_stock, df_mapeo, conn
    
    except Exception as e:
        st.error(f"❌ Error al conectar con Google Sheets: {str(e)}")
        st.info("""
        **Verifica tu configuración de secrets:**
        
        Asegúrate de tener un archivo `.streamlit/secrets.toml` con la siguiente estructura:
        
        ```toml
        [connections.gsheets]
        type = "service_account"
        project_id = "tu-proyecto-id"
        private_key_id = "..."
        private_key = "-----BEGIN PRIVATE KEY-----\\n...\\n-----END PRIVATE KEY-----\\n"
        client_email = "bot-streamlit@...iam.gserviceaccount.com"
        client_id = "..."
        auth_uri = "https://accounts.google.com/o/oauth2/auth"
        token_uri = "https://oauth2.googleapis.com/token"
        auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
        client_x509_cert_url = "..."
        ```
        """)
        st.stop()

# Cargar datos iniciales
with st.spinner("🔄 Cargando datos desde Google Sheets..."):
    df_stock, df_mapeo, conn = cargar_datos_sheets()

# Mostrar información del stock actual
st.subheader("📊 Stock Actual")
st.dataframe(df_stock, use_container_width=True)

st.markdown("---")

# Sección de carga de archivo
st.subheader("📤 Subir Archivo de Ventas del Día")
archivo_ventas = st.file_uploader(
    "Selecciona el archivo CSV con las ventas del día",
    type=["csv"],
    help="El archivo debe contener las columnas: 'producto' y 'cantidad'"
)

# Procesamiento de ventas
if archivo_ventas is not None:
    st.info(f"✅ Archivo cargado: {archivo_ventas.name}")
    
    # Botón para procesar
    if st.button("🚀 Procesar Ventas y Actualizar Stock", type="primary"):
        
        with st.spinner("⚙️ Procesando ventas y actualizando stock..."):
            try:
                # Leer el archivo de ventas
                df_ventas = pd.read_csv(archivo_ventas)
                
                # Validar columnas requeridas
                if 'producto' not in df_ventas.columns or 'cantidad' not in df_ventas.columns:
                    st.error("❌ El archivo CSV debe contener las columnas 'producto' y 'cantidad'")
                    st.stop()
                
                st.write("**Preview de ventas cargadas:**")
                st.dataframe(df_ventas.head(), use_container_width=True)
                
                # PASO A: Traducir productos usando el mapeo
                df_ventas_mapeado = df_ventas.merge(
                    df_mapeo,
                    left_on='producto',
                    right_on='producto_venta',
                    how='left'
                )
                
                # Verificar productos no mapeados
                productos_sin_mapeo = df_ventas_mapeado[df_ventas_mapeado['cod_admin'].isna()]
                
                if len(productos_sin_mapeo) > 0:
                    st.error("❌ **Error: Productos no encontrados en el mapeo**")
                    st.write("Los siguientes productos en el archivo de ventas no tienen un código administrativo asignado:")
                    st.dataframe(productos_sin_mapeo[['producto', 'cantidad']], use_container_width=True)
                    st.warning("Por favor, agrega estos productos a la pestaña 'mapeo_productos' en Google Sheets antes de continuar.")
                    st.stop()
                
                # PASO B: Agrupar ventas por cod_admin
                ventas_agrupadas = df_ventas_mapeado.groupby('cod_admin')['cantidad'].sum().reset_index()
                ventas_agrupadas.columns = ['cod_admin', 'total_vendido']
                
                st.write("**Ventas agrupadas por producto:**")
                st.dataframe(ventas_agrupadas, use_container_width=True)
                
                # PASO C: Calcular descuentos y actualizar stock
                log_cambios = []
                
                for _, venta in ventas_agrupadas.iterrows():
                    cod_admin = venta['cod_admin']
                    total_vendido = venta['total_vendido']
                    
                    # Buscar el producto en el stock
                    idx_producto = df_stock[df_stock['cod_admin'] == cod_admin].index
                    
                    if len(idx_producto) == 0:
                        st.warning(f"⚠️ Producto con cod_admin {cod_admin} no encontrado en stock")
                        continue
                    
                    idx = idx_producto[0]
                    
                    # Obtener datos del producto
                    descripcion = df_stock.loc[idx, 'descripcion']
                    um_adm = df_stock.loc[idx, 'um_adm']
                    um_suc = df_stock.loc[idx, 'um_suc']
                    peso_prom = df_stock.loc[idx, 'peso_prom']
                    stock_actual = df_stock.loc[idx, 'stock_actual']
                    
                    # Aplicar lógica de conversión
                    if um_adm == um_suc:
                        # Mismo tipo de unidad: descuento directo
                        descuento = total_vendido
                    elif um_adm == 'Unidad' and um_suc == 'Kilo':
                        # Venta en kilos, stock en unidades (hormas)
                        if pd.isna(peso_prom) or peso_prom == 0:
                            st.error(f"❌ Error: El producto '{descripcion}' requiere conversión pero tiene peso_prom inválido ({peso_prom})")
                            st.stop()
                        descuento = total_vendido / peso_prom
                    else:
                        st.warning(f"⚠️ Conversión no soportada para {descripcion}: {um_adm} -> {um_suc}")
                        continue
                    
                    # Calcular nuevo stock
                    nuevo_stock = stock_actual - descuento
                    
                    # Actualizar en el DataFrame
                    df_stock.loc[idx, 'stock_actual'] = nuevo_stock
                    
                    # Registrar el cambio
                    log_cambios.append({
                        'cod_admin': cod_admin,
                        'descripcion': descripcion,
                        'vendido_suc': f"{total_vendido} {um_suc}",
                        'descuento_adm': f"{descuento:.3f} {um_adm}",
                        'stock_anterior': f"{stock_actual:.3f} {um_adm}",
                        'stock_nuevo': f"{nuevo_stock:.3f} {um_adm}"
                    })
                
                # PASO D: Guardar en Google Sheets
                conn.update(worksheet="stock", data=df_stock)
                
                # PASO E: Mostrar feedback
                st.success("✅ ¡Stock actualizado con éxito en Google Sheets!")
                
                st.subheader("📋 Resumen de Cambios")
                df_log = pd.DataFrame(log_cambios)
                st.dataframe(df_log, use_container_width=True)
                
                # Limpiar caché para que se recarguen los datos actualizados
                st.cache_data.clear()
                
                st.info("🔄 La caché se ha limpiado. Recarga la página para ver el stock actualizado.")
                
            except Exception as e:
                st.error(f"❌ Error durante el procesamiento: {str(e)}")
                st.exception(e)

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: gray;'>
    <p>Sistema de Control de Stock v1.0 | Desarrollado con Streamlit 🚀</p>
</div>
""", unsafe_allow_html=True)
