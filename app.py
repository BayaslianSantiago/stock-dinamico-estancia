import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection

# --- 0. Configuración de la Página ---
st.set_page_config(
    page_title="Control de Stock (Fiambrería)",
    page_icon="🧀"
)

# --- 1. Conexión y Carga de Datos ---
st.title("🧀 Sistema de Control de Stock")
st.write("Esta app actualiza el stock en Google Sheets basado en un CSV de ventas.")

# Conectarse a Google Sheets usando los "Secrets"
try:
    conn = st.connection("gsheets", type=GsheetsConnection)
except Exception as e:
    st.error(f"Error al conectar con Google Sheets: {e}")
    st.stop()

# Usamos @st.cache_data para no leer los sheets cada vez que 
# interactuamos con la app. Solo se recarga cada 10 mins (ttl=600).
@st.cache_data(ttl=600)
def load_data():
    """Carga los datos de las pestañas 'stock' y 'mapeo_productos'."""
    st.write("Cargando datos maestros (Stock y Mapeo)...")
    
    # Leer la pestaña 'stock'
    df_stock = conn.read(
        worksheet="stock",  # El nombre de tu pestaña
        usecols=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9] # Ajusta el número de columnas
    )
    # Limpiar filas vacías que a veces trae gsheets
    df_stock = df_stock.dropna(how="all")
    
    # Leer la pestaña 'mapeo_productos'
    df_mapeo = conn.read(worksheet="mapeo_productos")
    df_mapeo = df_mapeo.dropna(how="all")

    # Asegurar que las columnas clave sean del tipo correcto
    df_stock['cod_admin'] = pd.to_numeric(df_stock['cod_admin'], errors='coerce')
    df_stock['stock_actual'] = pd.to_numeric(df_stock['stock_actual'], errors='coerce')
    df_stock['peso_prom'] = pd.to_numeric(df_stock['peso_prom'], errors='coerce')
    
    df_mapeo['cod_admin'] = pd.to_numeric(df_mapeo['cod_admin'], errors='coerce')

    return df_stock, df_mapeo

# Cargar los datos
try:
    df_stock, df_mapeo = load_data()
    st.success("Datos maestros cargados correctamente.")
    st.dataframe(df_stock.head(), use_container_width=True)
except Exception as e:
    st.error(f"Error al leer las pestañas de Google Sheets: {e}")
    st.error("Verifica que las pestañas 'stock' y 'mapeo_productos' existan y tengan datos.")
    st.stop()


# --- 2. Lógica de Subida y Procesamiento ---

st.header("1. Subir CSV de Ventas del Día")
uploaded_file = st.file_uploader(
    "Sube el CSV de ventas (el que limpiaste con tu script)", 
    type=["csv"]
)

