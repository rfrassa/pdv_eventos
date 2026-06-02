const API_BASE = (window.PDV_CONFIG && window.PDV_CONFIG.apiBase) || '';
const METODOS_PAGO = [
    { id: 'EF', label: 'Efectivo', icon: '💵' },
    { id: 'TC', label: 'Tarjeta crédito', icon: '💳' },
    { id: 'TD', label: 'Tarjeta débito', icon: '💳' },
    { id: 'TR', label: 'Transferencia/QR', icon: '📱' },
    { id: 'CU', label: 'Cuenta corriente', icon: '📋' },
    { id: 'OT', label: 'Otro', icon: '🧾' },
];

const PAYMENT_SHORTCUTS = [
    { key: 'F1', alt: 'A', methodId: 'EF' },
    { key: 'F2', alt: 'S', methodId: 'TC' },
    { key: 'F3', alt: 'D', methodId: 'TD' },
    { key: 'F4', alt: 'F', methodId: 'TR' },
    { key: 'F5', alt: 'G', methodId: 'CU' },
    { key: 'F6', alt: 'H', methodId: 'OT' },
];

let state = {
    productos: [],
    categorias: [],
    categoriaActiva: null,
    ticket: [],
    pedidoEditando: null,
    pdvActual: null,
    pdvs: [],
    evento: null,
    pagos: [],
    metodoSeleccionado: null,
    detallePedidoId: null,
    printerName: localStorage.getItem('pdv_printer') || '',
    impresoras: [],
};

function isTypingTarget(el) {
    if (!el) return false;
    const tag = (el.tagName || '').toUpperCase();
    return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || el.isContentEditable;
}

function printActiveContext() {
    if (state.detallePedidoId) {
        imprimirEnPC(state.detallePedidoId);
        return;
    }
    if (state.pedidoEditando) {
        imprimirEnPC(state.pedidoEditando);
        return;
    }
    showNotification('Abrí el detalle de un pedido para imprimir rápido', 'warning');
}

function getCsrfToken() {
    const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]*)/);
    return match ? match[1] : '';
}

async function apiFetch(url, options = {}) {
    const config = {
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
        },
        ...options,
    };
    const res = await fetch(API_BASE + url, config);
    if (!res.ok) {
        const err = await res.json().catch(() => ({ error: res.statusText }));
        throw new Error(err.error || err.detail || 'Error de conexión');
    }
    if (res.status === 204 || res.headers.get('content-length') === '0') return null;
    return res.json();
}

function showNotification(msg, type = 'success') {
    const el = document.getElementById('notification');
    el.textContent = msg;
    el.className = 'notification ' + type + ' show';
    setTimeout(() => { el.className = 'notification'; }, 3000);
}

function formatPrice(n) {
    return '$' + parseFloat(n).toFixed(2);
}

// Preferencia: usar impresión por navegador al confirmar (default = false).
// El flujo por defecto será intentar el agente local primero y fallback al navegador.
function isPreferBrowserPrint() {
    // Default to false (agent-first) when not set
    return localStorage.getItem('prefer_browser_print') === '1';
}
function setPreferBrowserPrint(v) {
    localStorage.setItem('prefer_browser_print', v ? '1' : '0');
}

// Agent URL usado por el frontend para impresión silenciosa
const AGENT_URL = 'http://127.0.0.1:34567';
// Token para autorizar peticiones al agente local (escrito en print_agent/agent.token)
const AGENT_TOKEN = '681c2ea1f0a74d4481ff647cbe42d28d';

// Render agent status indicator in sidebar and keep it updated
function renderAgentStatus() {
    const sidebar = document.getElementById('sidebar');
    if (!sidebar) return;
    if (document.getElementById('agent-status-wrap')) return;
    const wrap = document.createElement('div');
    wrap.id = 'agent-status-wrap';
    wrap.style.padding = '12px';
    wrap.style.borderTop = '1px solid #eee';
    wrap.style.display = 'flex';
    wrap.style.alignItems = 'center';
    wrap.style.gap = '8px';
    wrap.innerHTML = `
        <div id="agent-status-dot" style="width:12px;height:12px;border-radius:50%;background:#ccc"></div>
        <div style="flex:1">
            <div style="font-size:0.95rem">Agente local</div>
            <div id="agent-status-text" style="font-size:0.8rem;color:var(--text-light)">sin verificar</div>
        </div>
    `;
    sidebar.appendChild(wrap);

    async function pingAgent() {
        try {
            const res = await fetch(AGENT_URL + '/ping', { cache: 'no-store', headers: { 'x-print-token': AGENT_TOKEN } });
            if (res.ok) {
                const data = await res.json().catch(() => ({}));
                document.getElementById('agent-status-dot').style.background = '#2ecc71';
                document.getElementById('agent-status-text').textContent = data.printer || 'agente activo';
                return true;
            }
        } catch (e) {}
        document.getElementById('agent-status-dot').style.background = '#e74c3c';
        document.getElementById('agent-status-text').textContent = 'no responde';
        return false;
    }

    // Ping immediately and periodically
    pingAgent();
    setInterval(pingAgent, 8000);
}

// --- INIT ---
async function init() {
    try {
        const [productos, pdvs, impData] = await Promise.all([
            apiFetch('/api/productos/?disponibles=false'),
            apiFetch('/api/pdv/').catch(() => null),
            apiFetch('/api/impresoras/').catch(() => null),
        ]);

        if (impData && impData.impresoras) {
            state.impresoras = impData.impresoras;
            if (!state.printerName && state.impresoras.length > 0) {
                state.printerName = state.impresoras[0];
                localStorage.setItem('pdv_printer', state.printerName);
            }
        }
        const btnPrinterLabel = document.getElementById('btn-printer-name');
        if (btnPrinterLabel) btnPrinterLabel.textContent = state.printerName || 'Sin impresora';
        state.productos = productos;

        const cats = new Map();
        productos.forEach(p => {
            if (!cats.has(p.categoria)) {
                cats.set(p.categoria, { id: p.categoria, nombre: p.categoria_nombre });
            }
        });
        state.categorias = Array.from(cats.values());

        if (pdvs && pdvs.length > 0) {
            state.pdvs = pdvs;
        } else {
            state.pdvs = [
                { id: 1, nombre: 'PDV 1 - Entrada', impresora_ip: '192.168.0.58' },
                { id: 2, nombre: 'PDV 2 - Principal', impresora_ip: '192.168.0.58' },
                { id: 3, nombre: 'PDV 3 - VIP', impresora_ip: '192.168.0.58' },
            ];
        }
        state.pdvActual = state.pdvs[0];
        state.evento = { nombre: 'PDV Eventos' };

        document.getElementById('evento-nombre').textContent = state.evento.nombre || 'PDV Eventos';
        document.getElementById('btn-pdv-select').innerHTML = state.pdvActual.nombre + ' <span class="badge-pendientes" id="badge-pendientes">0</span>';
        document.getElementById('btn-guardar-label').textContent = 'GUARDAR';

        // Inicializar estado del boton imprimir al confirmar
        const printBtn = document.getElementById('btn-print-after');
        if (printBtn) {
            if (state.print_after_confirm) {
                printBtn.classList.add('active');
                printBtn.textContent = 'Imprimir al confirmar (ON)';
            } else {
                printBtn.classList.remove('active');
                printBtn.textContent = 'Imprimir Web';
            }
        }

        renderCategorias();
        renderProductos();
        renderTicket();
        actualizarBadgePendientes();
        setInterval(actualizarBadgePendientes, 15000);
    } catch (e) {
        document.getElementById('loading').textContent = 'Error al cargar: ' + e.message;
    }
}

