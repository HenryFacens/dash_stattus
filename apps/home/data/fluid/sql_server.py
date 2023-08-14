from django.db import connections
from itertools import groupby
import datetime


# DashBoard Fluid

def get_cliente_ativos():
    with connections['sql_server'].cursor() as cursor:
        cursor.execute(""" 
        SELECT id_cliente, razao_social
        FROM clientes
        WHERE ativo = 1;
                       """)
        clientes_ativos = cursor.fetchall()

    return clientes_ativos


def get_dti_dtf():

    now = datetime.datetime.now()

    start_date = (now - datetime.timedelta(days=90)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    end_date = now.replace(hour=23, minute=59, second=59, microsecond=999)

    start_str = start_date.strftime('%Y-%m-%d %H:%M:%S')
    end_str = end_date.strftime('%Y-%m-%d %H:%M:%S')

    # print(start_str)
    # print(end_str)
    return start_str, end_str

def get_amostras_status():

    clientes = get_cliente_ativos()


    lista_ids_clientes = [str(cliente[0]) for cliente in clientes]
    ids_clientes_str = ",".join(lista_ids_clientes)
    start_str, end_str = get_dti_dtf()

    with connections['sql_server'].cursor() as cursor:

        cursor.execute(f"""
        SELECT 
            id_cliente,
            MONTH(dt_amostra) AS Mes,
            CASE 
                WHEN v.id_relatorio IS NULL THEN 'Pendente'
                WHEN v.tipo_vazamento = 'Sem Ponto Suspeito, ' THEN 'Ponto Não Confirmado'
                ELSE 'Pontos Confirmados'
            END AS ClassificacaoVazamento,
            COUNT(*) AS Total
        FROM (
            SELECT id_amostra, id_cliente, seq, dt_amostra,
                ROW_NUMBER() OVER(PARTITION BY seq ORDER BY dt_amostra DESC) AS rn
            FROM devstattus4_4fluid.dbo.amostras
            WHERE classificacao = N'LEAK' 
            AND dt_amostra BETWEEN '{start_str}' AND '{end_str}' 
            AND id_cliente IN ({ids_clientes_str})
        ) AS a
        LEFT JOIN (
            SELECT id_amostra, id_relatorio, 
                ROW_NUMBER() OVER(PARTITION BY id_amostra ORDER BY id_relatorio DESC) AS rn
            FROM devstattus4_4fluid.dbo.relatorio_amostras
        ) AS r ON a.id_amostra = r.id_amostra
        LEFT JOIN devstattus4_4fluid.dbo.relatorio_vazamento AS v ON r.id_relatorio = v.id_relatorio
        WHERE a.rn = 1 AND (r.rn = 1 OR r.id_amostra IS NULL)
        GROUP BY 
            id_cliente,
            MONTH(dt_amostra),
            CASE 
                WHEN v.id_relatorio IS NULL THEN 'Pendente'
                WHEN v.tipo_vazamento = 'Sem Ponto Suspeito, ' THEN 'Ponto Não Confirmado'
                ELSE 'Pontos Confirmados'
            END
        ORDER BY id_cliente, MONTH(dt_amostra), ClassificacaoVazamento;
        """)
        
        tipo_vazamento = cursor.fetchall()

    total_amostras_results = get_total_amostras_por_mes(start_str, end_str)

    merged_results = mesclar_resultados(tipo_vazamento, total_amostras_results,clientes)
    # print(merged_results)
    final = incorporar_porcentagem_ao_payload(merged_results)

    final_organizado = organize_data(final)

    meses_unicos1 = obter_meses_unicos(final_organizado)
    
    return final_organizado, meses_unicos1

def get_total_amostras_por_mes(start_date, end_date):

    
    total_amostras_results = []

    with connections['sql_server'].cursor() as cursor:
            cursor.execute(f"""
            SELECT 
                id_cliente,
                MONTH(dt_amostra) AS Mes,
                COUNT(id_amostra) as total_de_amostras 
            FROM 
                devstattus4_4fluid.dbo.amostras 
            WHERE 
                dt_amostra BETWEEN '{start_date}' AND '{end_date}'
            GROUP BY
                id_cliente,
                MONTH(dt_amostra)
            ORDER BY
                id_cliente,
                MONTH(dt_amostra);
    """)
            
            results = cursor.fetchall()
            total_amostras_results.extend(results)

    return total_amostras_results

def mesclar_resultados(tipo_vazamento, total_amostras_results,clientes):

    dict_clientes = {id_cliente: razao for id_cliente, razao in clientes}

    meses = {
        1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril', 5: 'Maio',
        6: 'Junho', 7: 'Julho', 8: 'Agosto', 9: 'Setembro', 10: 'Outubro',
        11: 'Novembro', 12: 'Dezembro'
    }

    dict_total_amostras = {(id_cliente, mes): total for id_cliente, mes, total in total_amostras_results}

    merged_results = [
        (dict_clientes[id_cliente], meses[mes], classificacao, count, dict_total_amostras.get((id_cliente, mes), None))
        for id_cliente, mes, classificacao, count in tipo_vazamento
    ]
    return merged_results

def calcular_porcentagem(payload):
    data_grouped = {}
    for cliente, mes, tipo, count, total in payload:
        if (cliente, mes) not in data_grouped:
            data_grouped[(cliente, mes)] = {}
        data_grouped[(cliente, mes)][tipo] = count

    porcentagens = {}
    for (cliente, mes), values in data_grouped.items():
        sum_values = values.get('Ponto Não Confirmado', 0) + values.get('Pontos Confirmados', 0)
        if sum_values > 0:
            porcentagem = (values.get('Pontos Confirmados', 0) / sum_values) * 100
        else:
            porcentagem = 0
        porcentagens[(cliente, mes)] = porcentagem

    return porcentagens

def incorporar_porcentagem_ao_payload(payload):
    porcentagens = calcular_porcentagem(payload)
    
    payload_final = []
    for cliente, mes, tipo, count, total in payload:
        porcentagem = porcentagens.get((cliente, mes), None)
        payload_final.append((cliente, mes, tipo, count, total, porcentagem))
    return payload_final

def organize_data(data):
    organized_data = {}

    for entry in data:
        cliente, mes, status, valor, total_coletas, acuracia = entry

        if cliente not in organized_data:
            organized_data[cliente] = {}

        if mes not in organized_data[cliente]:
            organized_data[cliente][mes] = {'acuracia': acuracia, 'Total de Coletas': total_coletas, 'Pontos Confirmados': 0, 'Ponto Não Confirmado': 0, 'Pendente': 0}

        organized_data[cliente][mes][status] = valor

    # print(organized_data)
    return organized_data

def obter_meses_unicos(organizado):
    possiveis_meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    
    meses_unicos = set()
    
    for cliente, dados in organizado.items():
        for mes in dados:
            if mes in possiveis_meses:
                meses_unicos.add(mes)
    meses = list(meses_unicos)
    return meses

# Boletim de Medicao Fluid

def clientes_ativos_idmaster():
    with connections['sql_server'].cursor() as cursor:
        cursor.execute(""" 
        SELECT id_cliente, id_cliente_master, razao_social
        FROM devstattus4_4fluid.dbo.clientes
        WHERE ativo = 1;
                       """)
        clientes_ativos = cursor.fetchall()

    return clientes_ativos

def group_clients():
    clientes = clientes_ativos_idmaster()

    master_clients = {item[0]: {"name": item[2], "sub_clients": []} for item in clientes if item[1] is None and item[0] != 1}
    
    master_clients["default"] = {"name": "Sem Cliente Master", "sub_clients": []}
    
    for item in clientes:
        id_cliente, id_cliente_master, razao_social = item

        if id_cliente == 1:
            continue

        if id_cliente_master:
            if id_cliente_master in master_clients:
                master_clients[id_cliente_master]["sub_clients"].append((id_cliente, razao_social))
            else:
                # Em casos onde o cliente master ainda não foi adicionado ao dicionário (ordem invertida)
                master_clients["default"]["sub_clients"].append((id_cliente, razao_social))
        else:
            master_clients["default"]["sub_clients"].append((id_cliente, razao_social))

    if not master_clients["default"]["sub_clients"]:
        del master_clients["default"]

    # print(master_clients)
    return master_clients

def total_de_coletas(id_cliente, date_1, date_2):

    pontos = classificao_boletim(id_cliente, date_1, date_2)
    classes = qnt_class(id_cliente, date_1, date_2)

    # print(id_cliente)
    # print(date_1)
    # print(date_2)

    with connections['sql_server'].cursor() as cursor:
        cursor.execute(""" 
            SELECT 
                id_cliente,
                CAST(dt_amostra AS DATE) AS Dia,
                COUNT(id_amostra) as total_de_amostras 
            FROM 
                devstattus4_4fluid.dbo.amostras 
            WHERE 
                id_cliente = %s AND
                dt_amostra BETWEEN %s AND %s
            GROUP BY
                id_cliente,
                CAST(dt_amostra AS DATE)
            ORDER BY
                id_cliente,
                CAST(dt_amostra AS DATE);
                       """, [id_cliente, date_1, date_2])
        coletas_totais = cursor.fetchall()

    coletas_totais = [(item[0], item[1].isoformat(), item[2]) if isinstance(item[1], datetime.date) else item for item in coletas_totais]

    return coletas_totais, pontos, classes

def classificao_boletim(id_cliente, date_1, date_2):

    with connections['sql_server'].cursor() as cursor:
        cursor.execute(""" 
        SELECT 
            id_cliente,
            MONTH(dt_amostra) AS Mes,
            CASE 
                WHEN v.id_relatorio IS NULL THEN 'Pendente'
                WHEN v.tipo_vazamento = 'Sem Ponto Suspeito, ' THEN 'Ponto Não Confirmado'
                ELSE 'Pontos Confirmados'
            END AS ClassificacaoVazamento,
            COUNT(*) AS Total
        FROM (
            SELECT id_amostra, id_cliente, seq, dt_amostra,
                ROW_NUMBER() OVER(PARTITION BY seq ORDER BY dt_amostra DESC) AS rn
            FROM devstattus4_4fluid.dbo.amostras
            WHERE classificacao = N'LEAK' 
            AND dt_amostra BETWEEN %s AND %s
            AND id_cliente = %s
        ) AS a
        LEFT JOIN (
            SELECT id_amostra, id_relatorio, 
                ROW_NUMBER() OVER(PARTITION BY id_amostra ORDER BY id_relatorio DESC) AS rn
            FROM devstattus4_4fluid.dbo.relatorio_amostras
        ) AS r ON a.id_amostra = r.id_amostra
        LEFT JOIN devstattus4_4fluid.dbo.relatorio_vazamento AS v ON r.id_relatorio = v.id_relatorio
        WHERE a.rn = 1 AND (r.rn = 1 OR r.id_amostra IS NULL)
        GROUP BY 
            id_cliente,
            MONTH(dt_amostra),
            CASE 
                WHEN v.id_relatorio IS NULL THEN 'Pendente'
                WHEN v.tipo_vazamento = 'Sem Ponto Suspeito, ' THEN 'Ponto Não Confirmado'
                ELSE 'Pontos Confirmados'
            END
        ORDER BY id_cliente, MONTH(dt_amostra), ClassificacaoVazamento;
                       """, [date_1, date_2, id_cliente])
        pontos = cursor.fetchall()

    somas = {
        'Ponto Não Confirmado': 0,
        'Pontos Confirmados': 0,
        'Pendente': 0
        }

    for _, _, tipo, valor in pontos:
        if tipo in somas:
            somas[tipo] += valor
    # print(somas)
    return somas

def qnt_class(id_cliente, date_1, date_2):

        with connections['sql_server'].cursor() as cursor:
            cursor.execute(""" 
                SELECT 
                    id_cliente,
                    SUM(CASE WHEN classificacao = 'FRAU' THEN 1 ELSE 0 END) AS Fraude,
                    SUM(CASE WHEN classificacao = 'INCO' THEN 1 ELSE 0 END) AS Inconsistente,
                    SUM(CASE WHEN classificacao = 'LEAK' THEN 1 ELSE 0 END) AS PontoSuspeito,
                    SUM(CASE WHEN classificacao = 'LESS' THEN 1 ELSE 0 END) AS SemVazamento,
                    SUM(CASE WHEN classificacao = 'NOAC' THEN 1 ELSE 0 END) AS SemAcesso,
                    SUM(CASE WHEN classificacao = 'PASS' THEN 1 ELSE 0 END) AS Consumo,
                    SUM(CASE WHEN classificacao = 'PEND' THEN 1 ELSE 0 END) AS Pendente,
                    SUM(CASE WHEN classificacao = 'VISI' THEN 1 ELSE 0 END) AS VazamentoVisível
                FROM 
                    devstattus4_4fluid.dbo.amostras
                WHERE 
                    id_cliente = %s AND
                    dt_amostra BETWEEN %s AND %s
                GROUP BY 
                    id_cliente;
                        """, [id_cliente, date_1, date_2])
            qnt_class = cursor.fetchall()
        # print(qnt_class)
        return qnt_class