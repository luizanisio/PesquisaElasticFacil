# -*- coding: utf-8 -*-
# Teste Classe: 
# - PesquisaElasticFacil : Componente python que simplifica a construção de queries no ElasticSearch
#                        e aproxima o uso dos operadores de proximidade comuns no BRS em queries 
#                        internas do ElasticSearch. Permite aproveitar o conhecimento de usuários BRS
#                        ao receber critérios de proximidade usados no BRS (PROX, ADJ, COM) e convertê-los
#                        para os critérios do elastic, bem como simplificar a forma de escrita dos critérios 
#                        de pesquisa e traduzi-los para conjuntos mais robustos de pesquisa no ElasticSearch.
# Esse código, dicas de uso e outras informações: 
#   -> https://github.com/luizanisio/PesquisaElasticFacil/
# Luiz Anísio 

from re import T
import unittest
import sys
from util_pesquisaelastic_facil import PesquisaElasticFacil, GruposPesquisaElasticFacil, Operadores
import json

TESTES_TOKENS = (
    ('"termo1 123.termo2"',['"termo1"', 'ADJ1', '"123"', 'ADJ1', '"termo2"']),
    ('"termo1 123:termo2"',['"termo1"', 'ADJ1', '"123"', 'ADJ1', '"termo2"']),
    ('"termo1 123+termo2"',['"termo1"', 'ADJ1', '"123"', 'ADJ1', '"termo2"']),
    ('"termo1 123_termo2"',['"termo1"', 'ADJ1', '"123_termo2"']),
    ('"termo1 123/termo2"',['"termo1"', 'ADJ1', '"123"', 'ADJ1', '"termo2"']),
    ('"termo1* 123?/termo2"',['"termo1*"', 'ADJ1', '"123?"', 'ADJ1', '"termo2"']),
)

TESTES_CURINGAS = (
    ('casa*',  'casa.*'), ('casa','casa'), ('ca$sa','ca.*sa'), 
    ('?ca$sa','.{0,1}ca.*sa'), ('?ca$s*a','.{0,1}ca.*s.*a'), 
    ('*$ca???sa??','.*ca.{0,3}sa.{0,2}'), 
    ('casa?', 'casa.{0,1}'), 
    ('ca??sa?', 'ca.{0,2}sa.{0,1}'),
    ('?ca??sa?', '.{0,1}ca.{0,2}sa.{0,1}'),
    ('123.456,??', '123_?456_?.{0,2}'),
    ('123.456', '123_?456'), ('123456', '123_?456'),
    ('1234567', '1_?234_?567'),
    ('123456,??', '123_?456_?.{0,2}'),
    ('a123456,??', 'a123456 .{0,2}'), ('123:456.789,123','123_?456_?789_?123'),
    ('25/06/1976','25_?06_?1976'), ('25:06:1976','25_?06_?1976'), 
    ('123,456.789-00','123_?456_?789_?00'), ('123-456-789-00','123_?456_?789_?00'),
    ('123::456.789-00','123_?456_?789_?00')
)

TESTES_OPERADORES = (
    ('casa*', 'ADJ1', {'span_multi': {'match': {'wildcard': {'texto': {'case_insensitive': True,'value': 'casa*'}}}}}),
    ('ca??', 'ADJ2', {'span_multi': {'match': {'regexp': {'texto': {'case_insensitive': True,'value': 'ca.{0,2}'}}}}}),
    ('ca?a', 'E', {'regexp': {'texto': {'case_insensitive': True, 'value': 'ca.{0,1}a'}}}),
    ('?ca?a*', 'PROX10', {"span_multi": {"match": {"regexp": {"texto": {"case_insensitive": True, "value": ".{0,1}ca.{0,1}a.*"}}}}}),
    ('2020', 'E', {"regexp": {"texto": {"case_insensitive": True, "value": "2_?020"}}}),
    ('ano','E',{"term": {"texto": "ano"}}), 
    ('/"ano/"','E',{"term": {"texto.raw": "ano"}}), 
    ("'/plano/'",'E',{"term": {"texto.raw": "plano"}}), 
    ("/plana,",'E',{"term": {"texto": "plana"}}),
)

