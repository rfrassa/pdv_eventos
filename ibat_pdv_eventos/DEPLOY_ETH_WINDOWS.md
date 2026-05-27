# Despliegue Hibrido Windows (Servidor central + notebooks por ETH)

## Objetivo
- Esta PC corre el backend y frontend en una IP fija de red local.
- Cada notebook cliente se conecta por Ethernet (sin internet).
- La impresion sigue siendo local en cada notebook con su impresora USB.

## 1) Configurar IP fija en la PC servidor
- Ejemplo: 192.168.0.10 / mascara 255.255.255.0
- Sin gateway/internet si la red es aislada.

## 2) Ajustar script de arranque servidor
Editar iniciar_servidor_eth_fijo.bat:
- PDV_SERVER_IP=192.168.0.10
- Puerto 8080 (o el que definas)

## 3) Ejecutar sin empaquetar (modo rapido)
Desde esta carpeta:
- venv\\Scripts\\python.exe -m pip install -r requirements-windows.txt
- iniciar_servidor_eth_fijo.bat

## 4) Empaquetar EXE para esta PC
- Ejecutar build_server_exe.bat
- Se genera dist\\pdv_server.exe
- iniciar_servidor_eth_fijo.bat lo usara automaticamente si existe

## 5) Notebooks cliente
En cada notebook:
- Editar abrir_pdv_cliente.bat con la IP del servidor
- Ejecutar abrir_pdv_cliente.bat

## 6) Frontend con IP fija
Si necesitas forzar API contra IP fija, editar:
- static\\pwa\\pdv-config.js
- apiBase: 'http://192.168.0.10:8000'
- apiBase: 'http://192.168.0.10:8080'

Si el frontend se sirve desde el mismo Django del servidor, dejar apiBase vacio.

## Atajos de teclado en caja
- Alt+C: abrir cobro
- Alt+G: guardar pedido abierto
- Alt+N: nuevo ticket
- Alt+O: pendientes
- Alt+H: historial
- Alt+I: selector de impresora
- Alt+P: imprimir pedido en contexto (detalle/edicion)

En overlay de pago:
- 1..6: seleccionar metodo
- Enter: agregar pago o confirmar
- Ctrl+Backspace: limpiar pagos
- Esc: cerrar cobro