// --- CATEGORIAS ---
function renderCategorias() {
    const container = document.getElementById('categories');
    let html = '<button class="cat-btn active" data-id="" onclick="filtrarCategoria(\'\')">Todos</button>';
    state.categorias.forEach(c => {
        html += `<button class="cat-btn" data-id="${c.id}" onclick="filtrarCategoria(${c.id})">${c.nombre}</button>`;
    });
    container.innerHTML = html;
}

function filtrarCategoria(id) {
    state.categoriaActiva = id || null;
    document.querySelectorAll('.cat-btn').forEach(b => {
        b.classList.toggle('active', b.dataset.id == id);
    });
    renderProductos();
}

// --- PRODUCTOS ---
function renderProductos() {
    const grid = document.getElementById('products-grid');
    const loading = document.getElementById('loading');
    let productos = state.productos;
    if (state.categoriaActiva) {
        productos = productos.filter(p => p.categoria == state.categoriaActiva);
    }
    productos = productos.filter(p => p.disponible);
    if (productos.length === 0) {
        loading.style.display = 'block';
        loading.textContent = 'No hay productos disponibles';
        grid.innerHTML = '';
        return;
    }
    loading.style.display = 'none';
    let html = '';
    productos.forEach(p => {
        const impuesto = parseFloat(p.tasa_impuesto);
        const safeName = p.nombre.replace(/"/g, '');
        html += `
            <div class="product-card" data-id="${p.id}" data-nombre="${safeName}" data-precio="${p.precio}" data-impuesto="${p.tasa_impuesto}">
                <div class="product-name">${p.nombre}</div>
                <div class="product-price">${formatPrice(p.precio)}</div>
                ${impuesto > 0 ? `<div class="product-tax">IVA ${impuesto}%</div>` : ''}
            </div>
        `;
    });
    grid.innerHTML = html;
}

document.addEventListener('click', function(e) {
    const card = e.target.closest('.product-card');
    if (card) {
        const id = parseInt(card.dataset.id);
        const nombre = card.dataset.nombre;
        const precio = parseFloat(card.dataset.precio);
        const impuesto = parseFloat(card.dataset.impuesto);
        agregarAlTicket(id, nombre, precio, impuesto);
    }
});

// --- TICKET ---
function agregarAlTicket(id, nombre, precio, impuesto) {
    const existente = state.ticket.find(l => l.producto === id);
    if (existente) {
        existente.cantidad++;
    } else {
        state.ticket.push({
            producto: id,
            producto_nombre: nombre,
            cantidad: 1,
            precio_unitario: precio,
            tasa_impuesto: impuesto,
            nota: '',
        });
    }
    renderTicket();
    expandirTicket();
}

function toggleTicket() {
    const bar = document.getElementById('ticket-bar');
    bar.classList.toggle('expanded');
    bar.classList.remove('collapsed');
}

function expandirTicket() {
    const bar = document.getElementById('ticket-bar');
    bar.classList.add('expanded');
    bar.classList.remove('collapsed');
}

function renderTicket() {
    const body = document.getElementById('ticket-body');
    const count = document.getElementById('ticket-count');
    const total = document.getElementById('ticket-total');
    const topTotal = document.getElementById('top-total');
    const numItems = state.ticket.reduce((s, l) => s + l.cantidad, 0);
    let editTag = state.pedidoEditando ? ' <span class="detalle-edit-badge">Editando #' + state.pedidoEditando + '</span>' : '';
    const countText = numItems + ' producto' + (numItems !== 1 ? 's' : '') + editTag;
    if (count) count.innerHTML = countText;

    let subtotal = 0;
    let html = '';
    state.ticket.forEach((l, i) => {
        const totalLinea = l.cantidad * l.precio_unitario;
        subtotal += totalLinea;
        html += `
            <div class="ticket-line">
                <div class="ticket-line-qty">${l.cantidad}x</div>
                <div class="ticket-line-info">
                    <div class="ticket-line-name">${l.producto_nombre}</div>
                    ${l.nota ? `<div class="ticket-line-note">${l.nota}</div>` : ''}
                </div>
                <div class="ticket-line-price">${formatPrice(totalLinea)}</div>
                <div class="ticket-line-actions">
                    <button class="qty-btn remove" onclick="cambiarCantidad(${i}, -1)">−</button>
                    <button class="qty-btn add" onclick="cambiarCantidad(${i}, 1)">+</button>
                </div>
            </div>
        `;
    });

    if (state.ticket.length === 0) {
        html = '<div class="empty-state" style="padding:16px">El ticket está vacío</div>';
    }

    body.innerHTML = html;

    const totalStr = formatPrice(subtotal);
    if (total) total.textContent = totalStr;
    if (topTotal) topTotal.textContent = totalStr;

    // Update mobile ticket body
    if (body) body.innerHTML = html;

    // Update side (desktop) ticket elements if present
    const countSide = document.getElementById('ticket-count-side');
    const totalSide = document.getElementById('ticket-total-side');
    const bodySide = document.getElementById('ticket-body-side');
    const btnGuardarSide = document.getElementById('btn-guardar-label-side');
    if (countSide) countSide.innerHTML = countText;
    if (totalSide) totalSide.textContent = totalStr;
    if (bodySide) bodySide.innerHTML = html;
    if (btnGuardarSide) btnGuardarSide.textContent = document.getElementById('btn-guardar-label')?.textContent || 'GUARDAR';

    document.documentElement.style.setProperty('--ticket-height',
        (state.ticket.length > 0 ? '180px' : '0px'));
}

function cambiarCantidad(idx, delta) {
    const l = state.ticket[idx];
    l.cantidad += delta;
    if (l.cantidad <= 0) {
        state.ticket.splice(idx, 1);
    }
    renderTicket();
}

// --- NUEVO TICKET ---
function nuevoTicket() {
    if (state.ticket.length > 0 && !confirm('¿Cancelar el ticket actual?')) return;
    state.ticket = [];
    state.pedidoEditando = null;
    document.getElementById('btn-guardar-label').textContent = 'GUARDAR';
    renderTicket();
    document.getElementById('ticket-bar').classList.remove('expanded');
    showNotification('Ticket limpiado');
}

// --- GUARDAR PEDIDO ---
async function guardarPedido() {
    if (state.ticket.length === 0) {
        showNotification('El ticket está vacío', 'error');
        return;
    }

    const subtotal = state.ticket.reduce((s, l) => s + l.cantidad * l.precio_unitario, 0);
    const totalImpuestos = state.ticket.reduce((s, l) => {
        const imp = parseFloat(l.tasa_impuesto) || 0;
        return s + (l.cantidad * l.precio_unitario) * imp / 100;
    }, 0);
    const totalFinal = subtotal + totalImpuestos;

    const payload = {
        punto_venta: state.pdvActual.id,
        subtotal: Math.round(subtotal * 100) / 100,
        descuento_porcentaje: 0,
        total_impuestos: Math.round(totalImpuestos * 100) / 100,
        total_final: Math.round(totalFinal * 100) / 100,
        lineas: state.ticket.map(l => ({
            producto: l.producto,
            cantidad: l.cantidad,
            precio_unitario: l.precio_unitario,
            nota: l.nota || '',
        })),
        pagos: [],
    };

    try {
        const pedido = state.pedidoEditando
            ? await apiFetch('/api/pedidos/' + state.pedidoEditando + '/', {
                method: 'PATCH',
                body: JSON.stringify(payload),
            })
            : await apiFetch('/api/pedidos/', {
                method: 'POST',
                body: JSON.stringify(payload),
            });
        showNotification('Pedido guardado como abierto');
        document.getElementById('btn-guardar-label').textContent = 'GUARDAR';
        state.ticket = [];
        state.pedidoEditando = null;
        renderTicket();
        actualizarBadgePendientes();
    } catch (e) {
        showNotification('Error al guardar: ' + e.message, 'error');
    }
}

// --- PAGO ---
function abrirPago() {
    if (state.ticket.length === 0) {
        showNotification('El ticket está vacío', 'error');
        return;
    }

    const subtotal = state.ticket.reduce((s, l) => s + l.cantidad * l.precio_unitario, 0);
    const totalImpuestos = state.ticket.reduce((s, l) => {
        const imp = parseFloat(l.tasa_impuesto) || 0;
        return s + (l.cantidad * l.precio_unitario) * imp / 100;
    }, 0);
    const totalFinal = Math.round((subtotal + totalImpuestos) * 100) / 100;

    state.pagos = [];
    state.metodoSeleccionado = null;

    const overlay = document.getElementById('payment-overlay');
    overlay.classList.add('open');

    document.getElementById('pay-total').textContent = formatPrice(totalFinal);
    document.getElementById('payment-input-area').style.display = 'none';
    document.getElementById('btn-confirm-payment').disabled = true;

    renderPagos();
    renderMetodosPago();
}

function cerrarPago() {
    document.getElementById('payment-overlay').classList.remove('open');
    state.pagos = [];
    state.metodoSeleccionado = null;
}

function renderMetodosPago() {
    const container = document.getElementById('payment-methods');
    const remainder = getRemainder();
    let html = '';
    METODOS_PAGO.forEach((m, idx) => {
        const sc = PAYMENT_SHORTCUTS[idx];
        const usado = state.pagos.find(p => p.metodo === m.id);
        html += `
            <button class="pay-method-btn ${state.metodoSeleccionado === m.id ? 'selected' : ''}"
                onclick="seleccionarMetodo('${m.id}')"
                ${remainder <= 0 ? 'disabled' : ''}>
                <span class="pay-method-hotkey">${sc ? sc.key : ''}</span>
                ${m.icon}<br>${m.label}
            </button>
        `;
    });
    container.innerHTML = html;
}

function seleccionarMetodo(id) {
    const metodo = METODOS_PAGO.find(m => m.id === id);
    state.metodoSeleccionado = id;
    document.getElementById('pay-input-label').textContent = metodo.label;
    document.getElementById('pay-amount-input').value = '';
    document.getElementById('pay-recibido-input').value = '';
    document.getElementById('pay-recibido-input').parentElement.style.display = id === 'EF' ? 'block' : 'none';
    document.getElementById('payment-input-area').style.display = 'block';
    renderMetodosPago();
    actualizarInlineTotals();
    document.getElementById('pay-amount-input').focus();
}

function actualizarInlineTotals() {
    const totalEl = document.getElementById('pay-total');
    const remainder = getRemainder();
    document.getElementById('pay-inline-total').textContent = totalEl.textContent;
    document.getElementById('pay-inline-remainder').textContent = formatPrice(remainder);
}

function getRemainder() {
    const totalEl = document.getElementById('pay-total');
    const total = parseFloat(totalEl.textContent.replace('$', '')) || 0;
    const pagado = state.pagos.reduce((s, p) => s + p.monto, 0);
    return Math.round((total - pagado) * 100) / 100;
}

function renderPagos() {
    const remainder = getRemainder();
    const pagado = state.pagos.reduce((s, p) => s + p.monto, 0);
    const total = parseFloat(document.getElementById('pay-total').textContent.replace('$', '')) || 0;
    const excedente = Math.round((pagado - total) * 100) / 100;

    document.getElementById('pay-remainder').innerHTML = remainder > 0
        ? 'Restante: <span>' + formatPrice(remainder) + '</span>'
        : excedente > 0
            ? 'Vuelto: <span style="color:var(--success)">' + formatPrice(excedente) + '</span>'
            : '<span style="color:var(--success)">Cubierto</span>';
    document.getElementById('btn-confirm-payment').disabled = Math.abs(remainder) > 0.01;

    const list = document.getElementById('payment-list');
    let html = '';
    state.pagos.forEach((p, i) => {
        const metodo = METODOS_PAGO.find(m => m.id === p.metodo);
        const label = metodo ? metodo.label : p.metodo;
        let extra = '';
        if (p.metodo === 'EF' && p.monto_recibido && p.monto_recibido > p.monto) {
            const vuelto = Math.round((p.monto_recibido - p.monto) * 100) / 100;
            extra = `<div style="font-size:0.85rem;color:var(--success);font-weight:600">Vuelto: ${formatPrice(vuelto)}</div>`;
        } else if (p.metodo === 'EF' && p.monto_recibido) {
            extra = `<div style="font-size:0.75rem;color:var(--text-light)">Recibido: ${formatPrice(p.monto_recibido)}</div>`;
        }
        html += `
            <div class="payment-item">
                <div>
                    <div class="payment-item-method">${label}</div>
                    ${extra}
                </div>
                <div class="payment-item-amount">${formatPrice(p.monto)}</div>
                <button class="btn-remove-payment" onclick="quitarPago(${i})">&times;</button>
            </div>
        `;
    });
    if (state.pagos.length === 0) {
        html = '<div class="empty-state" style="padding:12px">Seleccioná un método de pago</div>';
    }
    list.innerHTML = html;
    renderMetodosPago();
    const inlineArea = document.getElementById('payment-input-area');
    if (inlineArea && inlineArea.style.display !== 'none') {
        actualizarInlineTotals();
    }
}

function agregarPago() {
    const input = document.getElementById('pay-amount-input');
    const montoIngresado = parseFloat(input.value);
    if (!montoIngresado || montoIngresado <= 0) {
        showNotification('Ingresá un monto válido', 'error');
        return;
    }

    const remainder = getRemainder();
    const pago = { metodo: state.metodoSeleccionado };

    if (state.metodoSeleccionado === 'EF') {
        const recibido = parseFloat(document.getElementById('pay-recibido-input').value) || montoIngresado;
        if (recibido < 0.01) {
            showNotification('Ingresá el efectivo recibido', 'error');
            return;
        }
        if (recibido < montoIngresado) {
            showNotification('El efectivo recibido no puede ser menor al monto', 'error');
            return;
        }
        const montoPago = Math.min(montoIngresado, remainder);
        pago.monto = Math.round(montoPago * 100) / 100;
        pago.monto_recibido = Math.round(recibido * 100) / 100;
    } else {
        if (montoIngresado > remainder + 0.01) {
            showNotification('El monto supera el restante', 'error');
            return;
        }
        pago.monto = Math.round(montoIngresado * 100) / 100;
    }

    state.pagos.push(pago);
    state.metodoSeleccionado = null;
    document.getElementById('payment-input-area').style.display = 'none';
    input.value = '';
    document.getElementById('pay-recibido-input').value = '';
    renderPagos();
    renderMetodosPago();

    if (Math.abs(getRemainder()) <= 0.01) {
        showNotification('Total cubierto. Podés confirmar el pago.');
    }
}

function quitarPago(idx) {
    state.pagos.splice(idx, 1);
    renderPagos();
}

function limpiarPagos() {
    state.pagos = [];
    state.metodoSeleccionado = null;
    document.getElementById('payment-input-area').style.display = 'none';
    renderPagos();
}

async function confirmarPago() {
    const remainder = getRemainder();
    if (Math.abs(remainder) > 0.01) {
        showNotification('Falta cubrir el total', 'error');
        return;
    }

    const subtotal = state.ticket.reduce((s, l) => s + l.cantidad * l.precio_unitario, 0);
    const totalImpuestos = state.ticket.reduce((s, l) => {
        const imp = parseFloat(l.tasa_impuesto) || 0;
        return s + (l.cantidad * l.precio_unitario) * imp / 100;
    }, 0);
    const totalFinal = Math.round((subtotal + totalImpuestos) * 100) / 100;

    const payload = {
        punto_venta: state.pdvActual.id,
        subtotal: Math.round(subtotal * 100) / 100,
        descuento_porcentaje: 0,
        total_impuestos: Math.round(totalImpuestos * 100) / 100,
        total_final: totalFinal,
        lineas: state.ticket.map(l => ({
            producto: l.producto,
            cantidad: l.cantidad,
            precio_unitario: l.precio_unitario,
            nota: l.nota || '',
        })),
        pagos: state.pagos,
    };

    try {
        const pedidoCreado = await apiFetch('/api/pedidos/', {
            method: 'POST',
            body: JSON.stringify(payload),
        });
        showNotification('Pago confirmado.');
        cerrarPago();
        state.ticket = [];
        state.pedidoEditando = null;
        renderTicket();
        apiFetch('/api/pedidos/' + pedidoCreado.id + '/imprimir-local/', {
            method: 'POST',
            body: JSON.stringify({ printer_name: state.printerName || undefined }),
        }).then(res => {
            if (res) showNotification('✅ Impresora: ' + res.impresora);
        }).catch(e => {
            console.warn('Impresión local falló, fallback navegador:', e);
            imprimirTicketNavegador(pedidoCreado.id);
        });
    } catch (e) {
        showNotification('Error al procesar pago: ' + e.message, 'error');
    }
}

// --- PEDIDOS PENDIENTES ---
async function actualizarBadgePendientes() {
    try {
        const pedidos = await apiFetch('/api/pedidos/abiertos/?punto_venta_id=' + state.pdvActual.id);
        const badge = document.getElementById('badge-pendientes');
        if (badge) {
            badge.textContent = pedidos.length;
            badge.style.display = pedidos.length > 0 ? 'inline-flex' : 'none';
        }
    } catch (_) {}
}

async function cargarPendientes() {
    try {
        const pedidos = await apiFetch('/api/pedidos/abiertos/?punto_venta_id=' + state.pdvActual.id);
        const list = document.getElementById('orders-list');
        if (pedidos.length === 0) {
            list.innerHTML = '<div class="empty-state">No hay pedidos pendientes</div>';
            return;
        }
        let html = '';
        pedidos.forEach(p => {
            html += `
                <div class="order-card">
                    <div class="order-card-info">
                        <div class="order-card-id">Pedido #${p.id}</div>
                        <div class="order-card-total">${formatPrice(p.total_final)}</div>
                        <div class="order-card-time">${new Date(p.creado).toLocaleString()}</div>
                    </div>
                    <div style="display:flex;gap:6px">
                        <button class="btn-resume-order" onclick="retomarPedido(${p.id})">Retomar</button>
                        <button class="btn-resume-order" style="background:var(--accent)" onclick="eliminarPedido(${p.id})">Eliminar</button>
                    </div>
                </div>
            `;
        });
        list.innerHTML = html;
    } catch (e) {
        showNotification('Error al cargar pedidos: ' + e.message, 'error');
    }
}

async function toggleOrders() {
    const overlay = document.getElementById('orders-overlay');
    if (overlay.classList.contains('open')) {
        overlay.classList.remove('open');
        return;
    }
    overlay.classList.add('open');
    await cargarPendientes();
}

async function eliminarPedido(id) {
    if (!confirm('¿Eliminar pedido #' + id + '?')) return;
    try {
        await apiFetch('/api/pedidos/' + id + '/', { method: 'DELETE' });
        showNotification('Pedido #' + id + ' eliminado');
        actualizarBadgePendientes();
        await cargarPendientes();
    } catch (e) {
        showNotification('Error al eliminar: ' + e.message, 'error');
    }
}

async function retomarPedido(id) {
    try {
        const pedido = await apiFetch('/api/pedidos/' + id + '/');
        state.ticket = pedido.lineas.map(l => ({
            producto: l.producto,
            producto_nombre: l.producto_nombre,
            cantidad: l.cantidad,
            precio_unitario: l.precio_unitario,
            tasa_impuesto: parseFloat(l.tasa_impuesto) || 0,
            nota: l.nota || '',
        }));
        state.pedidoEditando = id;
        document.getElementById('btn-guardar-label').textContent = 'EDITANDO #' + id;
        document.getElementById('orders-overlay').classList.remove('open');
        renderTicket();
        expandirTicket();
        showNotification('Pedido #' + id + ' cargado');
    } catch (e) {
        showNotification('Error al cargar pedido: ' + e.message, 'error');
    }
}

// --- HISTORIAL ---
async function cargarHistorial() {
    try {
        const data = await apiFetch('/api/pedidos/historial/?punto_venta_id=' + state.pdvActual.id + '&limite=100');
        const list = document.getElementById('historial-list');
        if (data.resultados.length === 0) {
            list.innerHTML = '<div class="empty-state">No hay pedidos en el historial</div>';
            return;
        }
        let html = '';
        data.resultados.forEach(p => {
            const estado = p.cerrado ? 'Cerrado' : 'Abierto';
            html += `
                <div class="order-card">
                    <div class="order-card-info">
                        <div class="order-card-id">Pedido #${p.id} <span style="font-size:0.7rem;color:${p.cerrado ? 'var(--success)' : 'var(--warning)'}">(${estado})</span></div>
                        <div class="order-card-total">${formatPrice(p.total_final)}</div>
                        <div class="order-card-time">${new Date(p.creado).toLocaleString()} - ${p.punto_venta_nombre}</div>
                    </div>
                    <div style="display:flex;gap:6px">
                        <button class="btn-resume-order" onclick="toggleDetalle(${p.id})">Ver</button>
                        <button class="btn-resume-order" onclick="imprimirEnPC(${p.id})">Imprimir${p.veces_impreso ? ' (' + p.veces_impreso + ')' : ''}</button>
                        <button class="btn-resume-order" style="background:var(--accent)" onclick="eliminarPedidoHistorial(${p.id})">Eliminar</button>
                    </div>
                </div>
            `;
        });
        list.innerHTML = html;
    } catch (e) {
        showNotification('Error al cargar historial: ' + e.message, 'error');
    }
}

async function toggleHistorial() {
    const overlay = document.getElementById('historial-overlay');
    if (overlay.classList.contains('open')) {
        overlay.classList.remove('open');
        return;
    }
    overlay.classList.add('open');
    await cargarHistorial();
}

async function eliminarPedidoHistorial(id) {
    if (!confirm('¿Eliminar permanentemente el pedido #' + id + '?')) return;
    try {
        await apiFetch('/api/pedidos/' + id + '/', { method: 'DELETE' });
        showNotification('Pedido #' + id + ' eliminado');
        await cargarHistorial();
    } catch (e) {
        showNotification('Error al eliminar: ' + e.message, 'error');
    }
}

// --- DETALLE DE PEDIDO ---
async function toggleDetalle(id) {
    const overlay = document.getElementById('detalle-overlay');
    const body = document.getElementById('detalle-body');
    const title = document.getElementById('detalle-title');
    if (overlay.classList.contains('open')) {
        overlay.classList.remove('open');
        return;
    }
    overlay.classList.add('open');
    state.detallePedidoId = id;
    title.textContent = 'Pedido #' + id;
    body.innerHTML = '<div class="empty-state">Cargando...</div>';

    try {
        const p = await apiFetch('/api/pedidos/' + id + '/');
        const fecha = new Date(p.creado).toLocaleString();
        const estado = p.cerrado ? 'Cerrado' : 'Abierto';
        const estadoClass = p.cerrado ? 'cerrado' : 'abierto';

        const categorias = new Set(p.lineas.map(l => l.categoria_nombre));
        const tieneSplit = categorias.has('Comidas') && categorias.has('Bebidas');

        let itemsHtml = '';
        p.lineas.forEach(l => {
            const total = l.cantidad * parseFloat(l.precio_unitario);
            itemsHtml += `
                <div class="detalle-item">
                    <div class="detalle-item-name">
                        <span class="detalle-item-qty">${l.cantidad}x</span> ${l.producto_nombre}
                        ${l.nota ? '<div class="detalle-item-note">(' + l.nota + ')</div>' : ''}
                    </div>
                    <div class="detalle-item-price">$${total.toFixed(2)}</div>
                </div>
            `;
        });

        let pagosHtml = '';
        p.pagos.forEach(pg => {
            let extra = '';
            if (pg.metodo === 'EF' && pg.monto_recibido) {
                const vuelto = parseFloat(pg.monto_recibido) - parseFloat(pg.monto);
                extra = '<div class="detalle-pago-extra">Recibido: $' + parseFloat(pg.monto_recibido).toFixed(2) + ' | Vuelto: $' + vuelto.toFixed(2) + '</div>';
            }
            pagosHtml += `
                <div class="detalle-pago-item">
                    <span>${pg.metodo_display}</span>
                    <span>$${parseFloat(pg.monto).toFixed(2)}</span>
                </div>
                ${extra}
            `;
        });

        const ticketIds = tieneSplit
            ? '#' + p.id + '-B / #' + p.id + '-C'
            : '#' + p.id;

        body.innerHTML = `
            <div class="detalle-header">
                <div class="detalle-id">${ticketIds}</div>
                <div class="detalle-pdv">${p.punto_venta_nombre}</div>
                <div class="detalle-fecha">${fecha}</div>
                <div style="margin-top:6px"><span class="detalle-tag ${estadoClass}">${estado}</span></div>
            </div>
            <div class="detalle-section">
                <div class="detalle-section-title">Productos</div>
                ${itemsHtml}
            </div>
            <div class="detalle-section">
                <div class="detalle-section-title">Resumen</div>
                <div class="detalle-total-line"><span>Subtotal</span><span>$${parseFloat(p.subtotal).toFixed(2)}</span></div>
                ${parseFloat(p.descuento_porcentaje) > 0 ? '<div class="detalle-total-line"><span>Descuento ' + p.descuento_porcentaje + '%</span><span></span></div>' : ''}
                <div class="detalle-total-line"><span>Impuestos</span><span>$${parseFloat(p.total_impuestos).toFixed(2)}</span></div>
                <div class="detalle-total-line final"><span>TOTAL</span><span>$${parseFloat(p.total_final).toFixed(2)}</span></div>
            </div>
            ${pagosHtml ? `
            <div class="detalle-section">
                <div class="detalle-section-title">Pagos</div>
                ${pagosHtml}
            </div>` : ''}
            <div style="display:flex;gap:8px;margin-top:16px">
                <button class="btn-resume-order" style="flex:1;text-align:center" onclick="imprimirEnPC(${p.id})">Imprimir</button>
                <button class="btn-resume-order" style="flex:1;text-align:center" onclick="window.open(API_BASE + '/api/pedidos/' + ${p.id} + '/imprimir-pdf/', '_blank')">PDF</button>
                <button class="btn-resume-order" style="flex:1;text-align:center" onclick="cerrarDetalle();imprimirTicketNavegador(${p.id})">Navegador</button>
            </div>
        `;
    } catch (e) {
        body.innerHTML = '<div class="empty-state">Error al cargar: ' + e.message + '</div>';
    }
}

function cerrarDetalle() {
    document.getElementById('detalle-overlay').classList.remove('open');
    state.detallePedidoId = null;
}

// --- IMPRIMIR: intento agente local (cliente) -> fallback servidor ---
async function imprimirEnPC(id) {
    const agentUrl = 'http://127.0.0.1:34567';
    try {
        // Try to detect local agent
        let agentAvailable = false;
        try {
            const ping = await fetch(agentUrl + '/ping', { cache: 'no-store', headers: { 'x-print-token': AGENT_TOKEN } });
            agentAvailable = ping && ping.ok;
        } catch (_) { agentAvailable = false; }

        // Fetch pedido once (source of truth: backend)
        const pedido = await apiFetch('/api/pedidos/' + id + '/');
        const categorias = new Set(pedido.lineas.map(l => l.categoria_nombre));

        const htmls = [];
        const mainHtml = buildTicketHtml(pedido);
        if (mainHtml) htmls.push(mainHtml);
        if (categorias.has('Comidas')) {
            const htmlC = buildComandaHtml(pedido, 'Comidas', 'COMIDAS', 'C');
            if (htmlC) htmls.push(htmlC);
        }
        if (categorias.has('Bebidas')) {
            const htmlB = buildComandaHtml(pedido, 'Bebidas', 'BEBIDAS', 'B');
            if (htmlB) htmls.push(htmlB);
        }

        if (agentAvailable && htmls.length > 0) {
            try {
                for (const h of htmls) {
                    const resp = await fetch(agentUrl + '/print/html', {
                        method: 'POST',
                        headers: { 'Content-Type': 'text/html', 'x-print-token': AGENT_TOKEN },
                        body: h,
                    });
                    if (!resp.ok) throw new Error('Agent print failed');
                    // small delay between prints
                    await new Promise(r => setTimeout(r, 120));
                }
                showNotification('✅ Impreso en impresora local (cliente)');
                return;
            } catch (err) {
                console.warn('Local agent printing failed, falling back to server:', err);
            }
        }

        // Fallback: send to backend server to handle printing
        const res = await apiFetch('/api/pedidos/' + id + '/imprimir-local/', {
            method: 'POST',
            body: JSON.stringify({ printer_name: state.printerName || undefined }),
        });
        if (res.ok === false) {
            showNotification('⚠️ Impresión local falló. Se abre impresión del navegador.', 'warning');
            imprimirTicketNavegador(id);
        } else {
            showNotification('✅ Ticket enviado a: ' + res.impresora);
        }
    } catch (e) {
        showNotification('⚠️ Error de impresión local. Se abre impresión del navegador.', 'warning');
        imprimirTicketNavegador(id);
    }
}

// --- SELECTOR DE IMPRESORA ---
function renderPrinterModal() {
    const overlay = document.getElementById('printer-overlay');
    if (!overlay) return;
    overlay.classList.add('open');
    const list = document.getElementById('printer-list');
    let html = '';
    state.impresoras.forEach(p => {
        const active = p === state.printerName ? 'style="background:var(--primary);color:#fff"' : '';
        html += `<button class="printer-item" ${active} onclick="seleccionarImpresora('${p.replace(/'/g, "\\'")}')">${p}</button>`;
    });
    if (state.impresoras.length === 0) {
        html = '<div class="empty-state">No hay impresoras disponibles</div>';
    }
    list.innerHTML = html;
}

async function selectPrinter() {
    try {
        const data = await apiFetch('/api/impresoras/');
        state.impresoras = data.impresoras || [];
    } catch (_) {}
    if (state.impresoras.length === 0) {
        showNotification('No hay impresoras disponibles', 'error');
        return;
    }
    renderPrinterModal();
}

function seleccionarImpresora(name) {
    state.printerName = name;
    localStorage.setItem('pdv_printer', state.printerName);
    const label = document.getElementById('btn-printer-name');
    if (label) label.textContent = state.printerName;
    showNotification('Impresora: ' + state.printerName);
    document.getElementById('printer-overlay').classList.remove('open');
}

function cerrarPrinterModal() {
    document.getElementById('printer-overlay').classList.remove('open');
}

// --- IMPRIMIR POR NAVEGADOR ---
function buildTicketHtml(pedido, categoriaNombre, etiqueta, sufijo, simple) {
    const pdv = pedido.punto_venta_nombre;
    const fecha = new Date(pedido.creado).toLocaleString();
    const ticketId = sufijo ? '#' + pedido.id + '-' + sufijo : '#' + pedido.id;
    const etiquetaHtml = etiqueta
        ? `<div class="center" style="font-size:14px;font-weight:bold;margin:4px 0 6px">--- ${etiqueta} ---</div>`
        : '';

    if (simple) {
        let lineasHtml = '';
        pedido.lineas.forEach(l => {
            if (categoriaNombre && l.categoria_nombre !== categoriaNombre) return;
            lineasHtml += `<div style="padding:4px 0;font-size:14px">${l.cantidad}x ${l.producto_nombre}${l.nota ? '<br><small>(' + l.nota + ')</small>' : ''}</div>`;
        });
        if (!lineasHtml) return null;

        return `
            <html>
            <head>
                <style>
                    body { font-family: Arial, Helvetica, sans-serif; font-size: 16px; width: 80mm; margin: 0 auto; padding: 10px; }
                    .header { text-align: center; font-weight: bold; font-size: 20px; margin: 0 0 2px; }
                    .subheader { text-align: center; font-weight: bold; font-size: 18px; margin: 0 0 6px; }
                    .evento { text-align: center; font-size: 16px; margin: 4px 0; }
                    .info { font-size: 14px; margin-bottom: 8px; }
                    @media print {
                        @page { margin: 0; size: 80mm auto; }
                        body { margin: 0; padding: 5mm; }
                    }
                </style>
            </head>
            <body>
                <div class="header">CENTRO DE ESTUDIANTES</div>
                <div class="subheader">IBAT San José</div>
                <div class="center" style="font-size:18px;font-weight:bold;margin:4px 0 6px">Peña IBAT 2026</div>
                ${etiquetaHtml}
                <div class="info">
                    PDV: ${pdv} | ${ticketId}<br>
                    ${fecha}
                </div>
                ${lineasHtml}
            </body>
            </html>
        `;
    }

    let lineasHtml = '';
    let subtotal = 0;
    pedido.lineas.forEach(l => {
        if (categoriaNombre && l.categoria_nombre !== categoriaNombre) return;
        const total = l.cantidad * parseFloat(l.precio_unitario);
        subtotal += total;
        lineasHtml += `
            <tr>
                <td>${l.cantidad}x ${l.producto_nombre}${l.nota ? '<br><small>(' + l.nota + ')</small>' : ''}</td>
                <td style="text-align:right">$${total.toFixed(2)}</td>
            </tr>
        `;
    });
    if (!lineasHtml) return null;

    let pagosHtml = '';
    pedido.pagos.forEach(p => {
        let extra = '';
        if (p.metodo === 'EF' && p.monto_recibido) {
            const vuelto = parseFloat(p.monto_recibido) - parseFloat(p.monto);
            extra = `<br><small>Recibido: $${parseFloat(p.monto_recibido).toFixed(2)} | Vuelto: $${vuelto.toFixed(2)}</small>`;
        }
        pagosHtml += `<tr><td>${p.metodo_display}</td><td style="text-align:right">$${parseFloat(p.monto).toFixed(2)}${extra}</td></tr>`;
    });

    const totalStr = categoriaNombre
        ? '$' + subtotal.toFixed(2)
        : '$' + parseFloat(pedido.total_final).toFixed(2);

    return `
        <html>
        <head>
            <style>
                body { font-family: Arial, Helvetica, sans-serif; font-size: 16px; width: 80mm; margin: 0 auto; padding: 10px; }
                .header { text-align: center; font-weight: bold; font-size: 20px; margin: 0 0 2px; }
                .subheader { text-align: center; font-weight: bold; font-size: 18px; margin: 0 0 6px; }
                .evento { text-align: center; font-size: 16px; margin: 4px 0; }
                .info { font-size: 14px; margin-bottom: 8px; }
                table { width: 100%; border-collapse: collapse; }
                td { padding: 4px 0; font-size: 15px; }
                .sep { border-top: 1px dashed #000; }
                .total { font-weight: bold; font-size: 18px; }
                .total td { padding: 6px 0; }
                .center { text-align: center; }
                .footer { text-align: center; font-size: 13px; margin-top: 8px; }
                .brand { text-align: center; font-size: 12px; color: #555; margin-top: 2px; }
                @media print {
                    @page { margin: 0; size: 80mm auto; }
                    body { margin: 0; padding: 5mm; }
                }
            </style>
        </head>
        <body>
            <div class="header">CENTRO DE ESTUDIANTES</div>
            <div class="subheader">IBAT San José</div>
            <div class="center" style="font-size:16px;font-weight:bold;margin:4px 0 6px">Peña IBAT 2026</div>
            ${etiquetaHtml}
            <div class="info">
                PDV: ${pdv} | ${ticketId}<br>
                ${fecha}
            </div>
            <table>
                <tr><td class="sep" colspan="2"></td></tr>
                ${lineasHtml}
                <tr><td class="sep" colspan="2"></td></tr>
            </table>
            <table>
                <tr class="total"><td>TOTAL</td><td style="text-align:right">${totalStr}</td></tr>
                <tr><td class="sep" colspan="2"></td></tr>
                ${pagosHtml}
                <tr><td class="sep" colspan="2"></td></tr>
            </table>
            <br>
            <div class="footer">Gracias por su compra</div>
            <div class="brand">created by RaízDigital®</div>
        </body>
        </html>
    `;
}

function buildComandaHtml(pedido, categoriaNombre, etiqueta, sufijo) {
    const pdv = pedido.punto_venta_nombre;
    const fecha = new Date(pedido.creado).toLocaleString();
    const ticketId = '#' + pedido.id + '-' + sufijo;

    const qrData = encodeURIComponent('Pedido ' + ticketId + ' - IBAT 2026');
    const qrUrl = 'https://api.qrserver.com/v1/create-qr-code/?size=80x80&data=' + qrData;

    let lineasHtml = '';
    const target = (categoriaNombre || '').toString().toLowerCase().trim();
    pedido.lineas.forEach(l => {
        const ln = (l.categoria_nombre || '').toString().toLowerCase().trim();
        let matched = false;
        if (target && ln) {
            if (ln === target) matched = true;
            else if (ln.includes(target)) matched = true;
            else if (target.includes(ln)) matched = true;
        }
        if (!matched) return;
        const nota = l.nota ? '<br><small>(' + l.nota + ')</small>' : '';
        lineasHtml += '<div style="padding:4px 0;font-size:14px">' + l.cantidad + 'x ' + l.producto_nombre + nota + '</div>';
    });
    if (!lineasHtml) return null;

    return `
        <html>
        <head>
            <style>
                body { font-family: Arial, Helvetica, sans-serif; font-size: 16px; width: 80mm; margin: 0 auto; padding: 10px; }
                .header { text-align: center; font-weight: bold; font-size: 20px; margin: 0 0 2px; }
                .subheader { text-align: center; font-weight: bold; font-size: 18px; margin: 0 0 6px; }
                .evento { text-align: center; font-size: 16px; margin: 4px 0; }
                .info { font-size: 14px; margin-bottom: 8px; }
                @media print {
                    @page { margin: 0; size: 80mm auto; }
                    body { margin: 0; padding: 5mm; }
                }
            </style>
        </head>
        <body>
            <div class="header">CENTRO DE ESTUDIANTES</div>
            <div class="subheader">IBAT San José</div>
            <div class="center" style="font-size:16px;font-weight:bold;margin:4px 0 6px">Peña IBAT 2026</div>
            <div class="center" style="font-size:14px;font-weight:bold;margin:4px 0">--- ${etiqueta} ---</div>
            <div class="info">
                PDV: ${pdv} | ${ticketId}<br>
                ${fecha}
            </div>
            ${lineasHtml}
            <div style="text-align:center;margin-top:8px">
                <img src="${qrUrl}" width="80" height="80" alt="QR">
            </div>
        </body>
        </html>
    `;
}

function openPrintWindow(html) {
    const ventana = window.open('', '_blank', 'width=400,height=600');
    ventana.document.write(html);
    ventana.document.close();
    ventana.focus();
    setTimeout(() => {
        try {
            ventana.print();
        } catch (e) {
            console.warn('print() failed:', e);
        }
        // Intentar cerrar la ventana tras imprimir (funciona si la ventana fue abierta por script)
        setTimeout(() => {
            try { ventana.close(); } catch (e) { /* ignore */ }
        }, 800);
    }, 500);
}

async function imprimirTicketNavegador(id) {
    try {
        const pedido = await apiFetch('/api/pedidos/' + id + '/');
        const categorias = new Set(pedido.lineas.map(l => l.categoria_nombre));

        const htmlParts = [];
        const htmlCompleto = buildTicketHtml(pedido);
        if (htmlCompleto) htmlParts.push(htmlCompleto);

        if (categorias.has('Comidas')) {
            const htmlComidas = buildComandaHtml(pedido, 'Comidas', 'COMIDAS', 'C');
            if (htmlComidas) htmlParts.push(htmlComidas);
        }
        if (categorias.has('Bebidas')) {
            const htmlBebidas = buildComandaHtml(pedido, 'Bebidas', 'BEBIDAS', 'B');
            if (htmlBebidas) htmlParts.push(htmlBebidas);
        }

        if (htmlParts.length === 0) return;

        // Normalizar: cada parte puede ser un documento completo (<html>...</html>).
        // Extraer el body de cada parte y concatenar con un separador de página.
        const combinedBodies = htmlParts.map(part => {
            const bodyMatch = part.match(/<body[^>]*>([\s\S]*)<\/body>/i);
            return bodyMatch ? bodyMatch[1] : part;
        }).join('<div style="page-break-after: always;"></div>');

        // Usar el head (estilos) del primer documento como referencia.
        const headMatch = htmlParts[0].match(/<head[^>]*>([\s\S]*?)<\/head>/i);
        const headHtml = headMatch ? headMatch[1] : '';

        const combinedHtml = `<html><head>${headHtml}</head><body>${combinedBodies}</body></html>`;
        openPrintWindow(combinedHtml);
    } catch (e) {
        showNotification('Error al preparar impresión: ' + e.message, 'error');
    }
}

// --- TABLERO EN VIVO ---
let _dashboardInterval = null;

function toggleDashboard() {
    const overlay = document.getElementById('dashboard-overlay');
    if (overlay.classList.contains('open')) {
        overlay.classList.remove('open');
        clearInterval(_dashboardInterval);
        _dashboardInterval = null;
        return;
    }
    const sel = document.getElementById('dashboard-pdv-select');
    sel.innerHTML = '<option value="">Todas las cajas</option>';
    state.pdvs.forEach(p => {
        const opt = document.createElement('option');
        opt.value = p.id;
        opt.textContent = p.nombre;
        sel.appendChild(opt);
    });
    overlay.classList.add('open');
    cargarDashboard();
    _dashboardInterval = setInterval(cargarDashboard, 7000);
}

function cambiarFiltroDashboard() {
    cargarDashboard();
}

async function cargarDashboard() {
    const statusEl = document.getElementById('dashboard-status');
    if (statusEl) statusEl.textContent = 'actualizando…';
    const pdvId = document.getElementById('dashboard-pdv-select').value;
    const url = '/api/resumen-ventas/' + (pdvId ? '?punto_venta_id=' + pdvId : '');
    try {
        const data = await apiFetch(url);
        renderDashboard(data);
        if (statusEl) statusEl.textContent = '● en vivo';
    } catch (e) {
        document.getElementById('dashboard-body').innerHTML =
            '<div class="empty-state">Error: ' + e.message + '</div>';
        if (statusEl) statusEl.textContent = 'sin conexión';
    }
}

function renderDashboard(data) {
    const totalFmt = '$' + parseFloat(data.total_general).toFixed(2);
    const ventas = data.total_pedidos;

    let metodosHtml = (data.total_por_metodo || []).map(m =>
        `<div class="dashboard-row">
            <span>${m.metodo_display}</span>
            <span class="dashboard-value">$${parseFloat(m.total).toFixed(2)}</span>
        </div>`
    ).join('');
    if (!metodosHtml) metodosHtml = '<div class="dashboard-empty">Sin ventas registradas</div>';

    let productosHtml = (data.por_producto || []).map(p =>
        `<div class="dashboard-row">
            <span>${p.nombre}</span>
            <span class="dashboard-units">${p.unidades} u.</span>
        </div>`
    ).join('');
    if (!productosHtml) productosHtml = '<div class="dashboard-empty">Sin ventas registradas</div>';

    document.getElementById('dashboard-body').innerHTML = `
        <div class="dashboard-total-card">
            <div class="dashboard-total-label">TOTAL VENDIDO</div>
            <div class="dashboard-total-amount">${totalFmt}</div>
            <div class="dashboard-total-sub">${ventas} venta${ventas !== 1 ? 's' : ''} cobrada${ventas !== 1 ? 's' : ''}</div>
        </div>
        <div class="dashboard-section">
            <div class="dashboard-section-title">Por m&eacute;todo de pago</div>
            ${metodosHtml}
        </div>
        <div class="dashboard-section">
            <div class="dashboard-section-title">Productos m&aacute;s vendidos</div>
            ${productosHtml}
        </div>
    `;
}

// --- PDV SELECTOR (simple) ---
function selectPDV() {
    const lineas = state.pdvs.map((p, i) => i + ': ' + p.nombre).join('\n');
    const idx = parseInt(prompt('Seleccioná PDV:\n' + lineas));
    if (idx >= 0 && idx < state.pdvs.length) {
        state.pdvActual = state.pdvs[idx];
        document.getElementById('btn-pdv-select').innerHTML = state.pdvActual.nombre + ' <span class="badge-pendientes" id="badge-pendientes">0</span>';
        showNotification('PDV cambiado a ' + state.pdvActual.nombre);
        actualizarBadgePendientes();
    }
}

// --- START ---
// --- SIDEBAR ---
function toggleSidebar() {
    document.getElementById('sidebar').classList.toggle('open');
    document.getElementById('sidebar-overlay').classList.toggle('open');
}

// --- KEYBOARD NAV ---
document.addEventListener('keydown', function(e) {
    const overlay = document.getElementById('payment-overlay');
    const paymentOpen = overlay && overlay.classList.contains('open');
    const key = e.key.toLowerCase();

    if (!paymentOpen && !isTypingTarget(e.target) && e.altKey) {
        if (key === 'n') { e.preventDefault(); nuevoTicket(); }
        else if (key === 'g') { e.preventDefault(); guardarPedido(); }
        else if (key === 'c') { e.preventDefault(); abrirPago(); }
        else if (key === 'o') { e.preventDefault(); toggleOrders(); }
        else if (key === 'h') { e.preventDefault(); toggleHistorial(); }
        else if (key === 'i') { e.preventDefault(); selectPrinter(); }
        return;
    }

    if (!paymentOpen) return;

    const input = document.getElementById('pay-amount-input');
    const recibido = document.getElementById('pay-recibido-input');
    const agregarBtn = document.querySelector('.btn-add-payment');
    const confirmarBtn = document.getElementById('btn-confirm-payment');

    if (e.key === 'Escape') { e.preventDefault(); cerrarPago(); return; }

    const shortcut = PAYMENT_SHORTCUTS.find(s => s.key.toLowerCase() === key || s.alt.toLowerCase() === key);
    if (shortcut) { e.preventDefault(); seleccionarMetodo(shortcut.methodId); return; }

    if (e.key === 'Enter') {
        const el = document.activeElement;
        if (el === input || el === recibido || el === agregarBtn) {
            e.preventDefault();
            agregarPago();
        } else if (el === confirmarBtn && !confirmarBtn.disabled) {
            e.preventDefault();
            confirmarPago();
        }
        return;
    }

    if ((e.ctrlKey || e.metaKey) && key === 'backspace') { e.preventDefault(); limpiarPagos(); return; }

    if (e.key !== 'Tab') return;

    const efVisible = recibido.parentElement.style.display !== 'none';

    const tabOrder = efVisible
        ? [input, recibido, agregarBtn, confirmarBtn]
        : [input, agregarBtn, confirmarBtn];

    const active = document.activeElement;
    const idx = tabOrder.indexOf(active);

    if (idx === -1) return;
    e.preventDefault();

    let next;
    if (e.shiftKey) {
        next = idx === 0 ? tabOrder[tabOrder.length - 1] : tabOrder[idx - 1];
    } else {
        next = idx === tabOrder.length - 1 ? tabOrder[0] : tabOrder[idx + 1];
    }
    if (!next) return;
    if (next === confirmarBtn && confirmarBtn.disabled) return;
    next.focus();
});

document.addEventListener('DOMContentLoaded', function() {
    init();

    function isForceSilent() { return localStorage.getItem('force_silent_print') === '1'; }
    function setForceSilent(v) {
        localStorage.setItem('force_silent_print', v ? '1' : '0');
        const cb = document.getElementById('force-silent-print-cb');
        if (cb) cb.checked = !!v;
    }
    function renderForceSilentToggle() {
        const sidebar = document.getElementById('sidebar');
        if (!sidebar || document.getElementById('force-silent-print-wrap')) return;
        const wrap = document.createElement('div');
        wrap.id = 'force-silent-print-wrap';
        wrap.style.cssText = 'padding:12px;border-top:1px solid #eee';
        wrap.innerHTML = `<label style="display:flex;align-items:center;gap:8px"><input id="force-silent-print-cb" type="checkbox"><span style="font-size:0.95rem">Forzar impresión silenciosa (si hay agente)</span></label>`;
        sidebar.appendChild(wrap);
        const cb = document.getElementById('force-silent-print-cb');
        cb.checked = isForceSilent();
        cb.addEventListener('change', e => {
            setForceSilent(e.target.checked);
            showNotification(e.target.checked ? 'Forzar impresión silenciosa activada' : 'Desactivada');
        });
    }
    renderForceSilentToggle();
    renderAgentStatus();

    function renderPreferBrowserToggle() {
        const sidebar = document.getElementById('sidebar');
        if (!sidebar || document.getElementById('prefer-browser-print-wrap')) return;
        const wrap = document.createElement('div');
        wrap.id = 'prefer-browser-print-wrap';
        wrap.style.cssText = 'padding:12px;border-top:1px solid #eee';
        wrap.innerHTML = `<label style="display:flex;align-items:center;gap:8px"><input id="prefer-browser-print-cb" type="checkbox"><span style="font-size:0.95rem">Imprimir por navegador al confirmar</span></label>`;
        sidebar.appendChild(wrap);
        const cb = document.getElementById('prefer-browser-print-cb');
        cb.checked = isPreferBrowserPrint();
        cb.addEventListener('change', e => {
            setPreferBrowserPrint(e.target.checked);
            showNotification(e.target.checked ? 'Impresión por navegador activada' : 'Impresión por agente preferida');
        });
    }
    renderPreferBrowserToggle();

    document.getElementById('toggle-order-list')?.addEventListener('click', () => document.getElementById('order-list')?.classList.toggle('collapsed'));
    document.getElementById('toggle-order-list-close')?.addEventListener('click', () => document.getElementById('order-list')?.classList.add('collapsed'));
    document.getElementById('toggle-compact')?.addEventListener('click', () => document.documentElement.classList.toggle('compact'));

    if (window.innerWidth >= 900) {
        document.getElementById('order-list')?.classList.remove('collapsed');
        const tb = document.getElementById('ticket-bar');
        if (tb) tb.style.display = 'none';
    }
});