TESTES_STR = ( ('DANO Adj MoRal','DANO ADJ1 MoRal'),
           ('"dano moral','"dano" ADJ1 "moral"'),
           ('dano com moral','dano PROX30 moral'),
           ('nao "dano moral" dano prox5 material','NAO ("dano" ADJ1 "moral") E (dano PROX5 material)'),
           ('"dano" prox10 "moral"', '"dano" PROX10 "moral"'),
           ('termo1 E termo2 termo3 OU termo4' , 'termo1 E termo2 E (termo3 OU termo4)'),
           ('termo1 E termo2 termo3 NÃO termo4' , 'termo1 E termo2 E termo3 NAO termo4'),
           ('termo1 E termo2 termo3 NÃO termo4 ou termo5' , 'termo1 E termo2 E termo3 NAO (termo4 OU termo5)'),
           ('dano moral e material','dano E moral E material'),
           ('dano prox5 material e estético', '(dano PROX5 material) E estetico'),
           ('dano prox5 material estético', '(dano PROX5 material) E estetico'),
           ('estético dano prox5 material', 'estetico E (dano PROX5 material)'),
           ('estético e dano prox5 material', 'estetico E (dano PROX5 material)'),
           ('dano moral (dano prox5 "material e estético)','dano E moral E (dano E ("material" ADJ1 "e" ADJ1 "estetico"))'),
           ('(dano moral) prova (agravo (dano prox5 "material e estético))','(dano E moral) E prova E (agravo E (dano E ("material" ADJ1 "e" ADJ1 "estetico")))'),
           ('teste1 adj2 teste2 prox3 teste3 teste4', '(teste1 ADJ2 teste2) E (teste2 PROX3 teste3) E teste4'),
           ('termo1 E termo2 OU termo3 OU termo4' , 'termo1 E (termo2 OU termo3 OU termo4)'),
           ('termo1 E termo2 OU (termo3 adj2 termo4)' , 'termo1 E (termo2 OU (termo3 ADJ2 termo4))'),
           ('termo1 OU termo2 termo3' , '(termo1 OU termo2) E termo3'),
           ('termo1 OU termo2 (termo3 termo4)' , '(termo1 OU termo2) E (termo3 E termo4)'),
           ('termo1 OU termo2 termo3 OU termo4' , '(termo1 OU termo2) E (termo3 OU termo4)'),
           ('termo1 OU termo2 (termo3 OU termo4 termo5)' , '(termo1 OU termo2) E ((termo3 OU termo4) E termo5)'),
           ('termo1 OU termo2 OU (termo3 OU termo4 termo5)' , 'termo1 OU termo2 OU ((termo3 OU termo4) E termo5)'),
           ('dano adj2 mora* dano prox10 moral prox5 material que?ra', '(dano ADJ2 mora*) E (dano PROX10 moral PROX5 material) E que?ra'),
           ('termo1 OU termo2 nao termo3' , '(termo1 OU termo2) NAO termo3'),
           ('termo1 OU termo2 nao (termo3 Ou termo4)' , '(termo1 OU termo2) NAO (termo3 OU termo4)'),
           ('((termo1 OU termo2) nao (termo3 Ou termo4)) termo5 prox10 termo6' , '((termo1 OU termo2) NAO (termo3 OU termo4)) E (termo5 PROX10 termo6)'),
           (':123.456.789,123 25/06/1976 25_06_1976 a.b a-b a,b','123.456.789,123 E 25/06/1976 E 25_06_1976 E a E b E a E b E a E b'),
           (':123:456.789,123 25_06_1976 a|b:c:: a1|2b:c3::','123 E 456.789,123 E 25_06_1976 E a E b E c E a1 E 2b E c3'),
           (':(123:456.789,123 (25_06_1976 a|b:c::)) a1|2b:c3::','(123 E 456.789,123 E (25_06_1976 E a E b E c)) E a1 E 2b E c3'),
        )