if uploaded_file is not None:
    st.header("2. Procesar y Actualizar Stock")
    
    # Cargar el CSV de ventas
    try:
        df_ventas = pd.read_csv(uploaded_file)
        st.write("**Ventas a procesar:**")
        st.dataframe(df_ventas.head())
    except Exception as e:
        st.error(f"No se pudo leer el CSV: {e}")
        st.stop()

    if st.button("ACTUALIZAR STOCK EN GOOGLE SHEETS", type="primary"):
        
        with st.spinner("Procesando ventas y actualizando stock..."):
            
            # --- A. TRADUCIR VENTAS ---
            # Unir ventas con el mapeo para obtener el 'cod_admin'
            df_ventas_traducidas = pd.merge(
                df_ventas,
                df_mapeo,
                left_on="producto",
                right_on="producto_venta",
                how="left"
            )
            
            # Manejar productos no mapeados
            no_mapeados = df_ventas_traducidas[df_ventas_traducidas['cod_admin'].isnull()]
            if not no_mapeados.empty:
                st.error("Error Crítico: Algunos productos de la venta no están en el archivo de mapeo. No se puede continuar.")
                st.write("Productos no encontrados:")
                st.dataframe(no_mapeados['producto'].unique())
                st.stop()

            # --- B. AGRUPAR VENTAS ---
            # Sumar todas las ventas por 'cod_admin'
            ventas_agrupadas = df_ventas_traducidas.groupby('cod_admin')['cantidad'].sum().reset_index()
            ventas_agrupadas.columns = ['cod_admin', 'total_vendido']
            
            # --- C. LÓGICA DE ACTUALIZACIÓN DE STOCK ---
            df_stock_actualizado = df_stock.copy()
            # Usar 'cod_admin' como índice para actualizaciones rápidas
            df_stock_actualizado = df_stock_actualizado.set_index('cod_admin')
            
            log_actualizaciones = []

            for _, venta in ventas_agrupadas.iterrows():
                cod = int(venta['total_vendido'])
                total_vendido = float(venta['total_vendido'])

                # Verificar si el producto existe en el stock
                if cod not in df_stock_actualizado.index:
                    log_actualizaciones.append({'cod_admin': cod, 'status': f"Error: Producto no existe en el 'stock' maestro."})
                    continue
                
                # Obtener datos del producto
                producto = df_stock_actualizado.loc[cod]
                stock_actual = float(producto['stock_actual'])
                um_adm = str(producto['um_adm'])
                um_suc = str(producto['um_suc'])
                peso_prom = float(producto['peso_prom'])
                
                descuento_en_um_adm = 0.0

                # --- ¡LA LÓGICA DE CONVERSIÓN CLAVE! ---
                if um_adm == um_suc:
                    # Caso 1: Venta por UNIDAD, Stock por UNIDAD (Fácil)
                    descuento_en_um_adm = total_vendido
                
                elif um_adm == 'Unidad' and um_suc == 'Kilos':
                    # Caso 2: Venta por KILOS, Stock por UNIDAD (Ej: Horma de queso)
                    if peso_prom == 0 or pd.isnull(peso_prom):
                        log_actualizaciones.append({'cod_admin': cod, 'status': f"Error: '{producto['descripcion']}' tiene Peso Promedio 0."})
                        continue
                    descuento_en_um_adm = total_vendido / peso_prom
                
                else:
                    # Caso 3: No soportado (Ej: Venta por UNIDAD, Stock por KILOS)
                    log_actualizaciones.append({'cod_admin': cod, 'status': f"Error: Tipo de conversión no manejada ({um_adm} -> {um_suc})."})
                    continue
                
                # Calcular y actualizar
                nuevo_stock = stock_actual - descuento_en_um_adm
                df_stock_actualizado.loc[cod, 'stock_actual'] = nuevo_stock
                
                log_actualizaciones.append({
                    'cod_admin': cod,
                    'producto': producto['descripcion'],
                    'stock_anterior': round(stock_actual, 2),
                    'vendido_convertido': round(descuento_en_um_adm, 2),
                    'stock_nuevo': round(nuevo_stock, 2),
                    'status': 'Actualizado'
                })

            # --- D. GUARDAR EN GOOGLE SHEETS ---
            # Volver a poner 'cod_admin' como columna
            df_stock_final = df_stock_actualizado.reset_index()
            
            # Asegurarse de que el orden de columnas es el mismo
            df_stock_final = df_stock_final[df_stock.columns.tolist()]
            
            try:
                # Escribir TODO el dataframe actualizado de vuelta a la pestaña 'stock'
                conn.update(
                    worksheet="stock",
                    data=df_stock_final
                )
                
                st.success("🎉 ¡Éxito! El stock ha sido actualizado en Google Sheets.")
                
                # Mostrar el log de lo que se hizo
                st.header("3. Resumen de Actualizaciones")
                df_log = pd.DataFrame(log_actualizaciones)
                st.dataframe(df_log, use_container_width=True)
                
                # Limpiar la caché para que la próxima carga muestre los datos nuevos
                st.cache_data.clear()

            except Exception as e:
                st.error(f"Error al escribir de vuelta en Google Sheets: {e}")
