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

1. 0.2 kg de Queso

2. 0.2 kg de Jamón Cocido

Entonces, vender 10 promos implica que también se consumieron internamente:

* 2 kg de Queso Tybo

* 2 kg de Jamón Cocido

2 kg de Mortadela

Y eso debe descontarse del stock aunque no figure explícitamente en la facturación.