TESTES_STR_CORRECAO = ( 
           ('dano Adj e moRal','dano E moRal'),
           ('dano (moRal)','dano E moRal'),
           ('dano e (moRal)','dano E moRal'),
           ('dano Adj (moRal)','dano ADJ1 moRal'),
           ('dano Adj (moRal material)','dano E (moRal E material)'),
           ('dano (ADJ moRal)','dano E moRal'),
           ('adj dano prox1(ADJ moRal not)','dano E moRal'),
           ('dano e ou adj5 prox5 moRal','dano PROX5 moRal'),
           ('dano e ou adj5 prox5 e moRal','dano E moRal'),
           ('dano e ou adj5 (adj5) prox5 e moRal','dano E moRal'),
           ('(termo1) ADJ1 (termo2)','termo1 ADJ1 termo2'),
           ('nao (termo1) nao ADJ1 (termo2)','NAO (termo1 ADJ1 termo2)'),
           ('a123456,??  dano? prox5 mora? dano adj20 material estetic??','a123456 E (dano? PROX5 mora?) E (dano ADJ20 material) E estetic??'),
           ('2020','2020'),('(2020)','2020'),("'2020'",'"2020"'),
           ('casa"dano - moral"','casa E ("dano" ADJ1 "moral")'),
           (':termo1, termo2:texto3 nao [termo4]' , 'termo1 E termo2 E texto3 NAO termo4'),
           ('termo1, termo2 texto3 nao [termo4]' , 'CONTÉM:  termo1  termo2 texto3 nao  termo4 '),
        )

inteligente = 'bla bla bla . blá, blá e [blá]'*5

