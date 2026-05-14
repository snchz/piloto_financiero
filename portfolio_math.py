def xnpv(rate, cash_flows):
    """
    Calcula el Valor Actual Neto (NPV) para flujos de caja irregulares.
    cash_flows es una lista de tuplas (fecha: datetime, importe: float).
    """
    if rate <= -1.0:
        return float('inf')
    
    t0 = cash_flows[0][0]
    total_npv = 0.0
    for date, amount in cash_flows:
        # Años entre la fecha inicial y la actual
        t = (date - t0).days / 365.0
        total_npv += amount / ((1.0 + rate) ** t)
    return total_npv

def xirr(cash_flows, guess=0.1, max_iter=100, tol=1e-6):
    """
    Calcula la Tasa Interna de Retorno (TIR / XIRR) usando Newton-Raphson.
    cash_flows: lista de (datetime, amount). 
    Retorna la tasa en decimal (ej. 0.10 = 10%).
    """
    if not cash_flows or len(cash_flows) < 2:
        return None
        
    # Ordenar por fecha por si acaso
    cash_flows = sorted(cash_flows, key=lambda x: x[0])
    
    # Comprobar si hay al menos un flujo positivo y uno negativo
    positives = sum(1 for _, amt in cash_flows if amt > 0)
    negatives = sum(1 for _, amt in cash_flows if amt < 0)
    if positives == 0 or negatives == 0:
        return None

    rate = guess
    for _ in range(max_iter):
        f_val = xnpv(rate, cash_flows)
        
        # Calcular derivada numéricamente
        rate_up = rate + 0.0001
        f_val_up = xnpv(rate_up, cash_flows)
        f_prime = (f_val_up - f_val) / 0.0001
        
        if abs(f_prime) < 1e-12:
            return None # Falla para evitar división por cero
            
        new_rate = rate - (f_val / f_prime)
        
        if abs(new_rate - rate) < tol:
            return new_rate
        rate = new_rate
        
    return None # No converge

def calcular_fifo(operaciones_activo):
    """
    Recibe una lista de operaciones (diccionarios) de un mismo activo.
    Calcula las posiciones abiertas actuales, beneficios realizados, etc., usando FIFO.
    Las operaciones deben estar ordenadas cronológicamente.
    """
    compras_abiertas = [] # Lista de {cantidad, precio_unitario, fecha}
    
    cantidad_total = 0.0
    beneficio_realizado = 0.0
    beneficio_realizado_base = 0.0
    
    for op in operaciones_activo:
        tipo = op['tipo'].upper()
        cantidad = float(op['cantidad'])
        precio = float(op['precio'])
        comisiones = float(op.get('comisiones', 0) or 0)
        impuestos = float(op.get('impuestos', 0) or 0)
        tasa_cambio = float(op.get('tasa_cambio', 1.0))
        
        if tipo in ('COMPRA', 'APORTACION'):
            # El coste real de la compra incluye las comisiones
            precio_unitario_real = (cantidad * precio + comisiones) / cantidad if cantidad > 0 else 0
            compras_abiertas.append({
                'cantidad': cantidad,
                'precio_unitario': precio_unitario_real,
                'tasa_cambio': tasa_cambio,
                'fecha': op['fecha']
            })
            cantidad_total += cantidad
            
        elif tipo == 'DIVIDENDO':
            # El ingreso neto del dividendo es tras comisiones e impuestos
            ingreso_neto = (cantidad * precio) - comisiones - impuestos
            ingreso_neto_base = ingreso_neto * tasa_cambio
            
            beneficio_realizado += ingreso_neto
            beneficio_realizado_base += ingreso_neto_base
            
            op['pnl'] = ingreso_neto
            op['pnl_base'] = ingreso_neto_base
            op['pnl_activo_base'] = ingreso_neto_base
            op['pnl_divisa_base'] = 0.0
            op['rentabilidad_pct'] = 0
            
        elif tipo == 'VENTA':
            cantidad_a_vender = cantidad
            coste_ventas = 0.0
            coste_ventas_base = 0.0
            
            while cantidad_a_vender > 0 and compras_abiertas:
                compra = compras_abiertas[0]
                if compra['cantidad'] <= cantidad_a_vender:
                    # Vendemos todo este lote
                    coste_ventas += compra['cantidad'] * compra['precio_unitario']
                    coste_ventas_base += compra['cantidad'] * compra['precio_unitario'] * compra['tasa_cambio']
                    cantidad_a_vender -= compra['cantidad']
                    compras_abiertas.pop(0)
                else:
                    # Vendemos parte de este lote
                    coste_ventas += cantidad_a_vender * compra['precio_unitario']
                    coste_ventas_base += cantidad_a_vender * compra['precio_unitario'] * compra['tasa_cambio']
                    compra['cantidad'] -= cantidad_a_vender
                    cantidad_a_vender = 0
            
            # El ingreso neto de la venta es tras comisiones e impuestos
            ingreso_neto = (cantidad * precio) - comisiones - impuestos
            ingreso_neto_base = ingreso_neto * tasa_cambio
            
            # Beneficio de la operación
            beneficio_op = ingreso_neto - coste_ventas
            beneficio_op_base = ingreso_neto_base - coste_ventas_base
            
            beneficio_realizado += beneficio_op
            beneficio_realizado_base += beneficio_op_base
            
            # Guardamos el resultado en el diccionario de la operación para el frontend
            op['pnl'] = beneficio_op
            op['pnl_base'] = beneficio_op_base
            op['pnl_activo_base'] = beneficio_op * tasa_cambio
            op['pnl_divisa_base'] = (coste_ventas * tasa_cambio) - coste_ventas_base
            op['rentabilidad_pct'] = (beneficio_op / coste_ventas) if coste_ventas > 0 else 0
            
            cantidad_total -= cantidad
            if cantidad_total < 1e-8: # Evitar errores de coma flotante
                cantidad_total = 0.0

    # Calcular coste medio de la posición actual
    coste_medio = 0.0
    coste_medio_base = 0.0
    if cantidad_total > 0 and compras_abiertas:
        total_coste = sum(c['cantidad'] * c['precio_unitario'] for c in compras_abiertas)
        total_coste_base = sum(c['cantidad'] * c['precio_unitario'] * c['tasa_cambio'] for c in compras_abiertas)
        coste_medio = total_coste / cantidad_total
        coste_medio_base = total_coste_base / cantidad_total
        
    return {
        'cantidad_actual': cantidad_total,
        'coste_medio': coste_medio,
        'coste_medio_base': coste_medio_base,
        'beneficio_realizado': beneficio_realizado,
        'beneficio_realizado_base': beneficio_realizado_base
    }
