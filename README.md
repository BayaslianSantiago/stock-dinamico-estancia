# stock-dinamico-estancia

| Producto   | Stock (hormas) | Promedio diario | Días restantes | Estado        |
| ---------- | -------------- | --------------- | -------------- | ------------- |
| Queso Tybo | 8              | 2               | 4 días         | ⚠ Bajo stock  |
| Queso Azul | 30             | 1               | 30 días        | ✅ OK          |
| Queso Brie | 40             | 0.5             | 80 días        | 📈 Sobrestock |



---

## Supongamos que se factura así:


    fecha,producto,cantidad_vendida,unidad_venta
    2025-11-12,PROMO_1,10,unidad
    2025-11-12,Queso Tybo,5.0,kg


### Pero “PROMO_1” en realidad incluye:

* 0.2 kg de Queso

* 0.2 kg de Jamón Cocido

Entonces, vender 10 promos implica que también se consumieron internamente:

* 2 kg de Queso Tybo

* 2 kg de Jamón Cocido

Podés crear un archivo aparte, por ejemplo promos_componentes.csv, donde se detalla la “receta” de cada promoción:

    promo,producto_base,cantidad_consumida,unidad_base
    PROMO_1,Queso Tybo,0.2,kg
    PROMO_1,Jamón Cocido,0.3,kg
    PROMO_1,Mortadela,0.2,kg
    
    PROMO_2,Queso Tybo,0.15,kg
    PROMO_2,Salame,0.25,kg
    PROMO_2,Mortadela,0.25,kg

El Script tiene que:

Detectar las ventas de promociones en la facturación.

Consultar la tabla de componentes.

Calcular el consumo indirecto real que generan las promos.

Sumarlo al consumo normal antes de actualizar el stock.

Y eso debe descontarse del stock aunque no figure explícitamente en la facturación.