TESTES_QUERIES = (
    ('dano adj2 moral', { "span_near": { "clauses": [ { "span_term": { "texto": "dano" } }, { "span_term": { "texto": "moral" } } ], "slop": 1, "in_order": True } }),
    ('outro adj6 dano adj2 moral', { "span_near": { "clauses": [ { "span_term": { "texto": "outro" } }, { "span_term": { "texto": "dano" } }, { "span_term": { "texto": "moral" } } ], "slop": 5, "in_order": True } }),
    ('dano* adj2 mora?', {"span_near": {"clauses": [{"span_multi": {"match": {"wildcard": {"texto": {"case_insensitive": True, "value": "dano*"}}}}}, {"span_multi": {"match": {"regexp": {"texto": {"case_insensitive": True, "value": "mora.{0,1}"}}}}}], "slop": 1, "in_order": True}}),
    (inteligente, {"more_like_this": {"fields": ["texto"], "like": " bla bla bla   bla  bla e  bla bla bla bla   bla  bla e  bla bla bla bla   bla  bla e  bla bla bla bla   bla  bla e  bla bla bla bla   bla  bla e  bla ", "unlike": [], "min_term_freq": 1, "min_doc_freq": 1, "max_query_terms": 30, "minimum_should_match": "50%"}}),
    (f'{inteligente} nao (outra coisa)', {"more_like_this": {"fields": ["texto"], "like": " bla bla bla   bla  bla e  bla bla bla bla   bla  bla e  bla bla bla bla   bla  bla e  bla bla bla bla   bla  bla e  bla bla bla bla   bla  bla e  bla  ", "unlike": [" outra coisa "], "min_term_freq": 1, "min_doc_freq": 1, "max_query_terms": 30, "minimum_should_match": "50%"}}),
    ('dano ou moral ou material nao teste', {"bool": {"must": [{"bool": {"should": [{"term": {"texto": "dano"}}, {"term": {"texto": "moral"}}, {"term": {"texto": "material"}}]}}], "must_not": [{"term": {"texto": "teste"}}]}}),
    ('nao teste dano ou moral ou material', {"bool": {"must": [{"bool": {"should": [{"term": {"texto": "dano"}}, {"term": {"texto": "moral"}}, {"term": {"texto": "material"}}]}}], "must_not": [{"term": {"texto": "teste"}}]}}),
    ('nao (teste) (dano ou moral ou material)', {"bool": {"must": [{"bool": {"should": [{"term": {"texto": "dano"}}, {"term": {"texto": "moral"}}, {"term": {"texto": "material"}}]}}], "must_not": [{"term": {"texto": "teste"}}]}}),
    ('teste nao (dano ou moral ou material)', {"bool": {"must": [{"term": {"texto": "teste"}}], "must_not": [{"bool": {"should": [{"term": {"texto": "dano"}}, {"term": {"texto": "moral"}}, {"term": {"texto": "material"}}]}}]}}),
    ('nao (processo ou prazo ou prescricional) codigo penal',{"bool": {"must": [{"term": {"texto": "codigo"}}, {"term": {"texto": "penal"}}], "must_not": [{"bool": {"should": [{"term": {"texto": "processo"}}, {"term": {"texto": "prazo"}}, {"term": {"texto": "prescricional"}}]}}]}}),
    ('pesquisa inteligente por símbolos: dois pontos',{"more_like_this": {"fields": ["texto"], "like": " pesquisa inteligente por simbolos  dois pontos", "unlike": [], "min_term_freq": 1, "min_doc_freq": 1, "max_query_terms": 30, "minimum_should_match": "50%"}}),    
    ('(dano adj2 moral adj5 material) ou ("dano moral") ou ("dano material") estético',
         {"bool": {"must": [{"bool": {"should": [{"span_near": {"clauses": [{"span_term": {"texto": "dano"}}, {"span_term": {"texto": "moral"}}, {"span_term": {"texto": "material"}}], "slop": 4, "in_order": True}}, {"span_near": {"clauses": [{"span_term": {"texto.raw": "dano"}}, {"span_term": {"texto.raw": "moral"}}], "slop": 0, "in_order": True}}, {"span_near": {"clauses": [{"span_term": {"texto.raw": "dano"}}, {"span_term": {"texto.raw": "material"}}], "slop": 0, "in_order": True}}]}}, {"term": {"texto": "estetico"}}]}}),
    ('processo (dano moral nao (dano prox100 material)) ou (dano material nao (dano prox100 moral))',
         {"bool": {"must": [{"term": {"texto": "processo"}}, {"bool": {"should": [{"bool": {"must": [{"term": {"texto": "dano"}}, {"term": {"texto": "moral"}}], "must_not": [{"span_near": {"clauses": [{"span_term": {"texto": "dano"}}, {"span_term": {"texto": "material"}}], "slop": 99, "in_order": False}}]}}, {"bool": {"must": [{"term": {"texto": "dano"}}, {"term": {"texto": "material"}}], "must_not": [{"span_near": {"clauses": [{"span_term": {"texto": "dano"}}, {"span_term": {"texto": "moral"}}], "slop": 99, "in_order": False}}]}}]}}]}} ),
    ('termo1 123/termo2',{"bool": {"must": [{"term": {"texto": "termo1"}}, {"regexp": {"texto": {"case_insensitive": True, "value": "123"}}}, {"term": {"texto": "termo2"}}]}}),
    ('"termo1 123/ termo2"',{"span_near": {"clauses": [{"span_term": {"texto.raw": "termo1"}}, {"span_term": {"texto.raw": "123"}}, {"span_term": {"texto.raw": "termo2"}}], "slop": 0, "in_order": True}}),
)

TESTES_GRUPOS = (
    ('dano adj2 moral', {"bool": {"must": [{ "span_near": { "clauses": [ { "span_term": { "texto": "dano" } }, { "span_term": { "texto": "moral" } } ], "slop": 1, "in_order": True } }]}}),
    ('dano adj2 moral .CAMPO.(teste)', {"bool": {"must": [{ "span_near": { "clauses": [ { "span_term": { "texto": "dano" } }, { "span_term": { "texto": "moral" } } ], "slop": 1, "in_order": True } }, {"term": {"CAMPO": "teste"}}]}}),
    ('dano adj2 moral .CAMPO.(teste1 adj2 teste2)', {"bool": {"must": [{ "span_near": { "clauses": [ { "span_term": { "texto": "dano" } }, { "span_term": { "texto": "moral" } } ], "slop": 1, "in_order": True } }, {"span_near": {"clauses": [{"span_term": {"CAMPO": "teste1"}}, {"span_term": {"CAMPO": "teste2"}}], "slop": 1, "in_order": True}}]}}),
    ('nao (dano adj2 moral) .CAMPO.(teste1 adj2 teste2)', {"bool": {"must": [{"bool": {"must_not": [{"span_near": {"clauses": [{"span_term": {"texto": "dano"}}, {"span_term": {"texto": "moral"}}], "slop": 1, "in_order": True}}]}}, {"span_near": {"clauses": [{"span_term": {"CAMPO": "teste1"}}, {"span_term": {"CAMPO": "teste2"}}], "slop": 1, "in_order": True}}]}}),
    ('dano adj2 moral .CAMPO.("teste1" adj2 teste2)', {"bool": {"must": [{"span_near": {"clauses": [{"span_term": {"texto": "dano"}}, {"span_term": {"texto": "moral"}}], "slop": 1, "in_order": True}}, {"span_near": {"clauses": [{"span_term": {"CAMPO.raw": "teste1"}}, {"span_term": {"CAMPO.raw": "teste2"}}], "slop": 1, "in_order": True}}]}}),
    ('dano adj2 moral .CAMPO.(>100 <50)', {"bool": {"must": [{"span_near": {"clauses": [{"span_term": {"texto": "dano"}}, {"span_term": {"texto": "moral"}}], "slop": 1, "in_order": True}}, {"range": {"CAMPO": {"gt": "100", "lt": "50"}}}]}}),
    ('dano adj2 moral .CAMPO.(>=100 <50)', {"bool": {"must": [{"span_near": {"clauses": [{"span_term": {"texto": "dano"}}, {"span_term": {"texto": "moral"}}], "slop": 1, "in_order": True}}, {"range": {"CAMPO": {"gte": "100", "lt": "50"}}}]}}),
    ('dano adj2 moral .CAMPO.(<=50)', {"bool": {"must": [{"span_near": {"clauses": [{"span_term": {"texto": "dano"}}, {"span_term": {"texto": "moral"}}], "slop": 1, "in_order": True}}, {"range": {"CAMPO": {"lte": "50"}}}]}}),
    ('dano adj2 moral .CAMPO.(=50)', {"bool": {"must": [{"span_near": {"clauses": [{"span_term": {"texto": "dano"}}, {"span_term": {"texto": "moral"}}], "slop": 1, "in_order": True}}, {"regexp": {"CAMPO": {"case_insensitive": True, "value": "50"}}}]}}),
    ('"Dano moral" estetico prox10 material ou "dano material"', {"bool": {"must": [{"bool": {"must": [{"span_near": {"clauses": [{"span_term": {"texto.raw": "dano"}}, {"span_term": {"texto.raw": "moral"}}], "slop": 0, "in_order": True}}, {"bool": {"should": [{"span_near": {"clauses": [{"span_term": {"texto": "estetico"}}, {"span_term": {"texto": "material"}}], "slop": 9, "in_order": False}}, {"span_near": {"clauses": [{"span_term": {"texto.raw": "dano"}}, {"span_term": {"texto.raw": "material"}}], "slop": 0, "in_order": True}}]}}]}}]}}),
    ("'Dano moral' estetico prox10 material .TIPO.(tipo1 tipo2) .DATA.(>=2020-08-01 <='2022-01-01')",
      {"bool": {"must": [{"bool": {"must": [{"span_near": {"clauses": [{"span_term": {"texto.raw": "dano"}}, {"span_term": {"texto.raw": "moral"}}], "slop": 0, "in_order": True}}, {"span_near": {"clauses": [{"span_term": {"texto": "estetico"}}, {"span_term": {"texto": "material"}}], "slop": 9, "in_order": False}}]}}, {"bool": {"must": [{"term": {"TIPO": "tipo1"}}, {"term": {"TIPO": "tipo2"}}]}}, {"range": {"DATA": {"gte": "2020-08-01", "lte": "2022-01-01"}}}]}})
)

################################################################################
################################################################################
################################################################################
################################################################################

class Teste(unittest.TestCase):

    def teste_0_tokens(self):
        # testes de curingas
        for i, teste in enumerate(TESTES_TOKENS):
            with self.subTest(f'Tokens {i} - "{teste[0]}" => "{teste[1]}"'):
                criterios, esperado = teste
                _criterios = f':{criterios}' if criterios[0] !=':' else criterios
                pe = PesquisaElasticFacil(_criterios)
                saida_lista = pe.converter_parenteses_para_listas(criterios)
                saida_aspas = pe.juntar_aspas(saida_lista)
                saida = pe.criterios_listas
                print(f'{i}) "{teste[0]}"\n  > Esperado: {esperado}\n  > Recebido: {saida}\n  > Saída lista: {saida_lista}\n  > Saída aspas: {saida_aspas}')
                self.assertEqual(esperado, saida)

    def teste_1_curingas(self):
        # testes de curingas
        for i, teste in enumerate(TESTES_CURINGAS):
            with self.subTest(f'Curingas {i} - "{teste[0]}" => "{teste[1]}"'):
                token, esperado = teste
                saida1 = Operadores.formatar_token(token)
                saida2 = Operadores.termo_regex_interroga(saida1)
                print(f'{i}) "{teste[0]}" > Esperado: {esperado} > Recebido: {saida2}')
                self.assertEqual(esperado, saida2)

    def teste_2_operadores(self):
        for i, teste in enumerate(TESTES_OPERADORES):
            with self.subTest(f'Operadores {i} - "{teste[0]}" + "{teste[1]}"'):
                token, operador, esperado = teste
                saida1 = Operadores.formatar_token(token)
                campo = Operadores.campo_texto_termo(termo=saida1,campo_texto='texto',sufixo_campo_raw='.raw')
                saida2 = PesquisaElasticFacil.as_query_operador(saida1,operador.upper(),campo)
                print(f'{i}) "{teste[0]}" > "{teste[1]}" >> \nEsperado: {json.dumps(esperado)}\nRecebido: {json.dumps(saida2)}')
                self.assertDictEqual(esperado, saida2)

    def teste_3_str(self):
        _testes = TESTES_STR + TESTES_STR_CORRECAO
        pos_falhas = len(TESTES_STR)                
        for i, teste in enumerate(_testes):
            _falha = ' - STR CORRECAO' if i>=pos_falhas else ''
            with self.subTest(f'Query str {i} - "{teste[0]}" + "{teste[1]}"'):
                criterio,esperado = teste 
                pbe = PesquisaElasticFacil(criterio)
                saida = pbe.criterios_reformatado.strip().replace('  ',' ')
                esperado = esperado.strip().replace('  ',' ')
                print(f'{i}{_falha}) "{teste[0]}"\n  > Esperado: {esperado}\n  > Recebido: {saida}')
                self.assertEqual(esperado, saida)

    def teste_4_queries(self):
        for i, teste in enumerate(TESTES_QUERIES):
            with self.subTest(f'Query {i} - "{teste[0]}" + "{teste[1]}"'):
                criterio, query = teste
                pe = PesquisaElasticFacil(criterios_originais=criterio, campo_texto='texto',sufixo_campo_raw='raw')
                saida = pe.criterios_elastic.get('query',{})
                print(f'{i}) "{teste[0]}" \nEsperado: {json.dumps(query)}\nRecebido: {json.dumps(saida)}')
                self.assertDictEqual(query, saida)

    def teste_4_grupos(self):
        for i, teste in enumerate(TESTES_GRUPOS):
            with self.subTest(f'Grupo {i} - "{teste[0]}" + "{teste[1]}"'):
                criterio, query = teste
                campos = {'texto':'raw','CAMPO':'raw','DATA':'','TIPO':''}
                pe = GruposPesquisaElasticFacil(criterios_agrupados=criterio, campo_texto_padrao='texto', campos_disponiveis=campos)
                saida = pe.as_query().get('query',{})
                print(f'{i}) "{teste[0]}" \nEsperado: {json.dumps(query)}\nRecebido: {json.dumps(saida)}')
                self.assertDictEqual(query, saida)

if __name__ == '__main__':
    unittest.main(buffer=True, failfast = True)
